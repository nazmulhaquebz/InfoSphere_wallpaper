"""
InfoSphere 1-Click Automated In-App Updater
Downloads, extracts, stages, and safely applies GitHub Releases in-place
while strictly preserving user data (photos, operator profile, credentials).
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from typing import Dict, Any, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_FILE = os.path.join(ROOT, "output", "update_status.json")
CACHE_DIR = os.path.join(ROOT, "output", "update_cache")
STAGING_DIR = os.path.join(ROOT, "output", "update_staging")

_GITHUB_REPO = "nazmulhaquebz/InfoSphere_wallpaper"
_RELEASES_API = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"

# Critical files that must NEVER be overwritten during an automated update
PROTECTED_FILES = [
    "user_information.txt",
    ".env",
    ".env.local",
]
PROTECTED_DIRS = [
    os.path.join("Picture", "Original Picture"),
    os.path.join("Picture", "cache"),
    "logs",
]


def write_status(
    status: str,
    pct: int = 0,
    message: str = "",
    speed_mb: float = 0.0,
    downloaded_mb: float = 0.0,
    total_mb: float = 0.0,
    version: str = "",
    error: Optional[str] = None
) -> None:
    """Atomically write update status for HUD and frontend consumers."""
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    payload = {
        "status": status,
        "pct": max(0, min(100, int(pct))),
        "message": message,
        "speed_mb": round(speed_mb, 2),
        "downloaded_mb": round(downloaded_mb, 2),
        "total_mb": round(total_mb, 2),
        "version": version,
        "error": error,
        "timestamp": int(time.time()),
    }
    tmp_path = f"{STATUS_FILE}.{os.getpid()}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, STATUS_FILE)
    except Exception as e:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


def get_latest_release() -> Dict[str, Any]:
    """Fetch metadata for the latest published GitHub release."""
    req = urllib.request.Request(
        _RELEASES_API,
        headers={
            "User-Agent": "InfoSphere-Updater/2.3",
            "Accept": "application/vnd.github+json"
        }
    )
    with urllib.request.urlopen(req, timeout=8.0) as resp:
        if resp.status != 200:
            raise RuntimeError(f"GitHub API returned HTTP {resp.status}")
        data = json.loads(resp.read().decode("utf-8"))

    tag_name = data.get("tag_name", "")
    zip_url = None

    # Priority 1: Check attached release assets for .zip
    for asset in data.get("assets", []):
        name = asset.get("name", "").lower()
        if name.endswith(".zip"):
            zip_url = asset.get("browser_download_url")
            break

    # Priority 2: Fall back to GitHub automatic tag zipball
    if not zip_url:
        zip_url = data.get("zipball_url") or f"https://github.com/{_GITHUB_REPO}/archive/refs/tags/{tag_name}.zip"

    return {
        "version": tag_name,
        "name": data.get("name", tag_name),
        "body": data.get("body", ""),
        "download_url": zip_url,
        "published_at": data.get("published_at", ""),
    }


def download_file(url: str, dest_path: str, version: str) -> None:
    """Download update archive with streaming chunks and live progress calculation."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "InfoSphere-Updater/2.3"}
    )

    with urllib.request.urlopen(req, timeout=20.0) as resp:
        total_size = int(resp.headers.get("content-length", 0) or 0)
        total_mb = total_size / (1024 * 1024) if total_size > 0 else 0.0

        downloaded = 0
        chunk_size = 64 * 1024  # 64 KB chunks
        start_time = time.time()
        last_update = 0.0

        with open(dest_path, "wb") as out_file:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)

                now = time.time()
                if now - last_update >= 0.15 or downloaded == total_size:
                    elapsed = max(0.001, now - start_time)
                    speed_mb = (downloaded / (1024 * 1024)) / elapsed
                    downloaded_mb = downloaded / (1024 * 1024)
                    pct = int((downloaded / total_size) * 80) if total_size > 0 else 50
                    write_status(
                        status="DOWNLOADING",
                        pct=pct,
                        message=f"Downloading {downloaded_mb:.1f} MB / {total_mb:.1f} MB ({pct}%)",
                        speed_mb=speed_mb,
                        downloaded_mb=downloaded_mb,
                        total_mb=total_mb,
                        version=version
                    )
                    last_update = now


def extract_and_stage(zip_path: str, staging_dir: str, version: str) -> str:
    """Extract zip archive and flatten if single top-level directory."""
    write_status(status="EXTRACTING", pct=85, message="Verifying archive integrity...", version=version)
    
    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir, ignore_errors=True)
    os.makedirs(staging_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        bad_file = zf.testzip()
        if bad_file:
            raise RuntimeError(f"Corrupt file in archive: {bad_file}")
        zf.extractall(staging_dir)

    # Check if archive has an outer wrapper directory (e.g., InfoSphere-v2.3.0/ or InfoSphere_wallpaper-main/)
    entries = [e for e in os.listdir(staging_dir) if not e.startswith(".")]
    resolved_root = staging_dir
    if len(entries) == 1:
        single_path = os.path.join(staging_dir, entries[0])
        if os.path.isdir(single_path):
            resolved_root = single_path

    # Verify that the extracted staging area actually contains essential engine files
    required_files = ["main.py", "infosphere_live_wallpaper.html"]
    for req in required_files:
        if not os.path.exists(os.path.join(resolved_root, req)):
            raise RuntimeError(f"Archive missing required core file: {req}")

    # Remove any protected files from the staging area so they cannot accidentally overwrite user files
    for pf in PROTECTED_FILES:
        target_pf = os.path.join(resolved_root, pf)
        if os.path.exists(target_pf):
            try:
                os.remove(target_pf)
            except OSError:
                pass

    for pd in PROTECTED_DIRS:
        target_pd = os.path.join(resolved_root, pd)
        if os.path.exists(target_pd):
            try:
                shutil.rmtree(target_pd, ignore_errors=True)
            except OSError:
                pass

    write_status(status="EXTRACTED", pct=95, message="Update validated. Preparing restart...", version=version)
    return resolved_root


def launch_apply_script(staging_root: str, dry_run: bool = False) -> None:
    """Trigger the detached update applicator script."""
    if dry_run:
        write_status(status="COMPLETED", pct=100, message="Dry-run completed successfully.")
        return

    write_status(status="RESTARTING", pct=100, message="Restarting InfoSphere Live Engine...")
    
    bat_path = os.path.join(ROOT, "core", "apply_update.bat")
    if not os.path.exists(bat_path):
        raise FileNotFoundError(f"Apply script not found at {bat_path}")

    # Launch detached batch process so current python process can exit cleanly
    cmd = [bat_path, ROOT, staging_root]
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    subprocess.Popen(
        cmd,
        cwd=ROOT,
        creationflags=flags,
        close_fds=True
    )


def run_update_pipeline(dry_run: bool = False, logger: Optional[logging.Logger] = None) -> bool:
    """Execute the full download, verify, stage, and apply pipeline."""
    log = logger or logging.getLogger("InfoSphereUpdater")
    try:
        write_status(status="CHECKING", pct=5, message="Checking latest GitHub release...")
        rel = get_latest_release()
        version = rel["version"]
        url = rel["download_url"]
        log.info(f"[Updater] Found release {version} at {url}")

        write_status(status="DOWNLOADING", pct=10, message="Starting download...", version=version)
        zip_path = os.path.join(CACHE_DIR, f"update_{version}.zip")
        download_file(url, zip_path, version)

        staged_path = extract_and_stage(zip_path, STAGING_DIR, version)
        log.info(f"[Updater] Staged update files at {staged_path}")

        launch_apply_script(staged_path, dry_run=dry_run)
        return True

    except Exception as err:
        err_msg = str(err)
        log.error(f"[Updater] Error: {err_msg}", exc_info=True)
        write_status(status="ERROR", pct=0, message=f"Update failed: {err_msg}", error=err_msg)
        return False


def main():
    parser = argparse.ArgumentParser(description="InfoSphere 1-Click Auto Updater")
    parser.add_argument("--start", action="store_true", help="Start update pipeline in background")
    parser.add_argument("--cli", action="store_true", help="Run update interactively in console")
    parser.add_argument("--dry-run", action="store_true", help="Download and stage without applying")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s"
    )

    if args.cli:
        print("=" * 60)
        print("  InfoSphere 1-Click Automated In-App Updater")
        print("=" * 60)
        success = run_update_pipeline(dry_run=args.dry_run)
        if success:
            print("\n[SUCCESS] Update prepared and engine restarting!")
        else:
            print("\n[FAILED] Update failed. Check logs for details.")
            sys.exit(1)
    else:
        run_update_pipeline(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
