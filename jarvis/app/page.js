"use client";

import { useState, useEffect } from "react";

const DEFAULT_SETTINGS = {
    refresh_interval_seconds: 10,
    resolution_width: "auto",
    resolution_height: "auto",
    display_mode: "primary",
    weather_city: "auto",
    show_weather: true,
    router: { enabled: false, ip: "192.168.0.1", refresh_secs: 10 },
    speedtest: { enabled: false },
    operator_profile: { enabled: true, name: "Local Operator", title: "System Administrator" },
    accessibility: { theme: "default", density: "comfortable", reduce_motion: false, font_scale: 1 },
};

function SourceBadge({ source, fallback = "UNAVAILABLE" }) {
    const label = source?.label || fallback;
    return <span className={`source-badge source-${label.toLowerCase()}`} title={source?.source || "Source unavailable"}>{label}</span>;
}

export default function Dashboard() {
    const [metrics, setMetrics] = useState({
        cpu: 0,
        ram: { total: 0, used: 0, pct: 0 },
        disks: [],
        network: [],
        uptime: 0
    });
    const [build, setBuild] = useState({
        repo: "Local Project",
        files: 0,
        branch: "N/A",
        status: "N/A"
    });
    const [posts, setPosts] = useState([]);
    const [newPost, setNewPost] = useState({ content: "", platform: "Twitter" });
    const [camFeed, setCamFeed] = useState({ active_file: "N/A", size_kb: 0, timestamp: Date.now() / 1000 });
    const [sysTime, setSysTime] = useState("00:00:00");
    const [cacheBuster, setCacheBuster] = useState(Date.now());
    const [provenance, setProvenance] = useState({});
    const [csrfToken, setCsrfToken] = useState("");
    const [settings, setSettings] = useState(DEFAULT_SETTINGS);
    const [saveStatus, setSaveStatus] = useState("");
    const [snapshotStatus, setSnapshotStatus] = useState("CONNECTING");
    const [appVersion, setAppVersion] = useState("2.1.0");

    // Camera slide transition state variables
    const [currentFile, setCurrentFile] = useState("");
    const [prevFile, setPrevFile] = useState("");
    const [isTransitioning, setIsTransitioning] = useState(false);

    // Dynamic router monitor & logs state variables
    const [routerData, setRouterData] = useState({ status: "UNKNOWN", total_online: 0, clients: [], tx_total_mb: 0, rx_total_mb: 0, band_5_count: 0, band_24_count: 0, wired_count: 0 });
    const [logs, setLogs] = useState([]);

    // Watch for camera picture changes to trigger flying animations
    useEffect(() => {
        if (!camFeed.active_file || camFeed.active_file === "N/A") return;
        
        if (!currentFile) {
            setCurrentFile(camFeed.active_file);
        } else if (currentFile !== camFeed.active_file) {
            setPrevFile(currentFile);
            setCurrentFile(camFeed.active_file);
            setIsTransitioning(true);
            
            const timer = setTimeout(() => {
                setPrevFile("");
                setIsTransitioning(false);
            }, 800);
            return () => clearTimeout(timer);
        }
    }, [camFeed.active_file, currentFile]);

    // Local system clock running in header
    useEffect(() => {
        setSysTime(new Date().toTimeString().split(" ")[0]);
        const clockTimer = setInterval(() => {
            setSysTime(new Date().toTimeString().split(" ")[0]);
        }, 1000);
        return () => clearInterval(clockTimer);
    }, []);

    // One canonical snapshot drives every live panel.
    useEffect(() => {
        const fetchSnapshot = async () => {
            try {
                const res = await fetch("/api/snapshot", { cache: "no-store" });
                if (!res.ok) throw new Error(`Snapshot HTTP ${res.status}`);
                const data = await res.json();
                setMetrics(data.metrics || metrics);
                setRouterData(data.router || {});
                setLogs(data.telemetry || []);
                setCamFeed(data.camera || {});
                setProvenance(data.provenance || {});
                setAppVersion(data.app_version || "2.1.0");
                setCacheBuster(Date.now());
                setSnapshotStatus("LIVE");
            } catch (err) {
                console.error("Error fetching telemetry snapshot:", err);
                setSnapshotStatus("OFFLINE");
            }
        };
        fetchSnapshot();
        const interval = setInterval(fetchSnapshot, 3000);
        return () => clearInterval(interval);
        // Initial metric defaults are intentionally not dependencies.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Poll git repository build status (every 10 seconds)
    useEffect(() => {
        const fetchBuild = async () => {
            try {
                const res = await fetch("/api/build");
                if (res.ok) {
                    const data = await res.json();
                    setBuild(data);
                }
            } catch (err) {
                console.error("Error fetching build status:", err);
            }
        };
        fetchBuild();
        const interval = setInterval(fetchBuild, 10000);
        return () => clearInterval(interval);
    }, []);

    // Fetch session token, settings, and timeline on load.
    const fetchPosts = async () => {
        try {
            const res = await fetch("/api/posts");
            if (res.ok) {
                const data = await res.json();
                setPosts(data);
            }
        } catch (err) {
            console.error("Error fetching posts:", err);
        }
    };

    useEffect(() => {
        fetchPosts();
        fetch("/api/session", { cache: "no-store" })
            .then(res => res.ok ? res.json() : Promise.reject(new Error("Session unavailable")))
            .then(data => setCsrfToken(data.csrf_token || ""))
            .catch(err => console.error(err));
        fetch("/api/settings", { cache: "no-store" })
            .then(res => res.ok ? res.json() : Promise.reject(new Error("Settings unavailable")))
            .then(data => setSettings({ ...DEFAULT_SETTINGS, ...data }))
            .catch(err => console.error(err));
    }, []);

    useEffect(() => {
        const root = document.documentElement;
        root.dataset.theme = settings.accessibility?.theme || "default";
        root.dataset.density = settings.accessibility?.density || "comfortable";
        root.dataset.reduceMotion = settings.accessibility?.reduce_motion ? "true" : "false";
        root.style.setProperty("--user-font-scale", String(settings.accessibility?.font_scale || 1));
    }, [settings.accessibility]);

    // Form submit handler for social publishing
    const handlePublish = async (e) => {
        e.preventDefault();
        if (!newPost.content.trim()) return;

        try {
            const res = await fetch("/api/posts", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
                body: JSON.stringify(newPost)
            });
            if (res.ok) {
                setNewPost({ ...newPost, content: "" });
                fetchPosts();
            }
        } catch (err) {
            console.error("Error publishing update:", err);
        }
    };

    const handleSaveSettings = async (event) => {
        event.preventDefault();
        setSaveStatus("SAVING");
        try {
            const res = await fetch("/api/settings", {
                method: "PUT",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
                body: JSON.stringify(settings),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Settings update failed");
            setSettings({ ...DEFAULT_SETTINGS, ...data.settings });
            setSaveStatus(data.restart_required ? "SAVED · RESTART ENGINE" : "SAVED");
        } catch (error) {
            setSaveStatus(`ERROR · ${error.message}`);
        }
    };

    // Calculate circular dial path offset
    const RADIUS = 50;
    const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
    const getStrokeOffset = (pct) => {
        const value = Math.min(100, Math.max(0, pct || 0));
        return CIRCUMFERENCE - (value / 100) * CIRCUMFERENCE;
    };

    // Format uptime (seconds to HH:MM:SS)
    const formatUptime = (seconds) => {
        if (!seconds) return "00:00:00";
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
    };

    // Parse network speed rates
    const rxRate = metrics.network && metrics.network.length > 0 ? metrics.network[0].rx : 0.0;
    const txRate = metrics.network && metrics.network.length > 0 ? metrics.network[0].tx : 0.0;

    // Convert active picture size to readable text
    const camSizeText = camFeed.size_kb ? `${camFeed.size_kb.toFixed(2)} KB` : "0.00 KB";

    return (
        <>
            <div className="glow-bg"></div>

            <header>
                <div className="logo">
                    <div className="dot green"></div>
                    <div className="dot blue"></div>
                    <div className="dot cyan"></div>
                    <h1>INFOSPHERE // JARVIS v{appVersion}</h1>
                </div>
                <div className="header-status">
                    <span className={`snapshot-state state-${snapshotStatus.toLowerCase()}`}>{snapshotStatus}</span>
                    <div className="sys-time">{sysTime}</div>
                </div>
            </header>

            <main className="grid-container">
                {/* 1. System Health Panel */}
                <section className="panel" id="systemPanel">
                    <div className="panel-header">
                        <div className="indicator green"></div>
                        <h2>SYSTEM HEALTH MONITOR</h2>
                        <SourceBadge source={provenance.system} fallback="MEASURED" />
                    </div>
                    <div className="panel-content">
                        <div className="stats-dials">
                            <div className="dial-container">
                                <svg className="progress-ring" width="120" height="120">
                                    <circle
                                        className="progress-ring__background"
                                        stroke="#0f1a30"
                                        strokeWidth="8"
                                        fill="transparent"
                                        r={RADIUS}
                                        cx="60"
                                        cy="60"
                                    />
                                    <circle
                                        className="progress-ring__circle"
                                        stroke="#00F5FF"
                                        strokeWidth="8"
                                        strokeDasharray={CIRCUMFERENCE}
                                        strokeDashoffset={getStrokeOffset(metrics.cpu)}
                                        fill="transparent"
                                        r={RADIUS}
                                        cx="60"
                                        cy="60"
                                    />
                                </svg>
                                <div className="dial-label">
                                    <span className="value">{metrics.cpu}%</span>
                                    <span className="label">CPU LOAD</span>
                                </div>
                            </div>

                            <div className="dial-container">
                                <svg className="progress-ring" width="120" height="120">
                                    <circle
                                        className="progress-ring__background"
                                        stroke="#0f1a30"
                                        strokeWidth="8"
                                        fill="transparent"
                                        r={RADIUS}
                                        cx="60"
                                        cy="60"
                                    />
                                    <circle
                                        className="progress-ring__circle"
                                        stroke="#00FF88"
                                        strokeWidth="8"
                                        strokeDasharray={CIRCUMFERENCE}
                                        strokeDashoffset={getStrokeOffset(metrics.ram.pct)}
                                        fill="transparent"
                                        r={RADIUS}
                                        cx="60"
                                        cy="60"
                                    />
                                </svg>
                                <div className="dial-label">
                                    <span className="value">{metrics.ram.pct}%</span>
                                    <span className="label">RAM LOAD</span>
                                </div>
                            </div>
                        </div>
                        <div className="ram-details">
                            RAM: {((metrics.ram.used || 0) / 1073741824).toFixed(2)} GB / {((metrics.ram.total || 0) / 1073741824).toFixed(2)} GB
                        </div>
                    </div>
                </section>

                {/* 2. Claude Connector & Network Panel */}
                <section className="panel" id="networkPanel">
                    <div className="panel-header">
                        <div className="indicator cyan"></div>
                        <h2>CLAUDE CONNECTOR & NETWORK</h2>
                        <SourceBadge source={provenance.network} fallback="MEASURED" />
                    </div>
                    <div className="panel-content">
                        <div className="connector-status">
                            <div className="status-badge">
                                <span className="pulse-dot"></span>
                                <span className="badge-text">MCP CLAUDE CONNECTOR: ACTIVE</span>
                            </div>
                            <div className="meta-label">Transport: Standard Input / Output (STDIO)</div>
                        </div>

                        <div className="net-speeds">
                            <div className="speed-box down">
                                <span className="arrow">↓</span>
                                <span className="speed-value">{rxRate.toFixed(2)} Mbps</span>
                                <span className="speed-label">DOWNLOAD SPEED</span>
                            </div>
                            <div className="speed-box up">
                                <span className="arrow">↑</span>
                                <span className="speed-value">{txRate.toFixed(2)} Mbps</span>
                                <span className="speed-label">UPLOAD SPEED</span>
                            </div>
                        </div>
                    </div>
                </section>

                {/* 3. Live HUD Camera Viewport Panel */}
                <section className="panel" id="cameraPanel">
                    <div className="panel-header">
                        <div className="indicator red"></div>
                        <h2>HUD STREAM VIEWPORT</h2>
                        <SourceBadge source={provenance.camera} fallback="CACHED" />
                    </div>
                    <div className="panel-content">
                        <div className="camera-viewport">
                            <div className="cam-recording">
                                <span className="rec-dot"></span>
                                <span className="rec-text">REC</span>
                            </div>
                            <div className="scanline-overlay"></div>
                            <div className="scanline-moving"></div>
                            <div className="crosshair-overlay"></div>

                            <div className="camera-image-container">
                                {prevFile && (
                                    /* eslint-disable-next-line @next/next/no-img-element */
                                    <img
                                        src={`/cache/${prevFile}`}
                                        alt="Previous Camera Frame"
                                        className="camera-image camera-image-fly-out"
                                    />
                                )}
                                {currentFile && (
                                    /* eslint-disable-next-line @next/next/no-img-element */
                                    <img
                                        src={`/cache/${currentFile}`}
                                        alt="Current Camera Frame"
                                        className={`camera-image ${isTransitioning ? "camera-image-fly-in" : "camera-image-idle"}`}
                                        key={currentFile}
                                    />
                                )}
                            </div>

                            <div className="cam-meta">
                                <span>CAM-01 (ACTIVE)</span>
                                <span>{camSizeText}</span>
                            </div>
                        </div>
                        <div className="ram-details" style={{ marginTop: "10px", fontSize: "0.8rem", color: "var(--cyan)" }}>
                            IMAGE FILE: {camFeed.active_file || "N/A"}
                        </div>
                    </div>
                </section>

                {/* 4. Active Repository Build Status */}
                <section className="panel" id="buildPanel">
                    <div className="panel-header">
                        <div className="indicator amber"></div>
                        <h2>ACTIVE REPOSITORY BUILD STATUS</h2>
                        <SourceBadge source={{ label: "CACHED", source: "15-second Git status cache" }} />
                    </div>
                    <div className="panel-content">
                        <div className="build-info">
                            <div className="info-row">
                                <span className="label">Target Repository:</span>
                                <span className="value cyan-text">{build.repo}</span>
                            </div>
                            <div className="info-row">
                                <span className="label">Total Code Files:</span>
                                <span className="value">{build.files}</span>
                            </div>
                            <div className="info-row">
                                <span className="label">Git Branch:</span>
                                <span className="value green-text">{build.branch}</span>
                            </div>
                            <div className="info-row">
                                <span className="label">Git Status:</span>
                                <span className={build.status === "CLEAN" ? "value green-text" : "value red-text"}>
                                    {build.status}
                                </span>
                            </div>
                        </div>
                    </div>
                </section>

                {/* 6. Dynamic Router & Telemetry Column */}
                <div className="panel-flex-column">
                    {/* Router Monitor Panel */}
                    <section className="panel flex-panel-content" id="routerDashboardPanel">
                        <div className="panel-header">
                            <div className="indicator cyan"></div>
                            <h2>ROUTER MONITOR</h2>
                            <SourceBadge source={provenance.router} fallback="UNAVAILABLE" />
                        </div>
                        <div className="panel-content" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-start', flexGrow: 1, overflow: 'hidden' }}>
                            <div className="net-speeds" style={{ marginBottom: '12px' }}>
                                <div className="speed-box" style={{ padding: '6px' }}>
                                    <span className="speed-value" style={{ fontSize: '0.9rem' }}>{routerData.total_online}</span>
                                    <span className="speed-label">ONLINE</span>
                                </div>
                                <div className="speed-box" style={{ padding: '6px' }}>
                                    <span className="speed-value" style={{ fontSize: '0.9rem' }}>{routerData.band_5_count}</span>
                                    <span className="speed-label">5 GHz</span>
                                </div>
                                <div className="speed-box" style={{ padding: '6px' }}>
                                    <span className="speed-value" style={{ fontSize: '0.9rem' }}>{routerData.band_24_count}</span>
                                    <span className="speed-label">2.4 GHz</span>
                                </div>
                                <div className="speed-box" style={{ padding: '6px' }}>
                                    <span className="speed-value" style={{ fontSize: '0.9rem' }}>{routerData.wired_count}</span>
                                    <span className="speed-label">WIRED</span>
                                </div>
                            </div>
                            
                            <div className="info-row" style={{ paddingBottom: '4px', marginBottom: '6px', fontSize: '0.75rem' }}>
                                <span className="label">TX Total: {routerData.tx_total_mb ? (routerData.tx_total_mb < 1024 ? `${routerData.tx_total_mb.toFixed(0)} MB` : `${(routerData.tx_total_mb/1024).toFixed(2)} GB`) : "0 MB"}</span>
                                <span className="label">RX Total: {routerData.rx_total_mb ? (routerData.rx_total_mb < 1024 ? `${routerData.rx_total_mb.toFixed(0)} MB` : `${(routerData.rx_total_mb/1024).toFixed(2)} GB`) : "0 MB"}</span>
                            </div>

                            <div className="device-table-container">
                                <table className="device-table">
                                    <thead>
                                        <tr>
                                            <th>DEVICE</th>
                                            <th>IP</th>
                                            <th>BAND</th>
                                            <th>TX/RX</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {routerData.clients && routerData.clients.length > 0 ? (
                                            routerData.clients.map((c, idx) => (
                                                <tr key={idx} className={c.is_blocked ? "blocked-row" : c.is_alerting ? "alerting-row" : ""}>
                                                    <td className="cyan-text" title={c.name}>{c.name}</td>
                                                    <td>{c.ip}</td>
                                                    <td>{c.band.replace(" GHz","G").replace("ired","")}</td>
                                                    <td>{c.tx_mb ? `${c.tx_mb.toFixed(1)}M` : "0"}/{c.rx_mb ? `${c.rx_mb.toFixed(1)}M` : "0"}</td>
                                                </tr>
                                            ))
                                        ) : (
                                            <tr>
                                                <td colSpan="4" style={{ textAlign: 'center', color: 'var(--text-dim)' }}>No devices online</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </section>

                    {/* Live Telemetry Panel */}
                    <section className="panel flex-panel-stretch" id="telemetryDashboardPanel">
                        <div className="panel-header">
                            <div className="indicator green"></div>
                            <h2>LIVE SYSTEM TELEMETRY</h2>
                            <SourceBadge source={provenance.telemetry} fallback="MEASURED" />
                        </div>
                        <div className="panel-content log-feed-container">
                            <div className="log-feed">
                                {logs && logs.length > 0 ? (
                                    logs.map((log, idx) => {
                                        let colClass = "log-default";
                                        if (log.includes("[ERROR")) colClass = "log-error";
                                        else if (log.includes("[WARN")) colClass = "log-warn";
                                        else if (log.includes("[OK")) colClass = "log-ok";
                                        else if (log.includes("[INFO")) colClass = "log-info";
                                        else if (log.includes("[SAFE")) colClass = "log-safe";
                                        
                                        return (
                                            <div key={idx} className={`log-row ${colClass}`}>
                                                {log}
                                            </div>
                                        );
                                    })
                                ) : (
                                    <div className="empty-feed">Awaiting system events...</div>
                                )}
                            </div>
                        </div>
                    </section>
                </div>

                {/* 5. Jarvis Social Publisher (Simulated) */}
                <section className="panel social-panel" id="socialPanel">
                    <div className="panel-header">
                        <div className="indicator blue"></div>
                        <h2>JARVIS SOCIAL PUBLISHER (SIMULATED)</h2>
                        <SourceBadge source={{ label: "SIMULATED", source: "Local-only draft timeline" }} />
                    </div>
                    <div className="panel-content social-grid">
                        <form className="post-form" onSubmit={handlePublish}>
                            <textarea
                                value={newPost.content}
                                onChange={(e) => setNewPost({ ...newPost, content: e.target.value })}
                                placeholder="Ask Jarvis to write an update or type your own milestone... (e.g. CPU load is normal at 14% and live cam rotating!)"
                                required
                            />
                            <div className="form-footer">
                                <select
                                    value={newPost.platform}
                                    onChange={(e) => setNewPost({ ...newPost, platform: e.target.value })}
                                >
                                    <option value="Twitter">Twitter / X</option>
                                    <option value="LinkedIn">LinkedIn</option>
                                    <option value="Mastodon">Mastodon</option>
                                </select>
                                <button type="submit" className="glow-button">PUBLISH SNAPSHOT</button>
                            </div>
                        </form>

                        <div className="feed-container">
                            <h3>LIVE SOCIAL TIMELINE</h3>
                            <div className="feed">
                                {posts.length === 0 ? (
                                    <div className="empty-feed">No published updates yet.</div>
                                ) : (
                                    posts.map((post) => (
                                        <div key={post.id} className="post-card">
                                            <div className="post-meta">
                                                <span className="post-platform">{post.platform}</span>
                                                <span>{new Date(post.timestamp).toLocaleTimeString()}</span>
                                            </div>
                                            <div className="post-content">{post.content}</div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>
                </section>

                <section className="panel settings-panel" id="settingsPanel">
                    <div className="panel-header">
                        <div className="indicator amber"></div>
                        <h2>ENGINE SETTINGS</h2>
                        <SourceBadge source={{ label: "LOCAL", source: "Validated local config.json" }} fallback="LOCAL" />
                    </div>
                    <form className="settings-form" onSubmit={handleSaveSettings}>
                        <fieldset>
                            <legend>DISPLAY & REFRESH</legend>
                            <label>Refresh seconds<input type="number" min="5" max="3600" value={settings.refresh_interval_seconds} onChange={e => setSettings({ ...settings, refresh_interval_seconds: Number(e.target.value) })} /></label>
                            <label>Width<input value={settings.resolution_width} onChange={e => setSettings({ ...settings, resolution_width: e.target.value })} placeholder="auto" /></label>
                            <label>Height<input value={settings.resolution_height} onChange={e => setSettings({ ...settings, resolution_height: e.target.value })} placeholder="auto" /></label>
                            <label>Display mode<select value={settings.display_mode} onChange={e => setSettings({ ...settings, display_mode: e.target.value })}><option value="primary">Primary</option><option value="virtual">All monitors</option></select></label>
                        </fieldset>

                        <fieldset>
                            <legend>DATA SOURCES</legend>
                            <label>Weather city<input value={settings.weather_city} onChange={e => setSettings({ ...settings, weather_city: e.target.value })} /></label>
                            <label>Router IP<input value={settings.router.ip} onChange={e => setSettings({ ...settings, router: { ...settings.router, ip: e.target.value } })} /></label>
                            <label>Router refresh<input type="number" min="5" max="3600" value={settings.router.refresh_secs} onChange={e => setSettings({ ...settings, router: { ...settings.router, refresh_secs: Number(e.target.value) } })} /></label>
                            <div className="toggle-grid">
                                <label><input type="checkbox" checked={settings.show_weather} onChange={e => setSettings({ ...settings, show_weather: e.target.checked })} /> Weather</label>
                                <label><input type="checkbox" checked={settings.router.enabled} onChange={e => setSettings({ ...settings, router: { ...settings.router, enabled: e.target.checked } })} /> Router</label>
                                <label><input type="checkbox" checked={settings.speedtest.enabled} onChange={e => setSettings({ ...settings, speedtest: { ...settings.speedtest, enabled: e.target.checked } })} /> Speed test</label>
                            </div>
                        </fieldset>

                        <fieldset>
                            <legend>OPERATOR PROFILE</legend>
                            <label>Name<input maxLength="64" value={settings.operator_profile.name} onChange={e => setSettings({ ...settings, operator_profile: { ...settings.operator_profile, name: e.target.value } })} /></label>
                            <label>Title<input maxLength="64" value={settings.operator_profile.title} onChange={e => setSettings({ ...settings, operator_profile: { ...settings.operator_profile, title: e.target.value } })} /></label>
                            <label className="check-label"><input type="checkbox" checked={settings.operator_profile.enabled} onChange={e => setSettings({ ...settings, operator_profile: { ...settings.operator_profile, enabled: e.target.checked } })} /> Show profile</label>
                        </fieldset>

                        <fieldset>
                            <legend>ACCESSIBILITY</legend>
                            <label>Theme<select value={settings.accessibility.theme} onChange={e => setSettings({ ...settings, accessibility: { ...settings.accessibility, theme: e.target.value } })}><option value="default">Default</option><option value="high_contrast">High contrast</option></select></label>
                            <label>Density<select value={settings.accessibility.density} onChange={e => setSettings({ ...settings, accessibility: { ...settings.accessibility, density: e.target.value } })}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label>
                            <label>Font scale<input type="number" step="0.05" min="0.85" max="1.15" value={settings.accessibility.font_scale} onChange={e => setSettings({ ...settings, accessibility: { ...settings.accessibility, font_scale: Number(e.target.value) } })} /></label>
                            <label className="check-label"><input type="checkbox" checked={settings.accessibility.reduce_motion} onChange={e => setSettings({ ...settings, accessibility: { ...settings.accessibility, reduce_motion: e.target.checked } })} /> Reduce motion</label>
                        </fieldset>

                        <div className="settings-actions">
                            <button type="submit" className="glow-button" disabled={!csrfToken || saveStatus === "SAVING"}>SAVE SETTINGS</button>
                            <span role="status" className="save-status">{saveStatus || "Changes are validated before writing."}</span>
                        </div>
                    </form>
                </section>
            </main>

            <footer>
                <div>Jarvis System Core v{appVersion}  |  Powered by Next.js & React</div>
                <div className="footer-right">Uptime: {formatUptime(metrics.uptime)}</div>
            </footer>
        </>
    );
}
