"""
InfoSphere Cyber Live Wallpaper Engine
core/config_loader.py

Loads config.json, creates a full default config if missing,
merges user settings with defaults so new keys always exist.
"""

import json
import sys
from pathlib import Path

# ── Default configuration ──────────────────────────────────────────────────
DEFAULT_CONFIG: dict = {
    # Branding
    "brand_name": "InfoSphere Cyber Live Wallpaper Engine",

    # Timing
    "refresh_interval_seconds": 10,

    # Resolution  (change to match your monitor)
    "resolution_width": "auto",
    "resolution_height": "auto",
    "display_mode": "primary",

    # Theme
    "theme": "cyber_dark",

    # File paths  (relative to project root)
    "output_path": "output/infosphere_wallpaper.png",
    "log_path":    "logs/wallpaper.log",

    # Panels to show  (set false to hide any panel)
    "show_cpu":             True,
    "show_ram":             True,
    "show_disk":            True,
    "show_ip":              True,
    "show_network":         True,
    "show_firewall_status": True,
    "show_telemetry":       True,
    "show_weather":         True,   # requires internet; set false for fully offline

    # Cosmetic threat animation. Disabled by default so simulated events are
    # never presented as real security actions unless the user opts in.
    "simulate_threats": False,

    "operator_profile": {
        "enabled": True,
        "name": "Local Operator",
        "title": "System Administrator",
    },

    "accessibility": {
        "theme": "default",
        "density": "comfortable",
        "reduce_motion": False,
        "font_scale": 1.0,
    },

    # Weather city ("auto" = detect from IP, or use a city name like "London")
    "weather_city": "auto",

    # Router monitoring is opt-in on fresh installs. Keep credentials outside
    # config.json and provide them through the named environment variable.
    "router": {
        "enabled": False,
        "ip": "192.168.0.1",
        "username": "admin",
        "password_env": "INFOSPHERE_ROUTER_PASSWORD",
        "refresh_secs": 10,
    },

    # Full speed tests consume significant bandwidth, so fresh installs leave
    # them disabled until explicitly enabled.
    "speedtest": {
        "enabled": False,
        "ping_interval_s": 5,
        "speed_interval_s": 300,
        "ping_host": "8.8.8.8",
        "ping_port": 53,
    },

    # Process management must always be explicit. The wallpaper should not
    # terminate or reprioritize unrelated applications by default.
    "process_optimizer": {
        "enabled": False,
        "terminate_updates": False,
        "throttle_on_load": False,
    },

    # Ethical-use footer text
    "ethical_footer": (
        "Local system monitoring only  |  No unauthorized scanning  |  Ethical use only"
    ),

    # ── Colour palette ─────────────────────────────────────────────────────
    # All values are CSS-style hex codes.  Change any to re-theme the wallpaper.
    "colors": {
        "background":    "#050A14",   # very dark navy
        "panel_bg":      "#070D1A",   # panel fill
        "panel_border":  "#1A3A5C",   # panel outline
        "accent_cyan":   "#00F5FF",
        "accent_green":  "#00FF88",
        "accent_amber":  "#FFB800",
        "accent_red":    "#FF3366",
        "accent_blue":   "#4488FF",
        "text_primary":  "#E0F4FF",
        "text_secondary":"#7AAABB",
        "text_dim":      "#5D8494"
    }
}

PROJECT_ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent
)
CONFIG_PATH = PROJECT_ROOT / "config.json"


# ── Public API ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    """
    Load and return the merged configuration dictionary.

    If config.json is missing it is created with defaults.
    If it exists, user values are merged on top of defaults so
    any key added in a future version is always present.
    """
    if not CONFIG_PATH.exists():
        print("[InfoSphere] config.json not found — creating with defaults.")
        _save_config(DEFAULT_CONFIG)
        return _deep_copy(DEFAULT_CONFIG)

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            user_cfg = json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"[InfoSphere] WARNING  config.json is invalid JSON ({exc}). Using defaults.")
        return _deep_copy(DEFAULT_CONFIG)
    except Exception as exc:
        print(f"[InfoSphere] WARNING  Cannot read config.json ({exc}). Using defaults.")
        return _deep_copy(DEFAULT_CONFIG)

    if not isinstance(user_cfg, dict):
        print("[InfoSphere] WARNING  config.json must contain a JSON object. Using defaults.")
        return _deep_copy(DEFAULT_CONFIG)

    return _deep_merge(DEFAULT_CONFIG, user_cfg)


# ── Helpers ────────────────────────────────────────────────────────────────

def _save_config(cfg: dict) -> None:
    """Write cfg to config.json with pretty indentation."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
        print(f"[InfoSphere] Default config saved -> {CONFIG_PATH}")
    except Exception as exc:
        print(f"[InfoSphere] WARNING  Could not write config.json: {exc}")


def _deep_copy(obj):
    """Simple deep-copy via JSON round-trip (avoids importing copy)."""
    return json.loads(json.dumps(obj))


def _deep_merge(defaults: dict, overrides: dict) -> dict:
    """Recursively merge mapping overrides without mutating either input."""
    merged = _deep_copy(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = _deep_copy(value)
    return merged
