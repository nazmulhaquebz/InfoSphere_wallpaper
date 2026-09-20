"""
core/user_info.py
InfoSphere User Information & Customization Module

Reads and parses user_information.txt so users worldwide can customize
their personal security banner, name, and operational role in real time on the live desktop HUD.
"""

from __future__ import annotations
import os
from pathlib import Path

DEFAULT_NAME = "NAZMUL"
DEFAULT_TITLE = "WELCOME TO THE NAZMUL SECURITY WORLD"
DEFAULT_STATUS = "● ADVANCED TACTICAL THREAT SHIELD · ACTIVE PERIMETER SCAN"
DEFAULT_ROLE = "SYSTEM ADMINISTRATOR"


def load_user_info(file_path: Path | str | None = None) -> dict[str, str]:
    """
    Parse user_information.txt into a clean dictionary.
    Supports KEY=VALUE format, comments (#), and simple plain text.
    """
    if file_path is None:
        file_path = Path(__file__).resolve().parent.parent / "user_information.txt"
    else:
        file_path = Path(file_path)

    if not file_path.is_file():
        return {
            "name": DEFAULT_NAME,
            "welcome_title": DEFAULT_TITLE,
            "status_subtitle": DEFAULT_STATUS,
            "role_title": DEFAULT_ROLE,
        }

    try:
        raw_text = file_path.read_text(encoding="utf-8").strip()
    except Exception:
        raw_text = ""

    if not raw_text:
        return {
            "name": DEFAULT_NAME,
            "welcome_title": DEFAULT_TITLE,
            "status_subtitle": DEFAULT_STATUS,
            "role_title": DEFAULT_ROLE,
        }

    lines = [
        line.strip()
        for line in raw_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not lines:
        return {
            "name": DEFAULT_NAME,
            "welcome_title": DEFAULT_TITLE,
            "status_subtitle": DEFAULT_STATUS,
            "role_title": DEFAULT_ROLE,
        }

    has_kv = any("=" in line for line in lines)

    if has_kv:
        kv_data = {}
        for line in lines:
            if "=" in line:
                k, v = line.split("=", 1)
                kv_data[k.strip().upper()] = v.strip().strip("'\"")

        name = kv_data.get("NAME") or kv_data.get("OPERATOR_NAME") or DEFAULT_NAME
        welcome = kv_data.get("WELCOME_TITLE") or f"WELCOME TO THE {name.upper()} SECURITY WORLD"
        status = kv_data.get("STATUS_SUBTITLE") or kv_data.get("STATUS") or DEFAULT_STATUS
        role = kv_data.get("ROLE_TITLE") or kv_data.get("TITLE") or DEFAULT_ROLE
    else:
        # User entered plain text
        first_line = lines[0]
        if "WELCOME" in first_line.upper():
            welcome = first_line
            name = (
                first_line.upper()
                .replace("WELCOME TO THE", "")
                .replace("SECURITY WORLD", "")
                .strip()
                or DEFAULT_NAME
            )
        else:
            name = first_line
            welcome = f"WELCOME TO THE {name.upper()} SECURITY WORLD"

        status = lines[1] if len(lines) > 1 else DEFAULT_STATUS
        role = lines[2] if len(lines) > 2 else DEFAULT_ROLE

    return {
        "name": name,
        "welcome_title": welcome,
        "status_subtitle": status,
        "role_title": role,
    }
