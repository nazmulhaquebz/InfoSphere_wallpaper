# 📜 Changelog & Version Control Ledger

All notable changes, architectural milestones, and security updates for **InfoSphere** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (`MAJOR.MINOR.PATCH`).

---

## 📅 Version Control Index

| Version | Release Date | Highlights | Type |
|---

## [2.6.0] - 2026-09-22

### 🚀 Highlights
- 3D/4D Live Hologram Video in Antigravity Pond, 10s Full-Sequence Walking Cadence, Speech Audio Toggle, and GPU Background Keying


## [2.5.1] - 2026-09-22

### 🚀 Highlights
- Live Walking Orbit-Dot Cyber Avatar in Antigravity Pond, 3D Orbital Rings, 5s Active Stay, and Modular Custom Photo Updater


## [2.5.0] - 2026-09-22

### 🚀 Highlights
- 5-Point Animated Cybernetic Hologram Avatar in Antigravity Pond with 100% Face Preservation, Laser Scanline Materialize, and Fluid Water Ripple Interaction


## [2.4.0] - 2026-09-21

### 🚀 Highlights
- GitHub Release Auto-Updater, 1-Click In-App Updater, HUD update badge, zero-data-loss pipeline, launcher sync, and security audit fixes
|---|---|---|
| [**2.4.0**](#240---2026-09-21) | **2026-09-21** | GitHub Release Auto-Updater, 1-Click In-App Updater, HUD update badge, zero-data-loss pipeline, launcher sync, and security audit fixes | Feature Release |
| [**2.3.0**](#230---2026-09-20) | **2026-09-20** | High-Contrast HUD · Zero-Popup Win32 SOC · 15s Speed Test · Global Portability | **Current Release** |
| [**2.2.0**](#220---2026-09-17) | **2026-09-17** | Native WorkerW Go Embedding · 60 FPS Pond · 3D Geospatial Defense Globe | Major Feature |
| [**2.1.0**](#210---2026-08-15) | **2026-08-15** | Unified JSON Telemetry Contract · Data Provenance · Multi-Monitor Spanning | Architecture |
| [**2.0.0**](#200---2026-06-10) | **2026-06-10** | Core Telemetry Engine · System Sensors · Initial Cyber Aesthetic | Initial Release |

---

## [2.3.0] - 2026-09-20

### 🚀 Added
- **Global Deployment & Portability**:
  - Removed all hardcoded drive letters (`F:\`) and user profiles (`C:\Users\nazmu`).
  - Added dynamic path and Python discovery in `launch_hidden.vbs`, `install_autostart_windows.bat`, and `ONE_CLICK_SETUP.bat`.
  - Added comprehensive `.gitignore` preventing bloat from runtime caches, bitmaps, and temporary debug scripts.
- **Ethical & Open-Source Policies**:
  - Added [`LICENSE`](LICENSE) (MIT License with an explicit Ethical Use & Responsible Monitoring Addendum).
  - Added [`SECURITY.md`](SECURITY.md) covering local loopback isolation, zero cloud tracking, and vulnerability disclosure.
  - Added [`CONTRIBUTING.md`](CONTRIBUTING.md) with guidelines for worldwide open-source contributors.
- **Real-Time 15-Second Network Benchmark**:
  - Ultra-fast micro-burst throughput testing with Cloudflare Dhaka BDIX edge endpoints.
  - Real-time Download Mbps, Upload Mbps, Latency, and Jitter sampling.
- **Google Local IP Weather Engine**:
  - Dynamic reverse IP geocoding with local ISP identification, city mapping, and hyper-local meteorological metrics.
- **Automated Version Control Manager**:
  - Created `bump_version.py` and `bump_version.bat` for one-command version and date updates.

### ⚡ Improved
- **Security Posture HUD Visibility**:
  - Upgraded gauge subtitle (`/ 100 SCORE`) from invisible dark slate (`#475569`) to high-contrast crisp silver (`#cbd5e1`) with bold weight.
  - Increased status line font size from `7.5px` to `9.5px` with cyber-cyan glowing bullet markers (`●`).
  - Replaced dark labels with bright silver-white typography for effortless legibility.
- **Zero-Flicker Background SOC Engine**:
  - Replaced legacy `subprocess.check_output(['arp', '-a'])` with native in-process Win32 `GetIpNetTable` in `iphlpapi.dll`.
  - Eliminated transient command prompt popups/flashing on system boot.
  - Added dynamic subnet prefix resolution (`host_ip.rsplit(".", 1)[0] + "."`) allowing automatic adaptation across home and office Wi-Fi networks.

### 🔒 Security
- Mutex upgraded to system-wide `Global\InfoSphereWallpaperEngine` to strictly prevent duplicate instances across Windows sessions.
- In-process ARP queries eliminate attack surface from command-line injection or shell hijacking.

---

## [2.2.0] - 2026-09-17

### 🚀 Added
- **Native Windows `WorkerW` Desktop Embedding**:
  - Compiled Go host binary (`infosphere_wallpaper.exe`) that attaches Microsoft Edge WebView2 directly into the Windows desktop shell (`WorkerW`).
  - Preserves 100% desktop icon interaction, dragging, clicking, and context menus.
- **60 FPS Bioluminescent Antigravity Pond**:
  - Fluid canvas rendering 10 dynamic Japanese Koi and Goldfish specimens with realistic spline swimming physics.
  - SVG Fractal Noise displacement filter generating organic water wave ripple caustics.
- **3D Geospatial Threat Defense Matrix**:
  - 4,000+ continent coordinate point-cloud sphere.
  - Parabolic protocol-colored laser attack vectors and critical BD infrastructure nodes (Dhaka BDIX, Kuakata SMW5, Cox's Bazar SMW4).
- **6-Theme Palette Switcher**:
  - Instant client-side switching between Cyber Cyan, Emerald Matrix, Imperial Gold, Stealth Violet, Crimson Alert, and Titanium OLED.

### ⚡ Improved
- Real-time Server-Sent Events (SSE) hub at port 8090 replacing polling for sub-millisecond telemetry synchronization.

---

## [2.1.0] - 2026-08-15

### 🚀 Added
- **Unified Telemetry Contract (`output/system_snapshot.json`)**:
  - Standardized JSON contract with explicit data provenance labels (`MEASURED`, `ESTIMATED`, `CACHED`, `DERIVED`, `VISUALIZATION`).
  - Atomic double-buffer file writing preventing file-lock race conditions.
- **Multi-Monitor & DPI Spanning**:
  - Virtual desktop coordinate calculation supporting ultra-wide, multi-monitor, and high-DPI scaling displays.

---

## [2.0.0] - 2026-06-10

### 🚀 Added
- Initial project architecture and core telemetry collection daemon (`main.py`).
- Hardware sensors for CPU, RAM, Disks, and Network Interface I/O counters via `psutil`.
- Basic cyber-themed wallpaper rendering pipeline.
