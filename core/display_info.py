"""Display, DPI, and virtual-desktop discovery with safe cross-platform fallbacks."""

from __future__ import annotations

import copy
import os
import platform
from typing import Any


DESIGN_WIDTH = 1920
DESIGN_HEIGHT = 1080


def _windows_display_info() -> dict[str, Any]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

    primary = {
        "x": 0,
        "y": 0,
        "width": int(user32.GetSystemMetrics(0) or DESIGN_WIDTH),
        "height": int(user32.GetSystemMetrics(1) or DESIGN_HEIGHT),
        "primary": True,
    }
    virtual = {
        "x": int(user32.GetSystemMetrics(76)),
        "y": int(user32.GetSystemMetrics(77)),
        "width": int(user32.GetSystemMetrics(78) or primary["width"]),
        "height": int(user32.GetSystemMetrics(79) or primary["height"]),
    }

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                    ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

    monitors = []
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
        ctypes.POINTER(RECT), wintypes.LPARAM,
    )

    @callback_type
    def callback(handle, _dc, _rect, _data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            rect = info.rcMonitor
            monitors.append({
                "x": int(rect.left),
                "y": int(rect.top),
                "width": int(rect.right - rect.left),
                "height": int(rect.bottom - rect.top),
                "primary": bool(info.dwFlags & 1),
            })
        return True

    try:
        user32.EnumDisplayMonitors(None, None, callback, 0)
    except Exception:
        monitors = [primary]

    dpi = 96
    try:
        dpi = int(user32.GetDpiForSystem())
    except Exception:
        try:
            dc = user32.GetDC(0)
            dpi = int(ctypes.windll.gdi32.GetDeviceCaps(dc, 88) or 96)
            user32.ReleaseDC(0, dc)
        except Exception:
            pass

    return {
        "platform": "Windows",
        "primary": primary,
        "virtual": virtual,
        "monitors": monitors or [primary],
        "monitor_count": len(monitors) or 1,
        "dpi": dpi,
        "scale_percent": round(dpi / 96 * 100),
        "source": "Windows display APIs",
    }


def detect_display_info() -> dict[str, Any]:
    if platform.system() == "Windows":
        try:
            return _windows_display_info()
        except Exception:
            pass

    width = int(os.environ.get("INFOSPHERE_DISPLAY_WIDTH", DESIGN_WIDTH))
    height = int(os.environ.get("INFOSPHERE_DISPLAY_HEIGHT", DESIGN_HEIGHT))
    primary = {"x": 0, "y": 0, "width": width, "height": height, "primary": True}
    return {
        "platform": platform.system() or "Unknown",
        "primary": primary,
        "virtual": dict(primary),
        "monitors": [primary],
        "monitor_count": 1,
        "dpi": 96,
        "scale_percent": 100,
        "source": "environment fallback",
    }


def resolve_display_config(config: dict) -> tuple[dict, dict]:
    """Return a copied config with concrete render dimensions plus metadata."""
    resolved = copy.deepcopy(config)
    display = detect_display_info()
    mode = str(resolved.get("display_mode", "primary")).lower()
    if mode not in ("primary", "virtual"):
        mode = "primary"
    target = display[mode]

    def dimension(value, detected, minimum):
        if str(value).lower() == "auto":
            return max(minimum, int(detected))
        try:
            return max(minimum, min(16384, int(value)))
        except (TypeError, ValueError):
            return max(minimum, int(detected))

    resolved["resolution_width"] = dimension(
        resolved.get("resolution_width", "auto"), target["width"], 320
    )
    resolved["resolution_height"] = dimension(
        resolved.get("resolution_height", "auto"), target["height"], 180
    )
    resolved["display_mode"] = mode
    display["selected_mode"] = mode
    display["selected_width"] = resolved["resolution_width"]
    display["selected_height"] = resolved["resolution_height"]
    resolved["_display_info"] = display
    return resolved, display
