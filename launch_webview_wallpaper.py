import sys
import threading
import time
import ctypes
import win32gui
import win32con
import win32api
import webview

# Win32 constants
HWND_BOTTOM     = 1
SWP_NOMOVE      = 0x0002
SWP_NOSIZE      = 0x0001
SWP_NOACTIVATE  = 0x0010
SWP_SHOWWINDOW  = 0x0040

user32 = ctypes.windll.user32

def position_as_wallpaper(hwnd):
    """
    Position the window at the bottom of the Z-order (behind all other windows),
    full screen, without embedding into WorkerW.
    
    This is the INTERACTIVE wallpaper approach:
    - Window stays below every other app (like a real wallpaper)
    - BUT mouse input still reaches it because it is a real top-level window
    - NOT embedded into WorkerW (which kills all input)
    """
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    
    # Remove title bar and window border
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    style &= ~win32con.WS_CAPTION
    style &= ~win32con.WS_THICKFRAME
    style &= ~win32con.WS_MINIMIZEBOX
    style &= ~win32con.WS_MAXIMIZEBOX
    style &= ~win32con.WS_SYSMENU
    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
    
    # Remove extended styles that could block input
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    ex_style &= ~win32con.WS_EX_APPWINDOW   # Hide from taskbar
    ex_style &= ~0x00000020                  # Remove WS_EX_TRANSPARENT (blocks input)
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
    
    # Place it fullscreen at HWND_BOTTOM so it stays behind all other windows
    # but is still a real window that receives mouse events
    ctypes.windll.user32.SetWindowPos(
        hwnd, HWND_BOTTOM,
        0, 0, screen_w, screen_h,
        SWP_NOACTIVATE | SWP_SHOWWINDOW
    )
    
    print(f"[InfoSphere] Interactive wallpaper positioned: {screen_w}x{screen_h} @ HWND_BOTTOM")

def keep_at_bottom(hwnd):
    """
    Continuously re-push the window to HWND_BOTTOM every second.
    This prevents other windows (like TaskBar) from accidentally popping it above them.
    """
    while True:
        try:
            if win32gui.IsWindow(hwnd):
                ctypes.windll.user32.SetWindowPos(
                    hwnd, HWND_BOTTOM,
                    0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                )
        except Exception:
            break
        time.sleep(1.5)

def on_webview_ready(window):
    print("Waiting for WebView window to spawn...")
    time.sleep(2.0)
    
    hwnd = win32gui.FindWindow(None, "InfoSphere_Live_Wallpaper_Overlay")
    if hwnd:
        print("Found WebView window! Positioning as interactive wallpaper...")
        position_as_wallpaper(hwnd)
        
        # Start background thread to keep it at bottom
        t = threading.Thread(target=keep_at_bottom, args=(hwnd,))
        t.daemon = True
        t.start()
        
        print("[InfoSphere] Interactive wallpaper running — mouse fully enabled!")
    else:
        print("Failed to find WebView Window handle!")

class Api:
    def get_mouse(self):
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        
        # Left mouse button state (GetAsyncKeyState returns negative when held down)
        lbtn_down = bool(win32api.GetAsyncKeyState(0x01) & 0x8000)
        # Right mouse button state
        rbtn_down = bool(win32api.GetAsyncKeyState(0x02) & 0x8000)
        
        return [pt.x, pt.y, lbtn_down, rbtn_down]

if __name__ == '__main__':
    url = "http://127.0.0.1:8090/infosphere_live_wallpaper.html"
    api = Api()
    window = webview.create_window(
        "InfoSphere_Live_Wallpaper_Overlay",
        url,
        js_api=api,
        fullscreen=False,   # We manually size/position it
        frameless=True,
        easy_drag=False
    )
    
    t = threading.Thread(target=on_webview_ready, args=(window,))
    t.daemon = True
    t.start()
    
    print("Starting InfoSphere Interactive Wallpaper Engine...")
    webview.start(private_mode=True)

