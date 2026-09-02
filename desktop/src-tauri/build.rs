fn ensure_windows_icon() {
    let path = std::path::Path::new("icons/icon.ico");
    if path.exists() {
        return;
    }
    if let Some(dir) = path.parent() {
        let _ = std::fs::create_dir_all(dir);
    }
    // A minimal 16x16 32bpp placeholder icon: tauri-build requires icons/icon.ico to exist
    // to embed a Windows executable resource, independent of the bundler's icon list.
    const W: u32 = 16;
    const H: u32 = 16;
    let xor_size = (W * H * 4) as usize;
    let and_row = (((W + 31) / 32) * 4) as usize;
    let and_size = and_row * H as usize;
    let image_size = 40 + xor_size + and_size;

    let mut bytes: Vec<u8> = Vec::with_capacity(6 + 16 + image_size);
    bytes.extend_from_slice(&[0, 0, 1, 0, 1, 0]); // ICONDIR
    bytes.push(W as u8);
    bytes.push(H as u8);
    bytes.extend_from_slice(&[0, 0, 1, 0, 32, 0]); // colors, reserved, planes, bitcount
    bytes.extend_from_slice(&(image_size as u32).to_le_bytes());
    bytes.extend_from_slice(&22u32.to_le_bytes()); // offset: 6 + 16

    bytes.extend_from_slice(&40u32.to_le_bytes()); // biSize
    bytes.extend_from_slice(&(W as i32).to_le_bytes());
    bytes.extend_from_slice(&((H * 2) as i32).to_le_bytes());
    bytes.extend_from_slice(&1u16.to_le_bytes()); // biPlanes
    bytes.extend_from_slice(&32u16.to_le_bytes()); // biBitCount
    bytes.extend_from_slice(&0u32.to_le_bytes()); // biCompression
    bytes.extend_from_slice(&((xor_size + and_size) as u32).to_le_bytes());
    bytes.extend_from_slice(&[0u8; 16]); // xPels, yPels, clrUsed, clrImportant

    for _ in 0..(W * H) {
        bytes.extend_from_slice(&[40, 40, 60, 255]); // BGRA
    }
    bytes.extend(std::iter::repeat(0u8).take(and_size));

    let _ = std::fs::write(path, bytes);
}

fn main() {
    ensure_windows_icon();
    tauri_build::build();
}
