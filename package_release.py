#!/usr/bin/env python3
"""
InfoSphere Release Packager
Creates a clean, production-ready distribution ZIP archive for GitHub Releases.
"""

import os
import sys
import zipfile
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))

def get_version():
    ver_file = os.path.join(ROOT, "VERSION")
    if os.path.exists(ver_file):
        with open(ver_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "2.3.0"

def create_release_zip():
    version = get_version()
    dist_dir = os.path.join(ROOT, "dist")
    os.makedirs(dist_dir, exist_ok=True)
    
    zip_name = f"InfoSphere-v{version}-Windows.zip"
    zip_path = os.path.join(dist_dir, zip_name)
    
    print(f"[*] Packaging InfoSphere v{version} for Windows...")
    print(f"[*] Output archive: {zip_path}")
    
    # Files and folders to exclude
    exclude_dirs = {
        ".git", ".github", ".vscode", ".idea", "__pycache__", 
        "node_modules", ".next", "dist", "scratch", "caveman", 
        ".agents", ".continue", ".kilocode", "tests"
    }
    exclude_exts = {".pyc", ".pyo", ".pdb", ".tmp", ".log", ".bak"}
    exclude_files = {"test_zip.zip", "scratch"}

    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(ROOT):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
            
            # Preserve empty directory placeholders if needed
            rel_root = os.path.relpath(root, ROOT)
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in exclude_exts or file in exclude_files:
                    continue
                # Skip actual .env file, keep .env.example
                if file == ".env":
                    continue
                # Skip personal pictures, keep .gitkeep
                if "Picture" in rel_root and "Original Picture" in rel_root and file != ".gitkeep":
                    continue
                if "Picture" in rel_root and "cache" in rel_root and file != ".gitkeep":
                    continue
                
                abs_path = os.path.join(root, file)
                archive_path = os.path.join(f"InfoSphere-v{version}", rel_root, file) if rel_root != "." else os.path.join(f"InfoSphere-v{version}", file)
                archive_path = archive_path.replace(os.sep, "/")
                
                zf.write(abs_path, archive_path)
                file_count += 1

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"[SUCCESS] Packaged {file_count} files into {zip_name} ({size_mb:.2f} MB)")
    return zip_path

if __name__ == "__main__":
    create_release_zip()
