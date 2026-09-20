#!/usr/bin/env python3
"""
InfoSphere Guard - Task Scheduler Safety Net
Immediately checks if engine mutex is held and exits silently.
"""
import sys, os, ctypes

if sys.stdout is None: sys.stdout = open(os.devnull, "w")
if sys.stderr is None: sys.stderr = open(os.devnull, "w")

ROOT = os.path.dirname(os.path.abspath(__file__))

def _is_engine_running():
    try:
        k32 = ctypes.windll.kernel32
        h = k32.OpenMutexW(0x00100000, False, "Global\\InfoSphereWallpaperEngine")
        if h: k32.CloseHandle(h); return True
    except: pass
    return False

if _is_engine_running():
    sys.exit(0)

# Not running — launch via VBS
vbs = os.path.join(ROOT, "launch_hidden.vbs")
if os.path.exists(vbs):
    import subprocess
    subprocess.Popen(["wscript.exe", vbs], creationflags=8, close_fds=True)
