#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::fs;

#[derive(Serialize)]
struct OpenedDocument {
    name: String,
    text: String,
}

fn requested_file_path() -> Option<String> {
    std::env::args()
        .skip(1)
        .find(|arg| !arg.starts_with('-'))
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

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![opened_document])
        .run(tauri::generate_context!())
        .expect("error while running SOV Schematic desktop shell");
}
