# 📜 Changelog & Version Control Ledger

All notable changes, architectural milestones, and security updates for **InfoSphere** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (`MAJOR.MINOR.PATCH`).

---

## 📅 Version Control Index

| Version | Release Date | Highlights | Type |
|---

## [2.6.3] - 2026-09-23

### 🚀 Highlights
- Full u2net High-Precision AI Matting: Replaced low-res u2netp with full 176 MB u2net neural network model across all 240 frames, preserving every fine wireframe grid line, point-cloud particle, and sunglasses reflection without edge erosion or jaggedness.
- High-Fidelity VP9 WebM Master (CRF 15): Encoded with Constant Quality CRF 15 at ~27 Mb/s with native 8-bit alpha (`yuva420p`) and embedded 48 kHz Opus audio, eliminating block compression and compression haze.
- Elimination of Destructive CSS Blurs: Removed double drop-shadow filters and nested 3D perspective transforms from the video element, allowing Chromium GPU compositor to render the hologram texture 1:1 razor-sharp.
- Permanent Top-Right Tactical Stationing: Re-anchored avatar directly in the user-specified top-right area (`top: 32px; right: 20px; width: 120px; height: 214px; z-index: 25;`), seamlessly bridging the clock panel and the pond water on a continuous, active walking loop.
- Synchronized Water & Fish Kinematics: Dynamically anchored feet contact at the top-right pond water surface with real-time bounding client calculation, emitting hydrodynamic ripples, Kelvin wake corridors, surface tension meniscus tension glow, and playful koi escort interactions.

## [2.6.2] - 2026-09-22

### 🚀 Highlights
- Native 1080x1920 Full HD Master Resolution: Zero downscaling applied; master video synthesized directly at 1080x1920 at 24 FPS with native 8-bit alpha channel (`yuva420p`, 9 Mbps bitrate, stereo Opus audio), guaranteeing razor-sharp clarity and pristine edge definition.
- 60 FPS Dynamic Walking Angles: Unified avatar kinematics into the 60 FPS animation loop with smoothstep easing, dynamic left/right horizontal facing, 3D yaw angle rotation, turn banking (`rotateZ`), and natural step cadence vertical bob and lateral sway.
- Walking ON Water Surface Kinematics: Added real-time liquid contact effects including a luminous cyan surface tension meniscus glow ring, dynamic translucent ground contact shadow, trailing hydrodynamic Kelvin V-wake waves, and footstep impact 3D water splashes.
- Playful Koi Fish Interactions: Friendly large koi (*Gold Ogon*, *Neon Cyan*, *Kohaku*) playfully escort the avatar, circling around footsteps and emitting glowing pearlescent bubbles (`pBubbles`) upon footstep ripples, while schooling tetras weave through the wake corridors.


## [2.6.1] - 2026-09-22

### 🚀 Highlights
- AI Neural Background Removal: Synthesized `Human/human_video/human_video_transparent.webm` using `u2netp` neural matting, achieving 100% transparent alpha (`rgba(0,0,0,0)`) on all background areas with zero dark box or bounding halo.
- Full Visual & Audio Preservation: 100% preserved the user's face, sunglasses, expression, dark navy suit, tie, shoes, and natural walking gestures.
- Native VP9 Yuva420p Hardware Acceleration: Direct WebM VP9 playback with native 8-bit alpha channel rendering directly on top of the Antigravity Pond caustics and koi fish.
- Audio Integration: Embedded stereo Opus speech track ("The digital lattice is now complete...") with interactive click-to-unmute toggle and visual cyan `VOICE ONLINE` HUD telemetry badge.
- Modular Python Pipeline: Packaged `Human/human_video/render_ai_transparent.py` with multi-threaded batching (4 worker threads) for lightning-fast rendering of any replacement video.


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
