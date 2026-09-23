// InfoSphere Live Wallpaper — Single Binary Go Engine
//
// ONE binary that does everything:
//  - Built-in HTTP file server (serves HTML/CSS/JS from project root)
//  - Built-in SSE broadcast (watches output/system_snapshot.json & config.json)
//  - WebView2 window manager (fullscreen, HWND_BOTTOM, hidden from taskbar)
//  - Mouse bridge (global Win32 cursor + click state sent into JS)
//
// Python main.py is ONLY needed for data collection (it writes JSON files).
// This binary reads those JSON files and pushes them to the browser.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"runtime/debug"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
	"unsafe"

	webview "github.com/jchv/go-webview2"
	"golang.org/x/sys/windows"
)

// ─── Win32 constants ─────────────────────────────────────────────────────────
const (
	HWND_BOTTOM = windows.HWND(1)

	SWP_NOMOVE       = 0x0002
	SWP_NOSIZE       = 0x0001
	SWP_NOACTIVATE   = 0x0010
	SWP_SHOWWINDOW   = 0x0040
	SWP_FRAMECHANGED = 0x0020

	GWL_STYLE   = -16
	GWL_EXSTYLE = -20

	WS_CAPTION       = 0x00C00000
	WS_THICKFRAME    = 0x00040000
	WS_MINIMIZEBOX   = 0x00020000
	WS_MAXIMIZEBOX   = 0x00010000
	WS_SYSMENU       = 0x00080000
	WS_CHILD         = 0x40000000
	WS_VISIBLE       = 0x10000000
	WS_EX_APPWINDOW  = 0x00040000
	WS_EX_TOOLWINDOW = 0x00000080
	WS_EX_NOACTIVATE = 0x08000000
)

// ─── Win32 API bindings ──────────────────────────────────────────────────────
var (
	user32                            = windows.NewLazySystemDLL("user32.dll")
	shcore                            = windows.NewLazySystemDLL("shcore.dll")
	kernel32                          = windows.NewLazySystemDLL("kernel32.dll")
	procGetSystemMetrics              = user32.NewProc("GetSystemMetrics")
	procSetWindowPos                  = user32.NewProc("SetWindowPos")
	procGetWindowLong                 = user32.NewProc("GetWindowLongW")
	procSetWindowLong                 = user32.NewProc("SetWindowLongW")
	procFindWindow                    = user32.NewProc("FindWindowW")
	procFindWindowEx                  = user32.NewProc("FindWindowExW")
	procGetCursorPos                  = user32.NewProc("GetCursorPos")
	procGetAsyncKeyState              = user32.NewProc("GetAsyncKeyState")
	procIsWindow                      = user32.NewProc("IsWindow")
	procSendMessageTimeout            = user32.NewProc("SendMessageTimeoutW")
	procEnumWindows                   = user32.NewProc("EnumWindows")
	procSetParent                     = user32.NewProc("SetParent")
	procGetParent                     = user32.NewProc("GetParent")
	procGetClientRect                 = user32.NewProc("GetClientRect")
	procSetProcessDpiAwarenessContext = user32.NewProc("SetProcessDpiAwarenessContext")
	procSetProcessDpiAwareness        = shcore.NewProc("SetProcessDpiAwareness")
	procSetProcessDPIAware            = user32.NewProc("SetProcessDPIAware")
	procCreateMutex                   = kernel32.NewProc("CreateMutexW")
	procOpenDesktop                   = user32.NewProc("OpenDesktopW")
	procSetThreadDesktop              = user32.NewProc("SetThreadDesktop")
	procShowWindow                    = user32.NewProc("ShowWindow")
	procIsIconic                      = user32.NewProc("IsIconic")
)


func ensureDefaultDesktop() {
	pDefault, _ := windows.UTF16PtrFromString("Default")
	hDesk, _, err := procOpenDesktop.Call(uintptr(unsafe.Pointer(pDefault)), 0, 0, 0x01FF)
	if hDesk != 0 {
		r, _, err2 := procSetThreadDesktop.Call(hDesk)
		log.Printf("[InfoSphere] ensureDefaultDesktop: hDesk=0x%X SetThreadDesktop=%v (err: %v)", hDesk, r, err2)
	} else {
		log.Printf("[InfoSphere] ensureDefaultDesktop: OpenDesktop failed (err: %v)", err)
	}
}


func initDPI() {
	if procSetProcessDpiAwarenessContext.Find() == nil {
		procSetProcessDpiAwarenessContext.Call(uintptr(0xFFFFFFFFFFFFFFFC)) // DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
	} else if procSetProcessDpiAwareness.Find() == nil {
		procSetProcessDpiAwareness.Call(2) // PROCESS_PER_MONITOR_DPI_AWARE
	} else if procSetProcessDPIAware.Find() == nil {
		procSetProcessDPIAware.Call()
	}
}

type POINT struct{ X, Y int32 }
type RECT struct{ Left, Top, Right, Bottom int32 }

func getSystemMetrics(n int) int32 {
	r, _, _ := procGetSystemMetrics.Call(uintptr(n))
	return int32(r)
}
func setWindowPos(hwnd, after windows.HWND, x, y, cx, cy int, fl uint) {
	procSetWindowPos.Call(uintptr(hwnd), uintptr(after),
		uintptr(x), uintptr(y), uintptr(cx), uintptr(cy), uintptr(fl))
}
func getWindowLong(hwnd windows.HWND, idx int32) int32 {
	r, _, _ := procGetWindowLong.Call(uintptr(hwnd), uintptr(idx))
	return int32(r)
}
func setWindowLong(hwnd windows.HWND, idx, val int32) {
	procSetWindowLong.Call(uintptr(hwnd), uintptr(idx), uintptr(val))
}
func getCursorPos() (int32, int32) {
	var pt POINT
	procGetCursorPos.Call(uintptr(unsafe.Pointer(&pt)))
	return pt.X, pt.Y
}
func getAsyncKeyState(vk int) uintptr {
	r, _, _ := procGetAsyncKeyState.Call(uintptr(vk))
	return r
}
func isWindow(hwnd windows.HWND) bool {
	r, _, _ := procIsWindow.Call(uintptr(hwnd))
	return r != 0
}
func findOurWindow(title string) windows.HWND {
	p, _ := windows.UTF16PtrFromString(title)
	h, _, _ := procFindWindow.Call(0, uintptr(unsafe.Pointer(p)))
	return windows.HWND(h)
}
func findWindowByClass(className string) windows.HWND {
	p, _ := windows.UTF16PtrFromString(className)
	h, _, _ := procFindWindow.Call(uintptr(unsafe.Pointer(p)), 0)
	return windows.HWND(h)
}

// findDesktopWorkerW finds the desktop wallpaper host window behind desktop icons.
// Windows creates WorkerW behind SHELLDLL_DefView when 0x052C is sent to Progman.
func findDesktopWorkerW() windows.HWND {
	ensureDefaultDesktop()
	progman := findWindowByClass("Progman")
	log.Printf("[InfoSphere] findDesktopWorkerW: progman = 0x%X", progman)
	if progman == 0 {
		return 0
	}

	// Trigger Explorer to ensure the background wallpaper WorkerW is spawned
	var result uintptr
	procSendMessageTimeout.Call(
		uintptr(progman),
		0x052C,
		0,
		0,
		0, // SMTO_NORMAL
		1000,
		uintptr(unsafe.Pointer(&result)),
	)

	pWorkerW, _ := windows.UTF16PtrFromString("WorkerW")
	pDefView, _ := windows.UTF16PtrFromString("SHELLDLL_DefView")

	// 1. Windows 11: WorkerW is spawned as a child inside Progman right behind SHELLDLL_DefView
	w, _, _ := procFindWindowEx.Call(uintptr(progman), 0, uintptr(unsafe.Pointer(pWorkerW)), 0)
	log.Printf("[InfoSphere] findDesktopWorkerW: WorkerW in Progman = 0x%X", w)
	if w != 0 {
		return windows.HWND(w)
	}

	// 2. Windows 10: SHELLDLL_DefView is in a top-level WorkerW, and the wallpaper layer
	// is the sibling WorkerW created right behind it
	var found windows.HWND
	cb := windows.NewCallback(func(h windows.HWND, _ uintptr) uintptr {
		dv, _, _ := procFindWindowEx.Call(uintptr(h), 0, uintptr(unsafe.Pointer(pDefView)), 0)
		if dv != 0 {
			nextW, _, _ := procFindWindowEx.Call(0, uintptr(h), uintptr(unsafe.Pointer(pWorkerW)), 0)
			if nextW != 0 {
				found = windows.HWND(nextW)
				return 0 // Stop enumeration
			}
		}
		return 1
	})
	procEnumWindows.Call(cb, 0)
	if found != 0 {
		return found
	}

	return 0
}

// ─── True Desktop Wallpaper Embedding (behind desktop icons) ───────────────
// Embeds the WebView2 window into the WorkerW layer.
// This puts the desktop icons (SHELLDLL_DefView / SysListView32) ON TOP of our
// wallpaper, making it a real native Windows wallpaper:
//   - Desktop icons are visible and fully interactive
//   - Right-click shows the native Windows desktop context menu
//   - Left-click drag on the desktop draws the Windows selection rectangle
//   - Fish & globe still react to mouse movement via the global Win32 mouse bridge
// showAllChildWindows recursively ensures all Chromium/D3D sub-windows are visible
func showAllChildWindows(h windows.HWND) {
	procShowWindow.Call(uintptr(h), 5) // SW_SHOW = 5
	var child uintptr
	for {
		child, _, _ = procFindWindowEx.Call(uintptr(h), child, 0, 0)
		if child == 0 {
			break
		}
		showAllChildWindows(windows.HWND(child))
	}
}

func positionAsWallpaper(hwnd, workerW windows.HWND) {
	w := getSystemMetrics(0)
	h := getSystemMetrics(1)

	if workerW == 0 || !isWindow(workerW) {
		workerW = findDesktopWorkerW()
	}
	if workerW != 0 && isWindow(workerW) {
		log.Printf("[InfoSphere] Embedding into WorkerW (0x%X) behind desktop icons...", workerW)

		// 1. Convert to child window of WorkerW
		style := getWindowLong(hwnd, GWL_STYLE)
		style &^= WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
		style |= WS_CHILD | WS_VISIBLE
		setWindowLong(hwnd, GWL_STYLE, style)

		// 2. Clear extended styles that don't apply to child windows
		ex := getWindowLong(hwnd, GWL_EXSTYLE)
		ex &^= WS_EX_APPWINDOW
		setWindowLong(hwnd, GWL_EXSTYLE, ex)

		// 3. SetParent to WorkerW — makes it physically part of desktop layer
		procSetParent.Call(uintptr(hwnd), uintptr(workerW))

		// 4. Position to fill WorkerW client area
		setWindowPos(hwnd, 0, 0, 0, int(w), int(h), SWP_SHOWWINDOW|SWP_NOACTIVATE|SWP_FRAMECHANGED)
		log.Printf("[InfoSphere] Embedded successfully: %dx%d inside WorkerW (desktop icons on top)", w, h)

		// Explicitly show all inner Chromium rendering windows
		showAllChildWindows(hwnd)

		// 5. Watchdog: ensure parent, visibility, and size stay locked even if Explorer restarts
		go func() {
			for {
				time.Sleep(2 * time.Second)
				if !isWindow(hwnd) {
					return
				}
				if isWindow(workerW) {
					p, _, _ := procGetParent.Call(uintptr(hwnd))
					if windows.HWND(p) != workerW {
						procSetParent.Call(uintptr(hwnd), uintptr(workerW))
						setWindowPos(hwnd, 0, 0, 0, int(w), int(h), SWP_SHOWWINDOW|SWP_NOACTIVATE)
					}
					showAllChildWindows(hwnd)
				}
			}
		}()
	} else {
		// Fallback for safety (e.g. if Progman couldn't be contacted)
		log.Printf("[InfoSphere] WorkerW not found, falling back to HWND_BOTTOM")
		style := getWindowLong(hwnd, GWL_STYLE)
		style &^= WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
		setWindowLong(hwnd, GWL_STYLE, style)

		ex := getWindowLong(hwnd, GWL_EXSTYLE)
		ex &^= WS_EX_APPWINDOW
		ex |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
		setWindowLong(hwnd, GWL_EXSTYLE, ex)

		setWindowPos(hwnd, HWND_BOTTOM, 0, 0, int(w), int(h),
			SWP_SHOWWINDOW|SWP_NOACTIVATE|SWP_FRAMECHANGED)
	}
}



// ─── Mouse state (polled at 60 Hz, read by JS via go_mouse binding) ──────────
var (
	mouseX    int32
	mouseY    int32
	lbtnState int32
	rbtnState int32
)

func pollMouse() {
	for {
		x, y := getCursorPos()
		atomic.StoreInt32(&mouseX, x)
		atomic.StoreInt32(&mouseY, y)
		var lb, rb int32
		if getAsyncKeyState(0x01)&0x8000 != 0 {
			lb = 1
		}
		if getAsyncKeyState(0x02)&0x8000 != 0 {
			rb = 1
		}
		atomic.StoreInt32(&lbtnState, lb)
		atomic.StoreInt32(&rbtnState, rb)
		time.Sleep(33 * time.Millisecond) // ~30 Hz: silky responsiveness, 50% less CPU context switching
	}
}

// ─── SSE hub (replaces infosphere_hub.exe) ───────────────────────────────────
type sseHub struct {
	mu       sync.RWMutex
	clients  map[chan []byte]struct{}
	lastSnap []byte
	lastCfg  []byte
}

func newSSEHub() *sseHub {
	return &sseHub{clients: make(map[chan []byte]struct{})}
}

func (h *sseHub) subscribe() chan []byte {
	ch := make(chan []byte, 16)
	h.mu.Lock()
	h.clients[ch] = struct{}{}
	snap := h.lastSnap
	h.mu.Unlock()
	if len(snap) > 0 {
		ch <- snap
	}
	return ch
}

func (h *sseHub) unsubscribe(ch chan []byte) {
	h.mu.Lock()
	delete(h.clients, ch)
	h.mu.Unlock()
	close(ch)
}

func (h *sseHub) broadcast(data []byte) {
	h.mu.Lock()
	h.lastSnap = data
	for ch := range h.clients {
		select {
		case ch <- data:
		default:
		}
	}
	h.mu.Unlock()
}

// watchFiles monitors system_snapshot.json and config.json at 1.0 Hz (cool, zero-CPU)
func (h *sseHub) watchFiles(root string) {
	snapPath := filepath.Join(root, "output", "system_snapshot.json")
	cfgPath  := filepath.Join(root, "config.json")
	var lastSnap, lastCfg time.Time
	var ticks int

	for range time.Tick(1000 * time.Millisecond) {
		ticks++
		if ticks%30 == 0 {
			debug.FreeOSMemory() // Release unused heap to Windows OS kernel
		}
		if fi, err := os.Stat(snapPath); err == nil && fi.ModTime().After(lastSnap) {
			lastSnap = fi.ModTime()
			if raw, err := os.ReadFile(snapPath); err == nil && len(raw) > 0 {
				var js json.RawMessage
				if json.Unmarshal(raw, &js) == nil {
					msg, _ := json.Marshal(map[string]interface{}{
						"type": "snapshot", "timestamp": time.Now().UnixNano(), "data": js,
					})
					h.broadcast(msg)
				}
			}
		}
		if fi, err := os.Stat(cfgPath); err == nil && fi.ModTime().After(lastCfg) {
			lastCfg = fi.ModTime()
			if raw, err := os.ReadFile(cfgPath); err == nil && len(raw) > 0 {
				var js json.RawMessage
				if json.Unmarshal(raw, &js) == nil {
					msg, _ := json.Marshal(map[string]interface{}{
						"type": "config", "timestamp": time.Now().UnixNano(), "data": js,
					})
					h.broadcast(msg)
				}
			}
		}
	}
}

// ─── HTTP server (file server + SSE + API) ───────────────────────────────────

// checkPortFree returns nil if the port is available to bind, or an error if it is already in use.
func checkPortFree(port int) error {
	addr := fmt.Sprintf("127.0.0.1:%d", port)
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return err
	}
	ln.Close()
	return nil
}

func startServer(root string, port int, hub *sseHub) error {
	cors := func(w http.ResponseWriter) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	}

	// SSE endpoint
	http.HandleFunc("/events", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		fl, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "streaming unsupported", 500)
			return
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")
		ch := hub.subscribe()
		defer hub.unsubscribe(ch)
		fmt.Fprintf(w, "event: connected\ndata: {\"status\":\"ok\"}\n\n")
		fl.Flush()
		for {
			select {
			case <-r.Context().Done():
				return
			case msg, ok := <-ch:
				if !ok {
					return
				}
				fmt.Fprintf(w, "data: %s\n\n", msg)
				fl.Flush()
			}
		}
	})

	// Snapshot REST
	http.HandleFunc("/api/snapshot", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		w.Header().Set("Content-Type", "application/json")
		if d, err := os.ReadFile(filepath.Join(root, "output", "system_snapshot.json")); err == nil {
			w.Write(d)
		} else {
			http.Error(w, `{"error":"not ready"}`, 503)
		}
	})

	// Config REST
	http.HandleFunc("/api/config", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		f := filepath.Join(root, "config.json")
		if r.Method == http.MethodPost {
			var js json.RawMessage
			if err := json.NewDecoder(r.Body).Decode(&js); err == nil {
				os.WriteFile(f, js, 0644)
				w.Header().Set("Content-Type", "application/json")
				w.Write([]byte(`{"status":"updated"}`))
				return
			}
			http.Error(w, "bad json", 400)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		if d, err := os.ReadFile(f); err == nil {
			w.Write(d)
		} else {
			http.Error(w, `{"error":"not found"}`, 404)
		}
	})

	// Pictures API (dynamically lists all images from Picture/Original Picture)
	http.HandleFunc("/api/pictures", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		w.Header().Set("Content-Type", "application/json")
		picDir := filepath.Join(root, "Picture", "Original Picture")
		entries, err := os.ReadDir(picDir)
		if err != nil {
			http.Error(w, `[]`, 200)
			return
		}
		var list []string
		for _, e := range entries {
			if !e.IsDir() {
				ext := strings.ToLower(filepath.Ext(e.Name()))
				if ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".webp" {
					list = append(list, e.Name())
				}
			}
		}
		json.NewEncoder(w).Encode(list)
	})

	// 1-Click Automated In-App Update API
	http.HandleFunc("/api/update/start", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		if r.Method != http.MethodPost {
			http.Error(w, `{"error":"method not allowed"}`, http.StatusMethodNotAllowed)
			return
		}
		cmd := exec.Command("python", "core/updater.py", "--start")
		cmd.Dir = root
		if err := cmd.Start(); err != nil {
			log.Printf("[Updater] Failed to launch updater: %v", err)
			http.Error(w, fmt.Sprintf(`{"error":"%v"}`, err), http.StatusInternalServerError)
			return
		}
		// Reap the child process in background to avoid zombie accumulation
		go func() { _ = cmd.Wait() }()
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"started"}`))
	})

	http.HandleFunc("/api/update/status", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		w.Header().Set("Content-Type", "application/json")
		statusFile := filepath.Join(root, "output", "update_status.json")
		if d, err := os.ReadFile(statusFile); err == nil {
			w.Write(d)
		} else {
			w.Write([]byte(`{"status":"IDLE","pct":0,"message":"Ready"}`))
		}
	})

	// Static files
	fs := http.FileServer(http.Dir(root))
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		w.Header().Set("Cache-Control", "no-cache")
		if strings.HasSuffix(r.URL.Path, ".html") {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
		}
		fs.ServeHTTP(w, r)
	})

	addr := fmt.Sprintf("127.0.0.1:%d", port)

	// Bind the listener synchronously so we can return an error immediately
	// if the port is already in use (another instance running).
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return fmt.Errorf("port %d already in use: %w", port, err)
	}
	log.Printf("[InfoSphere] HTTP server on http://%s", addr)
	go func() {
		if err := http.Serve(ln, nil); err != nil {
			log.Printf("[InfoSphere] Server notice: %v", err)
		}
	}()
	time.Sleep(200 * time.Millisecond)
	return nil
}

// ─── Entry point ─────────────────────────────────────────────────────────────
func main() {
	runtime.LockOSThread()

	// Project root = directory where this exe lives
	exe, _ := os.Executable()
	root, _ := filepath.Abs(filepath.Dir(exe))

	// Setup logging to logs/wallpaper_go.log immediately
	os.MkdirAll(filepath.Join(root, "logs"), 0755)
	if logFile, err := os.OpenFile(filepath.Join(root, "logs", "wallpaper_go.log"), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666); err == nil {
		defer logFile.Close()
		log.SetOutput(logFile)
	}

	defer func() {
		if r := recover(); r != nil {
			log.Printf("[InfoSphere] PANIC in main: %v", r)
		}
		log.Printf("[InfoSphere] main() finished, process exiting.")
	}()

	ensureDefaultDesktop()
	initDPI()

	log.Printf("[InfoSphere] === Starting Wallpaper Engine ===")
	log.Printf("[InfoSphere] Root: %s", root)

	// ── Prevent duplicate instances — named mutex singleton guard ─────────────
	// CreateMutex returns a handle AND sets GetLastError()=ERROR_ALREADY_EXISTS(183)
	// when the mutex already exists. lastErr is syscall.Errno from .Call().
	const port = 8090
	mutexName, _ := windows.UTF16PtrFromString("Local\\InfoSphereLiveWallpaperGo")
	hMutex, _, lastErr := procCreateMutex.Call(0, 0, uintptr(unsafe.Pointer(mutexName)))
	// syscall.Errno(183) == ERROR_ALREADY_EXISTS
	if syscall.Errno(183) == lastErr.(syscall.Errno) {
		// Another instance holds the mutex — exit immediately and silently.
		log.Printf("[InfoSphere] Mutex: another instance is already running. Exiting cleanly.")
		if hMutex != 0 {
			windows.CloseHandle(windows.Handle(hMutex))
		}
		return
	}
	// Port-based double-check: if another process already bound 8090, bail out.
	if err := checkPortFree(port); err != nil {
		log.Printf("[InfoSphere] Port %d already in use — another instance is running. Exiting cleanly.", port)
		if hMutex != 0 {
			windows.CloseHandle(windows.Handle(hMutex))
		}
		return
	}
	if hMutex != 0 {
		defer windows.CloseHandle(windows.Handle(hMutex))
	}

	hub := newSSEHub()
	go hub.watchFiles(root)
	if err := startServer(root, port, hub); err != nil {
		log.Printf("[InfoSphere] Cannot start HTTP server: %v — another instance may be running. Exiting.", err)
		return
	}
	log.Printf("[InfoSphere] Step 1: Starting mouse poll...")
	go pollMouse()

	url := fmt.Sprintf("http://127.0.0.1:%d/infosphere_live_wallpaper.html", port)
	log.Printf("[InfoSphere] Step 2: URL is %s", url)

	log.Printf("[InfoSphere] Step 3: Calling webview.NewWithOptions...")
	w := webview.NewWithOptions(webview.WebViewOptions{
		Debug:     false,
		AutoFocus: true,
		WindowOptions: webview.WindowOptions{
			Title: "InfoSphere_Live_Wallpaper",
		},
	})
	if w == nil {
		log.Fatal("[InfoSphere] WebView2 failed — is Edge WebView2 Runtime installed?")
	}
	defer w.Destroy()

	// ── Get HWND directly from WebView2 (reliable — no FindWindow needed) ─
	hwnd := windows.HWND(uintptr(w.Window()))
	log.Printf("[InfoSphere] Step 4: WebView2 HWND: 0x%X", hwnd)

	// ── Wallpaper Lockdown: injected before page script runs ─────────────
	// Prevents text selection highlight, right-click menu, drag ghosts,
	// and text I-beam cursor — making it behave like a native OS wallpaper.
	w.Init(`
(function(){
  var s = document.createElement('style');
  s.textContent = '*,*::before,*::after{user-select:none!important;-webkit-user-select:none!important;cursor:default!important;-webkit-user-drag:none!important;}';
  document.head && document.head.appendChild(s);
  var block = function(e){ e.preventDefault(); e.stopPropagation(); return false; };
  document.addEventListener('contextmenu', block, true);
  document.addEventListener('selectstart', block, true);
  document.addEventListener('dragstart',   block, true);
})();`)

	// ── Inject pywebview shim so JS mouse bridge works without changes ────
	w.Init(`
(function(){
  window.pywebview = window.pywebview || {};
  window.pywebview.api = window.pywebview.api || {};
  window.pywebview.api.get_mouse = function(){
    return (typeof go_mouse === 'function')
      ? go_mouse()
      : Promise.resolve([-9999,-9999,false,false]);
  };
})();`)

	// Bind mouse state
	w.Bind("go_mouse", func() []interface{} {
		return []interface{}{
			atomic.LoadInt32(&mouseX),
			atomic.LoadInt32(&mouseY),
			atomic.LoadInt32(&lbtnState) == 1,
			atomic.LoadInt32(&rbtnState) == 1,
		}
	})

	log.Printf("[InfoSphere] Loading: %s", url)
	w.Navigate(url)

	// ── Wait for WebView2 to initialize, then position as interactive wallpaper ──
	// CRITICAL: Win32 window operations MUST run on the main UI thread.
	// We use w.Dispatch() to marshal the call back onto the WebView2 message loop.
	go func() {
		time.Sleep(1200 * time.Millisecond)
		workerW := findDesktopWorkerW()
		log.Printf("[InfoSphere] Background goroutine resolved WorkerW: 0x%X", workerW)
		w.Dispatch(func() {
			positionAsWallpaper(hwnd, workerW)
		})
	}()

	log.Printf("[InfoSphere] Live wallpaper running. Author: Mohammad Nazmul Haque, Habiganj")
	w.Run()
	log.Printf("[InfoSphere] w.Run() finished cleanly.")
}
