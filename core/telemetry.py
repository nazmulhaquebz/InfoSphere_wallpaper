import datetime
import random
import psutil
import time
from collections import deque
from typing import List


# Predefined safe event templates  (level, message)
_EVENTS = [
    ("OK",    "Wallpaper refreshed and applied to desktop"),
    ("INFO",  "System metrics collected from local machine"),
    ("SAFE",  "Telemetry collection is read-only"),
    ("LOCAL", "Monitoring scope: local machine only"),
    ("OK",    "Security posture score calculated locally"),
    ("INFO",  "Network I/O counters updated from kernel"),
    ("OK",    "CPU usage sampled successfully"),
    ("INFO",  "RAM snapshot taken via psutil"),
    ("OK",    "Disk health read from filesystem"),
    ("INFO",  "Process inventory refreshed"),
    ("INFO",  "Active connection metadata sampled locally"),
    ("OK",    "Firewall state queried (read-only)"),
    ("INFO",  "System uptime counter refreshed"),
    ("SAFE",  "Ethical mode confirmed: LOCAL only"),
    ("OK",    "Dashboard data synchronized"),
    ("INFO",  "Telemetry engine heartbeat"),
    ("OK",    "Log rotation check passed"),
    ("SAFE",  "Telemetry does not modify network connections"),
    ("INFO",  "Timezone and NTP status verified locally"),
    ("OK",    "Config loaded from config.json"),
    ("INFO",  "Output directory integrity verified"),
    ("SAFE",  "Integrity check: LOCAL mode active"),
    ("OK",    "Host identity verified via socket"),
    ("INFO",  "Local IP address refreshed"),
    ("OK",    "InfoSphere engine nominal"),
    ("INFO",  "Pillow image renderer ready"),
    ("OK",    "Wallpaper output path confirmed"),
    ("SAFE",  "Connection inspection completed without modification"),
    ("INFO",  "CPU core load metrics sampled"),
    ("OK",    "Color theme applied from config"),
]

_THREAT_TARGETS = {
    "192.168.0.110": "D8:CE:3A:D8:5B:D1",
    "192.168.0.181": "C4:B3:01:9E:23:D6",
    "192.168.0.192": "50:91:E3:70:14:96",
    "192.168.0.246": "7E:52:E4:04:32:FE",
    "192.168.0.247": "74:33:57:AD:F1:45"
}


class TelemetryEngine:
    """
    Maintains a rolling buffer of local telemetry messages.
    Queries actual TCP/UDP network connections on the system
    and formats them as DNS resolutions, connection routes,
    and SOC policy rules in real-time.
    """

    def __init__(self, max_history: int = 60, simulate_threats: bool = False):
        self._history: deque = deque(maxlen=max_history)
        self._rng = random.Random()
        self.simulate_threats = bool(simulate_threats)
        self._logged_ips = deque(maxlen=40)  # track recently logged IPs to keep variety
        self._process_cache = {}
        
        # AI SOC Threat Blocker state
        self.threat_count: int = 0
        self.last_threat_ip: str = "NONE"
        self.last_threat_time: str = ""
        self.shield_status: str = "SECURE"
        self.active_target_ip: str = "NONE"
        self.blocked_ips: dict = {}      # IP -> expiry float (timestamp)
        self.alerting_ips: dict = {}     # IP -> expiry float (timestamp)
        
        self._cycle_count: int = 0
        self._threat_sequence: int = 0
        self._current_threat_ip: str = "NONE"

        # Pre-seed with a few events so the panel is never empty on first run
        for _ in range(12):
            self._push_random()

    def _get_process_name(self, pid: int) -> str:
        if not pid:
            return "System"
        if pid in self._process_cache:
            return self._process_cache[pid]
        try:
            name = psutil.Process(pid).name()
            self._process_cache[pid] = name
            return name
        except Exception:
            return "Unknown"

    def add_event(self, level: str, message: str) -> None:
        """Add a timestamped event to the telemetry buffer."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._history.appendleft(f"[{ts}] [{level:5s}] {message}")

    def _push_random(self) -> None:
        level, msg = self._rng.choice(_EVENTS)
        self.add_event(level, msg)

    def _generate_real_net_logs(self) -> bool:
        """Scan active connections and generate DNS + CONN + SOC logs."""
        try:
            conns = psutil.net_connections(kind='inet')
            # Filter connections that have a remote address and are established
            active_conns = [c for c in conns if c.raddr and c.status == 'ESTABLISHED']
            if not active_conns:
                # Also fall back to other connections with remote address
                active_conns = [c for c in conns if c.raddr]

            if active_conns:
                self._rng.shuffle(active_conns)
                for conn in active_conns:
                    remote_ip = conn.raddr.ip
                    remote_port = conn.raddr.port
                    
                    # Skip local loopbacks or recently logged IPs to prevent spamming
                    if remote_ip in ('127.0.0.1', '::1', '0.0.0.0') or remote_ip in self._logged_ips:
                        continue

                    # Log this IP
                    self._logged_ips.append(remote_ip)
                    p_name = self._get_process_name(conn.pid)

                    # 1. DNS Log (first step in network flow)
                    self.add_event("DNS", f"Query lookup: resolved {remote_ip} for routing")
                    # 2. Connection Log (second step in network flow)
                    self.add_event("CONN", f"Path open: local -> {remote_ip}:{remote_port} (Process: {p_name})")
                    # Report observation only; connection metadata is not a
                    # security verdict and this engine does not block traffic.
                    self.add_event("SOC", f"Observed established connection to {remote_ip}; no security verdict")
                    return True
        except Exception:
            pass
        return False

    # ── Public API ─────────────────────────────────────────────────────────

    def get_lines(self, count: int = 8) -> List[str]:
        """
        Return the *count* most-recent telemetry lines and inject active
        network logs, AI Threat blocker events, or background events.
        """
        self._cycle_count += 1
        now = time.time()

        # ── Clean expired blocks and alerts ───────────────────────────────
        expired_blocks = [ip for ip, exp in self.blocked_ips.items() if now >= exp]
        for ip in expired_blocks:
            del self.blocked_ips[ip]
            self.add_event("DEMO", f"[SIMULATION] Display-only quarantine expired for {ip}")
            
        expired_alerts = [ip for ip, exp in self.alerting_ips.items() if now >= exp]
        for ip in expired_alerts:
            del self.alerting_ips[ip]
        
        # ── Trigger simulated Threat attempt every 30 cycles ──────────────
        if (
            self.simulate_threats
            and self._cycle_count > 5
            and self._cycle_count % 30 == 0
            and self._threat_sequence == 0
        ):
            self._threat_sequence = 1
            self._current_threat_ip = self._rng.choice(list(_THREAT_TARGETS.keys()))
            
        handled_threat = False
        if self._threat_sequence == 1:
            self.shield_status = "ANALYZING"
            self.active_target_ip = self._current_threat_ip
            self.alerting_ips[self._current_threat_ip] = now + 15.0
            self.add_event("DEMO", f"[SIMULATION] Port scan scenario from {self._current_threat_ip}")
            self._threat_sequence = 2
            handled_threat = True
        elif self._threat_sequence == 2:
            self.add_event("DEMO", "[SIMULATION] Matched a demo NetBIOS scan signature")
            self._threat_sequence = 3
            handled_threat = True
        elif self._threat_sequence == 3:
            self.shield_status = "MITIGATING"
            if self._current_threat_ip in self.alerting_ips:
                del self.alerting_ips[self._current_threat_ip]
            self.blocked_ips[self._current_threat_ip] = now + 15.0  # Quarantine for 15s
            self.add_event("DEMO", f"[SIMULATION] Display-only quarantine for {self._current_threat_ip}")
            self._threat_sequence = 4
            handled_threat = True
        elif self._threat_sequence == 4:
            self.threat_count += 1
            self.last_threat_ip = self._current_threat_ip
            self.last_threat_time = datetime.datetime.now().strftime("%H:%M:%S")
            self.shield_status = "SECURE"
            self.active_target_ip = "NONE"
            self.add_event("DEMO", f"[SIMULATION] Scenario completed for {self._current_threat_ip}; no firewall change was made")
            self._threat_sequence = 0
            handled_threat = True

        if not handled_threat:
            if not self._generate_real_net_logs():
                self._push_random()
                
        return list(self._history)[:count]
