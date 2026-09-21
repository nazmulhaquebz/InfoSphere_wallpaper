#!/usr/bin/env python3
"""
InfoSphere Version Control Manager
Automates version bumping, date stamping, and synchronizes VERSION, CHANGELOG.md, and HUD templates.

Usage:
    python bump_version.py 2.3.1 "Release summary or notes"
    python bump_version.py --show
"""

import sys
import os
import re
import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
VERSION_FILE = ROOT_DIR / "VERSION"
CHANGELOG_FILE = ROOT_DIR / "CHANGELOG.md"
HTML_FILE = ROOT_DIR / "infosphere_live_wallpaper.html"


def get_current_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"


def bump_version(new_ver: str, notes: str = ""):
    old_ver = get_current_version()
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    print(f"\n=======================================================")
    print(f"  InfoSphere Version Control Manager")
    print(f"=======================================================")
    print(f"  Current Version : v{old_ver}")
    print(f"  Target Version  : v{new_ver}")
    print(f"  Release Date    : {today_str}")
    if notes:
        print(f"  Release Notes   : {notes}")
    print(f"-------------------------------------------------------")

    # 1. Update VERSION file
    VERSION_FILE.write_text(new_ver + "\n", encoding="utf-8")
    print(f"  [OK] Updated VERSION -> {new_ver}")

    # 2. Update infosphere_live_wallpaper.html
    if HTML_FILE.exists():
        content = HTML_FILE.read_text(encoding="utf-8")
        # Replace title
        content = re.sub(
            r"<title>InfoSphere · Tactical Cyber Live Wallpaper Engine v[0-9\.]+</title>",
            f"<title>InfoSphere · Tactical Cyber Live Wallpaper Engine v{new_ver}</title>",
            content
        )
        # Replace brand subtitle
        content = re.sub(
            r'<div class="brand-subtitle">v[0-9\.]+ · LOCAL & SECURE · KERNEL SYNC</div>',
            f'<div class="brand-subtitle">v{new_ver} · LOCAL & SECURE · KERNEL SYNC</div>',
            content
        )
        # Replace footer
        content = re.sub(
            r"InfoSphere v[0-9\.]+ · Intelligent Live Engine",
            f"InfoSphere v{new_ver} · Intelligent Live Engine",
            content
        )
        HTML_FILE.write_text(content, encoding="utf-8")
        print(f"  [OK] Synchronized infosphere_live_wallpaper.html header and footer")

    # 3. Update CHANGELOG.md
    if CHANGELOG_FILE.exists():
        cl_text = CHANGELOG_FILE.read_text(encoding="utf-8")
        
        # Check if version already documented
        if f"[{new_ver}]" not in cl_text:
            # Add table row to index
            table_marker = "|---|---|---|---|"
            new_row = f"| [**{new_ver}**](#{new_ver.replace('.', '')}---{today_str}) | **{today_str}** | {notes or 'Maintenance and optimizations'} | Feature Release |"
            if table_marker in cl_text:
                cl_text = cl_text.replace(table_marker, f"{table_marker}\n{new_row}")

            # Add section block
            section_marker = "---"
            summary_item = f"- {notes}" if notes else "- General stability, performance improvements, and maintenance."
            new_section = f"\n\n## [{new_ver}] - {today_str}\n\n### 🚀 Highlights\n{summary_item}\n"
            
            # Insert after the first ---
            parts = cl_text.split("---", 2)
            if len(parts) >= 3:
                cl_text = parts[0] + "---" + parts[1] + "---" + new_section + parts[2]
            else:
                cl_text += new_section

            CHANGELOG_FILE.write_text(cl_text, encoding="utf-8")
            print(f"  [OK] Added v{new_ver} ({today_str}) to CHANGELOG.md")
        else:
            print(f"  [INFO] Version {new_ver} already present in CHANGELOG.md")

    # 4. Update START_INFOSPHERE.bat
    start_bat = ROOT_DIR / "START_INFOSPHERE.bat"
    if start_bat.exists():
        bat_content = start_bat.read_text(encoding="utf-8")
        bat_content = re.sub(
            r"TACTICAL CYBER LIVE WALLPAPER ENGINE v[0-9\.]+",
            f"TACTICAL CYBER LIVE WALLPAPER ENGINE v{new_ver}",
            bat_content
        )
        bat_content = re.sub(
            r"Last Updated: \d{4}-\d{2}-\d{2}",
            f"Last Updated: {today_str}",
            bat_content
        )
        start_bat.write_text(bat_content, encoding="utf-8")
        print(f"  [OK] Synchronized START_INFOSPHERE.bat (v{new_ver}, {today_str})")

    # 5. Update STOP_INFOSPHERE.bat
    stop_bat = ROOT_DIR / "STOP_INFOSPHERE.bat"
    if stop_bat.exists():
        bat_content = stop_bat.read_text(encoding="utf-8")
        bat_content = re.sub(
            r"TACTICAL CYBER LIVE WALLPAPER ENGINE v[0-9\.]+",
            f"TACTICAL CYBER LIVE WALLPAPER ENGINE v{new_ver}",
            bat_content
        )
        bat_content = re.sub(
            r"Last Updated: \d{4}-\d{2}-\d{2}",
            f"Last Updated: {today_str}",
            bat_content
        )
        stop_bat.write_text(bat_content, encoding="utf-8")
        print(f"  [OK] Synchronized STOP_INFOSPHERE.bat (v{new_ver}, {today_str})")

    print(f"=======================================================")
    print(f"  [SUCCESS] Version bumped to v{new_ver} ({today_str})!")
    print(f"=======================================================\n")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print(f"Current version: v{get_current_version()}")
        return

    if sys.argv[1] in ("-s", "--show", "show"):
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        print(f"InfoSphere Version: v{get_current_version()} (Today: {today_str})")
        return

    new_ver = sys.argv[1].lstrip("v")
    notes = sys.argv[2] if len(sys.argv) > 2 else ""
    bump_version(new_ver, notes)


if __name__ == "__main__":
    main()
