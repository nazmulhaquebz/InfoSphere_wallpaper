#!/usr/bin/env python3
"""Non-destructive InfoSphere installation and runtime diagnostics."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from core.config_loader import load_config
from core.display_info import resolve_display_config
from core.telemetry_snapshot import validate_snapshot
from core.version import APP_VERSION


ROOT = Path(__file__).resolve().parent


def check(name, ok, detail, required=True):
    return {"name": name, "ok": bool(ok), "required": required, "detail": str(detail)}


def run_checks():
    results = []
    results.append(check("Python", sys.version_info >= (3, 10), sys.version.split()[0]))
    for module in ("PIL", "psutil", "speedtest"):
        found = importlib.util.find_spec(module) is not None
        results.append(check(f"Python module: {module}", found, "available" if found else "missing"))

    try:
        config, display = resolve_display_config(load_config())
        results.append(check("Configuration", True, "valid JSON and merged defaults"))
        results.append(check(
            "Display detection", display.get("monitor_count", 0) >= 1,
            f"{display.get('monitor_count')} monitor(s), {display.get('selected_width')}x{display.get('selected_height')}, {display.get('dpi')} DPI",
        ))
    except Exception as error:
        config = {}
        results.append(check("Configuration", False, error))

    output = ROOT / "output"
    try:
        output.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix="diagnostic_", suffix=".tmp", dir=output)
        os.close(descriptor)
        Path(temporary).unlink()
        results.append(check("Output directory", True, "writable"))
    except OSError as error:
        results.append(check("Output directory", False, error))

    snapshot_file = output / "system_snapshot.json"
    if snapshot_file.exists():
        try:
            snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
            errors = validate_snapshot(snapshot)
            results.append(check("Telemetry snapshot", not errors, "; ".join(errors) or "schema valid", required=False))
        except Exception as error:
            results.append(check("Telemetry snapshot", False, error, required=False))
    else:
        results.append(check("Telemetry snapshot", True, "not generated yet", required=False))

    for binary in ("security_audit.exe", "image_processor.exe"):
        exists = (ROOT / "core" / "bin" / binary).exists()
        results.append(check(f"Optional binary: {binary}", exists, "present" if exists else "missing", required=False))

    node = shutil.which("node")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    results.append(check("Node.js", bool(node), node or "not found"))
    results.append(check("npm", bool(npm), npm or "not found"))
    results.append(check(
        "Jarvis dependencies", (ROOT / "jarvis" / "node_modules").is_dir(),
        "installed" if (ROOT / "jarvis" / "node_modules").is_dir() else "run npm install",
    ))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    results = run_checks()
    payload = {
        "application": "InfoSphere",
        "version": APP_VERSION,
        "healthy": all(item["ok"] for item in results if item["required"]),
        "checks": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"InfoSphere v{APP_VERSION} diagnostics")
        for item in results:
            marker = "OK" if item["ok"] else ("WARN" if not item["required"] else "FAIL")
            print(f"[{marker:4}] {item['name']}: {item['detail']}")
        print("Overall:", "HEALTHY" if payload["healthy"] else "ACTION REQUIRED")
    return 0 if payload["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
