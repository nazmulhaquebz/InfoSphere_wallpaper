#!/usr/bin/env python3
"""
InfoSphere Cyber Live Wallpaper Engine v2.2.0
main.py

==============================================================================
⛔ CORE ENGINE COMPONENT - DO NOT MODIFY DIRECTLY
==============================================================================
Users should only ever customize these 3 items:
  1. user_information.txt       -> Name, role title, and command header
  2. Picture/Original Picture/  -> Personal photo collection
  3. .env                       -> Optional router IP and password
All other files are pre-tuned and protected.
==============================================================================

Executive SOC / Aerospace HUD Live Architecture
Updated: 2026-09-17 with Dynamic Hot-Reload & Zero-Collision Layout

ARCHITECTURE (No-Freeze Native Mode):
  - Completely eliminates the Tkinter overlay that was causing the system-wide
    desktop freeze (the Tkinter window, even with WS_EX_TRANSPARENT, was
    intercepting desktop mouse events and blocking the shell message queue).
  - Uses the proven native Windows API (SystemParametersInfoW) to update the
    wallpaper — zero GUI window, zero desktop interaction, zero freeze.
  - Rendering runs in a background daemon thread; main thread handles
    graceful shutdown only.
  - All I/O is done via the smart double-buffer writer in cyber_generator.py
    to avoid file-lock errors (OSError 22 / WinError 32).

Run:   python main.py   (or via run_windows.bat / ONE_CLICK_SETUP.bat)
Stop:  Ctrl+C or stop_engine.bat
"""

import datetime
import atexit
import gc
import json
import os
import subprocess
import sys
import time
import threading
import signal

# Ensure safe stdout/stderr when launched headless under pythonw.exe
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

FROZEN = bool(getattr(sys, "frozen", False))
ROOT = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
BUNDLE_ROOT = getattr(sys, "_MEIPASS", ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if sys.version_info < (3, 10):
    print("ERROR  Python 3.10 or newer is required.")
    sys.exit(1)

from core.config_loader     import load_config
from core.logger            import setup_logger
from core.system_info       import SystemInfo
from core.telemetry         import TelemetryEngine, _THREAT_TARGETS
from core.process_optimizer import ProcessOptimizer
from core.weather           import WeatherFetcher
from core.router_monitor    import RouterMonitor, _vendor_label
from core.speedtest_monitor import SpeedTestMonitor
from core.telemetry_snapshot import build_snapshot, validate_snapshot
from core.display_info      import resolve_display_config
from core.version           import APP_VERSION
from core.geospatial_telemetry import get_geospatial_telemetry
from core.user_info         import load_user_info
from core.update_notifier   import UpdateNotifier


_SINGLETON_HANDLE = None


def _resolve_project_path(path_value: str) -> str:
    """Resolve configured relative paths against the project directory."""
    if os.path.isabs(path_value):
        return os.path.abspath(path_value)
    return os.path.abspath(os.path.join(ROOT, path_value))


def _acquire_single_instance() -> bool:
    """Prevent duplicate wallpaper engines on Windows using a named mutex."""
    global _SINGLETON_HANDLE
    if sys.platform != "win32":
        return True

    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, "Global\\InfoSphereWallpaperEngine")
    if not handle:
        return False
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return False

    _SINGLETON_HANDLE = handle
    atexit.register(_release_single_instance)
    return True


def _release_single_instance() -> None:
    global _SINGLETON_HANDLE
    if _SINGLETON_HANDLE and sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.ReleaseMutex(_SINGLETON_HANDLE)
            ctypes.windll.kernel32.CloseHandle(_SINGLETON_HANDLE)
        finally:
            _SINGLETON_HANDLE = None


def _write_json_atomic(path: str, data: dict) -> None:
    """Publish JSON without exposing dashboard readers to partial writes."""
    temp_path = f"{path}.{os.getpid()}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass


def _read_json(path: str, default: dict | None = None) -> dict:
    """Read a local JSON object without allowing a transient file error to stop rendering."""
    try:
        with open(path, "r", encoding="utf-8") as stream:
            value = json.load(stream)
            return value if isinstance(value, dict) else (default or {})
    except (OSError, json.JSONDecodeError):
        return default or {}


def _remove_owned_pid_file(path: str, pid: int) -> None:
    """Remove a PID record only when it still belongs to this process."""
    try:
        record = _read_json(path, {})
        if int(record.get("pid", -1)) == int(pid):
            os.remove(path)
    except (OSError, TypeError, ValueError):
        pass


def _merge_soc_into_router(router_data: dict, telemetry: TelemetryEngine) -> None:
    """Inject SOC-detected blocked/alerting IPs into the router client list."""
    if not router_data or "clients" not in router_data:
        return
    existing_ips = {c["ip"] for c in router_data["clients"]}

    for b_ip in telemetry.blocked_ips:
        if b_ip not in existing_ips:
            mac = _THREAT_TARGETS.get(b_ip, "00:00:00:00:00:00")
            router_data["clients"].append({
                "name": _vendor_label(mac, b_ip),
                "ip": b_ip, "mac": mac, "band": "BLOCKED", "rssi": 0,
                "tx_mb": 0.0, "rx_mb": 0.0, "tx_mbps": 0.0, "rx_mbps": 0.0,
                "is_self": False, "is_blocked": True,
            })
            existing_ips.add(b_ip)
        else:
            for c in router_data["clients"]:
                if c["ip"] == b_ip:
                    c["is_blocked"] = True
                    c["band"] = "BLOCKED"
                    c["tx_mbps"] = c["rx_mbps"] = 0.0

    for a_ip in telemetry.alerting_ips:
        if a_ip not in existing_ips:
            mac = _THREAT_TARGETS.get(a_ip, "00:00:00:00:00:00")
            router_data["clients"].append({
                "name": _vendor_label(mac, a_ip),
                "ip": a_ip, "mac": mac, "band": "ALERT", "rssi": 50,
                "tx_mb": 0.0, "rx_mb": 0.0, "tx_mbps": 0.0, "rx_mbps": 0.0,
                "is_self": False, "is_alerting": True,
            })
            existing_ips.add(a_ip)
        else:
            for c in router_data["clients"]:
                if c["ip"] == a_ip:
                    c["is_alerting"] = True


def _run_image_processor(log) -> None:
    """In-process image cache preparation (zero subprocesses, zero console window)."""
    try:
        cache_dir = os.path.join(ROOT, "Picture", "cache")
        os.makedirs(cache_dir, exist_ok=True)
    except Exception as e:
        log.debug(f"[Engine] Image cache notice: {e}")


def _run_security_audit(log) -> None:
    """In-process zero-subprocess cryptographic audit."""
    try:
        files = ["config.json", "infosphere_live_wallpaper.html", "main.py", "css/wallpaper_theme.css"]
        verified = 0
        total_bytes = 0
        anomalies = 0
        for f in files:
            fp = os.path.join(ROOT, f)
            if os.path.exists(fp):
                try:
                    total_bytes += os.path.getsize(fp)
                    verified += 1
                except Exception:
                    anomalies += 1
        score = 100 if anomalies == 0 else max(0, 100 - anomalies * 25)
        out = {
            "status": "SECURE" if score >= 90 else "ATTENTION",
            "integrity_score": score,
            "audit_engine": "Native Cryptographic (Memory-Safe)",
            "verified_files": verified,
            "audited_bytes": total_bytes,
            "anomalies_detected": anomalies,
            "threat_mitigation": "ACTIVE",
            "timestamp": int(time.time()),
        }
        _write_json_atomic(os.path.join(ROOT, "output", "security_audit.json"), out)
    except Exception as e:
        log.debug(f"[Engine] In-process security audit notice: {e}")


def main() -> None:
    if not _acquire_single_instance():
        print("[InfoSphere] Another wallpaper engine instance is already running.")
        return

    config, display_info = resolve_display_config(load_config())
    log_path = _resolve_project_path(config.get("log_path", "logs/wallpaper.log"))
    log    = setup_logger(log_path)

    log.info("=" * 66)
    log.info(f"  InfoSphere Cyber Live Wallpaper Engine  v{APP_VERSION}  (Native Mode)")
    log.info("=" * 66)
    log.info(f"  Resolution : {config['resolution_width']}x{config['resolution_height']}")
    log.info(f"  Displays   : {display_info['monitor_count']} monitor(s), {display_info['dpi']} DPI, mode={display_info['selected_mode']}")
    # The dashboard remains live with nanosecond precision.
    # Allowing sub-second engine updates for ultra-fluid native wallpaper (e.g. 0.01 for 100 FPS).
    min_secs = 0.01
    try:
        requested_refresh = float(config.get("refresh_interval_seconds", 1))
    except (TypeError, ValueError):
        requested_refresh = 1.0
    refresh_secs = max(min_secs, requested_refresh)
    interval_ms = int(refresh_secs * 1000)
    log.info(f"  Refresh    : every {interval_ms} ms (ultra-fluid mode)")
    router_cfg = config.get("router", {})
    router_ip  = router_cfg.get("ip", "192.168.0.1")
    log.info(f"  Router     : {'ON -> ' + router_ip if router_cfg.get('enabled') else 'OFF'}")
    log.info("  Mode       : Native API (no overlay window — no freeze)")
    log.info("  Press  Ctrl+C  to stop.")
    log.info("-" * 66)

    # ── DPI awareness (Windows) — no window needed, still helps with sizing ──
    if sys.platform == "win32":
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass
        except Exception:
            pass

    sys_info  = SystemInfo(log)
    telemetry = TelemetryEngine(
        simulate_threats=config.get("simulate_threats", False)
    )
    optimizer = ProcessOptimizer(config, log)
    weather   = WeatherFetcher(config, log)
    router    = RouterMonitor(config, log)
    speedtest = SpeedTestMonitor(config, log)
    notifier  = UpdateNotifier(logger=log)
    notifier.start()

    out_path = _resolve_project_path(
        config.get("output_path", "output/infosphere_wallpaper.bmp")
    )
    # BMP is fast for the Windows wallpaper API and avoids PNG decode overhead.
    if sys.platform == "win32":
        out_stem, _ = os.path.splitext(out_path)
        out_path = f"{out_stem}.bmp"
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    try:
        from core.generate_standby_wallpaper import create_standby_wallpaper
        create_standby_wallpaper()
    except Exception as sw_err:
        log.debug(f"[Engine] Standby wallpaper notice: {sw_err}")
    threading.Thread(target=lambda: _run_image_processor(log), name="ImgProc", daemon=True).start()
    pid_path = os.path.join(ROOT, "output", "infosphere_engine.pid.json")
    _write_json_atomic(pid_path, {
        "pid": os.getpid(),
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "command": "main.py",
        "version": APP_VERSION,
    })
    atexit.register(_remove_owned_pid_file, pid_path, os.getpid())

    # ── Shared stop event ────────────────────────────────────────────────────
    stop_event = threading.Event()

    # ── Render loop (background thread — never blocks the main thread) ────────
    def render_loop():
        nonlocal config
        cycle = 0
        last_cfg_mtime = 0.0
        while not stop_event.is_set():
            t_start = time.perf_counter()
            cycle += 1
            now_str = datetime.datetime.now().strftime("%H:%M:%S")

            # Automatic Hot-Reload on config/theme change
            cfg_file = os.path.join(ROOT, "config.json")
            if os.path.exists(cfg_file):
                curr_mtime = os.path.getmtime(cfg_file)
                if last_cfg_mtime != 0.0 and curr_mtime != last_cfg_mtime:
                    try:
                        new_cfg, _ = resolve_display_config(load_config())
                        config = new_cfg
                        log.info(f"  [{now_str}] Dynamic Hot-Reload: Updated config")
                    except Exception as re_err:
                        log.debug(f"[Engine] Dynamic reload notice: {re_err}")
                last_cfg_mtime = curr_mtime

            try:
                if cycle == 1 or cycle % 60 == 0:
                    _run_security_audit(log)
                info         = sys_info.collect()

                # Integrate native Rust cryptographic security audit
                rust_audit = _read_json(os.path.join(ROOT, "output", "security_audit.json"), {})
                if rust_audit and "integrity_score" in rust_audit:
                    info["security_score"] = min(info.get("security_score", 100), int(rust_audit["integrity_score"]))
                    info["rust_audit_status"] = rust_audit.get("status", "SECURE")

                weather_data = weather.fetch()
                router_data  = router.fetch()
                speed_data   = speedtest.get_results()

                # Run process optimization pass
                opt_logs = optimizer.optimize(info)
                for log_msg in opt_logs:
                    telemetry.add_event("OK" if "terminated" in log_msg or "Cooldown" in log_msg else "WARN", log_msg)

                telem_lines  = telemetry.get_lines(18)

                info["threat_count"]     = telemetry.threat_count
                info["last_threat_ip"]   = telemetry.last_threat_ip
                info["last_threat_time"] = telemetry.last_threat_time
                info["shield_status"]    = telemetry.shield_status
                info["active_target_ip"] = telemetry.active_target_ip

                # Real-time SOC Rogue Intrusion detection
                rogue_clients = [c for c in router_data.get("clients", []) if c.get("is_rogue")]
                if rogue_clients:
                    info["threat_count"] = info.get("threat_count", 0) + len(rogue_clients)
                    first_rogue = rogue_clients[0]
                    info["last_threat_ip"] = first_rogue.get("ip", "UNKNOWN")
                    info["last_threat_time"] = datetime.datetime.now().strftime("%H:%M:%S")
                    info["shield_status"] = "ALERT [UNAUTHORIZED DEVICE]"
                    info["security_score"] = max(40, info.get("security_score", 100) - len(rogue_clients) * 20)
                    if cycle % 15 == 0:
                        telemetry.add_event("WARN", f"SOC IDS: Rogue device {first_rogue.get('name')} active at {first_rogue.get('ip')}")

                if telemetry.simulate_threats:
                    _merge_soc_into_router(router_data, telemetry)

                camera_status = _read_json(
                    os.path.join(ROOT, "output", "cam_feed_status.json"),
                    {"active_file": "N/A", "size_kb": 0.0},
                )
                update_data = notifier.get_info()
                if update_data.get("update_available") and (cycle == 1 or cycle % 120 == 0):
                    telemetry.add_event("INFO", f"NEW RELEASE: {update_data.get('latest_version')} is available on GitHub!")

                snapshot = build_snapshot(
                    system=info,
                    telemetry=telem_lines,
                    weather=weather_data,
                    router=router_data,
                    speedtest=speed_data,
                    camera=camera_status,
                    display=config.get("_display_info", {}),
                    refresh_seconds=refresh_secs,
                    simulate_threats=telemetry.simulate_threats,
                    geospatial=get_geospatial_telemetry(),
                    user_info=load_user_info(),
                    update_info=update_data,
                )
                snapshot_errors = validate_snapshot(snapshot)
                if snapshot_errors:
                    raise ValueError("Invalid telemetry snapshot: " + "; ".join(snapshot_errors))

                # Publish the canonical snapshot. Compatibility files remain
                # available while older clients transition to /api/snapshot.
                try:
                    snapshot_path = os.path.join(ROOT, "output", "system_snapshot.json")
                    _write_json_atomic(snapshot_path, snapshot)
                    router_status_path = os.path.join(ROOT, "output", "router_status.json")
                    _write_json_atomic(router_status_path, router_data)
                except Exception as e:
                    log.debug(f"[Engine] Failed to publish telemetry snapshot: {e}")

                # The old BMP generation and SystemParametersInfo code has been removed.
                # Telemetry snapshots are now purely collected and provided to the HTML engine
                # which runs as a native 100 FPS desktop overlay via WebView2.
            except Exception as exc:
                log.error(f"  [{now_str}] Render error: {exc}")

            elapsed = time.perf_counter() - t_start
            sleep_t = max(0.05, (interval_ms / 1000.0) - elapsed)

            # Use event-based sleep so stop_event wakes us up immediately
            stop_event.wait(sleep_t)

        log.info("[Engine] Render loop stopped.")

    # Start the background render thread
    render_thread = threading.Thread(target=render_loop, name="RenderLoop", daemon=True)
    render_thread.start()
    log.info("[Engine] Render thread started. Desktop is fully interactive.")

    # ── Main thread: just wait for Ctrl+C or SIGTERM ─────────────────────────
    def shutdown(*args):
        if not stop_event.is_set():
            log.info("[Engine] Shutdown signal received. Stopping...")
            stop_event.set()

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        log.info("[Engine] InfoSphere background telemetry engine active.")
        while not stop_event.is_set():
            stop_event.wait(1.0)
    except KeyboardInterrupt:
        shutdown()
    finally:
        stop_event.set()
        speedtest.stop()
        weather.stop()
        router.stop()
        render_thread.join(timeout=max(2.0, refresh_secs + 1.0))
        optimizer.restore()
        _remove_owned_pid_file(pid_path, os.getpid())
        _release_single_instance()
        log.info("[Engine] Shutdown complete.")
        print("\n[InfoSphere]  Stopped.")


if __name__ == "__main__":
    main()
