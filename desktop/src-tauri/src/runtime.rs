//! Host-admitted trusted Node CLI jobs. Job containment is not filesystem/network isolation.
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::HashMap,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Condvar, Mutex,
    },
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use tauri::Manager;

const MAX_ATTEMPTS: usize = 64;
const MAX_SOURCE: usize = 65_536;
const MAX_INPUT: usize = 65_536;
const CONFIG_LIMIT: u64 = 65_536;
const RECEIPT_LIMIT: u64 = 8_388_608;

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct StartRequest {
    request_id: String,
    provider_id: String,
    provider_version: String,
    grant_id: String,
    document_id: String,
    revision: u64,
    state_token: String,
    reference_id: String,
    source: String,
    source_hash: String,
    input_json: String,
    input_hash: String,
}
#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Limits {
    timeout_ms: u64,
    max_output_bytes: usize,
    max_processes: u32,
    max_memory_bytes: usize,
}
#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Provider {
    id: String,
    version: String,
    language: String,
    executable: PathBuf,
    executable_sha256: String,
    limits: Limits,
}
#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Grant {
    id: String,
    provider_id: String,
    provider_version: String,
    document_id: String,
    source_hash: String,
    request_id: String,
    expires_at_unix_ms: u64,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Host {
    schema: String,
    providers: Vec<Provider>,
    grants: Vec<Grant>,
}
struct Inner {
    attempts: HashMap<String, Arc<Attempt>>,
    active: Option<String>,
    blocked: bool,
    loaded: bool,
    host_lock: Option<File>,
}
pub struct RuntimeState {
    home: PathBuf,
    inner: Mutex<Inner>,
    stopping: AtomicBool,
}
struct Attempt {
    request: StartRequest,
    identity: String,
    directory: PathBuf,
    receipt: Mutex<Value>,
    cancel: AtomicBool,
    done: (Mutex<bool>, Condvar),
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .min(u64::MAX as u128) as u64
}
fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn valid_hash(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn valid_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || "-_.:@".contains(c))
}
fn validate_request(request: &StartRequest) -> Result<(), String> {
    if [
        &request.request_id,
        &request.document_id,
        &request.provider_id,
        &request.provider_version,
        &request.grant_id,
        &request.reference_id,
    ]
    .iter()
    .any(|id| !valid_id(id))
        || request.state_token.is_empty()
        || request.state_token.len() > 256
    {
        return Err("Invalid runtime request identity".into());
    }
    if request.source.len() > MAX_SOURCE || request.input_json.len() > MAX_INPUT {
        return Err("Code/input exceeds 64 KiB limit".into());
    }
    if !valid_hash(&request.source_hash)
        || !valid_hash(&request.input_hash)
        || hash(request.source.as_bytes()) != request.source_hash
        || hash(request.input_json.as_bytes()) != request.input_hash
    {
        return Err("Frozen code/input hash mismatch".into());
    }
    serde_json::from_str::<Value>(&request.input_json).map_err(|_| "Input is not JSON")?;
    Ok(())
}
fn validate_limits(limit: &Limits) -> Result<(), String> {
    if !(1..=20_000).contains(&limit.timeout_ms)
        || !(1..=1_048_576).contains(&limit.max_output_bytes)
        || !(1..=8).contains(&limit.max_processes)
        || !(33_554_432..=536_870_912).contains(&limit.max_memory_bytes)
    {
        return Err("Provider limits exceed admitted bounds".into());
    }
    Ok(())
}
fn validate_provider(provider: &Provider) -> Result<(), String> {
    if !supported_provider(provider)
        || !valid_hash(&provider.executable_sha256)
    {
        return Err("Unsupported provider declaration".into());
    }
    validate_limits(&provider.limits)?;
    if !provider.executable.is_absolute()
        || !provider.executable.is_file()
        || canonical(&provider.executable)? != provider.executable
    {
        return Err("Provider executable must be a canonical absolute file".into());
    }
    Ok(())
}
fn supported_provider(provider: &Provider) -> bool {
    provider.version == "1" && matches!((provider.id.as_str(), provider.language.as_str()),
        ("node-cli", "javascript") | ("python-cli", "python"))
}
fn canonical(path: &Path) -> Result<PathBuf, String> {
    let resolved = path.canonicalize().map_err(|e| e.to_string())?;
    #[cfg(windows)]
    {
        let text = resolved.to_str().ok_or("Non-Unicode host path")?;
        if let Some(rest) = text.strip_prefix("\\\\?\\UNC\\") {
            return Ok(PathBuf::from(format!("\\\\{rest}")));
        }
        if let Some(rest) = text.strip_prefix("\\\\?\\") {
            return Ok(PathBuf::from(rest));
        }
    }
    Ok(resolved)
}
fn private(path: &Path) -> Result<(), String> {
    #[cfg(windows)]
    {
        crate::mcp::protect_descriptor_path(path)?;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(
            path,
            fs::Permissions::from_mode(if path.is_dir() { 0o700 } else { 0o600 }),
        )
        .map_err(|e| e.to_string())?;
    }
    Ok(())
}
fn directory(path: &Path) -> Result<(), String> {
    fs::create_dir_all(path).map_err(|e| e.to_string())?;
    private(path)
}
fn write_private(path: &Path, bytes: &[u8]) -> Result<(), String> {
    // tempfile's Windows rename passes raw paths to MoveFileExW. Preserve the
    // canonical parent's extended-length prefix for both sides of that rename.
    #[cfg(windows)]
    let destination = path
        .parent()
        .ok_or("Output has no parent")?
        .canonicalize()
        .map_err(|e| e.to_string())?
        .join(path.file_name().ok_or("Output has no file name")?);
    #[cfg(not(windows))]
    let destination = path.to_path_buf();
    let path = destination.as_path();
    let parent = path.parent().ok_or("Output has no parent")?;
    let mut temporary = tempfile::NamedTempFile::new_in(parent).map_err(|e| e.to_string())?;
    private(temporary.path())?;
    temporary
        .write_all(bytes)
        .and_then(|_| temporary.as_file().sync_all())
        .map_err(|e| e.to_string())?;
    temporary.persist(path).map_err(|e| e.to_string())?;
    Ok(())
}
fn read_bounded(path: &Path, max: u64) -> Result<Vec<u8>, String> {
    let file = File::open(path).map_err(|e| e.to_string())?;
    let mut bytes = Vec::new();
    file.take(max + 1)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() as u64 > max {
        return Err("Host file exceeds size limit".into());
    }
    Ok(bytes)
}
fn persist(attempt: &Attempt) -> Result<(), String> {
    let receipt = attempt
        .receipt
        .lock()
        .map_err(|_| "Runtime receipt lock poisoned")?;
    write_private(
        &attempt.directory.join("receipt.json"),
        &serde_json::to_vec(&*receipt).map_err(|e| e.to_string())?,
    )
}
fn executable_hash(path: &Path) -> Result<String, String> {
    let mut file = File::open(path).map_err(|e| e.to_string())?;
    if file.metadata().map_err(|e| e.to_string())?.len() > 134_217_728 {
        return Err("Executable exceeds admitted hash size".into());
    }
    let mut digest = Sha256::new();
    let mut block = [0u8; 65_536];
    loop {
        let count = file.read(&mut block).map_err(|e| e.to_string())?;
        if count == 0 {
            break;
        }
        digest.update(&block[..count]);
    }
    Ok(format!("{:x}", digest.finalize()))
}
fn verify_terminal(path: &Path, receipt: &Value, request: &StartRequest) -> Result<(), String> {
    let recorded: Value =
        serde_json::from_slice(&read_bounded(&path.join("receipt.json"), RECEIPT_LIMIT)?)
            .map_err(|e| e.to_string())?;
    if &recorded != receipt {
        return Err("Durable receipt differs from retained state".into());
    }
    for field in ["requestHash", "hostHash", "grantHash"] {
        if !receipt
            .get(field)
            .and_then(Value::as_str)
            .is_some_and(valid_hash)
        {
            return Err("Retained identity hash invalid".into());
        }
    }
    if receipt.get("requestHash").and_then(Value::as_str)
        != Some(hash(&serde_json::to_vec(request).map_err(|e| e.to_string())?).as_str())
        || receipt
            .get("startedAtUnixMs")
            .and_then(Value::as_u64)
            .is_none()
        || receipt
            .get("finishedAtUnixMs")
            .and_then(Value::as_u64)
            .is_none()
    {
        return Err("Retained timing/request identity invalid".into());
    }
    let exit_code = receipt
        .get("exitCode")
        .ok_or("Retained exit code missing")?;
    if !exit_code.is_null()
        && !exit_code
            .as_u64()
            .is_some_and(|code| code <= u32::MAX as u64)
    {
        return Err("Retained exit code invalid".into());
    }
    if receipt.get("outcome").and_then(Value::as_str) == Some("succeeded")
        && exit_code.as_u64() != Some(0)
    {
        return Err("Successful receipt requires exit zero".into());
    }
    if receipt.get("schema").and_then(Value::as_str) != Some("schematically.cli-receipt@1")
        || receipt.get("requestId").and_then(Value::as_str) != Some(request.request_id.as_str())
        || receipt.get("documentId").and_then(Value::as_str) != Some(request.document_id.as_str())
    {
        return Err("Retained receipt identity mismatch".into());
    }
    let provider: Provider = serde_json::from_value(
        receipt
            .get("provider")
            .cloned()
            .ok_or("Retained provider missing")?,
    )
    .map_err(|e| e.to_string())?;
    validate_limits(&provider.limits)?;
    if !valid_hash(&provider.executable_sha256)
        || !provider.executable.is_absolute()
        || !supported_provider(&provider)
        || provider.id != request.provider_id
        || provider.version != request.provider_version
        || !matches!(
            receipt.get("outcome").and_then(Value::as_str),
            Some(
                "succeeded" | "failed" | "cancelled" | "timed-out" | "output-overflow" | "refused"
            )
        )
    {
        return Err("Retained terminal declaration invalid".into());
    }
    let stdout = read_bounded(
        &path.join("stdout.bin"),
        provider.limits.max_output_bytes as u64,
    )?;
    let stderr = read_bounded(
        &path.join("stderr.bin"),
        provider.limits.max_output_bytes as u64,
    )?;
    if stdout.len() + stderr.len() > provider.limits.max_output_bytes
        || receipt.get("stdoutBytes").and_then(Value::as_u64) != Some(stdout.len() as u64)
        || receipt.get("stderrBytes").and_then(Value::as_u64) != Some(stderr.len() as u64)
        || receipt.get("stdoutHash").and_then(Value::as_str) != Some(hash(&stdout).as_str())
        || receipt.get("stderrHash").and_then(Value::as_str) != Some(hash(&stderr).as_str())
        || receipt.get("outputHash").and_then(Value::as_str)
            != Some(hash(&[stdout.as_slice(), &[0], stderr.as_slice()].concat()).as_str())
        || receipt.get("stdout").and_then(Value::as_str)
            != Some(String::from_utf8_lossy(&stdout).as_ref())
        || receipt.get("stderr").and_then(Value::as_str)
            != Some(String::from_utf8_lossy(&stderr).as_ref())
    {
        return Err("Retained output evidence mismatch".into());
    }
    Ok(())
}
fn record_terminal(
    attempt: &Attempt,
    mut final_receipt: Value,
    stdout: &[u8],
    stderr: &[u8],
) -> Result<(), String> {
    final_receipt["stdout"] = json!(String::from_utf8_lossy(stdout));
    final_receipt["stderr"] = json!(String::from_utf8_lossy(stderr));
    final_receipt["stdoutHash"] = json!(hash(stdout));
    final_receipt["stderrHash"] = json!(hash(stderr));
    final_receipt["stdoutBytes"] = json!(stdout.len());
    final_receipt["stderrBytes"] = json!(stderr.len());
    final_receipt["outputHash"] = json!(hash(&[stdout, &[0], stderr].concat()));
    let mut visible = attempt
        .receipt
        .lock()
        .map_err(|_| "Runtime receipt poisoned")?;
    visible["phase"] = json!("recording");
    let recorded = write_private(&attempt.directory.join("stdout.bin"), stdout)
        .and_then(|_| write_private(&attempt.directory.join("stderr.bin"), stderr))
        .and_then(|_| {
            write_private(
                &attempt.directory.join("receipt.json"),
                &serde_json::to_vec(&final_receipt).map_err(|e| e.to_string())?,
            )
        });
    match recorded {
        Ok(()) => {
            *visible = final_receipt;
            Ok(())
        }
        Err(error) => {
            *visible = final_receipt;
            visible["phase"] = json!("unknown");
            visible["outcome"] = json!("unknown");
            visible["recordingError"] = json!(error);
            Err(error)
        }
    }
}
fn checked_visible(attempt: &Attempt) -> Result<(), String> {
    let mut receipt = attempt
        .receipt
        .lock()
        .map_err(|_| "Runtime receipt poisoned")?;
    if receipt.get("phase").and_then(Value::as_str) == Some("terminal") {
        if let Err(error) = verify_terminal(&attempt.directory, &receipt, &attempt.request) {
            receipt["phase"] = json!("unknown");
            receipt["outcome"] = json!("unknown");
            receipt["recordingError"] = json!(error);
            return Err("Retained terminal evidence changed".into());
        }
    }
    Ok(())
}
impl RuntimeState {
    pub fn new(app: &tauri::AppHandle) -> Result<Arc<Self>, String> {
        let home = match std::env::var_os("SOV_RUNTIME_DIR") {
            Some(path) => PathBuf::from(path),
            None => app
                .path()
                .app_local_data_dir()
                .map_err(|e| e.to_string())?
                .join("runtime"),
        };
        // Registration is inert: no default runtime directory/config/recovery effects.
        Ok(Arc::new(Self {
            home,
            inner: Mutex::new(Inner {
                attempts: HashMap::new(),
                active: None,
                blocked: false,
                loaded: false,
                host_lock: None,
            }),
            stopping: AtomicBool::new(false),
        }))
    }
    fn load(&self, inner: &mut Inner) -> Result<(), String> {
        if inner.loaded {
            return Ok(());
        }
        let home = &self.home;
        if !home.is_absolute() {
            return Err("SOV_RUNTIME_DIR must be absolute".into());
        }
        if !home.exists() {
            return Ok(());
        }
        directory(home)?;
        directory(&home.join("attempts"))?;
        directory(&home.join("consumed"))?;
        for entry in fs::read_dir(home.join("attempts")).map_err(|e| e.to_string())? {
            let path = entry.map_err(|e| e.to_string())?.path();
            if !path.is_dir()
                || path
                    .symlink_metadata()
                    .map_err(|e| e.to_string())?
                    .file_type()
                    .is_symlink()
            {
                return Err("Unexpected runtime attempt path".into());
            }
            if inner.attempts.len() >= MAX_ATTEMPTS {
                return Err("Retained runtime attempt ceiling reached".into());
            }
            let receipt_path = if path.join("receipt.json").is_file() {
                path.join("receipt.json")
            } else {
                path.join("intent.json")
            };
            let mut receipt: Value =
                serde_json::from_slice(&read_bounded(&receipt_path, RECEIPT_LIMIT)?)
                    .map_err(|e| e.to_string())?;
            let request: StartRequest = serde_json::from_value(
                receipt
                    .get("request")
                    .cloned()
                    .ok_or("Retained request missing")?,
            )
            .map_err(|e| e.to_string())?;
            validate_request(&request)?;
            let identity = hash(&serde_json::to_vec(&request).map_err(|e| e.to_string())?);
            if path.file_name().and_then(|name| name.to_str())
                != Some(hash(request.request_id.as_bytes()).as_str())
                || receipt.get("requestHash").and_then(Value::as_str) != Some(identity.as_str())
                || inner.attempts.contains_key(&request.request_id)
            {
                return Err("Retained request identity mismatch".into());
            }
            if receipt.get("phase").and_then(Value::as_str) != Some("terminal")
                || receipt.get("descendantsStopped") != Some(&Value::Bool(true))
                || receipt.get("recordingError").is_some()
            {
                receipt["phase"] = json!("unknown");
                receipt["outcome"] = json!("unknown");
                inner.blocked = true;
            } else if let Err(error) = verify_terminal(&path, &receipt, &request) {
                receipt["phase"] = json!("unknown");
                receipt["outcome"] = json!("unknown");
                receipt["recordingError"] = json!(error);
                inner.blocked = true;
            }
            inner.attempts.insert(
                request.request_id.clone(),
                Arc::new(Attempt {
                    request,
                    identity,
                    directory: path,
                    receipt: Mutex::new(receipt),
                    cancel: AtomicBool::new(false),
                    done: (Mutex::new(true), Condvar::new()),
                }),
            );
        }
        inner.loaded = true;
        Ok(())
    }
    fn host(&self) -> Result<Option<(Host, String)>, String> {
        if !self.home.is_absolute() {
            return Err("SOV_RUNTIME_DIR must be absolute".into());
        }
        let path = self.home.join("providers.json");
        if !path.exists() {
            return Ok(None);
        }
        private(&path)?;
        let bytes = read_bounded(&path, CONFIG_LIMIT)?;
        let host: Host = serde_json::from_slice(&bytes).map_err(|_| "Invalid providers.json")?;
        if host.schema != "schematically.cli-host@1"
            || host.providers.len() > 1
            || host.grants.len() > 64
        {
            return Err("Invalid host registry bounds".into());
        }
        for provider in &host.providers {
            validate_provider(provider)?;
        }
        let mut ids = std::collections::HashSet::new();
        for grant in &host.grants {
            if !valid_id(&grant.id)
                || !ids.insert(&grant.id)
                || !valid_id(&grant.request_id)
                || !valid_id(&grant.document_id)
                || !valid_hash(&grant.source_hash)
            {
                return Err("Invalid host grant identity".into());
            }
        }
        Ok(Some((host, hash(&bytes))))
    }
    fn find(&self, request_id: &str, document_id: &str) -> Result<Arc<Attempt>, String> {
        let mut inner = self.inner.lock().map_err(|_| "Runtime state poisoned")?;
        self.load(&mut inner)?;
        let attempt = inner
            .attempts
            .get(request_id)
            .ok_or("Runtime request not found")?
            .clone();
        if attempt.request.document_id != document_id {
            return Err("Runtime document identity changed".into());
        }
        if let Err(error) = checked_visible(&attempt) {
            inner.blocked = true;
            return Err(error);
        }
        Ok(attempt)
    }
    pub fn stop(&self) -> Result<(), String> {
        self.stopping.store(true, Ordering::SeqCst);
        let attempts: Vec<_> = self
            .inner
            .lock()
            .map_err(|_| "Runtime state poisoned")?
            .attempts
            .values()
            .cloned()
            .collect();
        for attempt in &attempts {
            attempt.cancel.store(true, Ordering::SeqCst);
        }
        let until = Instant::now() + Duration::from_secs(5);
        for attempt in attempts {
            let (lock, wake) = &attempt.done;
            let done = lock.lock().map_err(|_| "Runtime completion poisoned")?;
            let (done, _) = wake
                .wait_timeout_while(
                    done,
                    until.saturating_duration_since(Instant::now()),
                    |done| !*done,
                )
                .map_err(|_| "Runtime completion poisoned")?;
            if !*done {
                return Err("Runtime shutdown completion unknown".into());
            }
            let receipt = attempt
                .receipt
                .lock()
                .map_err(|_| "Runtime receipt poisoned")?;
            if receipt.get("descendantsStopped") == Some(&Value::Bool(false))
                || receipt.get("recordingError").is_some()
            {
                return Err("Runtime shutdown cleanup/recording failed".into());
            }
        }
        Ok(())
    }
}
#[tauri::command]
pub fn desktop_runtime_providers(
    state: tauri::State<'_, Arc<RuntimeState>>,
) -> Result<Value, String> {
    let Some((host, _)) = state.host()? else {
        return Ok(json!({"providers":[]}));
    };
    Ok(
        json!({"providers":host.providers.into_iter().map(|p|json!({"id":p.id,"version":p.version,"language":p.language,"limits":p.limits,"authority":"trusted-user-code; no filesystem or network isolation"})).collect::<Vec<_>>()}),
    )
}
#[tauri::command]
pub fn desktop_runtime_status(
    state: tauri::State<'_, Arc<RuntimeState>>,
    request_id: String,
    document_id: String,
) -> Result<Value, String> {
    let attempt = state.find(&request_id, &document_id)?;
    let value = attempt
        .receipt
        .lock()
        .map_err(|_| "Runtime receipt poisoned")?
        .clone();
    Ok(value)
}
#[tauri::command]
pub fn desktop_runtime_cancel(
    state: tauri::State<'_, Arc<RuntimeState>>,
    request_id: String,
    document_id: String,
) -> Result<Value, String> {
    let attempt = state.find(&request_id, &document_id)?;
    attempt.cancel.store(true, Ordering::SeqCst);
    let mut value = attempt
        .receipt
        .lock()
        .map_err(|_| "Runtime receipt poisoned")?
        .clone();
    value["cancelRequested"] = json!(true);
    Ok(value)
}
#[tauri::command]
pub fn desktop_runtime_results(
    state: tauri::State<'_, Arc<RuntimeState>>,
    request_id: String,
    document_id: String,
) -> Result<Value, String> {
    let attempt = state.find(&request_id, &document_id)?;
    let value = attempt
        .receipt
        .lock()
        .map_err(|_| "Runtime receipt poisoned")?
        .clone();
    if value.get("phase").and_then(Value::as_str) != Some("terminal")
        || value.get("descendantsStopped") != Some(&Value::Bool(true))
        || value.get("recordingError").is_some()
    {
        return Err("Runtime has no verified terminal receipt".into());
    }
    Ok(value)
}
#[tauri::command]
pub fn desktop_runtime_start(
    state: tauri::State<'_, Arc<RuntimeState>>,
    request: StartRequest,
) -> Result<Value, String> {
    #[cfg(not(windows))]
    {
        let _ = (state, request);
        return Err("Node CLI is admitted only on Windows".into());
    }
    #[cfg(windows)]
    {
        validate_request(&request)?;
        let identity = hash(&serde_json::to_vec(&request).map_err(|e| e.to_string())?);
        let mut inner = state.inner.lock().map_err(|_| "Runtime state poisoned")?;
        state.load(&mut inner)?;
        if let Some(attempt) = inner.attempts.get(&request.request_id).cloned() {
            if attempt.identity != identity {
                return Err("Request replay identities differ".into());
            }
            if let Err(error) = checked_visible(&attempt) {
                inner.blocked = true;
                return Err(error);
            }
            return Ok(attempt
                .receipt
                .lock()
                .map_err(|_| "Runtime receipt poisoned")?
                .clone());
        }
        if state.stopping.load(Ordering::SeqCst) || inner.blocked || inner.active.is_some() {
            return Err("Runtime admission held by active/unknown/stopping job".into());
        }
        if inner.attempts.len() >= MAX_ATTEMPTS {
            return Err("Retained attempt limit reached".into());
        }
        let (host, host_hash) = state.host()?.ok_or("No host runtime registration")?;
        let provider = host
            .providers
            .iter()
            .find(|p| p.id == request.provider_id && p.version == request.provider_version)
            .ok_or("Runtime provider not registered")?
            .clone();
        let grant = host
            .grants
            .iter()
            .find(|g| g.id == request.grant_id)
            .ok_or("Execution grant not found")?
            .clone();
        if grant.provider_id != request.provider_id
            || grant.provider_version != request.provider_version
            || grant.document_id != request.document_id
            || grant.source_hash != request.source_hash
            || grant.request_id != request.request_id
            || grant.expires_at_unix_ms <= now_ms()
        {
            return Err("Execution grant expired or identities differ".into());
        }
        if executable_hash(&provider.executable)? != provider.executable_sha256 {
            return Err("Registered executable hash changed".into());
        }
        if inner.host_lock.is_none() {
            use std::os::windows::fs::OpenOptionsExt;
            let lock = OpenOptions::new()
                .create(true)
                .truncate(false)
                .read(true)
                .write(true)
                .share_mode(0)
                .open(state.home.join("host.lock"))
                .map_err(|_| "Runtime host already owned or unavailable")?;
            private(&state.home.join("host.lock"))?;
            inner.host_lock = Some(lock);
        }
        let consumed = state.home.join("consumed").join(hash(grant.id.as_bytes()));
        if consumed.exists() {
            return Err("Single-use execution grant consumed".into());
        }
        let directory_path = state
            .home
            .join("attempts")
            .join(hash(request.request_id.as_bytes()));
        if let Err(error) = fs::create_dir(&directory_path)
            .map_err(|e| e.to_string())
            .and_then(|_| private(&directory_path))
        {
            inner.blocked = true;
            return Err(error);
        }
        let receipt = json!({"schema":"schematically.cli-receipt@1","requestId":request.request_id,"documentId":request.document_id,"request":request,"requestHash":identity,"hostHash":host_hash,"provider":provider,"grantHash":hash(&serde_json::to_vec(&grant).map_err(|e|e.to_string())?),"phase":"intent","outcome":"intent","startedAtUnixMs":now_ms(),"descendantsStopped":false,"stdout":"","stderr":""});
        if let Err(error) = write_private(
            &directory_path.join("intent.json"),
            &serde_json::to_vec(&receipt).map_err(|e| e.to_string())?,
        ) {
            inner.blocked = true;
            return Err(error);
        }
        // Exclusive host lock serializes grant consumption; intent is durable first.
        if let Err(error) = write_private(
            &consumed,
            &serde_json::to_vec(&json!({"requestId":request.request_id,"requestHash":identity}))
                .map_err(|e| e.to_string())?,
        ) {
            inner.blocked = true;
            return Err(error);
        }
        let attempt = Arc::new(Attempt {
            request: request.clone(),
            identity,
            directory: directory_path,
            receipt: Mutex::new(receipt.clone()),
            cancel: AtomicBool::new(false),
            done: (Mutex::new(false), Condvar::new()),
        });
        inner.active = Some(request.request_id.clone());
        inner
            .attempts
            .insert(request.request_id.clone(), attempt.clone());
        drop(inner);
        let owner = state.inner().clone();
        let worker_attempt = attempt.clone();
        if let Err(problem) = std::thread::Builder::new()
            .name("schematically-cli".into())
            .spawn(move || complete(owner, worker_attempt, provider))
        {
            let mut value = receipt.clone();
            value["phase"] = json!("terminal");
            value["outcome"] = json!("refused");
            value["error"] = json!(problem.to_string());
            value["descendantsStopped"] = json!(true);
            value["finishedAtUnixMs"] = json!(now_ms());
            value["exitCode"] = Value::Null;
            let recorded = record_terminal(&attempt, value, &[], &[]);
            let mut inner = state.inner.lock().map_err(|_| "Runtime state poisoned")?;
            inner.active = None;
            inner.blocked = recorded.is_err();
            *attempt
                .done
                .0
                .lock()
                .map_err(|_| "Runtime completion poisoned")? = true;
            attempt.done.1.notify_all();
            recorded?;
            return Err("Runtime worker unavailable; grant consumed".into());
        }
        Ok(receipt)
    }
}
#[cfg(windows)]
fn complete(owner: Arc<RuntimeState>, attempt: Arc<Attempt>, provider: Provider) {
    let execution = windows::execute(&attempt, &provider, &owner.stopping);
    let mut value = attempt
        .receipt
        .lock()
        .unwrap_or_else(|e| e.into_inner())
        .clone();
    value["phase"] = json!("terminal");
    value["outcome"] = json!(execution.outcome);
    value["exitCode"] = json!(execution.exit_code);
    value["finishedAtUnixMs"] = json!(now_ms());
    value["descendantsStopped"] = json!(execution.stopped);
    if let Some(error) = execution.error {
        value["error"] = json!(error);
    }
    let recorded = record_terminal(&attempt, value, &execution.stdout, &execution.stderr);
    let mut inner = owner.inner.lock().unwrap_or_else(|e| e.into_inner());
    inner.active = None;
    inner.blocked |= !execution.stopped || recorded.is_err();
    drop(inner);
    *attempt.done.0.lock().unwrap_or_else(|e| e.into_inner()) = true;
    attempt.done.1.notify_all();
}

#[cfg(windows)]
mod windows {
    use super::*;
    use std::{ffi::c_void, os::windows::ffi::OsStrExt};
    use windows_sys::Win32::{
        Foundation::*,
        Security::SECURITY_ATTRIBUTES,
        Storage::FileSystem::*,
        System::{JobObjects::*, Pipes::*, Threading::*},
    };
    struct Handle(HANDLE);
    impl Drop for Handle {
        fn drop(&mut self) {
            if !self.0.is_null() && self.0 != INVALID_HANDLE_VALUE {
                unsafe {
                    CloseHandle(self.0);
                }
            }
        }
    }
    struct Attributes {
        storage: Vec<usize>,
        initialized: bool,
    }
    impl Attributes {
        fn pointer(&mut self) -> LPPROC_THREAD_ATTRIBUTE_LIST {
            self.storage.as_mut_ptr().cast()
        }
    }
    impl Drop for Attributes {
        fn drop(&mut self) {
            if self.initialized {
                unsafe {
                    DeleteProcThreadAttributeList(self.pointer());
                }
            }
        }
    }
    struct Child {
        job: Handle,
        process: Handle,
        thread: Handle,
        assigned: bool,
        pid: u32,
    }
    impl Drop for Child {
        fn drop(&mut self) {
            unsafe {
                if !self.process.0.is_null() {
                    if self.assigned {
                        TerminateJobObject(self.job.0, 125);
                    } else {
                        TerminateProcess(self.process.0, 125);
                    }
                    WaitForSingleObject(self.process.0, 3000);
                }
            }
        }
    }
    pub(super) struct Execution {
        pub outcome: &'static str,
        pub exit_code: Option<u32>,
        pub stdout: Vec<u8>,
        pub stderr: Vec<u8>,
        pub stopped: bool,
        pub error: Option<String>,
    }
    fn checked(ok: bool, operation: &str) -> Result<(), String> {
        if ok {
            Ok(())
        } else {
            Err(format!("{operation}: {}", std::io::Error::last_os_error()))
        }
    }
    fn wide(path: &std::ffi::OsStr) -> Vec<u16> {
        path.encode_wide().chain(Some(0)).collect()
    }
    fn quote(value: &str) -> String {
        let mut result = String::from("\"");
        let mut slashes = 0;
        for c in value.chars() {
            if c == '\\' {
                slashes += 1;
                continue;
            }
            if c == '"' {
                result.push_str(&"\\".repeat(slashes * 2 + 1));
                result.push(c);
            } else {
                result.push_str(&"\\".repeat(slashes));
                result.push(c);
            }
            slashes = 0;
        }
        result.push_str(&"\\".repeat(slashes * 2));
        result.push('"');
        result
    }
    unsafe fn pipe() -> Result<(Handle, Handle), String> {
        let mut read = std::ptr::null_mut();
        let mut write = std::ptr::null_mut();
        let security = SECURITY_ATTRIBUTES {
            nLength: std::mem::size_of::<SECURITY_ATTRIBUTES>() as u32,
            lpSecurityDescriptor: std::ptr::null_mut(),
            bInheritHandle: 1,
        };
        checked(
            CreatePipe(&mut read, &mut write, &security, 0) != 0,
            "CreatePipe",
        )?;
        let read = Handle(read);
        let write = Handle(write);
        checked(
            SetHandleInformation(read.0, HANDLE_FLAG_INHERIT, 0) != 0,
            "SetHandleInformation",
        )?;
        Ok((read, write))
    }
    unsafe fn drain(
        handle: &Handle,
        output: &mut Vec<u8>,
        total: &mut usize,
        limit: usize,
    ) -> Result<bool, String> {
        loop {
            let mut available = 0;
            let ok = PeekNamedPipe(
                handle.0,
                std::ptr::null_mut(),
                0,
                std::ptr::null_mut(),
                &mut available,
                std::ptr::null_mut(),
            );
            if ok == 0 {
                let error = std::io::Error::last_os_error();
                if error.raw_os_error() == Some(ERROR_BROKEN_PIPE as i32) {
                    return Ok(false);
                }
                return Err(error.to_string());
            }
            if available == 0 {
                return Ok(false);
            }
            if *total >= limit {
                return Ok(true);
            }
            let mut buffer = [0u8; 8192];
            let count = (available as usize).min(buffer.len()).min(limit - *total);
            let mut read = 0;
            checked(
                ReadFile(
                    handle.0,
                    buffer.as_mut_ptr(),
                    count as u32,
                    &mut read,
                    std::ptr::null_mut(),
                ) != 0,
                "ReadFile",
            )?;
            output.extend_from_slice(&buffer[..read as usize]);
            *total += read as usize;
        }
    }
    unsafe fn run(
        attempt: &Attempt,
        provider: &Provider,
        stopping: &AtomicBool,
    ) -> Result<Execution, String> {
        let deadline = Instant::now() + Duration::from_millis(provider.limits.timeout_ms);
        let module = attempt.directory.join(if provider.id == "python-cli" { "code.py" } else { "code.mjs" });
        let input = attempt.directory.join("input.json");
        write_private(&module, attempt.request.source.as_bytes())?;
        write_private(&input, attempt.request.input_json.as_bytes())?;
        // Keep the actual authored entry module immutable through its load/use.
        use std::os::windows::fs::OpenOptionsExt;
        let _source_lock = OpenOptions::new()
            .read(true)
            .share_mode(FILE_SHARE_READ)
            .open(&module)
            .map_err(|e| e.to_string())?;
        if hash(&read_bounded(&module, MAX_SOURCE as u64)?) != attempt.request.source_hash {
            return Err("Frozen entry module changed".into());
        }
        // Recheck immediately before CreateProcess; hold a no-write/no-delete executable
        // handle through launch so its admitted bytes cannot be replaced between checks.
        let executable_name = wide(provider.executable.as_os_str());
        let executable = Handle(CreateFileW(
            executable_name.as_ptr(),
            GENERIC_READ,
            FILE_SHARE_READ,
            std::ptr::null(),
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            std::ptr::null_mut(),
        ));
        checked(
            !executable.0.is_null() && executable.0 != INVALID_HANDLE_VALUE,
            "Open admitted executable",
        )?;
        if executable_hash(&provider.executable)? != provider.executable_sha256 {
            return Err("Executable changed before launch".into());
        }
        let job = Handle(CreateJobObjectW(std::ptr::null(), std::ptr::null()));
        checked(!job.0.is_null(), "CreateJobObjectW")?;
        let mut limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | JOB_OBJECT_LIMIT_JOB_MEMORY;
        limits.BasicLimitInformation.ActiveProcessLimit = provider.limits.max_processes;
        limits.JobMemoryLimit = provider.limits.max_memory_bytes;
        checked(
            SetInformationJobObject(
                job.0,
                JobObjectExtendedLimitInformation,
                (&limits as *const JOBOBJECT_EXTENDED_LIMIT_INFORMATION).cast(),
                std::mem::size_of_val(&limits) as u32,
            ) != 0,
            "SetInformationJobObject",
        )?;
        let (stdout_read, stdout_write) = pipe()?;
        let (stderr_read, stderr_write) = pipe()?;
        let security = SECURITY_ATTRIBUTES {
            nLength: std::mem::size_of::<SECURITY_ATTRIBUTES>() as u32,
            lpSecurityDescriptor: std::ptr::null_mut(),
            bInheritHandle: 1,
        };
        let input_name = wide(input.as_os_str());
        let stdin = Handle(CreateFileW(
            input_name.as_ptr(),
            GENERIC_READ,
            FILE_SHARE_READ,
            &security,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            std::ptr::null_mut(),
        ));
        checked(
            !stdin.0.is_null() && stdin.0 != INVALID_HANDLE_VALUE,
            "Open frozen stdin",
        )?;
        if hash(&read_bounded(&input, MAX_INPUT as u64)?) != attempt.request.input_hash {
            return Err("Frozen stdin changed".into());
        }
        let mut required = 0usize;
        InitializeProcThreadAttributeList(std::ptr::null_mut(), 1, 0, &mut required);
        checked(required > 0, "Attribute list size")?;
        let mut attrs = Attributes {
            storage: vec![
                0;
                (required + std::mem::size_of::<usize>() - 1)
                    / std::mem::size_of::<usize>()
            ],
            initialized: false,
        };
        checked(
            InitializeProcThreadAttributeList(attrs.pointer(), 1, 0, &mut required) != 0,
            "InitializeProcThreadAttributeList",
        )?;
        attrs.initialized = true;
        let handles = [stdin.0, stdout_write.0, stderr_write.0];
        checked(
            UpdateProcThreadAttribute(
                attrs.pointer(),
                0,
                PROC_THREAD_ATTRIBUTE_HANDLE_LIST as usize,
                handles.as_ptr().cast::<c_void>(),
                std::mem::size_of_val(&handles),
                std::ptr::null_mut(),
                std::ptr::null(),
            ) != 0,
            "UpdateProcThreadAttribute",
        )?;
        let mut startup = STARTUPINFOEXW::default();
        startup.StartupInfo.cb = std::mem::size_of::<STARTUPINFOEXW>() as u32;
        startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
        startup.StartupInfo.hStdInput = stdin.0;
        startup.StartupInfo.hStdOutput = stdout_write.0;
        startup.StartupInfo.hStdError = stderr_write.0;
        startup.lpAttributeList = attrs.pointer();
        let command = format!(
            "{} {} {}",
            quote(&provider.executable.to_string_lossy()),
            if provider.id == "python-cli" { "-I -u" } else { "--unhandled-rejections=strict" },
            quote(&module.to_string_lossy())
        );
        let mut command: Vec<u16> = command.encode_utf16().chain(Some(0)).collect();
        let cwd = wide(attempt.directory.as_os_str());
        let mut entries = vec![format!(
            "SOV_RUNTIME_REQUEST_ID={}",
            attempt.request.request_id
        )];
        for key in ["SystemRoot", "TEMP", "TMP"] {
            if let Some(value) = std::env::var_os(key) {
                entries.push(format!("{key}={}", value.to_string_lossy()));
            }
        }
        entries.sort_by_key(|value| value.to_ascii_uppercase());
        let environment: Vec<u16> = (entries.join("\0") + "\0\0").encode_utf16().collect();
        let mut info = PROCESS_INFORMATION::default();
        // Preflight is part of the provider deadline. Never create a process after
        // that allowance, even though the later suspended-resume gate also checks it.
        if Instant::now() >= deadline
            || attempt.cancel.load(Ordering::SeqCst)
            || stopping.load(Ordering::SeqCst)
        {
            return Ok(Execution {
                outcome: if Instant::now() >= deadline {
                    "timed-out"
                } else {
                    "cancelled"
                },
                exit_code: None,
                stdout: Vec::new(),
                stderr: Vec::new(),
                stopped: true,
                error: None,
            });
        }
        checked(
            CreateProcessW(
                executable_name.as_ptr(),
                command.as_mut_ptr(),
                std::ptr::null(),
                std::ptr::null(),
                1,
                CREATE_SUSPENDED
                    | CREATE_UNICODE_ENVIRONMENT
                    | EXTENDED_STARTUPINFO_PRESENT
                    | CREATE_NO_WINDOW,
                environment.as_ptr().cast(),
                cwd.as_ptr(),
                &startup.StartupInfo,
                &mut info,
            ) != 0,
            "CreateProcessW",
        )?;
        let mut child = Child {
            job,
            process: Handle(info.hProcess),
            thread: Handle(info.hThread),
            assigned: false,
            pid: info.dwProcessId,
        };
        checked(
            AssignProcessToJobObject(child.job.0, child.process.0) != 0,
            "AssignProcessToJobObject",
        )?;
        child.assigned = true;
        drop(stdout_write);
        drop(stderr_write);
        {
            let mut receipt = attempt
                .receipt
                .lock()
                .map_err(|_| "Runtime receipt poisoned")?;
            receipt["phase"] = json!("running");
            receipt["outcome"] = json!("running");
            receipt["pid"] = json!(child.pid);
            receipt["assignedBeforeResume"] = json!(true);
        }
        persist(attempt)?;
        let mut outcome = "failed";
        let mut exit_code = None;
        let mut stdout = Vec::new();
        let mut stderr = Vec::new();
        let mut total = 0;
        let mut error = None;
        if Instant::now() >= deadline {
            outcome = "timed-out";
        } else if attempt.cancel.load(Ordering::SeqCst) || stopping.load(Ordering::SeqCst) {
            outcome = "cancelled";
        } else {
            checked(ResumeThread(child.thread.0) != u32::MAX, "ResumeThread")?;
            loop {
                match drain(
                    &stdout_read,
                    &mut stdout,
                    &mut total,
                    provider.limits.max_output_bytes,
                )
                .and_then(|overflow| {
                    drain(
                        &stderr_read,
                        &mut stderr,
                        &mut total,
                        provider.limits.max_output_bytes,
                    )
                    .map(|second| overflow || second)
                }) {
                    Ok(true) => {
                        outcome = "output-overflow";
                        break;
                    }
                    Err(problem) => {
                        error = Some(problem);
                        break;
                    }
                    Ok(false) => {}
                }
                if attempt.cancel.load(Ordering::SeqCst) || stopping.load(Ordering::SeqCst) {
                    outcome = "cancelled";
                    break;
                }
                if Instant::now() >= deadline {
                    outcome = "timed-out";
                    break;
                }
                match WaitForSingleObject(child.process.0, 0) {
                    WAIT_OBJECT_0 => {
                        let mut code = 0;
                        checked(
                            GetExitCodeProcess(child.process.0, &mut code) != 0,
                            "GetExitCodeProcess",
                        )?;
                        exit_code = Some(code);
                        outcome = if code == 0 { "succeeded" } else { "failed" };
                        break;
                    }
                    WAIT_TIMEOUT => {}
                    _ => return Err("Process observation failed".into()),
                }
                std::thread::sleep(Duration::from_millis(5));
            }
        }
        checked(
            TerminateJobObject(child.job.0, 125) != 0,
            "TerminateJobObject",
        )?;
        let until = Instant::now() + Duration::from_secs(3);
        let mut stopped = false;
        while Instant::now() < until {
            let mut accounting = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION::default();
            checked(
                QueryInformationJobObject(
                    child.job.0,
                    JobObjectBasicAccountingInformation,
                    (&mut accounting as *mut JOBOBJECT_BASIC_ACCOUNTING_INFORMATION).cast(),
                    std::mem::size_of_val(&accounting) as u32,
                    std::ptr::null_mut(),
                ) != 0,
                "QueryInformationJobObject",
            )?;
            if accounting.ActiveProcesses == 0 {
                stopped = true;
                break;
            }
            std::thread::sleep(Duration::from_millis(5));
        }
        if drain(
            &stdout_read,
            &mut stdout,
            &mut total,
            provider.limits.max_output_bytes,
        )? || drain(
            &stderr_read,
            &mut stderr,
            &mut total,
            provider.limits.max_output_bytes,
        )? {
            outcome = "output-overflow";
        }
        if !stopped {
            error = Some("Descendant cleanup incomplete".into());
            outcome = "unknown";
        }
        Ok(Execution {
            outcome,
            exit_code,
            stdout,
            stderr,
            stopped,
            error,
        })
    }
    pub(super) fn execute(
        attempt: &Attempt,
        provider: &Provider,
        stopping: &AtomicBool,
    ) -> Execution {
        match unsafe { run(attempt, provider, stopping) } {
            Ok(result) => result,
            Err(error) => Execution {
                outcome: "unknown",
                exit_code: None,
                stdout: Vec::new(),
                stderr: Vec::new(),
                stopped: false,
                error: Some(error),
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn request() -> StartRequest {
        StartRequest {
            request_id: "request-1".into(),
            provider_id: "node-cli".into(),
            provider_version: "1".into(),
            grant_id: "grant-1".into(),
            document_id: "doc-1".into(),
            revision: 0,
            state_token: "state".into(),
            reference_id: "ref-1".into(),
            source: "console.log(1)".into(),
            source_hash: hash(b"console.log(1)"),
            input_json: "{}".into(),
            input_hash: hash(b"{}"),
        }
    }
    #[test]
    fn frozen_request_hashes_are_verified() {
        let mut value = request();
        assert!(validate_request(&value).is_ok());
        value.source.push(' ');
        assert!(validate_request(&value).is_err());
    }
    #[test]
    fn frozen_input_requires_json_and_exact_hash() {
        let mut value = request();
        value.input_json = "broken".into();
        value.input_hash = hash(value.input_json.as_bytes());
        assert!(validate_request(&value).is_err());
    }
    #[test]
    fn reference_ids_cannot_be_paths() {
        let mut value = request();
        value.reference_id = "../code".into();
        assert!(validate_request(&value).is_err());
    }
    #[test]
    fn exact_identity_changes_with_authority() {
        let value = request();
        let before = hash(&serde_json::to_vec(&value).unwrap());
        let mut changed = value;
        changed.grant_id = "another".into();
        assert_ne!(before, hash(&serde_json::to_vec(&changed).unwrap()));
    }
    #[test]
    fn atomic_receipt_preserves_old_on_missing_parent() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("old");
        write_private(&path, b"old").unwrap();
        assert!(write_private(&dir.path().join("missing/new"), b"new").is_err());
        assert_eq!(fs::read(path).unwrap(), b"old");
    }
    #[test]
    fn bounded_host_read_refuses_oversize() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config");
        fs::write(&path, b"12345").unwrap();
        assert!(read_bounded(&path, 4).is_err());
        assert_eq!(read_bounded(&path, 5).unwrap(), b"12345");
    }
}
