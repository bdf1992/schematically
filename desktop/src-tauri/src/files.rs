//! Native file effects. The editor owns parsing, serialization and document semantics.
use rand::{rngs::OsRng, RngCore};
use serde::Serialize;
use std::{fs, io::Write, path::{Path, PathBuf}, sync::Mutex};

#[derive(Default)]
pub struct FileState(pub Mutex<Option<(PathBuf, String)>>);
impl FileState {
    fn reset(&self)->Result<(),String>{
        *self.0.lock().map_err(|_| "File association unavailable")?=None;
        Ok(())
    }
}

#[derive(Debug, Serialize)]
pub struct OpenedDocument { pub name: String, pub text: String, pub token: String }
#[derive(Debug, Serialize)]
pub struct SavedDocument { pub name: String, pub token: String }

pub fn random_token() -> String {
    let mut bytes = [0u8; 32];
    OsRng.fill_bytes(&mut bytes);
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
fn file_name(path: &Path) -> String {
    path.file_name().unwrap_or_default().to_string_lossy().into_owned()
}
pub fn read_document(state: &FileState, path: PathBuf) -> Result<OpenedDocument, String> {
    let text = fs::read_to_string(&path).map_err(|e| format!("Could not read {}: {e}", path.display()))?;
    let token = random_token();
    *state.0.lock().map_err(|_| "File association unavailable")? = Some((path.clone(), token.clone()));
    Ok(OpenedDocument { name: file_name(&path), text, token })
}

#[tauri::command]
pub fn desktop_open_document(state: tauri::State<'_, FileState>) -> Result<Option<OpenedDocument>, String> {
    let Some(path) = rfd::FileDialog::new().add_filter("SOV Schematic", &["sov", "sovpak", "json"]).pick_file() else { return Ok(None) };
    read_document(&state, path).map(Some)
}

#[tauri::command]
pub fn desktop_reset_document(state: tauri::State<'_, FileState>) -> Result<(), String> {
    state.reset()
}

/// `token` identifies the current native handle; it never accepts a caller-supplied path.
#[tauri::command]
pub fn desktop_save_document(
    state: tauri::State<'_, FileState>, token: Option<String>, text: String,
    name: String, format: String, save_as: bool,
) -> Result<Option<SavedDocument>, String> {
    save_document(&state,token,text,name,format,save_as,|suggested,extension| {
        rfd::FileDialog::new().add_filter("SOV Schematic", &[extension]).set_file_name(suggested).save_file()
    })
}
fn save_document(
    state:&FileState,token:Option<String>,text:String,name:String,format:String,save_as:bool,
    choose:impl FnOnce(&str,&str)->Option<PathBuf>,
)->Result<Option<SavedDocument>,String>{
    let extension = match format.as_str() { "document" => "sov", "package" => "sovpak", _ => return Err("Unsupported file format".into()) };
    let current = state.0.lock().map_err(|_| "File association unavailable")?.clone();
    let target = if !save_as {
        match (&current, &token) {
            (Some((path, expected)), Some(actual)) if actual == expected => Some(path.clone()),
            (_, Some(_)) => return Err("Native file handle is stale".into()),
            _ => None,
        }
    } else { None };
    let path = match target {
        Some(path) => path,
        None => {
            // A suggested basename is presentation only, never filesystem authority.
            let suggested = Path::new(&name).file_name().unwrap_or_default().to_string_lossy();
            let Some(mut path) = choose(suggested.as_ref(),extension) else { return Ok(None) };
            if path.extension().is_none() { path.set_extension(extension); }
            path
        }
    };
    // A dialog yields control; refuse if another lifecycle operation changed the association.
    // Hold the association lock across the write so reset/open cannot race the final replacement.
    let mut association=state.0.lock().map_err(|_| "File association unavailable")?;
    if *association!=current {return Err("Native file association changed during save".into());}
    let parent = path.parent().ok_or("No parent directory for save")?;
    let mut temporary = tempfile::NamedTempFile::new_in(parent).map_err(|e| format!("Could not prepare save: {e}"))?;
    temporary.write_all(text.as_bytes()).map_err(|e| format!("Could not write document: {e}"))?;
    temporary.as_file().sync_all().map_err(|e| format!("Could not flush document: {e}"))?;
    temporary.persist(&path).map_err(|e| format!("Could not replace {}: {e}", path.display()))?;
    let token = random_token();
    *association = Some((path.clone(), token.clone()));
    Ok(Some(SavedDocument { name: file_name(&path), token }))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn save(state:&FileState,token:Option<String>,text:&str,path:&Path)->Result<Option<SavedDocument>,String>{
        save_document(state,token,text.into(),"saved.sov".into(),"document".into(),false,|_,_|Some(path.to_path_buf()))
    }
    #[test]
    fn native_read_associates_exact_path_and_opaque_token(){
        let dir=tempfile::tempdir().unwrap();let path=dir.path().join("source.sov");
        fs::write(&path,"authored source").unwrap();let state=FileState::default();
        let opened=read_document(&state,path.clone()).unwrap();
        assert_eq!(opened.name,"source.sov");assert_eq!(opened.text,"authored source");
        assert_eq!(opened.token.len(),64);assert_eq!(state.0.lock().unwrap().as_ref().unwrap().0,path);
    }
    #[test]
    fn native_unreadable_source_does_not_replace_association(){
        let dir=tempfile::tempdir().unwrap();let path=dir.path().join("kept.sov");fs::write(&path,"kept").unwrap();
        let state=FileState::default();let opened=read_document(&state,path).unwrap();
        assert!(read_document(&state,dir.path().join("missing.sov")).unwrap_err().contains("Could not read"));
        assert_eq!(state.0.lock().unwrap().as_ref().unwrap().1,opened.token);
    }
    #[test]
    fn native_non_utf8_source_is_explicit_error(){
        let dir=tempfile::tempdir().unwrap();let path=dir.path().join("bad.sov");fs::write(&path,[0xff,0xfe]).unwrap();
        let state=FileState::default();assert!(read_document(&state,path).is_err());assert!(state.0.lock().unwrap().is_none());
    }
    #[test]
    fn native_reset_invalidates_previous_handle(){
        let dir=tempfile::tempdir().unwrap();let path=dir.path().join("kept.sov");fs::write(&path,"kept").unwrap();
        let state=FileState::default();let opened=read_document(&state,path.clone()).unwrap();state.reset().unwrap();
        assert!(save(&state,Some(opened.token),"wrong",&path).unwrap_err().contains("stale"));assert_eq!(fs::read_to_string(path).unwrap(),"kept");
    }
    #[test]
    fn native_save_atomically_replaces_selected_file_and_rotates_token(){
        let dir=tempfile::tempdir().unwrap();let path=dir.path().join("kept.sov");fs::write(&path,"old").unwrap();
        let state=FileState::default();let opened=read_document(&state,path.clone()).unwrap();
        let saved=save(&state,Some(opened.token.clone()),"new authored document",&path).unwrap().unwrap();
        assert_ne!(saved.token,opened.token);assert_eq!(fs::read_to_string(&path).unwrap(),"new authored document");
        assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
    }
    #[test]
    fn native_stale_save_preserves_existing_bytes(){
        let dir=tempfile::tempdir().unwrap();let path=dir.path().join("kept.sov");fs::write(&path,"kept").unwrap();
        let state=FileState::default();read_document(&state,path.clone()).unwrap();
        assert!(save(&state,Some("wrong".into()),"lost",&path).is_err());assert_eq!(fs::read_to_string(path).unwrap(),"kept");
    }
    #[test]
    fn native_save_cancel_preserves_association(){
        let dir=tempfile::tempdir().unwrap();let path=dir.path().join("kept.sov");fs::write(&path,"kept").unwrap();
        let state=FileState::default();let opened=read_document(&state,path).unwrap();
        assert!(save_document(&state,None,"new".into(),"new.sov".into(),"document".into(),true,|_,_|None).unwrap().is_none());
        assert_eq!(state.0.lock().unwrap().as_ref().unwrap().1,opened.token);
    }
    #[test]
    fn native_write_failure_preserves_association(){
        let dir=tempfile::tempdir().unwrap();let path=dir.path().join("kept.sov");fs::write(&path,"kept").unwrap();
        let state=FileState::default();let opened=read_document(&state,path.clone()).unwrap();
        assert!(save_document(&state,None,"new".into(),"new.sov".into(),"document".into(),true,|_,_|Some(dir.path().join("missing/new.sov"))).is_err());
        assert_eq!(state.0.lock().unwrap().as_ref().unwrap().1,opened.token);assert_eq!(fs::read_to_string(path).unwrap(),"kept");
    }
    #[test]
    fn native_replace_directory_failure_leaves_no_temporary_file(){
        let dir=tempfile::tempdir().unwrap();let target=dir.path().join("directory.sov");fs::create_dir(&target).unwrap();
        assert!(save(&FileState::default(),None,"new",&target).is_err());
        assert!(target.is_dir());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
    }
    #[test]
    fn native_package_save_selects_extension_and_basename_only(){
        let dir=tempfile::tempdir().unwrap();let target=dir.path().join("export");let state=FileState::default();
        let saved=save_document(&state,None,"package text".into(),"folder/export.sovpak".into(),"package".into(),true,|name,ext|{
            assert_eq!(name,"export.sovpak");assert_eq!(ext,"sovpak");Some(target)
        }).unwrap().unwrap();
        assert_eq!(saved.name,"export.sovpak");assert_eq!(fs::read_to_string(dir.path().join("export.sovpak")).unwrap(),"package text");
    }
    #[test]
    fn native_unknown_format_refuses_before_dialog(){
        assert!(save_document(&FileState::default(),None,"new".into(),"name".into(),"unknown".into(),true,|_,_|panic!("must not prompt")).is_err());
    }
    #[test]
    fn native_association_change_during_dialog_refuses_write(){
        let dir=tempfile::tempdir().unwrap();let original=dir.path().join("original.sov");let target=dir.path().join("new.sov");fs::write(&original,"kept").unwrap();
        let state=FileState::default();read_document(&state,original.clone()).unwrap();
        let result=save_document(&state,None,"new".into(),"new.sov".into(),"document".into(),true,|_,_|{state.reset().unwrap();Some(target.clone())});
        assert!(result.unwrap_err().contains("association changed"));assert!(!target.exists());assert_eq!(fs::read_to_string(original).unwrap(),"kept");
    }
}
