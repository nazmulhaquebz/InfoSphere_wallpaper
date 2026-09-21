"""
InfoSphere Cyber Live Wallpaper Engine
core/router_monitor.py  v6.5

TP-Link Archer Router Monitor - Maximum Discovery Edition
==========================================================
NEW IN v6.5 - ROOT-CAUSE FIXES
================================
[FIX-A] Router login tries password encoding variants plus a cookie-based
        session fallback (TP-Link Archer/AX).
        Login failure is now printed to the log with the exact HTTP reason.

[FIX-B] DHCP lease table is queried SEPARATELY from the online-hosts table so
        even if the hosts_info API fails we still get real hostnames from DHCP.
        Hostname map (MAC -> name) is built and applied to every discovered device.

[FIX-C] mDNS multicast (224.0.0.251 : 5353) PTR queries resolve device names
        even when the router API is completely inaccessible.  Works for
        Apple, Android 11+, modern Windows, and most IoT devices.

[FIX-D] Band/signal info is merged from a dedicated wireless-station table
        query so 5 GHz devices are correctly classified even when the main
        hosts_info table omits the flag.

[FIX-E] TX/RX for ARP-discovered devices: when router API data is available
        it is merged into ARP entries so TX/RX MB shows real values.

[FIX-F] _resolve_names_parallel now runs mDNS -> DNS -> NetBIOS in priority
        order and the result always replaces vendor/synthetic labels.

[FIX-G] fetch() is always a plain dict (backward-compat).  Background thread
        guarantees non-blocking reads at any time.

SAFETY NOTICE:
  OK Only works on routers you own and have admin access to
  OK Uses YOUR credentials (username + password you set)
  OK Read-only - queries device list and stats, changes nothing
  OK Local network only - all requests go to 192.168.x.x
  NO Never use on routers you do not own
  NO Never use to monitor others without their consent

CONFIGURATION (in config.json):
  "router": {
    "enabled":      true,
    "ip":           "192.168.0.1",
    "username":     "admin",
    "password":     "your_router_password",
    "refresh_secs": 5
  }
"""

from __future__ import annotations

import base64
import os
import hashlib
import http.cookiejar
import ipaddress
import json
import logging
import platform
import re
import socket
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# -- Optional dependency -------------------------------------------------------
try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

_IS_WINDOWS: bool = platform.system() == "Windows"

# -- Constants -----------------------------------------------------------------
_VERSION            = "6.6"
_SESSION_TTL        = 270
_DEFAULT_REFRESH    = 5.0
_REQUEST_TIMEOUT    = 4.0
_MAX_CLIENTS        = 32
_HOSTNAME_TTL       = 300        # seconds; mDNS/DNS results cached
_MDNS_TIMEOUT       = 0.4        # seconds per mDNS query
_BW_SPIKE_CAP       = 500.0      # MB/s sanity cap

_LOGIN_PATH   = "/cgi-bin/luci/;stok=/rpc/data"
_API_TPL      = "/cgi-bin/luci/;stok={stok}/rpc/data"

# All TP-Link payload variants we attempt
_PAYLOAD_HOSTS    = {"hosts_info": {"table": "online"},    "method": "get"}
_PAYLOAD_DHCP     = {"hosts_info": {"table": "dhcp_lease"},"method": "get"}
_PAYLOAD_DHCP2    = {"dhcpd":      {"table": "lease"},     "method": "get"}
_PAYLOAD_WIRELESS = {"wireless":   {"table": "station"},   "method": "get"}

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# TP-Link tpEncrypt XOR scheme (from tpEncrypt.new.js / newer Archer firmware)
# su.encrypt(text, key, alphabet) — each char is XOR-indexed into alphabet
# ---------------------------------------------------------------------------
_TP_ENCRYPT_ALPHABET = (
    "yLwVl0zKqws7LgKPRQ84Mdt708T1qQ3Ha7xv3H7NyU84p21BriUWBU43odz3iP4r"
    "BL3cD02KZciXTysVXiV8ngg6vL48rPJyAUw0HurW20xqxv9aYb4M9wK1Ae0wlro5"
    "10qXeU07kV57fQMc8L6aLgMLwygtc0F10a0Dg70TOoouyFhdysuRMO51yY5ZlOZZL"
    "Eal1h0t9YQW0Ko7oBwmCAHoic4HYbUyVeU3sfQ1xtXcPcf1aT303wAQhv66qzW"
)
_TP_ENCRYPT_KEY      = "RDpbLfCPsJZ7fiv"


def _tp_encrypt(text: str, key: str = _TP_ENCRYPT_KEY,
                alphabet: str = _TP_ENCRYPT_ALPHABET) -> str:
    """
    Python port of the JS su.encrypt() function from tpEncrypt.new.js.
    Used by newer TP-Link Archer C6 / AX firmware for password encoding.
    """
    n = alphabet
    p = len(n)
    h = len(text)
    a = len(key)
    c = max(h, a)
    out = []
    for y in range(c):
        i_v = 187
        s_v = 187
        if h <= y:
            s_v = ord(key[y])
        elif a <= y:
            i_v = ord(text[y])
        else:
            i_v = ord(text[y])
            s_v = ord(key[y])
        out.append(n[(i_v ^ s_v) % p])
    return "".join(out)

_VENDORS: Dict[str, str] = {
    "38-d5-7a": "Dell",    "50-91-e3": "Reecam",  "74-33-57": "Huawei",
    "bc-7f-a4": "Samsung", "d8-ce-3a": "Xiaomi",  "a4-5e-60": "Xiaomi",
    "ac-de-48": "Apple",   "3c-5a-b4": "Google",  "cc-47-40": "Apple",
    "b0-a4-60": "TP-Link", "8c-f5-a3": "Xiaomi",  "44-6a-2e": "Apple",
    "dc-a6-32": "RPi",     "b8-27-eb": "RPi",     "00-50-56": "VMware",
    "08-00-27": "VBox",    "52-54-00": "QEMU",    "18-31-bf": "Amazon",
    "fc-65-de": "Xiaomi",  "64-b5-c6": "Xiaomi",  "34-ce-00": "Xiaomi",
    "7c-f1-7e": "TP-Link", "c4-b3-01": "Apple",   "7e-52-e4": "Android",
}

# ---------------------------------------------------------------------------
# LOCAL HOST OVERRIDES  — statically known devices on THIS network
# Populated from ARP + NetBIOS scan at first run.  MAC -> friendly name.
# Format: uppercase colon-separated MAC (e.g. "C4:B3:01:9E:23:D6")
# ---------------------------------------------------------------------------
_LOCAL_HOSTS: Dict[str, str] = {
    "7C:F1:7E:88:5A:83": "TP-Link Router",
    "D8:CE:3A:D8:5B:D1": "Xiaomi-Phone",
    "74:33:57:AD:F1:45": "Huawei-Phone",
    "C4:B3:01:9E:23:D6": "MacBookAir",
    "50:91:E3:70:14:96": "Reecam-Camera",
    "7E:52:E4:04:32:FE": "Android-Phone",
}

_BAND_5G   = "5 GHz"
_BAND_24G  = "2.4 GHz"
_BAND_WLAN = "WLAN"
_BAND_WIRE = "Wired"
_BAND_LAN  = "Local"


# =============================================================================
#  DATA MODELS
# =============================================================================

@dataclass
class NetworkClient:
    name:            str
    ip:              str
    mac:             str
    band:            str
    rssi:            int
    tx_mb:           float
    rx_mb:           float
    tx_mbps:         float = 0.0
    rx_mbps:         float = 0.0
    is_self:         bool  = False
    is_rogue:        bool  = False
    soc_status:      str   = "VERIFIED"
    device_type:     str   = "general"
    hostname_source: str   = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":            self.name,
            "ip":              self.ip,
            "mac":             self.mac,
            "band":            self.band,
            "rssi":            self.rssi,
            "tx_mb":           self.tx_mb,
            "rx_mb":           self.rx_mb,
            "tx_mbps":         self.tx_mbps,
            "rx_mbps":         self.rx_mbps,
            "is_self":         self.is_self,
            "is_rogue":        self.is_rogue,
            "soc_status":      self.soc_status,
            "device_type":     self.device_type,
            "hostname_source": self.hostname_source,
            # Backward-compat aliases for older dashboard code
            "active":          True,
        }


# =============================================================================
#  MAIN CLASS
# =============================================================================

class RouterMonitor:
    VERSION: str = _VERSION

    def __init__(
        self,
        config: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._log = logger or logging.getLogger("InfoSphere.RouterMonitor")
        cfg = config.get("router", {})

        self.enabled:  bool  = bool(cfg.get("enabled", False))
        self.ip:       str   = os.environ.get("INFOSPHERE_ROUTER_IP", cfg.get("ip", "192.168.0.1")).strip()
        self.username: str   = os.environ.get("INFOSPHERE_ROUTER_USERNAME", cfg.get("username", "")).strip()
        password_env = str(
            cfg.get("password_env", "INFOSPHERE_ROUTER_PASSWORD")
        ).strip()
        legacy_password = str(cfg.get("password", "")).strip()
        self.password: str = os.environ.get(password_env, legacy_password).strip()
        # Support both "refresh_secs" and "refresh" key names
        self.refresh:  float = float(
            cfg.get("refresh_secs", cfg.get("refresh", _DEFAULT_REFRESH))
        )

        try:
            router_address = ipaddress.ip_address(self.ip)
            is_local = (
                router_address.version == 4
                and (router_address.is_private or router_address.is_link_local)
            )
        except ValueError:
            is_local = False

        if self.enabled and not is_local:
            self.enabled = False
            self._log.error(
                "[RouterMonitor] Refusing non-local or invalid router IP: %r",
                self.ip,
            )

        self._base:          str = f"http://{self.ip}"
        self._subnet_prefix: str = self.ip.rsplit(".", 1)[0] + "."

        # -- Session state -----------------------------------------------------
        self._stok:       str   = ""
        self._stok_born:  float = 0.0
        self._login_fail: int   = 0      # consecutive login failures

        # Cookie-jar for cookie-based TP-Link auth fallback
        self._cookiejar = http.cookiejar.CookieJar()
        self._opener    = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookiejar)
        )

        self._lock: threading.RLock = threading.RLock()

        # -- Caches ------------------------------------------------------------
        self._snapshot:  Dict[str, Any] = self._empty_dict()
        self._snap_time: float = 0.0
        if not self.enabled:
            self._snapshot["status"] = "DISABLED"
            self._snapshot["router_ip"] = self.ip

        # Bandwidth delta: key -> (tx_bytes, rx_bytes, timestamp)
        self._bw_prev: Dict[str, Tuple[float, float, float]] = {}

        # Hostname cache: IP -> (name, source, cached_at)
        self._name_cache: Dict[str, Tuple[str, str, float]] = {}
        self._name_lock   = threading.Lock()

        # DHCP hostname map built from router: MAC -> hostname
        self._dhcp_names: Dict[str, str] = {}

        # Wireless station map built from router: MAC -> (band, rssi)
        self._wifi_info: Dict[str, Tuple[str, int]] = {}

        # Host IP cached
        self._host_ip_val: Optional[str] = None

        self._running = False
        self._thread: Optional[threading.Thread] = None

        if self.enabled:
            threading.Thread(
                target=self._compile_scanner, daemon=True, name="Scanner-Compile"
            ).start()
            self._start()

        self._log.info(
            "[RouterMonitor] v%s target=%s refresh=%.1fs psutil=%s",
            _VERSION, self.ip, self.refresh, _HAS_PSUTIL,
        )

    def _compile_scanner(self) -> None:
        """In-process NetworkSOC analyzer is used natively."""
        pass

    def _run_go_scanner(self) -> List[NetworkClient]:
        """In-process native Win32 ARP scanner and NetworkSOC analyzer."""
        try:
            from core.network_soc import NetworkSOC
            if not hasattr(self, '_soc_analyzer') or self._soc_analyzer is None:
                self._soc_analyzer = NetworkSOC(logger=self._log)
            soc_res = self._soc_analyzer.scan_network()
            clients: List[NetworkClient] = []
            for d in soc_res.get("clients", []):
                if d.get("is_self"):
                    continue
                clients.append(NetworkClient(
                    name=d["name"],
                    ip=d["ip"],
                    mac=d["mac"],
                    band=d["band"],
                    rssi=d["rssi"],
                    tx_mb=d.get("tx_mb", 0.0),
                    rx_mb=d.get("rx_mb", 0.0),
                    tx_mbps=d.get("tx_mbps", 0.0),
                    rx_mbps=d.get("rx_mbps", 0.0),
                    is_self=d.get("is_self", False),
                    is_rogue=d.get("is_rogue", False),
                    soc_status=d.get("soc_status", "VERIFIED"),
                    device_type=d.get("device_type", "general"),
                    hostname_source="soc_analyzer"
                ))
            return clients
        except Exception as e:
            self._log.debug(f"[RouterMonitor] NetworkSOC invocation notice: {e}")
            return self._fetch_arp()

    # -- Public API ------------------------------------------------------------

    def fetch(self) -> Dict[str, Any]:
        """Return latest snapshot as a plain dict.  Never blocks."""
        with self._lock:
            return dict(self._snapshot)

    def stop(self) -> None:
        with self._lock:
            self._running = False

    # -- Background loop -------------------------------------------------------

    def _start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="RouterMonitor"
        )
        self._thread.start()

    def _loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
            t0 = time.perf_counter()
            try:
                snap = self._build_snapshot()
                with self._lock:
                    self._snapshot  = snap
                    self._snap_time = time.time()
            except Exception as exc:
                self._log.error("[RouterMonitor] Loop error: %s", exc, exc_info=True)
            elapsed = time.perf_counter() - t0
            time.sleep(max(0.5, self.refresh - elapsed))

    # -- Snapshot builder ------------------------------------------------------

    def _build_snapshot(self) -> Dict[str, Any]:
        t0 = time.perf_counter()
        clients: List[NetworkClient] = []
        status         = "OFFLINE"
        session_method = "none"

        # Step 1: Establish router session
        api_ok = self._ensure_session()
        api_clients = []
        if api_ok:
            # Step 2a: Fetch DHCP lease table -> real hostnames per MAC
            self._refresh_dhcp_names()
            # Step 2b: Fetch wireless station table -> real band/RSSI
            self._refresh_wifi_info()
            # Step 2c: Fetch online hosts with TX/RX bytes
            api_clients, ok = self._fetch_online_hosts()

        # Step 2: Run Go scanner
        go_clients = self._run_go_scanner()

        if go_clients:
            status         = "ONLINE [Go Scanner]"
            session_method = "go_scanner"
            if api_clients:
                status         = "ONLINE [Go + Router API]"
                session_method = "go_router_api"
                
                # Index API clients by MAC and IP
                api_by_mac = {c.mac: c for c in api_clients if c.mac not in ("", "SELF")}
                api_by_ip = {c.ip: c for c in api_clients if c.ip}
                
                for c in go_clients:
                    match = api_by_mac.get(c.mac) or api_by_ip.get(c.ip)
                    if match:
                        c.tx_mb = match.tx_mb
                        c.rx_mb = match.rx_mb
                        c.band  = match.band
                        c.rssi  = match.rssi
                        if match.name and match.hostname_source in ("router", "dhcp"):
                            c.name = match.name
                            c.hostname_source = match.hostname_source
                            
                # Add any API clients that were not found by the Go scanner
                go_ips = {c.ip for c in go_clients}
                for c in api_clients:
                    if c.ip not in go_ips:
                        go_clients.append(c)
            clients = go_clients
        else:
            # Fallback to old ARP logic if Go scanner is not working/compiled yet
            if api_clients:
                clients        = api_clients
                status         = "ONLINE [Router API]"
                session_method = "router_api"
            else:
                clients        = self._fetch_arp()
                status         = "ONLINE [ARP + mDNS]"
                session_method = "arp_mdns"

        # Step 4: Merge DHCP/wifi info into clients (primarily useful if we fell back to ARP)
        self._merge_router_data(clients)

        # Step 5: Host node
        host    = self._build_host()
        clients = [c for c in clients if c.ip != host.ip]

        # Step 6: Resolve ALL hostnames (mDNS -> DNS -> NetBIOS -> label)
        self._resolve_all(clients)

        clients.sort(key=lambda c: _last_octet(c.ip))
        all_nodes: List[NetworkClient] = [host] + clients

        # Step 7: Delta bandwidth
        self._apply_bw(all_nodes)
        all_nodes = all_nodes[:_MAX_CLIENTS]

        ms = round((time.perf_counter() - t0) * 1000, 1)
        self._log.debug(
            "[RouterMonitor] Snapshot %s - %d nodes - %.1f ms",
            status, len(all_nodes), ms
        )

        return {
            "status":           status,
            "router_ip":        self.ip,
            "clients":          [c.to_dict() for c in all_nodes],
            "total_online":     len(all_nodes),
            "tx_total_mb":      round(sum(c.tx_mb   for c in all_nodes), 2),
            "rx_total_mb":      round(sum(c.rx_mb   for c in all_nodes), 2),
            "tx_total_mbps":    round(sum(c.tx_mbps for c in all_nodes), 4),
            "rx_total_mbps":    round(sum(c.rx_mbps for c in all_nodes), 4),
            "band_5_count":     sum(1 for c in all_nodes if c.band == _BAND_5G),
            "band_24_count":    sum(1 for c in all_nodes if c.band in (_BAND_24G, _BAND_WLAN)),
            "wired_count":      sum(1 for c in all_nodes if c.band == _BAND_WIRE),
            "wlan_count":       sum(1 for c in all_nodes if c.band == _BAND_WLAN),
            "local_count":      sum(1 for c in all_nodes if c.band == _BAND_LAN),
            "scan_ms":          ms,
            "session_method":   session_method,
            "timestamp":        time.time(),
        }

    # -- Session management ----------------------------------------------------

    def _ensure_session(self) -> bool:
        if not self.password:
            if self._login_fail == 0:
                self._log.warning(
                    "[Router] Authentication skipped: set the configured "
                    "password environment variable to enable router API access."
                )
                self._login_fail = 1
            return False
        if self._stok and (time.time() - self._stok_born) < _SESSION_TTL:
            return True
        # Back-off: if we've failed, wait longer before retrying to avoid lockout
        if self._login_fail >= 1:
            # Use exponential backoff capped at 120s (TP-Link lockout window)
            wait = min(120, 15 * (2 ** (self._login_fail - 1)))
            if (time.time() - self._stok_born) < wait:
                return False
        return self._login()

    def _login(self) -> bool:
        """
        TP-Link Archer C6 multi-mode login  v6.6
        Tries encoding variants in priority order:
          1. tpEncrypt XOR  (newer Archer C6/AX firmware — tpEncrypt.new.js)
          2. MD5-upper      (classic TP-Link Luci API)
          3. MD5-lower
          4. plain text
          5. Base64
          6. Cookie-based (SPA routers)
        Backs off on repeated failure to avoid IP-level lockout.
        """
        url = f"{self._base}{_LOGIN_PATH}"
        pw  = self.password

        # All encoding variants of the password
        pw_md5u   = hashlib.md5(pw.encode()).hexdigest().upper()
        pw_md5l   = hashlib.md5(pw.encode()).hexdigest().lower()
        pw_b64    = base64.b64encode(pw.encode()).decode("ascii")
        pw_xor    = _tp_encrypt(pw)   # TP-Link tpEncrypt.new.js XOR scheme

        variants = [
            ("tpEncrypt-XOR", pw_xor),
            ("MD5-upper",     pw_md5u),
            ("MD5-lower",     pw_md5l),
            ("plain",         pw),
            ("base64",        pw_b64),
        ]

        consecutive_5 = 0   # track how many times we get error_code=5
        for variant_name, v in variants:
            self._stok = ""
            payload    = {"method": "do", "login": {"password": v}}
            resp       = self._post(url, payload)

            if resp is None:
                continue

            err = resp.get("error_code", resp.get("errorcode", 0))
            try:
                err_int = int(err)
            except (TypeError, ValueError):
                err_int = 0

            stok = resp.get("stok", "")
            if isinstance(stok, str) and stok:
                self._stok       = stok
                self._stok_born  = time.time()
                self._login_fail = 0
                self._log.info(
                    "[Router] Login OK via %s (stok=%s...)",
                    variant_name, stok[:8]
                )
                return True

            if err_int == 5:
                consecutive_5 += 1
                if consecutive_5 >= 2:
                    # Router is genuinely in lockout — stop hammering
                    self._login_fail += 1
                    self._stok_born   = time.time()
                    self._log.warning(
                        "[Router] IP lockout (error_code=5 x%d). "
                        "Backing off. Open http://%s in browser to unlock.",
                        consecutive_5, self.ip
                    )
                    return False
                # Single 5 might just be wrong-password on newer firmware — continue
                continue

            self._log.debug(
                "[Router] %s rejected — error_code=%s resp=%s",
                variant_name, err, str(resp)[:80]
            )

        # Cookie-based fallback (newer SPA-style routers)
        if self._cookie_login():
            return True

        self._login_fail += 1
        self._stok_born   = time.time()
        self._log.warning(
            "[Router] All login variants failed (fail #%d). "
            "Open http://%s in a browser and verify the configured credentials.",
            self._login_fail, self.ip,
        )
        return False

    def _cookie_login(self) -> bool:
        """
        TP-Link Archer AX / newer models: login via cookie, not stok URL.
        Returns True and sets stok on success.
        """
        url     = f"{self._base}/cgi-bin/luci/"
        pw_md5  = hashlib.md5(self.password.encode()).hexdigest().upper()
        payload = f"username={self.username}&password={pw_md5}"

        try:
            req = urllib.request.Request(
                url, data=payload.encode(), method="POST"
            )
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            req.add_header("User-Agent",   _USER_AGENT)
            req.add_header("Referer",      f"{self._base}/")
            with self._opener.open(req, timeout=_REQUEST_TIMEOUT) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if "logout" in body.lower() or "stok" in body.lower():
                    m = re.search(r"stok=([a-f0-9]+)", body)
                    if m:
                        self._stok       = m.group(1)
                        self._stok_born  = time.time()
                        self._login_fail = 0
                        self._log.info("[Router] Cookie-based login OK.")
                        return True
        except Exception as exc:
            self._log.debug("[Router] Cookie login failed: %s", exc)
        return False

    # -- Router data fetchers --------------------------------------------------

    def _fetch_online_hosts(self) -> Tuple[List[NetworkClient], bool]:
        """Fetch the online-hosts table from the router."""
        url  = f"{self._base}{_API_TPL.format(stok=self._stok)}"
        resp = self._post(url, _PAYLOAD_HOSTS)

        if resp is None:
            self._stok = ""
            return [], False

        info = resp.get("hosts_info", {})
        if not isinstance(info, dict):
            self._stok = ""
            return [], False

        clients: List[NetworkClient] = []
        for raw in info.get("online", []):
            ip = str(raw.get("ip", "")).strip()
            if not ip:
                continue

            mac  = _fmt_mac(str(raw.get("mac", "")))
            name = self._best_name_from_router(raw, mac, ip)

            wifi = str(raw.get("wifi", "")).lower()
            if "5" in wifi:
                band = _BAND_5G
            elif wifi in ("1", "2", "true", "yes", "wlan"):
                band = _BAND_24G
            else:
                band = _BAND_WIRE

            # Override band with wireless station table if available [FIX-D]
            if mac in self._wifi_info:
                band, _ = self._wifi_info[mac]

            try:
                rssi = max(0, min(100, int(raw.get("signal", 80))))
            except (TypeError, ValueError):
                rssi = 80
            if mac in self._wifi_info:
                _, rssi = self._wifi_info[mac]

            clients.append(NetworkClient(
                name            = name,
                ip              = ip,
                mac             = mac,
                band            = band,
                rssi            = rssi,
                tx_mb           = _b2mb(raw.get("tx_bytes", 0)),
                rx_mb           = _b2mb(raw.get("rx_bytes", 0)),
                hostname_source = "router",
            ))
        return clients, True

    def _refresh_dhcp_names(self) -> None:
        """
        [FIX-B] Query the DHCP lease table and build MAC->hostname map.
        Tries two payload variants for different TP-Link firmware versions.
        """
        url = f"{self._base}{_API_TPL.format(stok=self._stok)}"
        for payload in (_PAYLOAD_DHCP, _PAYLOAD_DHCP2):
            resp = self._post(url, payload)
            if not resp:
                continue

            entries = (
                resp.get("hosts_info", {}).get("dhcp_lease", [])
                or resp.get("dhcpd", {}).get("lease", [])
                or []
            )
            for e in entries:
                mac  = _fmt_mac(str(e.get("mac", "")))
                name = str(e.get("hostname", e.get("name", ""))).strip()
                if mac and name and name not in ("*", "-", "unknown"):
                    self._dhcp_names[mac] = name
            if self._dhcp_names:
                self._log.debug(
                    "[Router] DHCP names loaded: %d entries",
                    len(self._dhcp_names)
                )
                return

    def _refresh_wifi_info(self) -> None:
        """
        [FIX-D] Query wireless station table to get REAL band and RSSI.
        Populates self._wifi_info: MAC -> (band_str, rssi_int).
        """
        url  = f"{self._base}{_API_TPL.format(stok=self._stok)}"
        resp = self._post(url, _PAYLOAD_WIRELESS)
        if not resp:
            return

        stations = resp.get("wireless", {}).get("station", [])
        for s in stations:
            mac  = _fmt_mac(str(s.get("mac", "")))
            freq = str(s.get("frequency", s.get("band", ""))).lower()
            if "5" in freq:
                band = _BAND_5G
            else:
                band = _BAND_24G
            try:
                rssi = max(0, min(100, abs(int(s.get("rssi", s.get("signal", -60))))))
            except (TypeError, ValueError):
                rssi = 70
            if mac:
                self._wifi_info[mac] = (band, rssi)

    def _best_name_from_router(self, raw: dict, mac: str, ip: str) -> str:
        """
        Pick the best hostname in priority order:
          1. Local static overrides (scanned from this network)
          2. DHCP lease table (most accurate)
          3. hosts_info hostname field
          4. Vendor label
        """
        # Local known devices (static table from network scan)
        if mac in _LOCAL_HOSTS:
            return _LOCAL_HOSTS[mac]
        if mac in self._dhcp_names:
            return self._dhcp_names[mac]
        hn = str(raw.get("hostname", "")).strip()
        if hn and hn not in ("*", "-", "unknown", "(unknown)", ""):
            return hn
        return _vendor_label(mac, ip)

    # -- ARP scanner -----------------------------------------------------------

    def _fetch_arp(self) -> List[NetworkClient]:
        skip = {self.ip, self._host_ip()}
        result: List[NetworkClient] = []

        if _IS_WINDOWS:
            try:
                import ctypes
                from ctypes import wintypes

                class MIB_IPNETROW(ctypes.Structure):
                    _fields_ = [
                        ('dwIndex', wintypes.DWORD),
                        ('dwPhysAddrLen', wintypes.DWORD),
                        ('bPhysAddr', ctypes.c_byte * 8),
                        ('dwAddr', wintypes.DWORD),
                        ('dwType', wintypes.DWORD),
                    ]

                class MIB_IPNETTABLE(ctypes.Structure):
                    _fields_ = [
                        ('dwNumEntries', wintypes.DWORD),
                        ('table', MIB_IPNETROW * 1),
                    ]

                iphlpapi = ctypes.windll.iphlpapi
                size = wintypes.ULONG(0)
                iphlpapi.GetIpNetTable(None, ctypes.byref(size), False)
                if size.value > 0:
                    buf = ctypes.create_string_buffer(size.value)
                    pTable = ctypes.cast(buf, ctypes.POINTER(MIB_IPNETTABLE))
                    if iphlpapi.GetIpNetTable(pTable, ctypes.byref(size), False) == 0:
                        num = pTable.contents.dwNumEntries
                        row_size = ctypes.sizeof(MIB_IPNETROW)
                        for i in range(num):
                            row = MIB_IPNETROW.from_buffer(buf, 4 + i * row_size)
                            if row.dwPhysAddrLen == 6:
                                raw_addr = row.dwAddr
                                ip = f"{raw_addr & 0xFF}.{(raw_addr >> 8) & 0xFF}.{(raw_addr >> 16) & 0xFF}.{(raw_addr >> 24) & 0xFF}"
                                if not ip.startswith(self._subnet_prefix) or ip in skip:
                                    continue
                                mac = ":".join(f"{b & 0xFF:02X}" for b in row.bPhysAddr[:6])
                                if _is_broadcast(mac):
                                    continue
                                result.append(NetworkClient(
                                    name            = _vendor_label(mac, ip),
                                    ip              = ip,
                                    mac             = mac,
                                    band            = _BAND_WLAN,
                                    rssi            = 70,
                                    tx_mb           = 0.0,
                                    rx_mb           = 0.0,
                                    hostname_source = "pending",
                                ))
                        return result
            except Exception as e:
                self._log.debug("[RouterMonitor] Win32 GetIpNetTable notice: %s", e)

        return result

    def _merge_router_data(self, clients: List[NetworkClient]) -> None:
        """
        [FIX-E] For ARP-discovered clients, apply local overrides first,
        then DHCP hostnames, then wifi band/rssi from the router tables.
        """
        for c in clients:
            # Priority 1: local static known devices
            if c.mac in _LOCAL_HOSTS:
                c.name            = _LOCAL_HOSTS[c.mac]
                c.hostname_source = "local"
            elif c.mac in self._dhcp_names:
                c.name            = self._dhcp_names[c.mac]
                c.hostname_source = "dhcp"
            if c.mac in self._wifi_info:
                c.band, c.rssi = self._wifi_info[c.mac]

    # -- Host node -------------------------------------------------------------

    def _build_host(self) -> NetworkClient:
        tx_b = rx_b = 0
        if _HAS_PSUTIL:
            try:
                ctr  = psutil.net_io_counters()
                tx_b = ctr.bytes_sent
                rx_b = ctr.bytes_recv
            except Exception:
                pass
        return NetworkClient(
            name            = f"{socket.gethostname()} (Host)",
            ip              = self._host_ip(),
            mac             = "SELF",
            band            = _BAND_LAN,
            rssi            = 100,
            tx_mb           = _b2mb(tx_b),
            rx_mb           = _b2mb(rx_b),
            is_self         = True,
            hostname_source = "localhost",
        )

    # -- Hostname resolution ---------------------------------------------------

    def _resolve_all(self, clients: List[NetworkClient]) -> None:
        """
        [FIX-F] Resolve every client's hostname in parallel.
        Priority: DHCP (already applied) -> mDNS -> DNS -> NetBIOS -> label.
        Always replaces vendor/synthetic/pending names.
        """
        def _work(c: NetworkClient) -> None:
            if c.hostname_source in ("router", "dhcp", "localhost", "local", "soc_analyzer"):
                return   # already have a real name
            name, source = self._resolve_name(c.ip)
            c.name            = name
            c.hostname_source = source

        with ThreadPoolExecutor(max_workers=10) as exe:
            list(exe.map(_work, clients))

    def _resolve_name(self, ip: str) -> Tuple[str, str]:
        """Tiered resolution with TTL cache."""
        now = time.time()
        with self._name_lock:
            hit = self._name_cache.get(ip)
            if hit and (now - hit[2]) < _HOSTNAME_TTL:
                return hit[0], hit[1]

        # Tier 1: mDNS (multicast DNS - works for Apple, Android, IoT)
        mdns = _mdns_lookup(ip)
        if mdns:
            self._cache_name(ip, mdns, "mdns")
            return mdns, "mdns"

        # Tier 2: Reverse DNS
        try:
            fqdn  = socket.gethostbyaddr(ip)[0]
            short = fqdn.split(".")[0]
            if short and short != ip and len(short) > 1:
                self._cache_name(ip, short, "dns")
                return short, "dns"
        except (socket.herror, socket.gaierror, OSError):
            pass

        # Tier 3: NetBIOS (Windows only)
        if _IS_WINDOWS:
            nb = _netbios(ip)
            if nb:
                self._cache_name(ip, nb, "netbios")
                return nb, "netbios"

        # Tier 4: Synthetic
        label = f"Device_{_last_octet(ip)}"
        self._cache_name(ip, label, "synthetic")
        return label, "synthetic"

    def _cache_name(self, ip: str, name: str, source: str) -> None:
        with self._name_lock:
            self._name_cache[ip] = (name, source, time.time())

    # -- Delta bandwidth -------------------------------------------------------

    def _apply_bw(self, nodes: List[NetworkClient]) -> None:
        now = time.time()
        for n in nodes:
            key  = n.mac if n.mac not in ("", "SELF") else n.ip
            tx_b = n.tx_mb * 1_048_576
            rx_b = n.rx_mb * 1_048_576

            if key in self._bw_prev:
                ptx, prx, pt = self._bw_prev[key]
                dt   = max(now - pt, 0.001)
                d_tx = max(tx_b - ptx, 0.0)
                d_rx = max(rx_b - prx, 0.0)
                n.tx_mbps = round(min((d_tx / dt) / 1_048_576, _BW_SPIKE_CAP), 4)
                n.rx_mbps = round(min((d_rx / dt) / 1_048_576, _BW_SPIKE_CAP), 4)

            self._bw_prev[key] = (tx_b, rx_b, now)

    # -- HTTP transport --------------------------------------------------------

    def _post(self, url: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        body = urllib.parse.urlencode({"data": json.dumps(payload)}).encode()
        req  = urllib.request.Request(url, data=body, method="POST")
        req.add_header("User-Agent",   _USER_AGENT)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Referer",      f"{self._base}/")
        req.add_header("Origin",       self._base)
        req.add_header("Connection",   "keep-alive")
        try:
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            self._log.debug("[Router] HTTP %d from %s", e.code, url)
        except urllib.error.URLError as e:
            self._log.debug("[Router] URLError %s -> %s", e.reason, url)
        except (json.JSONDecodeError, ValueError) as e:
            self._log.debug("[Router] JSON parse: %s", e)
        except OSError as e:
            self._log.debug("[Router] OS net: %s", e)
        return None

    # -- Utilities -------------------------------------------------------------

    def _host_ip(self) -> str:
        if self._host_ip_val:
            return self._host_ip_val
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                self._host_ip_val = s.getsockname()[0]
                return self._host_ip_val
        except OSError:
            return "127.0.0.1"

    def _one_shot_warmup(self) -> None:
        """
        Fast socket-based subnet sweep at startup.
        Populates the system's ARP table dynamically by attempting TCP connections,
        which triggers the OS to perform ARP requests without spawning 254 ping.exe processes.
        """
        def _ping_socket(n: int) -> None:
            ip = f"{self._subnet_prefix}{n}"
            if ip == self._host_ip() or ip == self.ip:
                return
            try:
                # Attempt to connect to NetBIOS port 135 (very fast locally)
                # This causes the OS to send an ARP request to the IP
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.15)
                s.connect((ip, 135))
                s.close()
            except Exception:
                pass

        self._log.info("[Router] Fast socket ARP warmup starting...")
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=80) as exe:
            list(exe.map(_ping_socket, range(1, 255)))
        self._log.info(
            "[Router] Fast socket ARP warmup done in %.2f seconds.",
            time.perf_counter() - t0
        )

    @staticmethod
    def _empty_dict() -> Dict[str, Any]:
        return {
            "status": "INITIALIZING", "router_ip": "", "clients": [],
            "total_online": 0, "tx_total_mb": 0.0, "rx_total_mb": 0.0,
            "tx_total_mbps": 0.0, "rx_total_mbps": 0.0, "band_5_count": 0,
            "band_24_count": 0, "wired_count": 0, "wlan_count": 0,
            "local_count": 0, "scan_ms": 0.0, "session_method": "none",
            "timestamp": time.time(),
        }


# =============================================================================
#  mDNS RESOLVER  [FIX-C]
# =============================================================================

def _mdns_lookup(ip: str) -> str:
    """
    Send a multicast DNS PTR query for the reverse IP and return the
    device's advertised hostname.  Works for Apple (Bonjour), modern
    Android, Windows 10+, and most IoT/smart-home devices.
    """
    try:
        octets  = ip.split(".")
        reverse = ".".join(reversed(octets)) + ".in-addr.arpa"
        packet  = _dns_query(reverse, qtype=12)   # 12 = PTR

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(_MDNS_TIMEOUT)
        sock.sendto(packet, ("224.0.0.251", 5353))

        deadline = time.time() + _MDNS_TIMEOUT
        while time.time() < deadline:
            try:
                data, _ = sock.recvfrom(4096)
                name = _dns_parse_ptr(data)
                if name and name != ip:
                    return name.rstrip(".")
            except socket.timeout:
                break
    except OSError:
        pass
    finally:
        try:
            sock.close()
        except Exception:
            pass
    return ""


def _dns_query(name: str, qtype: int = 12) -> bytes:
    """Build a minimal DNS query packet."""
    header = struct.pack(">HHHHHH", 0x0001, 0x0100, 1, 0, 0, 0)
    labels = b""
    for part in name.split("."):
        enc = part.encode("ascii")
        labels += bytes([len(enc)]) + enc
    labels += b"\x00"
    question = labels + struct.pack(">HH", qtype, 1)   # QTYPE=PTR, QCLASS=IN
    return header + question


def _dns_parse_ptr(data: bytes) -> str:
    """Extract the first PTR name from a raw DNS response packet."""
    try:
        if len(data) < 12:
            return ""
        ancount = struct.unpack(">H", data[6:8])[0]
        if ancount == 0:
            return ""
        # Skip header (12) + question section
        pos = 12
        # Skip question name
        while pos < len(data) and data[pos] != 0:
            if data[pos] & 0xC0 == 0xC0:
                pos += 2
                break
            pos += data[pos] + 1
        else:
            pos += 1
        pos += 4   # skip QTYPE + QCLASS
        # Now at first answer
        if pos < len(data):
            if data[pos] & 0xC0 == 0xC0:
                pos += 2
            else:
                while pos < len(data) and data[pos] != 0:
                    pos += data[pos] + 1
                pos += 1
        pos += 10  # TYPE(2) + CLASS(2) + TTL(4) + RDLENGTH(2)
        return _dns_read_name(data, pos)
    except Exception:
        return ""


def _dns_read_name(data: bytes, pos: int) -> str:
    """Decode a DNS label-sequence name, following compression pointers."""
    parts = []
    visited = set()
    while pos < len(data):
        length = data[pos]
        if length == 0:
            break
        if length & 0xC0 == 0xC0:
            if pos + 1 >= len(data):
                break
            ptr = ((length & 0x3F) << 8) | data[pos + 1]
            if ptr in visited:
                break
            visited.add(ptr)
            pos = ptr
            continue
        pos += 1
        parts.append(data[pos:pos + length].decode("ascii", errors="replace"))
        pos += length
    return ".".join(parts)


# =============================================================================
#  MODULE HELPERS
# =============================================================================

def _vendor_label(mac: str, ip: str) -> str:
    prefix = "-".join(mac.lower().replace(":", "-").split("-")[:3])
    vendor = _VENDORS.get(prefix, "")
    octet  = _last_octet(ip)
    return f"{vendor}_{octet}" if vendor else f"Device_{octet}"


def _b2mb(raw: Any) -> float:
    try:
        return round(int(raw) / 1_048_576, 3)
    except (TypeError, ValueError):
        return 0.0


def _fmt_mac(raw: str) -> str:
    d = re.sub(r"[^0-9a-fA-F]", "", raw)
    if len(d) == 12:
        return ":".join(d[i:i+2].upper() for i in range(0, 12, 2))
    return raw.upper()


def _is_broadcast(mac: str) -> bool:
    d = re.sub(r"[^0-9a-fA-F]", "", mac).upper()
    return not d or d in ("FFFFFFFFFFFF", "000000000000")


def _last_octet(ip: str) -> int:
    try:
        return int(ip.rsplit(".", 1)[-1])
    except (IndexError, ValueError):
        return 0


def _flags() -> Dict[str, Any]:
    if _IS_WINDOWS:
        return {"creationflags": 0x08000000 | 0x00000008}
    return {}


def _netbios(ip: str) -> str:
    """Query NetBIOS node status via direct UDP port 137 socket (0 subprocesses)."""
    try:
        query = (
            b'\x12\x34\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00'
            b' CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\x00\x00\x21\x00\x01'
        )
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.sendto(query, (ip, 137))
            data, _ = s.recvfrom(1024)
            if len(data) > 57:
                num_names = data[56]
                offset = 57
                for _ in range(num_names):
                    if offset + 18 > len(data):
                        break
                    name_bytes = data[offset:offset+15]
                    name_type = data[offset+15]
                    if name_type == 0x00:
                        name = name_bytes.decode('ascii', errors='ignore').strip()
                        if name:
                            return name
                    offset += 18
    except Exception:
        pass
    return ""
