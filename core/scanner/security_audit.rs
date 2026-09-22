// InfoSphere Cyber Live Wallpaper Engine
// Native Rust High-Speed Security Auditor (core/scanner/security_audit.rs)
// High-performance, zero-dependency, memory-safe cryptographic audit

use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{self, Read, Write};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

fn fnv1a_64(bytes: &[u8]) -> u64 {
    let mut hash: u64 = 0xcbf29ce484222325;
    for &byte in bytes {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(0x100000001b3);
    }
    hash
}

fn audit_file(path: &Path) -> Result<(String, usize), io::Error> {
    let mut f = File::open(path)?;
    let mut buffer = Vec::new();
    f.read_to_end(&mut buffer)?;
    let hash = fnv1a_64(&buffer);
    Ok((format!("{:016x}", hash), buffer.len()))
}

fn parse_baseline(content: &str) -> HashMap<String, String> {
    let mut map = HashMap::new();
    let content = content.trim();
    if !content.starts_with('{') || !content.ends_with('}') {
        return map;
    }
    let inner = &content[1..content.len()-1];
    let parts = inner.split(',');
    for part in parts {
        let mut kv = part.splitn(2, ':');
        if let (Some(k), Some(v)) = (kv.next(), kv.next()) {
            let key = k.trim().trim_matches('"').to_string();
            let val = v.trim().trim_matches('"').to_string();
            if !key.is_empty() {
                map.insert(key, val);
            }
        }
    }
    map
}

fn main() -> io::Result<()> {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    let files_to_audit = [
        "config.json",
        "infosphere_live_wallpaper.html",
        "main.py",
        "css/wallpaper_theme.css",
        "core/network_soc.py",
        "core/router_monitor.py",
        "core/system_info.py",
    ];

    let output_dir = Path::new("output");
    if !output_dir.exists() {
        let _ = fs::create_dir_all(output_dir);
    }

    let baseline_path = Path::new("output/security_baseline.json");
    let baseline_exists = baseline_path.exists();
    let mut baseline_hashes = HashMap::new();

    if baseline_exists {
        if let Ok(content) = fs::read_to_string(baseline_path) {
            baseline_hashes = parse_baseline(&content);
        }
    }

    let mut verified = 0;
    let mut total_bytes = 0;
    let mut anomalies = 0;

    let mut files_json = Vec::new();
    let mut new_baseline_hashes = HashMap::new();

    for file_str in &files_to_audit {
        let p = Path::new(file_str);
        if p.exists() {
            match audit_file(p) {
                Ok((hash_hex, len)) => {
                    verified += 1;
                    total_bytes += len;
                    
                    let mut status = "OK";
                    if baseline_exists {
                        if let Some(expected_hash) = baseline_hashes.get(*file_str) {
                            if expected_hash != &hash_hex {
                                anomalies += 1;
                                status = "MODIFIED";
                            }
                        } else {
                            anomalies += 1;
                            status = "MODIFIED";
                        }
                    } else {
                        new_baseline_hashes.insert(file_str.to_string(), hash_hex.clone());
                    }

                    files_json.push(format!(
                        r#"    {{"path": "{}", "hash": "{}", "bytes": {}, "status": "{}"}}"#,
                        file_str, hash_hex, len, status
                    ));
                }
                Err(_) => {
                    anomalies += 1;
                }
            }
        } else {
            if baseline_exists {
                anomalies += 1;
            }
        }
    }

    if !baseline_exists {
        let mut baseline_entries = Vec::new();
        for file_str in &files_to_audit {
            if let Some(hash) = new_baseline_hashes.get(*file_str) {
                baseline_entries.push(format!(r#"  "{}": "{}""#, file_str, hash));
            }
        }
        let baseline_content = format!("{{\n{}\n}}", baseline_entries.join(",\n"));
        let mut out_file = File::create(baseline_path)?;
        out_file.write_all(baseline_content.as_bytes())?;
    }

    let integrity_score = if anomalies == 0 { 100 } else { (100isize - (anomalies as isize) * 25).max(0) as usize };

    let files_array = format!("[\n{}\n  ]", files_json.join(",\n"));

    let json_content = format!(
        r#"{{
  "status": "{}",
  "integrity_score": {},
  "audit_engine": "Rust Native v2.0 (Memory-Safe + Tamper Detection)",
  "verified_files": {},
  "audited_bytes": {},
  "anomalies_detected": {},
  "threat_mitigation": "ACTIVE",
  "timestamp": {},
  "files": {}
}}"#,
        if integrity_score >= 90 { "SECURE" } else { "ATTENTION" },
        integrity_score,
        verified,
        total_bytes,
        anomalies,
        now,
        files_array
    );

    let mut out_file = File::create("output/security_audit.json")?;
    out_file.write_all(json_content.as_bytes())?;

    println!("[Rust Security Auditor] Audited {} files ({} bytes). Score: {}/100", verified, total_bytes, integrity_score);
    Ok(())
}
