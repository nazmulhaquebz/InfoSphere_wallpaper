#!/usr/bin/env bash
# ==============================================================
#  InfoSphere Cyber Live Wallpaper Engine  v2.0
#  run_kali.sh  —  One-Click Launcher for Kali / Debian Linux
# ==============================================================
#
#  Usage:
#    chmod +x run_kali.sh   (first time only)
#    ./run_kali.sh
#
#  No root / sudo required for normal operation.
# ==============================================================

set -e   # Exit immediately if a command fails (except where handled)

# ── Colours for terminal output ───────────────────────────────────────────
RED='\033[0;31m';  GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; BOLD='\033[1m';   RESET='\033[0m'

banner() {
    echo ""
    echo -e "${CYAN}${BOLD} ╔══════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${CYAN}${BOLD} ║     InfoSphere Cyber Live Wallpaper Engine  v2.0         ║${RESET}"
    echo -e "${CYAN}${BOLD} ║     One-Click Kali / Debian Launcher                     ║${RESET}"
    echo -e "${CYAN}${BOLD} ╚══════════════════════════════════════════════════════════╝${RESET}"
    echo ""
}

ok()   { echo -e " ${GREEN}[OK]${RESET}   $1"; }
info() { echo -e " ${CYAN}[INFO]${RESET} $1"; }
warn() { echo -e " ${YELLOW}[WARN]${RESET} $1"; }
fail() { echo -e " ${RED}[ERROR]${RESET} $1"; }

banner

# ── Step 1: Locate Python 3 ───────────────────────────────────────────────
info "Step 1/4 — Checking Python 3..."
PYTHON=""
for cmd in python3.11 python3.10 python3.9 python3.8 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1)
        PYTHON="$cmd"
        ok "Found: $ver  (using '$cmd')"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3 is not installed."
    echo ""
    echo "  Install it with one of these commands:"
    echo "    sudo apt update && sudo apt install python3 python3-pip -y   (Debian/Kali/Ubuntu)"
    echo ""
    exit 1
fi

# ── Step 2: Locate pip ────────────────────────────────────────────────────
info "Step 2/4 — Checking pip..."
PIP=""
for cmd in pip3.11 pip3.10 pip3.9 pip3.8 pip3 pip; do
    if command -v "$cmd" &>/dev/null; then
        PIP="$cmd"
        ok "Found pip: '$cmd'"
        break
    fi
done

if [ -z "$PIP" ]; then
    warn "pip not found. Trying to install via apt..."
    if command -v apt-get &>/dev/null; then
        apt-get install -y python3-pip 2>/dev/null || {
            fail "Could not install pip. Try:  sudo apt install python3-pip -y"
            exit 1
        }
        PIP="pip3"
    else
        fail "Cannot install pip automatically. Install manually and retry."
        exit 1
    fi
fi

# ── Step 3: Install / upgrade dependencies ────────────────────────────────
info "Step 3/4 — Installing dependencies (Pillow, psutil)..."
echo "  (Using: $PIP — this only takes a moment)"
echo ""

# Try without --break-system-packages first (older pip / venv),
# then with it (Debian 12+ / Kali 2023+)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

install_deps() {
    $PIP install --quiet --upgrade pip "$@" 2>/dev/null || true
    $PIP install --quiet -r "$SCRIPT_DIR/requirements.txt" "$@"
}

install_deps || install_deps --break-system-packages || {
    fail "Could not install dependencies."
    echo ""
    echo "  Manual fix options:"
    echo "    $PIP install Pillow psutil"
    echo "    $PIP install Pillow psutil --break-system-packages"
    echo "    $PIP install Pillow psutil --user"
    echo ""
    exit 1
}
ok "Dependencies installed: Pillow, psutil"

# ── Step 4: Prepare directories ───────────────────────────────────────────
info "Step 4/4 — Preparing directories..."
mkdir -p "$SCRIPT_DIR/output"
mkdir -p "$SCRIPT_DIR/logs"
ok "output/ and logs/ are ready."

# ── Optional: Detect desktop environment ──────────────────────────────────
echo ""
DE="${XDG_CURRENT_DESKTOP:-${DESKTOP_SESSION:-unknown}}"
info "Desktop environment detected: ${DE}"

if [[ "$DE" == "unknown" || -z "$DE" ]]; then
    warn "Desktop environment not detected from environment variables."
    warn "The wallpaper setter will try all available methods automatically."
fi

# ── Launch ────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD} ╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}${BOLD} ║  Launching InfoSphere Wallpaper Engine...                ║${RESET}"
echo -e "${CYAN}${BOLD} ║  Press Ctrl+C to stop cleanly at any time.               ║${RESET}"
echo -e "${CYAN}${BOLD} ╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""

cd "$SCRIPT_DIR"
$PYTHON main.py

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    fail "The engine exited with error code $EXIT_CODE."
    echo "  Check:  $SCRIPT_DIR/logs/wallpaper.log  for details."
    echo ""
fi
