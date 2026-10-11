//! Authenticated loopback transport only. Every RPC is evaluated by the active editor.
use crate::files::random_token;
use axum::{body::{to_bytes, Body}, extract::State, http::{HeaderMap, Request, StatusCode}, response::{IntoResponse, Response}, routing::post, Json, Router};
use hyper_util::{rt::{TokioIo, TokioTimer}, service::TowerToHyperService};
use serde::Serialize;
use serde_json::{json, Value};
use std::{collections::HashMap, fs, io::Write, net::TcpListener, sync::{atomic::{AtomicBool, AtomicU64, Ordering}, Arc, Mutex}, time::{Duration, Instant}};
use tauri::{Emitter, Manager};
use tokio::sync::{oneshot, OwnedSemaphorePermit, Semaphore};

const BODY_LIMIT: usize = 1_048_576;
const BODY_TIMEOUT: Duration = Duration::from_secs(5);
const REQUEST_TIMEOUT: Duration = Duration::from_secs(15);
const HEADER_TIMEOUT: Duration = Duration::from_secs(5);
const MAX_CONNECTIONS: usize = 16;
const MAX_HEADER_BUFFER: usize = 32_768;
#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct RelayRequest { request_id: String, rpc: Value }
#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RelayInfo { endpoint: String, descriptor_path: String, build: String }
pub struct RelayState {
    ready: AtomicBool, running: AtomicBool, sequence: AtomicU64,
    pending: Mutex<HashMap<String, Pending>>, pub info: RelayInfo,
}
struct Pending {
    sender: oneshot::Sender<Value>, _permit: OwnedSemaphorePermit,
    started: bool, deadline: Instant,
}
#[derive(Clone)]
struct Transport { relay: Arc<RelayState>, app: tauri::AppHandle, token: String, host: String, permit: Arc<Semaphore> }
// A queued request can be cancelled; a started effect keeps its permit until the editor replies.
struct PendingRequest { state: Arc<RelayState>, id: String }
impl Drop for PendingRequest {
    fn drop(&mut self) {
        if let Ok(mut pending) = self.state.pending.lock() {
            if pending.get(&self.id).map(|request| !request.started).unwrap_or(false) {
                pending.remove(&self.id);
            }
        }
    }
}
impl RelayState {
    fn begin(&self,request_id:&str)->bool {
        if !self.running.load(Ordering::SeqCst) || !self.ready.load(Ordering::SeqCst) { return false; }
        let Ok(mut pending)=self.pending.lock() else { return false };
        let Some(request)=pending.get_mut(request_id) else { return false };
        if request.started { return false; }
        if Instant::now()>=request.deadline { pending.remove(request_id);return false; }
        request.started=true;
        true
    }
    fn respond(&self,request_id:&str,response:Value)->Result<(),String> {
        let mut pending=self.pending.lock().map_err(|_| "Relay unavailable")?;
        if !pending.get(request_id).map(|request|request.started).unwrap_or(false) {
            return Err("Request expired, unknown or not begun".into());
        }
        let request=pending.remove(request_id).ok_or("Request expired or unknown")?;
        drop(pending);
        request.sender.send(response).map_err(|_| "HTTP caller expired; editor completion released the request".into())
    }
    pub fn stop(&self) {
        self.running.store(false, Ordering::SeqCst);
        self.ready.store(false, Ordering::SeqCst);
        if let Ok(mut pending) = self.pending.lock() { pending.clear(); }
        let _ = fs::remove_file(&self.info.descriptor_path);
    }
}

#[tauri::command]
pub fn desktop_mcp_ready(state: tauri::State<'_, Arc<RelayState>>) {
    state.ready.store(true, Ordering::SeqCst);
    eprintln!("desktop startup: ready pid={}", std::process::id());
}
#[tauri::command]
pub fn desktop_mcp_info(state: tauri::State<'_, Arc<RelayState>>) -> RelayInfo { state.info.clone() }
#[tauri::command]
pub fn desktop_mcp_begin(state: tauri::State<'_, Arc<RelayState>>, request_id: String) -> bool {
    state.begin(&request_id)
}
#[tauri::command]
pub fn desktop_mcp_respond(state: tauri::State<'_, Arc<RelayState>>, request_id: String, response: Value) -> Result<(), String> {
    state.respond(&request_id,response)
}
fn authorized(headers:&HeaderMap,token:&str,host:&str)->bool {
    let authorization=format!("Bearer {token}");
    headers.get_all("authorization").iter().count()==1
        && headers.get("authorization").and_then(|v|v.to_str().ok())==Some(authorization.as_str())
        && headers.get_all("host").iter().count()==1
        && headers.get("host").and_then(|v|v.to_str().ok())==Some(host)
        && !headers.contains_key("origin")
}
fn error(status: StatusCode, message: &str) -> Response { (status, Json(json!({"error":message}))).into_response() }
#[cfg(windows)]
pub(crate) fn protect_descriptor_path(path: &std::path::Path) -> Result<(), String> {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::{Foundation::LocalFree, Security::{
        Authorization::{ConvertStringSecurityDescriptorToSecurityDescriptorW, SDDL_REVISION_1},
        SetFileSecurityW, DACL_SECURITY_INFORMATION, PROTECTED_DACL_SECURITY_INFORMATION,
    }};
    // A protected DACL replaces all inherited grants, including CodexSandboxUsers.
    // OW is the owner-rights SID; System and Administrators retain recovery access.
    let sddl:Vec<u16>="D:P(A;;FA;;;OW)(A;;FA;;;SY)(A;;FA;;;BA)".encode_utf16().chain(Some(0)).collect();
    let name:Vec<u16>=path.as_os_str().encode_wide().chain(Some(0)).collect();
    let mut descriptor=std::ptr::null_mut();
    // Conversion allocates one Windows security descriptor; all paths below free it once.
    unsafe {
        if ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl.as_ptr(),SDDL_REVISION_1,&mut descriptor,std::ptr::null_mut())==0 {
            return Err(format!("Could not construct private MCP descriptor ACL: {}",std::io::Error::last_os_error()));
        }
        let result=SetFileSecurityW(name.as_ptr(),DACL_SECURITY_INFORMATION|PROTECTED_DACL_SECURITY_INFORMATION,descriptor);
        let failure=if result==0 { Some(std::io::Error::last_os_error()) } else { None };
        LocalFree(descriptor);
        if let Some(error)=failure { return Err(format!("Could not protect MCP descriptor path {}: {error}",path.display())); }
    }
    Ok(())
}
async fn relay(State(transport): State<Transport>, request: Request<Body>) -> Response {
    let started=Instant::now();
    if !authorized(request.headers(),&transport.token,&transport.host) { return error(StatusCode::FORBIDDEN, "Local authorization required; browser origins are refused"); }
    let protocol_headers = request.headers().get_all("mcp-protocol-version");
    if protocol_headers.iter().count() > 1 || protocol_headers.iter().any(|value| !matches!(value.to_str(), Ok("2025-03-26" | "2025-06-18"))) {
        return error(StatusCode::BAD_REQUEST, "Unsupported MCP protocol version");
    }
    if !transport.relay.running.load(Ordering::SeqCst) || !transport.relay.ready.load(Ordering::SeqCst) { return error(StatusCode::SERVICE_UNAVAILABLE, "Editor bridge is not ready"); }
    let Ok(permit) = transport.permit.clone().try_acquire_owned() else { return error(StatusCode::TOO_MANY_REQUESTS, "Another editor request is in progress") };
    let body = match tokio::time::timeout(BODY_TIMEOUT, to_bytes(request.into_body(), BODY_LIMIT)).await {
        Ok(Ok(body)) => body,
        Ok(Err(_)) => return error(StatusCode::PAYLOAD_TOO_LARGE, "Body unavailable or exceeds 1 MiB"),
        Err(_) => return error(StatusCode::REQUEST_TIMEOUT, "Request body timed out"),
    };
    let rpc: Value = match serde_json::from_slice(&body) {
        Ok(value) => value,
        Err(_) => return (StatusCode::BAD_REQUEST, Json(json!({"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"Parse error"}}))).into_response(),
    };
    let id = rpc.get("id").cloned().unwrap_or(Value::Null);
    let request_id = transport.relay.sequence.fetch_add(1, Ordering::SeqCst).to_string();
    let (sender, receiver) = oneshot::channel();
    match transport.relay.pending.lock() {
        Ok(mut pending) => { pending.insert(request_id.clone(), Pending { sender, _permit:permit, started:false, deadline:started+REQUEST_TIMEOUT }); },
        Err(_) => return error(StatusCode::SERVICE_UNAVAILABLE, "Relay unavailable"),
    }
    let _pending=PendingRequest { state:transport.relay.clone(),id:request_id.clone() };
    if transport.app.emit("desktop-mcp-request", RelayRequest { request_id: request_id.clone(), rpc }).is_err() {
        if let Ok(mut pending) = transport.relay.pending.lock() { pending.remove(&request_id); }
        return error(StatusCode::SERVICE_UNAVAILABLE, "Editor unavailable");
    }
    let response = tokio::time::timeout(REQUEST_TIMEOUT.saturating_sub(started.elapsed()), receiver).await;
    match response {
        Ok(Ok(response)) if response.is_null() => StatusCode::ACCEPTED.into_response(),
        Ok(Ok(response)) => Json(response).into_response(),
        _ => (StatusCode::GATEWAY_TIMEOUT, Json(json!({"jsonrpc":"2.0","id":id,"error":{"code":-32000,"message":"Editor response timed out"}}))).into_response(),
    }
}
pub fn start(app: &tauri::AppHandle) -> Result<Arc<RelayState>, String> {
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|e| e.to_string())?;
    listener.set_nonblocking(true).map_err(|e| e.to_string())?;
    let host = listener.local_addr().map_err(|e| e.to_string())?.to_string();
    let endpoint = format!("http://{host}/mcp");
    let token = random_token();
    let directory = app.path().app_local_data_dir().map_err(|e| e.to_string())?.join("mcp");
    fs::create_dir_all(&directory).map_err(|e| e.to_string())?;
    #[cfg(windows)]
    protect_descriptor_path(&directory)?;
    #[cfg(unix)] {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&directory, fs::Permissions::from_mode(0o700)).map_err(|e| e.to_string())?;
    }
    let descriptor = directory.join(format!("{}.json", std::process::id()));
    let build = option_env!("SOV_BUILD_REVISION").unwrap_or("unversioned").to_string();
    let info = RelayInfo { endpoint: endpoint.clone(), descriptor_path: descriptor.to_string_lossy().into_owned(), build: build.clone() };
    let mut temporary = tempfile::NamedTempFile::new_in(&directory).map_err(|e| e.to_string())?;
    #[cfg(windows)]
    protect_descriptor_path(temporary.path())?;
    #[cfg(unix)] {
        use std::os::unix::fs::PermissionsExt;
        temporary.as_file().set_permissions(fs::Permissions::from_mode(0o600)).map_err(|e| e.to_string())?;
    }
    // The secret is written only after directory and temporary-file ACL protection succeeds.
    temporary.write_all(json!({"endpoint":endpoint,"token":token,"build":build,"pid":std::process::id()}).to_string().as_bytes()).map_err(|e| e.to_string())?;
    temporary.as_file().sync_all().map_err(|e| e.to_string())?;
    temporary.persist(&descriptor).map_err(|e| e.to_string())?;
    let state = Arc::new(RelayState { ready: AtomicBool::new(false), running: AtomicBool::new(true), sequence: AtomicU64::new(1), pending: Mutex::new(HashMap::new()), info });
    let transport = Transport { relay: state.clone(), app: app.clone(), token, host, permit: Arc::new(Semaphore::new(1)) };
    let worker_state = state.clone();
    tauri::async_runtime::spawn(async move {
        let listener = match tokio::net::TcpListener::from_std(listener) { Ok(listener) => listener, Err(error) => { eprintln!("MCP listener unavailable: {error}"); worker_state.stop(); return; } };
        let router = Router::new().route("/mcp", post(relay)).fallback(|| async { error(StatusCode::NOT_FOUND, "POST /mcp only") }).with_state(transport);
        let connections=Arc::new(Semaphore::new(MAX_CONNECTIONS));
        let mut tasks=tokio::task::JoinSet::new();
        while worker_state.running.load(Ordering::SeqCst) {
            while tasks.try_join_next().is_some() {}
            tokio::select! {
                _=tokio::time::sleep(Duration::from_millis(100))=>{},
                _=tasks.join_next(),if !tasks.is_empty()=>{},
                accepted=listener.accept()=>{
                    let (stream,_)=match accepted {Ok(connection)=>connection,Err(error)=>{eprintln!("MCP accept failed: {error}");break}};
                    let Ok(permit)=connections.clone().try_acquire_owned() else {drop(stream);continue};
                    let service=TowerToHyperService::new(router.clone());
                    tasks.spawn(async move {
                        let _permit=permit;
                        let mut builder=hyper::server::conn::http1::Builder::new();
                        builder.timer(TokioTimer::new()).header_read_timeout(HEADER_TIMEOUT)
                            .max_buf_size(MAX_HEADER_BUFFER).keep_alive(false);
                        // Also bound a client that never consumes its response bytes.
                        let _=tokio::time::timeout(Duration::from_secs(25),builder.serve_connection(TokioIo::new(stream),service)).await;
                    });
                }
            }
        }
        tasks.abort_all();
        while tasks.join_next().await.is_some() {}
        worker_state.stop();
    });
    Ok(state)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture(expired:bool)->(Arc<RelayState>,Arc<Semaphore>,oneshot::Receiver<Value>,tempfile::TempDir){
        let directory=tempfile::tempdir().unwrap();let descriptor=directory.path().join("descriptor.json");fs::write(&descriptor,"descriptor").unwrap();
        let state=Arc::new(RelayState{ready:AtomicBool::new(true),running:AtomicBool::new(true),sequence:AtomicU64::new(1),pending:Mutex::new(HashMap::new()),
            info:RelayInfo{endpoint:"http://127.0.0.1:1/mcp".into(),descriptor_path:descriptor.to_string_lossy().into_owned(),build:"test".into()}});
        let permit=Arc::new(Semaphore::new(1));let (sender,receiver)=oneshot::channel();
        state.pending.lock().unwrap().insert("1".into(),Pending{sender,_permit:permit.clone().try_acquire_owned().unwrap(),started:false,
            deadline:if expired{Instant::now()-Duration::from_secs(1)}else{Instant::now()+REQUEST_TIMEOUT}});
        (state,permit,receiver,directory)
    }
    fn headers()->HeaderMap{
        let mut headers=HeaderMap::new();headers.insert("host","127.0.0.1:1234".parse().unwrap());headers.insert("authorization","Bearer secret".parse().unwrap());headers
    }
    #[test]
    fn relay_begin_admits_once_and_preserves_permit(){
        let (state,permit,_,_directory)=fixture(false);assert!(state.begin("1"));assert!(!state.begin("1"));assert!(!state.begin("missing"));assert_eq!(permit.available_permits(),0);
    }
    #[test]
    fn relay_expired_queue_refuses_and_releases_permit(){
        let (state,permit,_,_directory)=fixture(true);assert!(!state.begin("1"));assert_eq!(permit.available_permits(),1);assert!(state.pending.lock().unwrap().is_empty());
    }
    #[test]
    fn relay_not_ready_refuses_before_effect(){
        let (state,_,_,_directory)=fixture(false);state.ready.store(false,Ordering::SeqCst);assert!(!state.begin("1"));assert!(!state.pending.lock().unwrap().get("1").unwrap().started);
    }
    #[test]
    fn relay_queue_cancellation_releases_permit(){
        let (state,permit,_,_directory)=fixture(false);drop(PendingRequest{state:state.clone(),id:"1".into()});assert_eq!(permit.available_permits(),1);assert!(!state.begin("1"));
    }
    #[test]
    fn relay_started_cancellation_retains_permit_until_response(){
        let (state,permit,mut receiver,_directory)=fixture(false);assert!(state.begin("1"));drop(PendingRequest{state:state.clone(),id:"1".into()});
        assert_eq!(permit.available_permits(),0);state.respond("1",json!({"completed":true})).unwrap();assert_eq!(receiver.try_recv().unwrap(),json!({"completed":true}));assert_eq!(permit.available_permits(),1);
    }
    #[test]
    fn relay_reply_after_http_timeout_releases_started_permit(){
        let (state,permit,receiver,_directory)=fixture(false);assert!(state.begin("1"));drop(receiver);
        assert!(state.respond("1",Value::Null).unwrap_err().contains("expired"));assert_eq!(permit.available_permits(),1);assert!(!state.begin("1"));
    }
    #[test]
    fn relay_reply_before_begin_is_refused(){
        let (state,permit,_,_directory)=fixture(false);assert!(state.respond("1",Value::Null).is_err());assert_eq!(permit.available_permits(),0);assert!(state.begin("1"));
    }
    #[test]
    fn relay_stop_clears_descriptor_pending_and_admission(){
        let (state,permit,_,_directory)=fixture(false);assert!(state.begin("1"));state.stop();
        assert!(!std::path::Path::new(&state.info.descriptor_path).exists());assert_eq!(permit.available_permits(),1);assert!(!state.begin("1"));state.stop();
    }
    #[test]
    fn relay_exact_authenticated_loopback_host_is_admitted(){assert!(authorized(&headers(),"secret","127.0.0.1:1234"));}
    #[test]
    fn relay_wrong_bearer_and_foreign_host_are_refused(){
        assert!(!authorized(&headers(),"different","127.0.0.1:1234"));assert!(!authorized(&headers(),"secret","localhost:1234"));
        let mut no_token=headers();no_token.remove("authorization");assert!(!authorized(&no_token,"secret","127.0.0.1:1234"));
    }
    #[test]
    fn relay_duplicate_authentication_headers_are_refused(){
        let mut auth=headers();auth.append("authorization","Bearer secret".parse().unwrap());assert!(!authorized(&auth,"secret","127.0.0.1:1234"));
        let mut host=headers();host.append("host","127.0.0.1:1234".parse().unwrap());assert!(!authorized(&host,"secret","127.0.0.1:1234"));
    }
    #[test]
    fn relay_browser_origin_including_null_is_refused(){
        let mut headers=headers();headers.insert("origin","null".parse().unwrap());assert!(!authorized(&headers,"secret","127.0.0.1:1234"));
    }
    #[cfg(windows)]
    #[test]
    fn relay_private_acl_preserves_owner_file_access(){
        use std::os::windows::ffi::OsStrExt;
        use windows_sys::Win32::{Foundation::LocalFree,Security::{GetFileSecurityW,DACL_SECURITY_INFORMATION,
            Authorization::{ConvertSecurityDescriptorToStringSecurityDescriptorW,SDDL_REVISION_1}}};
        let file=tempfile::NamedTempFile::new().unwrap();protect_descriptor_path(file.path()).unwrap();fs::write(file.path(),"private").unwrap();assert_eq!(fs::read_to_string(file.path()).unwrap(),"private");
        let path:Vec<u16>=file.path().as_os_str().encode_wide().chain(Some(0)).collect();
        // Read the actual OS DACL, not the input declaration passed to the setter.
        unsafe {
            let mut needed=0;GetFileSecurityW(path.as_ptr(),DACL_SECURITY_INFORMATION,std::ptr::null_mut(),0,&mut needed);assert!(needed>0);
            let mut descriptor=vec![0usize;(needed as usize+std::mem::size_of::<usize>()-1)/std::mem::size_of::<usize>()];
            assert_ne!(GetFileSecurityW(path.as_ptr(),DACL_SECURITY_INFORMATION,descriptor.as_mut_ptr().cast(),needed,&mut needed),0);
            let mut text=std::ptr::null_mut();
            assert_ne!(ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor.as_mut_ptr().cast(),SDDL_REVISION_1,DACL_SECURITY_INFORMATION,&mut text,std::ptr::null_mut()),0);
            let mut length=0;while *text.add(length)!=0 {length+=1;assert!(length<4096);}
            let actual=String::from_utf16_lossy(std::slice::from_raw_parts(text,length));LocalFree(text.cast());
            assert!(actual.starts_with("D:P"),"{actual}");assert_eq!(actual.matches('(').count(),3,"{actual}");
            for principal in [";;;OW)",";;;SY)",";;;BA)"] {assert!(actual.contains(principal),"{actual}");}
        }
    }
    #[cfg(windows)]
    #[test]
    fn relay_private_acl_failure_is_explicit(){
        let dir=tempfile::tempdir().unwrap();assert!(protect_descriptor_path(&dir.path().join("absent")).unwrap_err().contains("Could not protect"));
    }
}
