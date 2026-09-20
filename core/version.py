"""Single application version source."""

from pathlib import Path


VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"
try:
    APP_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()
except OSError:
    APP_VERSION = "0.0.0-dev"
