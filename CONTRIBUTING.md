# Contributing to InfoSphere

Thank you for your interest in contributing to **InfoSphere**! We welcome ethical security researchers, UI/UX designers, Python/Go developers, and open-source enthusiasts worldwide.

---

## Code of Conduct & Ethical Standards

All contributors and community members must abide by our ethical principles:
- **Defensive & Ethical**: Contributions must enhance security observability, visualization, efficiency, or stability. Features intended for offensive hacking, network penetration, or malicious spying will be rejected immediately.
- **Respectful & Inclusive**: We maintain an open, welcoming, and harassment-free environment for everyone regardless of experience level, background, or identity.

---

## Development Workflow

1. **Fork the Repository**: Create your personal fork on GitHub.
2. **Clone Locally**:
   ```bash
   git clone https://github.com/<your-username>/InfoSphere_wallpaper.git
   cd InfoSphere_wallpaper
   ```
3. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/enhanced-telemetry-hud
   ```
4. **Make Your Changes**:
   - Keep scripts modular and portable across Windows 10 and Windows 11.
   - Never introduce hardcoded absolute paths, personal usernames, or unmanaged subprocess windows.
   - Run tests using `python -m unittest discover -s tests -t .`.
5. **Commit with Clear Messages**:
   ```bash
   git commit -m "feat(telemetry): add GPU temperature estimation metrics"
   ```
6. **Push and Open a Pull Request**:
   Push to your branch and submit a PR against `main`. Provide a clear description of the problem solved and test results.

---

## Architectural Guidelines

- **Zero-Flicker Execution**: Never use visible shell subprocesses (`subprocess.check_output(['cmd', ...])`). Use native Win32 APIs via `ctypes` or Go syscalls to prevent console popup windows.
- **Atomic File Operations**: All telemetry JSON snapshots (`output/system_snapshot.json`) must be written atomically via temporary files and renamed in-place to prevent reader race conditions.
- **Performance Budget**: The entire engine (Python + Go + WebView2) should consume < 1.5% CPU and < 150 MB RAM on modern hardware.
