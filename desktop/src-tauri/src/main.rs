#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::fs;
use std::path::PathBuf;
use std::time::Duration;
use tauri::Manager;

mod files;
mod mcp;

const SMOKE_REPORT_FLAG: &str = "--smoke-report";
// A smoke run that hears nothing from the page by then exits with SMOKE_SILENT_EXIT_CODE.
const SMOKE_SILENCE_LIMIT: Duration = Duration::from_secs(30);
const SMOKE_SILENT_EXIT_CODE: i32 = 2;

/// Where a smoke run writes the page's load report: the value after `--smoke-report`.
struct SmokeReport(PathBuf);

#[derive(Serialize)]
struct LoadReport {
    name: String,
    components: u64,
    wires: u64,
    ok: bool,
    error: Option<String>,
}

/// The document named on the command line: the first argument that is not a flag and is not
/// the value of `--smoke-report`.
fn requested_file_path() -> Option<String> {
    launch_arguments(std::env::args().skip(1)).0
}
fn launch_arguments(args:impl IntoIterator<Item=String>)->(Option<String>,Option<PathBuf>){
    let mut args=args.into_iter();let mut document=None;let mut report=None;
    while let Some(arg) = args.next() {
        if arg == SMOKE_REPORT_FLAG {
            let value=args.next().map(PathBuf::from);
            if report.is_none(){report=value;}
            continue;
        }
        if !arg.starts_with('-')&&document.is_none(){document=Some(arg);}
    }
    (document,report)
}

fn smoke_report_path() -> Option<PathBuf> {
    launch_arguments(std::env::args().skip(1)).1
}

#[cfg(test)]
mod tests {
    use super::*;
    fn parse(args:&[&str])->(Option<String>,Option<PathBuf>){launch_arguments(args.iter().map(|arg|arg.to_string()))}
    #[test]
    fn launch_smoke_report_value_is_never_a_document(){
        assert_eq!(parse(&["--smoke-report","report.json","source.sov"]),(Some("source.sov".into()),Some(PathBuf::from("report.json"))));
        assert_eq!(parse(&["source.sov","--smoke-report","report.json"]),(Some("source.sov".into()),Some(PathBuf::from("report.json"))));
    }
    #[test]
    fn launch_missing_paths_are_not_invented(){assert_eq!(parse(&[]),(None,None));assert_eq!(parse(&["--smoke-report"]),(None,None));}
    #[test]
    fn launch_first_document_wins_and_flags_are_ignored(){assert_eq!(parse(&["--flag","first.sov","second.sov"]).0,Some("first.sov".into()));}
}

#[tauri::command]
fn opened_document(state: tauri::State<'_, files::FileState>) -> Result<Option<files::OpenedDocument>, String> {
    requested_file_path().map(|path| files::read_document(&state, PathBuf::from(path))).transpose()
}

/// Registered only in a smoke run. Writes what the page loaded to the report path and ends the
/// process: 0 when the document loaded, 1 when it did not or the report could not be written.
/// `std::process::exit` rather than `AppHandle::exit`, so the exit code a CI job reads does not
/// depend on how the event loop forwards it.
#[tauri::command]
fn report_loaded(
    app: tauri::AppHandle,
    report: tauri::State<'_, SmokeReport>,
    name: String,
    components: u64,
    wires: u64,
    ok: bool,
    error: Option<String>,
) {
    let body = LoadReport {
        name,
        components,
        wires,
        ok,
        error,
    };
    let written = serde_json::to_string_pretty(&body)
        .map_err(|e| e.to_string())
        .and_then(|text| fs::write(&report.0, text).map_err(|e| e.to_string()));
    if let Err(problem) = &written {
        eprintln!("smoke report could not be written to {}: {problem}", report.0.display());
    }
    if let Some(relay) = app.try_state::<std::sync::Arc<mcp::RelayState>>() { relay.stop(); }
    std::process::exit(if ok && written.is_ok() { 0 } else { 1 });
}

fn main() {
    let builder = tauri::Builder::default().manage(files::FileState::default())
        .setup(|app| {
            let relay = mcp::start(app.handle()).map_err(std::io::Error::other)?;
            if smoke_report_path().is_some() {
                let watchdog_relay=relay.clone();
                std::thread::spawn(move || {
                    std::thread::sleep(SMOKE_SILENCE_LIMIT);
                    eprintln!("smoke run: the page reported nothing within {SMOKE_SILENCE_LIMIT:?}");
                    watchdog_relay.stop();
                    std::process::exit(SMOKE_SILENT_EXIT_CODE);
                });
            }
            app.manage(relay);
            Ok(())
        });
    let builder = match smoke_report_path() {
        Some(path) => {
            builder
                .manage(SmokeReport(path))
                .invoke_handler(tauri::generate_handler![opened_document, report_loaded,
                    files::desktop_open_document, files::desktop_save_document, files::desktop_reset_document,
                    mcp::desktop_mcp_ready, mcp::desktop_mcp_info, mcp::desktop_mcp_begin, mcp::desktop_mcp_respond])
        }
        None => builder.invoke_handler(tauri::generate_handler![opened_document,
            files::desktop_open_document, files::desktop_save_document, files::desktop_reset_document,
            mcp::desktop_mcp_ready, mcp::desktop_mcp_info, mcp::desktop_mcp_begin, mcp::desktop_mcp_respond]),
    };
    builder
        .build(tauri::generate_context!())
        .expect("error while building SOV Schematic desktop shell")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                if let Some(relay) = app.try_state::<std::sync::Arc<mcp::RelayState>>() { relay.stop(); }
            }
        });
}
