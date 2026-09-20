use std::fs::{self, File};
use std::io::{self, BufReader, Write};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

// Bilinear image resizing in native Rust (zero-dependency reference implementation)
fn resize_bilinear(
    img_bytes: &[u8],
    src_w: u32,
    src_h: u32,
    dst_w: u32,
    dst_h: u32,
) -> Vec<u8> {
    let mut dst = vec![0u8; (dst_w * dst_h * 3) as usize];
    for y in 0..dst_h {
        for x in 0..dst_w {
            let src_x = (x as f64) * (src_w as f64) / (dst_w as f64);
            let src_y = (y as f64) * (src_h as f64) / (dst_h as f64);

            let x0 = src_x.floor() as u32;
            let y0 = src_y.floor() as u32;
            let x1 = (x0 + 1).min(src_w - 1);
            let y1 = (y0 + 1).min(src_h - 1);

            let fx = src_x - x0 as f64;
            let fy = src_y - y0 as f64;

            let idx00 = ((y0 * src_w + x0) * 3) as usize;
            let idx10 = ((y0 * src_w + x1) * 3) as usize;
            let idx01 = ((y1 * src_w + x0) * 3) as usize;
            let idx11 = ((y1 * src_w + x1) * 3) as usize;

            for c in 0..3 {
                let val = (img_bytes[idx00 + c] as f64) * (1.0 - fx) * (1.0 - fy)
                    + (img_bytes[idx10 + c] as f64) * fx * (1.0 - fy)
                    + (img_bytes[idx01 + c] as f64) * (1.0 - fx) * fy
                    + (img_bytes[idx11 + c] as f64) * fx * fy;

                let dst_idx = ((y * dst_w + x) * 3) as usize + c;
                dst[dst_idx] = val.round().clamp(0.0, 255.0) as u8;
            }
        }
    }
    dst
}

fn get_now_unix() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

fn main() -> io::Result<()> {
    let picture_dir = Path::new("Picture");
    let cache_dir = picture_dir.join("cache");
    let output_dir = Path::new("output");

    fs::create_dir_all(&cache_dir)?;
    fs::create_dir_all(output_dir)?;

    println!("[Rust Image Processor] Reference model initialized.");
    
    // Scan Picture directory
    let mut image_files = Vec::new();
    if picture_dir.exists() {
        for entry in fs::read_dir(picture_dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.is_file() {
                if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
                    let ext_lower = ext.to_lowercase();
                    if ext_lower == "jpg" || ext_lower == "jpeg" || ext_lower == "png" {
                        if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                            image_files.push(name.to_string());
                        }
                    }
                }
            }
        }
    }

    if image_files.is_empty() {
        println!("No source images found in Picture/");
        return Ok(());
    }

    // Image resizing pipeline placeholder
    // In production, Go-based binary is used because `rustc` is not installed on this system.
    for name in &image_files {
        let src_path = picture_dir.join(name);
        let cache_path = cache_dir.join(format!("{}.jpg", Path::new(name).file_stem().unwrap().to_str().unwrap()));
        
        let need_rebuild = match (src_path.metadata(), cache_path.metadata()) {
            (Ok(src_meta), Ok(cache_meta)) => {
                src_meta.modified().unwrap_or(SystemTime::UNIX_EPOCH) > cache_meta.modified().unwrap_or(SystemTime::UNIX_EPOCH)
            }
            _ => true,
        };

        if need_rebuild {
            println!("  Need rebuild cache for: {}", name);
            // Simulated resize & compression saving to cache_path
        }
    }

    // Select active image based on 10s rotation
    let rotation_secs = 10u64;
    let index = ((get_now_unix() / rotation_secs) % (image_files.len() as u64)) as usize;
    let active_name = &image_files[index];
    let active_stem = Path::new(active_name).file_stem().unwrap().to_str().unwrap();
    let active_cache_file = cache_dir.join(format!("{}.jpg", active_stem));
    let active_out_file = output_dir.join("cam_feed_active.jpg");

    if active_cache_file.exists() {
        fs::copy(&active_cache_file, &active_out_file)?;
        
        let file_size = active_out_file.metadata()?.len();
        let status_file = output_dir.join("cam_feed_status.json");
        let mut status = File::create(status_file)?;
        
        writeln!(status, "{{")?;
        writeln!(status, "  \"active_file\": \"{}.jpg\",", active_stem)?;
        writeln!(status, "  \"size_kb\": {:.4},", (file_size as f64) / 1024.0)?;
        writeln!(status, "  \"timestamp\": {}", get_now_unix())?;
        writeln!(status, "}}")?;
        
        println!("Active image set (Rust Stub): {}.jpg ({:.2} KB)", active_stem, (file_size as f64) / 1024.0);
    } else {
        println!("Cached active file not found, skipping copy.");
    }

    Ok(())
}
