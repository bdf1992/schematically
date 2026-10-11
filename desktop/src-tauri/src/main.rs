#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::fs;
use std::path::PathBuf;
use std::time::Duration;
use tauri::Manager;

mod files;
mod mcp;
mod runtime;

const SMOKE_REPORT_FLAG: &str = "--smoke-report";
// A smoke run that hears nothing from the page by then exits with SMOKE_SILENT_EXIT_CODE.
const SMOKE_SILENCE_LIMIT: Duration = Duration::from_secs(30);
const SMOKE_SILENT_EXIT_CODE: i32 = 2;

struct ObservedAssets {
    inner: std::sync::Arc<std::sync::OnceLock<Box<dyn tauri::Assets<tauri::Wry>>>>,
    calls: std::sync::atomic::AtomicUsize,
}

impl ObservedAssets {
    fn provider(&self) -> &dyn tauri::Assets<tauri::Wry> {
        self.inner.get().expect("Asset provider initialized before build").as_ref()
    }
}

impl tauri::Assets<tauri::Wry> for ObservedAssets {
    fn setup(&self, app: &tauri::App<tauri::Wry>) {
        self.provider().setup(app);
    }

    fn get(&self, key: &tauri::utils::assets::AssetKey) -> Option<std::borrow::Cow<'_, [u8]>> {
        let started = std::time::Instant::now();
        let content = self.provider().get(key);
        let elapsed = started.elapsed();
        let label = match key.as_ref() {
            "" | "/" => Some("root"),
            "index.html" | "/index.html" => Some("index"),
            _ => None,
        };
        if let Some(label) = label {
            let call = self.calls.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            if call < 8 {
                eprintln!("desktop asset: label={label} call={} elapsed-ms={} decoded-bytes={} present={}",
                    call + 1, elapsed.as_millis(), content.as_ref().map_or(0, |bytes| bytes.len()), content.is_some());
            }
        }
        content
    }

    fn iter(&self) -> Box<tauri::utils::assets::AssetsIter<'_>> {
        self.provider().iter()
    }

    fn csp_hashes(&self, html_path: &tauri::utils::assets::AssetKey)
        -> Box<dyn Iterator<Item = tauri::utils::assets::CspHash<'_>> + '_>
    {
        self.provider().csp_hashes(html_path)
    }
}

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
/// Requests event-loop exit after retaining the report, allowing normal main/CRT cleanup.
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
    app.exit(if ok && written.is_ok() { 0 } else { 1 });
}

fn main() -> std::process::ExitCode {
    let builder = tauri::Builder::default().manage(files::FileState::default())
        .setup(|app| {
            let setup_started = std::time::Instant::now();
            eprintln!("desktop startup: setup pid={}", std::process::id());
            let configured = &app.config().app.windows;
            if configured.len() != 1 || configured[0].create || configured[0].label != "main" {
                return Err(std::io::Error::other("Desktop requires one explicitly created main window").into());
            }
            let window_config = configured[0].clone();
            let relay = mcp::start(app.handle()).map_err(std::io::Error::other)?;
            if !app.manage(relay.clone()) {
                relay.stop();
                return Err(std::io::Error::other("Desktop relay state was already registered").into());
            }
            eprintln!("desktop startup: relay-registered pid={}", std::process::id());
            let runtime = match runtime::RuntimeState::new(app.handle()) {
                Ok(runtime) => runtime,
                Err(problem) => { relay.stop(); return Err(std::io::Error::other(problem).into()); }
            };
            if !app.manage(runtime) {
                relay.stop();
                return Err(std::io::Error::other("Desktop runtime state already registered").into());
            }
            // Navigation cannot begin before commands can resolve the relay state.
            let response_calls = std::sync::atomic::AtomicUsize::new(0);
            let page_calls = std::sync::atomic::AtomicUsize::new(0);
            let window = tauri::WebviewWindowBuilder::from_config(app.handle(), &window_config)
                .and_then(|builder| builder
                    .on_web_resource_request(move |request, response| {
                        let label = match request.uri().path() {
                            "/" => Some("root"),
                            "/index.html" | "index.html" => Some("index"),
                            _ => None,
                        };
                        if let Some(label) = label {
                            let call = response_calls.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                            if call < 8 {
                                eprintln!("desktop response: label={label} call={} status={} body-bytes={} setup-elapsed-ms={}",
                                    call + 1, response.status().as_u16(), response.body().len(), setup_started.elapsed().as_millis());
                            }
                        }
                    })
                    .on_page_load(move |_window, payload| {
                        let call = page_calls.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                        if call < 8 {
                            let label = if payload.url().scheme() == "about" && payload.url().path() == "blank" {
                                "aboutblank"
                            } else if matches!(payload.url().path(), "/" | "/index.html" | "index.html") {
                                "root"
                            } else { "other" };
                            let event = match payload.event() {
                                tauri::webview::PageLoadEvent::Started => "started",
                                tauri::webview::PageLoadEvent::Finished => "finished",
                            };
                            eprintln!("desktop page: label={label} event={event} call={} setup-elapsed-ms={}",
                                call + 1, setup_started.elapsed().as_millis());
                        }
                    })
                    .build());
            if let Err(problem) = window {
                relay.stop();
                eprintln!("desktop startup: window-create-failed pid={}", std::process::id());
                return Err(problem.into());
            }
            eprintln!("desktop startup: window-created pid={}", std::process::id());
            if smoke_report_path().is_some() {
                let watchdog_relay=relay.clone();
                std::thread::spawn(move || {
                    std::thread::sleep(SMOKE_SILENCE_LIMIT);
                    eprintln!("smoke run: the page reported nothing within {SMOKE_SILENCE_LIMIT:?}");
                    watchdog_relay.stop();
                    std::process::exit(SMOKE_SILENT_EXIT_CODE);
                });
            }
            Ok(())
        });
    let builder = match smoke_report_path() {
        Some(path) => {
            builder
                .manage(SmokeReport(path))
                .invoke_handler(tauri::generate_handler![opened_document, report_loaded,
                    files::desktop_open_document, files::desktop_save_document, files::desktop_reset_document,
                    mcp::desktop_mcp_ready, mcp::desktop_mcp_info, mcp::desktop_mcp_begin, mcp::desktop_mcp_respond,
                    runtime::desktop_runtime_providers, runtime::desktop_runtime_start, runtime::desktop_runtime_status, runtime::desktop_runtime_cancel, runtime::desktop_runtime_results])
        }
        None => builder.invoke_handler(tauri::generate_handler![opened_document,
            files::desktop_open_document, files::desktop_save_document, files::desktop_reset_document,
            mcp::desktop_mcp_ready, mcp::desktop_mcp_info, mcp::desktop_mcp_begin, mcp::desktop_mcp_respond,
            runtime::desktop_runtime_providers, runtime::desktop_runtime_start, runtime::desktop_runtime_status, runtime::desktop_runtime_cancel, runtime::desktop_runtime_results]),
    };
    let requested_code = std::rc::Rc::new(std::cell::Cell::new(None));
    let captured_code = requested_code.clone();
    let mut context = tauri::generate_context!();
    let assets = std::sync::Arc::new(std::sync::OnceLock::new());
    let previous = context.set_assets(Box::new(ObservedAssets {
        inner: assets.clone(),
        calls: std::sync::atomic::AtomicUsize::new(0),
    }));
    assert!(assets.set(previous).is_ok(), "Asset provider registered once");
    let runtime_code = builder
        .build(context)
        .expect("error while building SOV Schematic desktop shell")
        .run_return(move |app, event| {
            // Wry emits the requested code but currently exits its loop with zero.
            // Retain explicit requests; ordinary last-window close has no code.
            if let tauri::RunEvent::ExitRequested { code: Some(code), .. } = &event {
                captured_code.set(Some(*code));
            }
            if matches!(event, tauri::RunEvent::Exit) {
                if let Some(runtime) = app.try_state::<std::sync::Arc<runtime::RuntimeState>>() {
                    if let Err(problem) = runtime.stop() {
                        eprintln!("desktop runtime shutdown failed: {problem}");
                        captured_code.set(Some(1));
                    }
                }
                if let Some(relay) = app.try_state::<std::sync::Arc<mcp::RelayState>>() { relay.stop(); }
            }
        });
    let code = requested_code.get().unwrap_or(runtime_code);
    match u8::try_from(code) {
        Ok(code) => std::process::ExitCode::from(code),
        Err(_) => {
            eprintln!("desktop exit: unsupported event-loop code {code}");
            std::process::ExitCode::FAILURE
        }
    }
}
