"""
InfoSphere Update Notifier
Monitors GitHub Releases in the background and notifies users when a newer
version of InfoSphere is published.
"""

import json
import logging
import os
import re
import threading
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple

from core.version import APP_VERSION

_GITHUB_REPO = "nazmulhaquebz/InfoSphere_wallpaper"
_RELEASES_API = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"
_DEFAULT_CHECK_INTERVAL_SEC = 2 * 60 * 60  # Check every 2 hours


def parse_version(ver_str: str) -> Tuple[int, ...]:
    """Parse version string like 'v2.3.0' or '2.3.1' into tuple of integers."""
    if not ver_str:
        return (0, 0, 0)
    m = re.match(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(ver_str).strip())
    if m:
        parts = [int(x) for x in m.groups() if x is not None]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    return (0, 0, 0)


class UpdateNotifier:
    """Non-blocking background thread that checks for GitHub Releases updates."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        check_interval: int = _DEFAULT_CHECK_INTERVAL_SEC,
        current_version: Optional[str] = None
    ):
        self._log = logger or logging.getLogger("UpdateNotifier")
        self._check_interval = check_interval
        self._current_version = current_version or APP_VERSION
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._cached_info: Dict[str, Any] = {
            "update_available": False,
            "current_version": self._current_version,
            "latest_version": f"v{self._current_version}" if not str(self._current_version).startswith("v") else self._current_version,
            "release_name": f"InfoSphere {self._current_version}",
            "release_url": f"https://github.com/{_GITHUB_REPO}/releases/latest",
            "download_url": "",
            "published_at": "",
            "checked_at": "",
            "check_status": "PENDING"
        }
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background check worker thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._worker_loop, name="UpdateCheckWorker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal worker to stop."""
        self._stop_event.set()

    def get_info(self) -> Dict[str, Any]:
        """Return thread-safe snapshot of update status."""
        with self._lock:
            return dict(self._cached_info)

    def check_now(self) -> Dict[str, Any]:
        """Perform a check immediately and return result."""
        self._do_check()
        return self.get_info()

    def check_for_updates(self) -> Dict[str, Any]:
        """Alias for check_now()."""
        return self.check_now()

    def _do_check(self) -> None:
        """Query GitHub Releases API and compare version tags."""
        current_tuple = parse_version(self._current_version)
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        req = urllib.request.Request(
            _RELEASES_API,
            headers={
                "User-Agent": "InfoSphere-UpdateNotifier/1.0",
                "Accept": "application/vnd.github+json"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                if resp.status != 200:
                    self._set_status(check_status=f"HTTP_{resp.status}", checked_at=now_iso)
                    return
                data = json.loads(resp.read().decode("utf-8"))
                
                remote_tag = data.get("tag_name", "")
                remote_tuple = parse_version(remote_tag)
                is_newer = remote_tuple > current_tuple
                
                # Look for downloadable zip asset
                download_url = data.get("html_url", "")
                for asset in data.get("assets", []):
                    name = asset.get("name", "")
                    if name.endswith(".zip"):
                        download_url = asset.get("browser_download_url", download_url)
                        break

                with self._lock:
                    self._cached_info = {
                        "update_available": is_newer,
                        "current_version": self._current_version,
                        "latest_version": remote_tag or f"v{self._current_version}",
                        "release_name": data.get("name", f"InfoSphere {remote_tag}"),
                        "release_url": data.get("html_url", f"https://github.com/{_GITHUB_REPO}/releases/latest"),
                        "download_url": download_url,
                        "published_at": data.get("published_at", ""),
                        "checked_at": now_iso,
                        "check_status": "UP_TO_DATE" if not is_newer else "UPDATE_AVAILABLE"
                    }

                if is_newer:
                    self._log.info(f"[UpdateNotifier] New version available: {remote_tag} (Current: {self._current_version})")
                else:
                    self._log.debug(f"[UpdateNotifier] InfoSphere is up to date ({self._current_version}).")

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as net_err:
            self._set_status(check_status="OFFLINE", checked_at=now_iso)
            self._log.debug(f"[UpdateNotifier] Network check notice: {net_err}")
        except Exception as err:
            self._set_status(check_status="ERROR", checked_at=now_iso)
            self._log.debug(f"[UpdateNotifier] Unexpected check error: {err}")

    def _set_status(self, check_status: str, checked_at: str) -> None:
        with self._lock:
            self._cached_info["check_status"] = check_status
            self._cached_info["checked_at"] = checked_at

    def _worker_loop(self) -> None:
        # Initial boot delay so we don't compete with startup rendering
        if self._stop_event.wait(5.0):
            return
        
        while not self._stop_event.is_set():
            self._do_check()
            if self._stop_event.wait(self._check_interval):
                break
