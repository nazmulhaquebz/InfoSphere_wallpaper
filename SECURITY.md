# Security Policy & Responsible Disclosure

## Supported Versions

InfoSphere is actively maintained. Security patches and vulnerability fixes are released for the following versions:

| Version | Supported          | Status             |
| ------- | ------------------ | ------------------ |
| 2.6.x   | :white_check_mark: | Current Production |
| 2.5.x   | :white_check_mark: | Maintenance        |
| < 2.5.0 | :x:                | Deprecated         |

---

## Ethical Architecture & Privacy Guarantee

InfoSphere adheres to a **Privacy-First & Defensive-Only** architectural model:

1. **Loopback & Local Isolation**: All internal telemetry communication between the Python engine, Go Hub, and WebView2 runs strictly on `127.0.0.1` (loopback). No network sockets are exposed to the public internet or external subnets.
2. **Zero Inbound Telemetry / Zero Cloud Tracking**: No user metrics, keystrokes, personal files, browsing histories, or hardware identifiers are ever sent to external cloud servers or analytical trackers.
3. **In-Process Hardware Queries**: Network interface and ARP table readings use native Windows Win32 API (`GetIpNetTable` in `iphlpapi.dll`) in-process, preventing shell execution, command-line tampering, and console flickering.
4. **Defensive Intrusion Awareness**: The built-in SOC Analyzer is an observability tool intended to identify unauthorized MAC addresses on your own home or office Wi-Fi. It performs no invasive attacks or credential harvesting.
5. **Rust Native Tamper Detection (v2.0)**: Core engine files are FNV1a-64 hash-fingerprinted on every audit cycle. Any unauthorized modification since the initial baseline is immediately detected and reported as ATTENTION status with the specific modified file listed.

---

## Reporting a Vulnerability

We take the security and integrity of this project seriously. If you discover a security vulnerability or potential exploit, please do **NOT** open a public issue on GitHub.

Instead, please report it privately:

- **Security Contact**: Mohammad Nazmul Haque
- **Email**: [nazmul2121@gmail.com](mailto:nazmul2121@gmail.com)
- **Subject**: `[SECURITY VULNERABILITY] InfoSphere - <Issue Summary>`

Please include:
- A description of the vulnerability and affected components.
- Step-by-step instructions or proof-of-concept to reproduce the behavior.
- Proposed remediation or patch (if available).

We will acknowledge receipt within **48 hours**, investigate thoroughly, and release a patch promptly.
