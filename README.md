# InfoSphere · Tactical Cyber Live Wallpaper Engine v2.3.0

An ultra-modern, interactive, 60 FPS live cyber HUD wallpaper for Windows (10/11) with native `WorkerW` desktop embedding, real-time system telemetry, 3D geospatial threat defense globe, bioluminescent antigravity aquarium pond, and network SOC intrusion detection.

---

## ⚡ Quick Start: Setup Guide for Another Computer

Follow these simple steps to get InfoSphere running on any Windows 10/11 computer.

### 1. Prerequisites (First-Time Install)

Before running the project for the first time, make sure your computer has:

| Component | Requirement | Purpose | Download Link |
|---|---|---|---|
| **Operating System** | Windows 10 or Windows 11 (64-bit) | Live desktop embedding in `WorkerW` layer | — |
| **Python** | Python 3.10 or newer | Background telemetry engine (`main.py`) | [python.org/downloads](https://www.python.org/downloads/) |
| **WebView2 Runtime** | Microsoft Edge WebView2 | Renders the HTML5/CSS3/WebGL live wallpaper | [Microsoft WebView2](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) *(Usually already installed)* |
| **Git** *(optional)* | Any recent version | For cloning the repository | [git-scm.com](https://git-scm.com/downloads) |

> [!IMPORTANT]
> **When installing Python**: You **MUST** check the box that says:
> **`☑ Add python.exe to PATH`** at the bottom of the first installer screen!

*(Note: Go is **not** required for standard use because the precompiled `infosphere_wallpaper.exe` binary is already included!)*

---

### 2. Step-by-Step Setup ("One by One")

#### Step 1: Clone or Download the Repository
Open Command Prompt or PowerShell and clone the repository:
```cmd
git clone https://github.com/<your-username>/InfoSphere_wallpaper.git
cd InfoSphere_wallpaper
```
*Or click **Code -> Download ZIP** on GitHub, extract the folder anywhere on your computer (e.g., `C:\InfoSphere_wallpaper`), and open that folder.*

---

#### Step 2: Install Python Dependencies
Open PowerShell or Command Prompt inside the project folder and run:
```cmd
python -m pip install -r requirements.txt
```
This installs only 3 lightweight packages:
- `Pillow` (Display & imaging support)
- `psutil` (Hardware metrics: CPU, RAM, Disk, Network I/O counters)
- `speedtest-cli` (Network throughput benchmarks)

---

#### Step 3: Run the Live Wallpaper
Simply double-click:
👉 **`START_INFOSPHERE.bat`**

**What happens automatically:**
1. Silently launches the Python telemetry engine (`main.py` via `pythonw.exe`).
2. Launches the Go live wallpaper host (`infosphere_wallpaper.exe`).
3. Embeds the HUD seamlessly behind your desktop icons in Windows `WorkerW`.
4. Your desktop icons, shortcuts, and mouse clicks remain **100% interactive and functional** on top.
5. Zero popup terminal windows — runs completely silently in the background!

---

#### Step 4 (Optional): Enable Silent Auto-Start on Windows Login
If you want the wallpaper to start automatically whenever you turn on your computer:
👉 Double-click **`install_autostart_windows.bat`**

- Registers a silent startup entry in your Windows user registry (`HKCU\Run`).
- Starts with zero console popups when you log in.

To remove autostart at any time, run:
```cmd
remove_autostart_windows.bat
```

---

#### Step 5: How to Stop the Wallpaper
Whenever you want to stop the engine or return to a static desktop:
👉 Double-click **`STOP_INFOSPHERE.bat`**

- Cleanly terminates the Go engine, WebView2 instances, and Python telemetry engine, and releases port 8090.

---

## ⚙️ Configuration & Customization (`config.json`)

You can customize the engine by editing `config.json` in any text editor:

```json
{
  "refresh_interval_seconds": 1.0,
  "show_weather": true,
  "weather_city": "auto",
  "speedtest": {
    "enabled": true,
    "speed_interval_s": 15,
    "ping_host": "8.8.8.8"
  },
  "router": {
    "enabled": true,
    "ip": "192.168.0.1",
    "refresh_secs": 10
  }
}
```

- **Weather**: Auto-detects your city, temperature, and local ISP IP via Google IP reverse geocoding.
- **Speedtest**: Measures real-time download/upload and ping jitter every 15 seconds without choking your internet.
- **Subnet/Router**: Dynamically discovers connected devices on your Wi-Fi/LAN (phones, cameras, laptops) using native Win32 hardware ARP tables.

---

## 🛠️ Developer Notes: Recompiling the Go Binary (Optional)

If you have [Go 1.21+](https://go.dev/) installed and make changes to `core/wallpaper/wallpaper.go`:
```cmd
cd core\wallpaper
go build -ldflags="-H=windowsgui -s -w" -buildvcs=false -o ..\..\infosphere_wallpaper.exe .
```
This produces a compact, windowless Windows GUI executable that attaches WebView2 to the `WorkerW` desktop handle.

---

## 📄 License & Ethical Use Notice
Local system monitoring only. No unauthorized network scanning. Ethical use only.
Designed for personal workstation observability and cyber aesthetics.
