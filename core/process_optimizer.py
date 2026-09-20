"""
InfoSphere Cyber Live Wallpaper Engine
core/process_optimizer.py  v1.0
"""

import logging
import psutil

# Optional updater processes. They are never touched unless the user explicitly
# enables both the optimizer and terminate_updates in config.json.
TARGET_KILLS = {
    'adobearm.exe', 'acrotray.exe', 'braveupdate.exe', 'bravesoftwareupdate.exe',
    'googleupdate.exe', 'gupdate.exe', 'gupdatem.exe', 'microsoftedgeupdate.exe',
    'edgeupdate.exe', 'onedriveupdater.exe', 'dellsupportassist.exe',
    'dellsupportassistupdater.exe', 'delltechhub.exe', 'mobsync.exe',
    'lghub_updater.exe', 'epicgameslauncher.exe'
}

# Essential interactive shells & main apps we should never throttle
WHITELIST_APPS = {
    'explorer.exe', 'taskmgr.exe', 'chrome.exe', 'whatsapp.exe', 'ms-teams.exe',
    'vscode.exe', 'python.exe', 'pythonw.exe', 'node.exe', 'wscript.exe',
    'system', 'idle', 'spoolsv.exe', 'dwm.exe', 'wininit.exe', 'winlogon.exe',
    'services.exe', 'lsass.exe', 'svchost.exe', 'csrss.exe', 'smss.exe'
}

class ProcessOptimizer:
    def __init__(self, config: dict | None = None, logger=None):
        self.logger = logger or logging.getLogger("InfoSphere")
        cfg = (config or {}).get("process_optimizer", {})
        self.enabled = bool(cfg.get("enabled", False))
        self.terminate_updates = bool(cfg.get("terminate_updates", False))
        self.throttle_on_load = bool(cfg.get("throttle_on_load", False))
        # Track processes we throttled: PID -> (original priority, create time)
        self._throttled_pids = {}

    def optimize(self, info: dict) -> list:
        """
        Main optimization pass. Returns a list of log messages to inject
        into the live SOC telemetry feed.
        """
        if not self.enabled:
            return []

        logs = []
        cpu_percent = info.get("cpu_percent", 0.0)
        cpu_temp = info.get("cpu_temp", 37.0)
        temp_is_measured = info.get("cpu_temp_source") == "CPU_SENSOR"

        # Estimated temperatures are presentation-only and must never trigger
        # process priority changes. CPU load remains an independent signal.
        check_throttle = self.throttle_on_load and (
            (temp_is_measured and cpu_temp > 65.0) or cpu_percent > 40.0
        )
        
        terminated_names = []
        throttled_count = 0

        # Run process list exactly ONCE per pass
        attrs = ['pid', 'name']
        if check_throttle:
            attrs.append('cpu_percent')

        for p in psutil.process_iter(attrs=attrs):
            try:
                pid = p.info['pid']
                name = p.info['name']
                if not name:
                    continue
                name_l = name.lower()

                # 1. Terminate updaters & bloatware
                if self.terminate_updates and name_l in TARGET_KILLS:
                    p.terminate()
                    terminated_names.append(name)
                    continue

                # 2. Thermal Throttling / Priority Optimization
                if check_throttle:
                    p_cpu = p.info.get('cpu_percent') or 0.0
                    if (name_l not in WHITELIST_APPS and 
                        pid not in self._throttled_pids and 
                        p_cpu > 2.0):
                        try:
                            orig_priority = p.nice()
                            idle_priority = getattr(psutil, "IDLE_PRIORITY_CLASS", 10)
                            p.nice(idle_priority)
                            self._throttled_pids[pid] = (
                                orig_priority,
                                p.create_time(),
                            )
                            throttled_count += 1
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            except Exception as e:
                self.logger.debug(f"Optimizer loop error: {e}")

        if terminated_names:
            unique_names = list(set(terminated_names))
            if len(unique_names) > 2:
                logs.append(f"Optimizer: terminated {len(terminated_names)} updaters ({', '.join(unique_names[:2])}...)")
            else:
                logs.append(f"Optimizer: terminated {len(terminated_names)} updaters ({', '.join(unique_names)})")

        if throttled_count > 0:
            logs.append(f"Thermal throttling: set {throttled_count} background tasks to IDLE priority")

        # ── 3. Restore priorities when system cools down ──
        # Cool threshold: load < 25% and temp < 60C
        elif ((not temp_is_measured or cpu_temp < 60.0)
              and cpu_percent < 25.0 and self._throttled_pids):
            restored_count = 0
            for pid, (orig_priority, create_time) in list(self._throttled_pids.items()):
                try:
                    if psutil.pid_exists(pid):
                        p = psutil.Process(pid)
                        if p.create_time() == create_time:
                            p.nice(orig_priority)
                            restored_count += 1
                except Exception:
                    pass
                del self._throttled_pids[pid]

            if restored_count > 0:
                logs.append(f"Cooldown: restored priority class for {restored_count} background tasks")

        return logs

    def restore(self) -> None:
        """Best-effort restoration of priorities changed by this instance."""
        for pid, (orig_priority, create_time) in list(self._throttled_pids.items()):
            try:
                process = psutil.Process(pid)
                if process.create_time() == create_time:
                    process.nice(orig_priority)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            finally:
                self._throttled_pids.pop(pid, None)
