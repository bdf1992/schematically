#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::fs;
use std::path::PathBuf;
use std::time::Duration;

const SMOKE_REPORT_FLAG: &str = "--smoke-report";
// A smoke run that hears nothing from the page by then exits with SMOKE_SILENT_EXIT_CODE.
const SMOKE_SILENCE_LIMIT: Duration = Duration::from_secs(30);
const SMOKE_SILENT_EXIT_CODE: i32 = 2;

#[derive(Serialize)]
struct OpenedDocument {
    name: String,
    text: String,
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
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        if arg == SMOKE_REPORT_FLAG {
            args.next();
            continue;
        }
        if !arg.starts_with('-') {
            return Some(arg);
        }
    }
    None
}

fn smoke_report_path() -> Option<PathBuf> {
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        if arg == SMOKE_REPORT_FLAG {
            return args.next().map(PathBuf::from);
        }
    }
    None
}

#[tauri::command]
fn opened_document() -> Option<OpenedDocument> {
    let path = requested_file_path()?;
    let text = fs::read_to_string(&path).ok()?;
    let name = std::path::Path::new(&path)
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or(path);
    Some(OpenedDocument { name, text })
}

/// Registered only in a smoke run. Writes what the page loaded to the report path and ends the
/// process: 0 when the document loaded, 1 when it did not or the report could not be written.
/// `std::process::exit` rather than `AppHandle::exit`, so the exit code a CI job reads does not
/// depend on how the event loop forwards it.
#[tauri::command]
fn report_loaded(
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
    std::process::exit(if ok && written.is_ok() { 0 } else { 1 });
}

fn main() {
    let builder = tauri::Builder::default();
    let builder = match smoke_report_path() {
        Some(path) => {
            std::thread::spawn(|| {
                std::thread::sleep(SMOKE_SILENCE_LIMIT);
                eprintln!("smoke run: the page reported nothing within {SMOKE_SILENCE_LIMIT:?}");
                std::process::exit(SMOKE_SILENT_EXIT_CODE);
            });
            builder
                .manage(SmokeReport(path))
                .invoke_handler(tauri::generate_handler![opened_document, report_loaded])
        }
        None => builder.invoke_handler(tauri::generate_handler![opened_document]),
    };
    builder
        .run(tauri::generate_context!())
        .expect("error while running SOV Schematic desktop shell");
}
