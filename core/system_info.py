"""
InfoSphere Cyber Live Wallpaper Engine
core/system_info.py  v3.0
"""

import datetime
import getpass
import logging
import platform
import socket
import subprocess
import time

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


class SystemInfo:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("InfoSphere")
        self._prev_bytes_sent: int = 0
        self._prev_bytes_recv: int = 0
        self._prev_net_time: float = 0.0
        # Caching slow lookups to improve cycle responsiveness and reduce CPU
        self._wifi_cache: dict = {}
        self._wifi_cache_ts: float = 0.0
        self._firewall_cache: str = "UNKNOWN"
        self._firewall_cache_ts: float = 0.0
        self._cache_ttl: float = 20.0  # cache details for 20s
        self._gpu_temp_cache: float = 0.0
        self._gpu_temp_ts: float = 0.0
        self._proc_cache: dict = {"total": 0, "bg": 0}
        self._proc_cache_ts: float = 0.0
        self._proc_ttl: float = 15.0
        # Pre-seed psutil CPU tracking
        if _PSUTIL:
            try:
                psutil.cpu_percent(interval=None)
                psutil.cpu_percent(percpu=True, interval=None)
            except Exception:
                pass

    def collect(self) -> dict:
        info: dict = {}
        try:
            info["hostname"]  = _safe(socket.gethostname,  "UNKNOWN")
            info["username"]  = _safe(getpass.getuser,     "UNKNOWN")
            info["os_name"]   = self._os_name()
            info["local_ip"]  = self._local_ip()
            info["platform"]  = platform.system()
            info["time_ns"]   = time.time_ns()
            info["time_now"]  = datetime.datetime.now()

            if _PSUTIL:
                vm   = psutil.virtual_memory()
                disk = self._disk_usage()
                net  = psutil.net_io_counters()

                cores                 = self._cpu_per_core()
                info["cpu_cores"]     = cores
                info["cpu_percent"]   = round(sum(cores) / len(cores), 1) if cores else 0.0
                info["cpu_count"]     = _safe(psutil.cpu_count, 1)
                info["cpu_freq_mhz"]  = self._cpu_freq()
                cpu_temp, temp_source = self._cpu_temperature(info["cpu_percent"])
                info["cpu_temp"]        = cpu_temp
                info["cpu_temp_source"] = temp_source
                info["ram_percent"]   = vm.percent
                info["ram_used_gb"]   = round(vm.used  / 1024**3, 2)
                info["ram_total_gb"]  = round(vm.total / 1024**3, 2)
                info["disk_percent"]  = disk.percent if disk else 0.0
                info["disk_used_gb"]  = round(disk.used  / 1024**3, 1) if disk else 0.0
                info["disk_total_gb"] = round(disk.total / 1024**3, 1) if disk else 0.0
                info["uptime"]        = self._uptime()
                info["uptime_secs"]   = self._uptime_secs()
                proc_counts = self._get_process_counts()
                info["process_count"] = proc_counts["total"]
                info["bg_process_count"] = proc_counts["bg"]

                bytes_sent = net.bytes_sent if net else 0
                bytes_recv = net.bytes_recv if net else 0
                info["net_sent_mb"]      = round(bytes_sent / 1024**2, 1)
                info["net_recv_mb"]      = round(bytes_recv / 1024**2, 1)
                info["net_packets_sent"] = net.packets_sent if net else 0
                info["net_packets_recv"] = net.packets_recv if net else 0

                spd = self._net_speed(bytes_sent, bytes_recv)
                info.update(spd)
            else:
                info.update(self._null_metrics())

            info.update(self._wifi_info())
            info["firewall_status"] = self._firewall()
            info["security_score"]  = self._security_score(info)

        except Exception as exc:
            self.logger.error(f"SystemInfo.collect failed: {exc}", exc_info=True)
        return info

    def _os_name(self) -> str:
        try:
            sys = platform.system()
            if sys == "Windows":
                ver   = platform.version().split(".")
                build = ver[2] if len(ver) > 2 else "?"
                return f"Windows {platform.release()}  build {build}"
            if sys == "Linux":
                try:
                    with open("/etc/os-release") as f:
                        for line in f:
                            if line.startswith("PRETTY_NAME="):
                                return line.split("=",1)[1].strip().strip('"')
                except OSError:
                    pass
                return f"Linux {platform.release()}"
            return f"{sys} {platform.release()}"
        except Exception:
            return "Unknown OS"

    def _local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]; s.close(); return ip
        except Exception:
            try: return socket.gethostbyname(socket.gethostname())
            except Exception: return "127.0.0.1"

    def _cpu_freq(self) -> str:
        try:
            f = psutil.cpu_freq()
            return f"{f.current:.0f} MHz" if f else "N/A"
        except Exception: return "N/A"

    def _cpu_per_core(self) -> list:
        try: return psutil.cpu_percent(percpu=True)
        except Exception: return []

    def _cpu_temperature(self, cpu_percent: float) -> tuple[float, str]:
        # Prefer a real CPU sensor whenever the platform exposes one.
        try:
            sensors = getattr(psutil, "sensors_temperatures", lambda: {})() or {}
            preferred = ("coretemp", "k10temp", "cpu_thermal", "acpitz")
            ordered = [
                *[(name, sensors[name]) for name in preferred if name in sensors],
                *[(name, entries) for name, entries in sensors.items() if name not in preferred],
            ]
            for _, entries in ordered:
                for entry in entries:
                    value = float(getattr(entry, "current", 0.0) or 0.0)
                    label = str(getattr(entry, "label", "")).lower()
                    if 0 < value < 120 and (not label or "cpu" in label or "core" in label or "package" in label):
                        return round(value, 1), "CPU_SENSOR"
        except Exception:
            pass

        now = time.time()
        gpu_temp = 0.0

        # Check GPU cache (10 seconds TTL)
        if now - self._gpu_temp_ts < 10.0:
            gpu_temp = self._gpu_temp_cache
        else:
            # 1. In-process NVIDIA NVML query (zero subprocesses, zero conhost)
            try:
                import ctypes
                for dll_path in (r"C:\Windows\System32\nvml.dll", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll"):
                    if os.path.exists(dll_path):
                        nvml = ctypes.CDLL(dll_path)
                        if nvml.nvmlInit_v2() == 0:
                            dev = ctypes.c_void_p()
                            if nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev)) == 0:
                                t = ctypes.c_uint()
                                if nvml.nvmlDeviceGetTemperature(dev, 0, ctypes.byref(t)) == 0:
                                    if 0 < t.value < 120:
                                        gpu_temp = float(t.value)
                                        self._gpu_temp_cache = gpu_temp
                                        self._gpu_temp_ts = now
                            nvml.nvmlShutdown()
                            break
            except Exception:
                pass

        if gpu_temp > 0.0:
            cpu_temp = gpu_temp + 1.5 + (cpu_percent * 0.10)
            return round(cpu_temp, 1), "GPU_PROXY_ESTIMATE"

        # 2. Realistic laptop CPU thermal curve:
        # Idle (0-20%): 40°C - 44°C (cool, green)
        # Moderate (20-60%): 45°C - 55°C
        # Full Load (60-100%): 56°C - 68°C
        import random
        base_temp = 41.5
        load_temp = min(cpu_percent, 100.0) * 0.22
        cpu_temp = base_temp + load_temp + random.uniform(-0.4, 0.4)
        return round(cpu_temp, 1), "LOAD_ESTIMATE"

    def _get_process_counts(self) -> dict:
        now = time.time()
        if self._proc_cache and (now - self._proc_cache_ts) < self._proc_ttl:
            return self._proc_cache

        total = 0
        bg_count = 0
        try:
            import getpass
            current_user = getpass.getuser().lower()
            known_apps = {'explorer.exe', 'taskmgr.exe', 'chrome.exe', 'whatsapp.exe', 'ms-teams.exe', 'vscode.exe', 'python.exe', 'pythonw.exe', 'node.exe'}
            for p in psutil.process_iter(attrs=['name', 'username']):
                total += 1
                try:
                    p_user = (p.info.get('username') or '').split('\\')[-1].lower()
                    name = p.info['name'].lower()
                    if p_user == current_user and name not in known_apps:
                        bg_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            total = len(list(psutil.pids())) if hasattr(psutil, "pids") else 0
            bg_count = 0

        self._proc_cache = {"total": total, "bg": bg_count}
        self._proc_cache_ts = now
        return self._proc_cache

    def _disk_usage(self):
        root = "/" if platform.system() != "Windows" else "C:\\"
        try: return psutil.disk_usage(root)
        except Exception: return None

    def _uptime_secs(self) -> int:
        try: return int(datetime.datetime.now().timestamp() - psutil.boot_time())
        except Exception: return 0

    def _uptime(self) -> str:
        try:
            s = self._uptime_secs()
            d, r = divmod(s, 86400); h, r = divmod(r, 3600); m = r // 60
            return f"{d}d {h:02d}h {m:02d}m" if d else f"{h:02d}h {m:02d}m"
        except Exception: return "N/A"

    def _net_speed(self, sent: int, recv: int) -> dict:
        now = time.time()
        result = {"net_tx_speed":"0 B/s","net_rx_speed":"0 B/s",
                  "net_tx_kbps":0.0,"net_rx_kbps":0.0}
        elapsed = now - self._prev_net_time
        if elapsed > 0.1 and self._prev_net_time > 0:
            tx_kb = max(0, sent - self._prev_bytes_sent) / elapsed / 1024
            rx_kb = max(0, recv - self._prev_bytes_recv) / elapsed / 1024
            result.update({"net_tx_kbps": round(tx_kb,1),
                           "net_rx_kbps": round(rx_kb,1),
                           "net_tx_speed": _fmt_speed(tx_kb),
                           "net_rx_speed": _fmt_speed(rx_kb)})
        self._prev_bytes_sent = sent
        self._prev_bytes_recv = recv
        self._prev_net_time   = now
        return result

    def _wifi_info(self) -> dict:
        now = time.time()
        if self._wifi_cache and (now - self._wifi_cache_ts) < self._cache_ttl:
            return self._wifi_cache

        base = {"wifi_ssid":"N/A","wifi_signal":"N/A","wifi_speed":"N/A",
                "wifi_band":"N/A","wifi_bssid":"N/A","wifi_status":"UNKNOWN"}
        try:
            if platform.system() == "Windows":
                res = self._wifi_windows(base)
            elif platform.system() == "Linux":
                res = self._wifi_linux(base)
            else:
                res = base
            self._wifi_cache = res
            self._wifi_cache_ts = now
            return res
        except Exception as e:
            self.logger.debug(f"WiFi: {e}")
        return base

    def _wifi_windows(self, base: dict) -> dict:
        """Native Win32 wlanapi.dll query (zero subprocesses, zero console window)."""
        try:
            import ctypes
            from ctypes import wintypes
            wlanapi = ctypes.windll.wlanapi
            handle = wintypes.HANDLE()
            negotiated_version = wintypes.DWORD()
            if wlanapi.WlanOpenHandle(2, None, ctypes.byref(negotiated_version), ctypes.byref(handle)) == 0:
                class WLAN_INTERFACE_INFO(ctypes.Structure):
                    _fields_ = [
                        ("InterfaceGuid", ctypes.c_byte * 16),
                        ("strInterfaceDescription", wintypes.WCHAR * 256),
                        ("isState", wintypes.DWORD)
                    ]
                class WLAN_INTERFACE_INFO_LIST(ctypes.Structure):
                    _fields_ = [
                        ("dwNumberOfItems", wintypes.DWORD),
                        ("dwIndex", wintypes.DWORD),
                        ("InterfaceInfo", WLAN_INTERFACE_INFO * 1)
                    ]
                class DOT11_SSID(ctypes.Structure):
                    _fields_ = [
                        ("uSSIDLength", wintypes.ULONG),
                        ("ucSSID", ctypes.c_char * 32)
                    ]
                class WLAN_ASSOCIATION_ATTRIBUTES(ctypes.Structure):
                    _fields_ = [
                        ("dot11Ssid", DOT11_SSID),
                        ("dot11BssType", wintypes.DWORD),
                        ("dot11Bssid", ctypes.c_byte * 6),
                        ("dot11PhyType", wintypes.DWORD),
                        ("uDot11PhyIndex", wintypes.ULONG),
                        ("wlanSignalQuality", wintypes.ULONG),
                        ("ulRxRate", wintypes.ULONG),
                        ("ulTxRate", wintypes.ULONG)
                    ]
                class WLAN_CONNECTION_ATTRIBUTES(ctypes.Structure):
                    _fields_ = [
                        ("isState", wintypes.DWORD),
                        ("wlanConnectionMode", wintypes.DWORD),
                        ("strProfileName", wintypes.WCHAR * 256),
                        ("wlanAssociationAttributes", WLAN_ASSOCIATION_ATTRIBUTES),
                    ]
                pList = ctypes.POINTER(WLAN_INTERFACE_INFO_LIST)()
                if wlanapi.WlanEnumInterfaces(handle, None, ctypes.byref(pList)) == 0 and pList:
                    num = pList.contents.dwNumberOfItems
                    for i in range(num):
                        info = pList.contents.InterfaceInfo[i]
                        if info.isState == 1:  # connected
                            pData = ctypes.c_void_p()
                            dataSize = wintypes.DWORD()
                            if wlanapi.WlanQueryInterface(handle, ctypes.byref(info.InterfaceGuid), 7, None, ctypes.byref(dataSize), ctypes.byref(pData), None) == 0 and pData:
                                conn = ctypes.cast(pData, ctypes.POINTER(WLAN_CONNECTION_ATTRIBUTES)).contents
                                assoc = conn.wlanAssociationAttributes
                                ssid_len = min(32, int(assoc.dot11Ssid.uSSIDLength))
                                ssid = assoc.dot11Ssid.ucSSID[:ssid_len].decode('utf-8', errors='replace')
                                signal = f"{assoc.wlanSignalQuality}%"
                                rx_rate = f"{assoc.ulRxRate / 1000.0:.1f} Mbps"
                                bssid = ":".join(f"{b & 0xFF:02X}" for b in assoc.dot11Bssid)
                                base.update({
                                    "wifi_ssid": ssid or "N/A",
                                    "wifi_bssid": bssid or "N/A",
                                    "wifi_signal": signal or "N/A",
                                    "wifi_speed": rx_rate or "N/A",
                                    "wifi_band": "5 GHz" if "5G" in ssid else "2.4 GHz",
                                    "wifi_status": "CONNECTED"
                                })
                                wlanapi.WlanFreeMemory(pData)
                                break
                    wlanapi.WlanFreeMemory(pList)
                wlanapi.WlanCloseHandle(handle, None)
        except Exception as e:
            self.logger.debug(f"WiFi native error: {e}")
        return base

    def _wifi_linux(self, base: dict) -> dict:
        try:
            r = subprocess.run(
                ["nmcli","-t","-f","ACTIVE,SSID,SIGNAL,RATE,BSSID","dev","wifi"],
                capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                if line.startswith("yes:"):
                    p = line.split(":")
                    if len(p) >= 4:
                        base.update({"wifi_ssid":p[1],"wifi_signal":p[2]+"%",
                                     "wifi_speed":p[3],"wifi_status":"CONNECTED"})
                        return base
        except Exception: pass
        try:
            s = subprocess.run(["iwgetid","-r"],capture_output=True,text=True,timeout=4)
            if s.stdout.strip():
                base["wifi_ssid"]   = s.stdout.strip()
                base["wifi_status"] = "CONNECTED"
        except Exception: pass
        return base

    def _firewall(self) -> str:
        """Native Windows Registry firewall query (zero subprocesses, zero console window)."""
        now = time.time()
        if self._firewall_cache != "UNKNOWN" and (now - self._firewall_cache_ts) < self._cache_ttl:
            return self._firewall_cache

        res = "UNKNOWN"
        try:
            if platform.system() == "Windows":
                import winreg
                for prof in ("StandardProfile", "DomainProfile", "PublicProfile"):
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\{prof}") as k:
                            if winreg.QueryValueEx(k, "EnableFirewall")[0] == 1:
                                res = "ACTIVE"
                                break
                    except Exception:
                        pass
                if res == "UNKNOWN":
                    res = "INACTIVE"
            elif platform.system() == "Linux":
                r = subprocess.run(["ufw","status"],capture_output=True,text=True,timeout=5)
                if "active"   in r.stdout.lower(): res = "ACTIVE"
                elif "inactive" in r.stdout.lower(): res = "INACTIVE"
            self._firewall_cache = res
            self._firewall_cache_ts = now
            return res
        except Exception as e:
            self.logger.debug(f"Firewall: {e}")
        return "ACTIVE"

    def _security_score(self, info: dict) -> int:
        """Return a conservative score from security data collected here."""
        score = 100
        fw = info.get("firewall_status","UNKNOWN")
        if fw == "INACTIVE":
            score -= 40
        elif fw != "ACTIVE":
            score -= 15
        return max(0, min(100, score))

    @staticmethod
    def _null_metrics() -> dict:
        return {"cpu_percent":0.0,"cpu_count":0,"cpu_freq_mhz":"N/A","cpu_cores":[],
                "cpu_temp":0.0,"cpu_temp_source":"UNAVAILABLE",
                "bg_process_count":0,
                "ram_percent":0.0,"ram_used_gb":0.0,"ram_total_gb":0.0,
                "disk_percent":0.0,"disk_used_gb":0.0,"disk_total_gb":0.0,
                "uptime":"N/A","uptime_secs":0,"process_count":0,
                "net_sent_mb":0.0,"net_recv_mb":0.0,
                "net_packets_sent":0,"net_packets_recv":0,
                "net_tx_speed":"0 B/s","net_rx_speed":"0 B/s",
                "net_tx_kbps":0.0,"net_rx_kbps":0.0}


def _safe(fn, default):
    try: return fn()
    except Exception: return default

def _fmt_speed(kbps: float) -> str:
    if kbps >= 1024: return f"{kbps/1024:.2f} MB/s"
    if kbps >= 1:    return f"{kbps:.1f} KB/s"
    return f"{kbps*1024:.0f} B/s"
