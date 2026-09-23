package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"runtime/debug"
	"strings"
	"sync"
	"time"
)

// Hub manages connected SSE clients and broadcasts telemetry snapshots
type Hub struct {
	mu           sync.RWMutex
	clients      map[chan []byte]bool
	lastSnapshot []byte
	lastConfig   []byte
	projectRoot  string
	port         string
}

func NewHub(root, port string) *Hub {
	return &Hub{
		clients:     make(map[chan []byte]bool),
		projectRoot: root,
		port:        port,
	}
}

func (h *Hub) addClient(ch chan []byte) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.clients[ch] = true
	// Immediately send the latest snapshot if available
	if len(h.lastSnapshot) > 0 {
		ch <- h.lastSnapshot
	}
}

func (h *Hub) removeClient(ch chan []byte) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if _, ok := h.clients[ch]; ok {
		delete(h.clients, ch)
		close(ch)
	}
}

func (h *Hub) Broadcast(data []byte) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.lastSnapshot = data
	for ch := range h.clients {
		select {
		case ch <- data:
		default:
			// Client channel full, skip
		}
	}
}

// WatchFiles monitors output/system_snapshot.json and config.json for changes
func (h *Hub) WatchFiles() {
	snapshotPath := filepath.Join(h.projectRoot, "output", "system_snapshot.json")
	configPath := filepath.Join(h.projectRoot, "config.json")

	var lastSnapMod time.Time
	var lastCfgMod time.Time

	ticker := time.NewTicker(1000 * time.Millisecond) // Cool, zero-CPU 1.0Hz checking
	defer ticker.Stop()
	var ticks int

	for range ticker.C {
		ticks++
		if ticks%30 == 0 {
			debug.FreeOSMemory() // Return unused heap pages to OS
		}
		// Check system_snapshot.json
		if info, err := os.Stat(snapshotPath); err == nil {
			if info.ModTime().After(lastSnapMod) {
				lastSnapMod = info.ModTime()
				if data, err := os.ReadFile(snapshotPath); err == nil && len(data) > 0 {
					var js json.RawMessage
					if json.Unmarshal(data, &js) == nil {
						msg := map[string]interface{}{
							"type":      "snapshot",
							"timestamp": time.Now().UnixNano(),
							"data":      js,
						}
						if payload, err := json.Marshal(msg); err == nil {
							h.Broadcast(payload)
						}
					}
				}
			}
		}

		// Check config.json
		if info, err := os.Stat(configPath); err == nil {
			if info.ModTime().After(lastCfgMod) {
				lastCfgMod = info.ModTime()
				if data, err := os.ReadFile(configPath); err == nil && len(data) > 0 {
					var js json.RawMessage
					if json.Unmarshal(data, &js) == nil {
						msg := map[string]interface{}{
							"type":      "config",
							"timestamp": time.Now().UnixNano(),
							"data":      js,
						}
						if payload, err := json.Marshal(msg); err == nil {
							h.Broadcast(payload)
						}
					}
				}
			}
		}
	}
}

func main() {
	// Determine project root directory
	exePath, err := os.Executable()
	var rootDir string
	if err == nil {
		// If running in core/hub, parent-parent is project root
		candidate := filepath.Join(filepath.Dir(exePath), "..", "..")
		if _, err := os.Stat(filepath.Join(candidate, "config.json")); err == nil {
			rootDir = candidate
		}
	}
	if rootDir == "" {
		// Fallback to current working directory
		cwd, _ := os.Getwd()
		rootDir = cwd
		if _, err := os.Stat(filepath.Join(rootDir, "config.json")); err != nil {
			rootDir = filepath.Join(cwd, "..", "..")
		}
	}
	rootDir, _ = filepath.Abs(rootDir)

	port := "8090"
	if len(os.Args) > 1 {
		port = os.Args[1]
	}

	hub := NewHub(rootDir, port)
	go hub.WatchFiles()

	// ─── HTTP Endpoints ───────────────────────────────────────────────────

	// CORS helper
	enableCors := func(w http.ResponseWriter) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	}

	// SSE Real-Time Event Stream
	http.HandleFunc("/events", func(w http.ResponseWriter, r *http.Request) {
		enableCors(w)
		flusher, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")

		ch := make(chan []byte, 16)
		hub.addClient(ch)
		defer hub.removeClient(ch)

		// Send connected confirmation
		fmt.Fprintf(w, "event: connected\ndata: {\"status\":\"ok\",\"time\":%d}\n\n", time.Now().UnixMilli())
		flusher.Flush()

		ctx := r.Context()
		for {
			select {
			case <-ctx.Done():
				return
			case msg, ok := <-ch:
				if !ok {
					return
				}
				fmt.Fprintf(w, "data: %s\n\n", msg)
				flusher.Flush()
			}
		}
	})

	// JSON Snapshot REST API
	http.HandleFunc("/api/snapshot", func(w http.ResponseWriter, r *http.Request) {
		enableCors(w)
		w.Header().Set("Content-Type", "application/json")
		snapFile := filepath.Join(rootDir, "output", "system_snapshot.json")
		if data, err := os.ReadFile(snapFile); err == nil {
			w.Write(data)
		} else {
			http.Error(w, "{\"error\":\"Snapshot not ready\"}", http.StatusServiceUnavailable)
		}
	})

	// Config REST API (GET & POST for instant updates)
	http.HandleFunc("/api/config", func(w http.ResponseWriter, r *http.Request) {
		enableCors(w)
		cfgFile := filepath.Join(rootDir, "config.json")

		if r.Method == http.MethodPost {
			body, err := io.ReadAll(r.Body)
			if err != nil {
				http.Error(w, "Invalid body", http.StatusBadRequest)
				return
			}
			var js map[string]interface{}
			if err := json.Unmarshal(body, &js); err != nil {
				http.Error(w, "Invalid JSON", http.StatusBadRequest)
				return
			}
			if err := os.WriteFile(cfgFile, body, 0644); err != nil {
				http.Error(w, "Failed to save config", http.StatusInternalServerError)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			w.Write([]byte("{\"status\":\"updated\"}"))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		if data, err := os.ReadFile(cfgFile); err == nil {
			w.Write(data)
		} else {
			http.Error(w, "{\"error\":\"Config not found\"}", http.StatusNotFound)
		}
	})

	// Static File Server for Live Wallpaper Assets
	fileServer := http.FileServer(http.Dir(rootDir))
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		enableCors(w)
		// Custom headers for smooth rendering
		w.Header().Set("Cache-Control", "no-cache")
		if strings.HasSuffix(r.URL.Path, ".html") {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
		}
		fileServer.ServeHTTP(w, r)
	})

	log.Printf("================================================================")
	log.Printf("  InfoSphere Intelligent Live Wallpaper · Go Event Hub")
	log.Printf("  Serving at: http://127.0.0.1:%s", port)
	log.Printf("  Live SSE Event Stream : http://127.0.0.1:%s/events", port)
	log.Printf("  Project Root Directory: %s", rootDir)
	log.Printf("================================================================")

	if err := http.ListenAndServe("127.0.0.1:"+port, nil); err != nil {
		log.Fatalf("Fatal: Go Event Hub server failed: %v", err)
	}
}
