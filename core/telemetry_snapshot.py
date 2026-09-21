"""Versioned, JSON-safe telemetry contract shared by the engine and Jarvis."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

from core.version import APP_VERSION


SCHEMA_VERSION = "1.0"
PROVENANCE_VALUES = {
    "MEASURED", "ESTIMATED", "CACHED", "SIMULATED", "DERIVED",
    "UNAVAILABLE", "VISUALIZATION",
}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def temperature_provenance(source: str) -> str:
    source = str(source or "").upper()
    if source == "CPU_SENSOR":
        return "MEASURED"
    if source.endswith("ESTIMATE"):
        return "ESTIMATED"
    return "UNAVAILABLE"


def _dashboard_metrics(system: dict) -> dict:
    ram_total_gb = float(system.get("ram_total_gb", 0.0) or 0.0)
    ram_used_gb = float(system.get("ram_used_gb", 0.0) or 0.0)
    disk_total_gb = float(system.get("disk_total_gb", 0.0) or 0.0)
    rx_kbps = float(system.get("net_rx_kbps", 0.0) or 0.0)
    tx_kbps = float(system.get("net_tx_kbps", 0.0) or 0.0)
    return {
        "cpu": float(system.get("cpu_percent", 0.0) or 0.0),
        "ram": {
            "total": int(ram_total_gb * 1024**3),
            "used": int(ram_used_gb * 1024**3),
            "pct": float(system.get("ram_percent", 0.0) or 0.0),
        },
        "disks": [{
            "mount": "system",
            "pct": float(system.get("disk_percent", 0.0) or 0.0),
            "total_gb": disk_total_gb,
        }],
        "network": [{
            "iface": "active",
            "rx": round(rx_kbps * 8 / 1000, 2),
            "tx": round(tx_kbps * 8 / 1000, 2),
        }],
        "uptime": int(system.get("uptime_secs", 0) or 0),
        "temperature": {
            "value_c": float(system.get("cpu_temp", 0.0) or 0.0),
            "source": str(system.get("cpu_temp_source", "UNAVAILABLE")),
            "provenance": temperature_provenance(system.get("cpu_temp_source", "")),
        },
    }


def build_snapshot(
    system: dict,
    telemetry: list,
    weather: dict | None,
    router: dict | None,
    speedtest: dict | None,
    camera: dict | None,
    display: dict | None,
    refresh_seconds: float,
    simulate_threats: bool = False,
    geospatial: dict | None = None,
    user_info: dict | None = None,
    update_info: dict | None = None,
) -> dict:
    """Build the canonical snapshot consumed by every presentation layer."""
    weather = weather or {}
    router = router or {}
    speedtest = speedtest or {}
    camera = camera or {}
    display = display or {}
    geospatial = geospatial or {}
    user_info = user_info or {}
    update_info = update_info or {}

    temp_provenance = temperature_provenance(system.get("cpu_temp_source", ""))
    router_status = str(router.get("status", "")).upper()
    provenance = {
        "system": {"label": "MEASURED", "source": "local operating-system APIs"},
        "temperature": {
            "label": temp_provenance,
            "source": str(system.get("cpu_temp_source", "UNAVAILABLE")),
        },
        "network": {"label": "MEASURED", "source": "local interface counters"},
        "weather": {
            "label": "CACHED" if weather else "UNAVAILABLE",
            "source": "weather fetcher cache",
        },
        "router": {
            "label": "MEASURED" if router_status.startswith("ONLINE") else "UNAVAILABLE",
            "source": router_status or "NO DATA",
        },
        "speedtest": {
            "label": "CACHED" if speedtest else "UNAVAILABLE",
            "source": "background speed-test result",
        },
        "telemetry": {
            "label": "SIMULATED" if simulate_threats else "MEASURED",
            "source": "local event log",
        },
        "camera": {
            "label": "CACHED" if camera.get("active_file") not in (None, "", "N/A") else "UNAVAILABLE",
            "source": "local image cache",
        },
        "security": {"label": "DERIVED", "source": "firewall, router, and telemetry signals"},
        "radar": {
            "label": "SIMULATED" if simulate_threats else "VISUALIZATION",
            "source": "decorative local animation",
        },
        "geospatial": {
            "label": "MEASURED",
            "source": "local socket inspection and CIRT threat matrix",
        },
    }

    return _json_safe({
        "schema_version": SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "refresh_seconds": float(refresh_seconds),
        "provenance": provenance,
        "metrics": _dashboard_metrics(system),
        "system": system,
        "router": router,
        "weather": weather,
        "speedtest": speedtest,
        "telemetry": telemetry,
        "camera": camera,
        "display": display,
        "geospatial": geospatial,
        "user_info": user_info,
        "update_info": update_info,
    })



def validate_snapshot(snapshot: dict) -> list[str]:
    """Return validation errors; an empty list means the contract is valid."""
    errors = []
    if not isinstance(snapshot, dict):
        return ["snapshot must be an object"]
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    for key in ("generated_at", "provenance", "metrics", "system", "router", "telemetry"):
        if key not in snapshot:
            errors.append(f"missing field: {key}")
    for name, item in snapshot.get("provenance", {}).items():
        label = item.get("label") if isinstance(item, dict) else None
        if label not in PROVENANCE_VALUES:
            errors.append(f"invalid provenance label for {name}: {label}")
    return errors
