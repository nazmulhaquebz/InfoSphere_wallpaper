import crypto from "crypto";
import express from "express";
import fs from "fs";
import path from "path";
import { execFileSync } from "child_process";
import { fileURLToPath } from "url";
import next from "next";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createMcpServer } from "./core/mcp_server.js";

const JARVIS_ROOT = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(JARVIS_ROOT, "..");
const OUTPUT_DIR = path.join(PROJECT_ROOT, "output");
const SNAPSHOT_FILE = path.join(OUTPUT_DIR, "system_snapshot.json");
const ENGINE_CONFIG_FILE = path.join(PROJECT_ROOT, "config.json");
const JARVIS_CONFIG_FILE = path.join(JARVIS_ROOT, "config.json");
const POSTS_FILE = path.join(JARVIS_ROOT, "data", "social_posts.json");
const LOGS_DIR = path.join(JARVIS_ROOT, "logs");
const LOGS_FILE = path.join(LOGS_DIR, "jarvis.log");
const PID_FILE = path.join(OUTPUT_DIR, "jarvis.pid.json");
const HOST = "127.0.0.1";
const APP_VERSION = readText(path.join(PROJECT_ROOT, "VERSION"), "0.0.0-dev").trim();
const jarvisConfig = readJson(JARVIS_CONFIG_FILE, {});
const configuredPort = Number(jarvisConfig.port);
const PORT = Number.isInteger(configuredPort) && configuredPort >= 1024 && configuredPort <= 65535
    ? configuredPort
    : 8080;
const CSRF_TOKEN = crypto.randomBytes(32).toString("hex");
const ALLOWED_PLATFORMS = new Set(["Twitter", "LinkedIn", "Mastodon"]);

fs.mkdirSync(LOGS_DIR, { recursive: true });
fs.mkdirSync(OUTPUT_DIR, { recursive: true });
fs.mkdirSync(path.dirname(POSTS_FILE), { recursive: true });

function readJson(file, fallback) {
    try {
        const value = JSON.parse(fs.readFileSync(file, "utf-8"));
        return value ?? fallback;
    } catch {
        return fallback;
    }
}

function readText(file, fallback = "") {
    try { return fs.readFileSync(file, "utf-8"); } catch { return fallback; }
}

function writeJsonAtomic(file, value) {
    const temporary = `${file}.${process.pid}.tmp`;
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(temporary, JSON.stringify(value, null, 2), { encoding: "utf-8", flag: "w" });
    try {
        fs.renameSync(temporary, file);
    } catch {
        fs.copyFileSync(temporary, file);
        fs.unlinkSync(temporary);
    }
}

const logger = {
    info: (message) => {
        const line = `[${new Date().toISOString()}] [INFO] ${message}\n`;
        fs.appendFileSync(LOGS_FILE, line);
        console.error(line.trim());
    },
    error: (message) => {
        const line = `[${new Date().toISOString()}] [ERROR] ${message}\n`;
        fs.appendFileSync(LOGS_FILE, line);
        console.error(line.trim());
    },
};

console.log = (...args) => {
    const message = args.map(arg => typeof arg === "object" ? JSON.stringify(arg) : String(arg)).join(" ");
    logger.info(`[Console] ${message}`);
};

function getSnapshot() {
    return readJson(SNAPSHOT_FILE, {
        schema_version: "1.0",
        app_version: APP_VERSION,
        generated_at: null,
        refresh_seconds: 10,
        provenance: {},
        metrics: { cpu: 0, ram: { total: 0, used: 0, pct: 0 }, disks: [], network: [], uptime: 0 },
        system: {},
        router: { status: "NO DATA", total_online: 0, clients: [] },
        weather: {},
        speedtest: {},
        telemetry: ["[INFO] Telemetry snapshot is not available yet."],
        camera: { active_file: "N/A", size_kb: 0, timestamp: 0 },
        display: {},
    });
}

function publicSettings(config) {
    const router = config.router || {};
    const speedtest = config.speedtest || {};
    const profile = config.operator_profile || {};
    const accessibility = config.accessibility || {};
    return {
        refresh_interval_seconds: config.refresh_interval_seconds ?? 10,
        resolution_width: config.resolution_width ?? "auto",
        resolution_height: config.resolution_height ?? "auto",
        display_mode: config.display_mode || "primary",
        weather_city: config.weather_city || "auto",
        show_weather: config.show_weather !== false,
        router: {
            enabled: Boolean(router.enabled),
            ip: String(router.ip || "192.168.0.1"),
            refresh_secs: Number(router.refresh_secs || 10),
        },
        speedtest: { enabled: Boolean(speedtest.enabled) },
        operator_profile: {
            enabled: profile.enabled !== false,
            name: String(profile.name || "Local Operator"),
            title: String(profile.title || "System Administrator"),
        },
        accessibility: {
            theme: accessibility.theme || "default",
            density: accessibility.density || "comfortable",
            reduce_motion: Boolean(accessibility.reduce_motion),
            font_scale: Number(accessibility.font_scale || 1),
        },
    };
}

function boundedString(value, name, maxLength, fallback = "") {
    if (typeof value !== "string") return fallback;
    const clean = value.trim();
    if (!clean || clean.length > maxLength || /[\r\n\0]/.test(clean)) {
        throw new Error(`${name} must be 1-${maxLength} plain-text characters`);
    }
    return clean;
}

function boundedNumber(value, name, minimum, maximum) {
    const number = Number(value);
    if (!Number.isFinite(number) || number < minimum || number > maximum) {
        throw new Error(`${name} must be between ${minimum} and ${maximum}`);
    }
    return number;
}

function resolutionValue(value, name) {
    if (value === "auto") return "auto";
    return Math.round(boundedNumber(value, name, 320, 16384));
}

function mergeValidatedSettings(current, input) {
    if (!input || typeof input !== "object" || Array.isArray(input)) {
        throw new Error("settings body must be an object");
    }
    const nextConfig = structuredClone(current);
    nextConfig.refresh_interval_seconds = boundedNumber(input.refresh_interval_seconds, "refresh interval", 5, 3600);
    nextConfig.resolution_width = resolutionValue(input.resolution_width, "resolution width");
    nextConfig.resolution_height = resolutionValue(input.resolution_height, "resolution height");
    if (!["primary", "virtual"].includes(input.display_mode)) throw new Error("display mode is invalid");
    nextConfig.display_mode = input.display_mode;
    nextConfig.weather_city = boundedString(input.weather_city, "weather city", 64, "auto");
    nextConfig.show_weather = Boolean(input.show_weather);

    const router = input.router || {};
    nextConfig.router = { ...(current.router || {}) };
    nextConfig.router.enabled = Boolean(router.enabled);
    nextConfig.router.ip = boundedString(router.ip, "router IP", 255, "192.168.0.1");
    nextConfig.router.refresh_secs = boundedNumber(router.refresh_secs, "router refresh", 5, 3600);
    nextConfig.speedtest = { ...(current.speedtest || {}), enabled: Boolean(input.speedtest?.enabled) };

    const profile = input.operator_profile || {};
    nextConfig.operator_profile = {
        enabled: profile.enabled !== false,
        name: boundedString(profile.name, "operator name", 64, "Local Operator"),
        title: boundedString(profile.title, "operator title", 64, "System Administrator"),
    };

    const accessibility = input.accessibility || {};
    if (!["default", "high_contrast"].includes(accessibility.theme)) throw new Error("theme is invalid");
    if (!["compact", "comfortable"].includes(accessibility.density)) throw new Error("density is invalid");
    nextConfig.accessibility = {
        theme: accessibility.theme,
        density: accessibility.density,
        reduce_motion: Boolean(accessibility.reduce_motion),
        font_scale: boundedNumber(accessibility.font_scale, "font scale", 0.85, 1.15),
    };
    return nextConfig;
}

logger.info("Initializing Jarvis backend with Next.js custom server...");
const dev = process.argv.includes("--dev");
const nextApp = next({ dev });
const handle = nextApp.getRequestHandler();

try {
    const mcpServer = createMcpServer(logger);
    const transport = new StdioServerTransport();
    mcpServer.connect(transport)
        .then(() => logger.info("Jarvis MCP Stdio Server connected."))
        .catch(error => logger.error(`MCP connection error: ${error.message}`));
} catch (error) {
    logger.error(`Failed to initialize MCP Server: ${error.message}`);
}

nextApp.prepare().then(() => {
    const app = express();
    const rateBuckets = new Map();
    let cachedBuild = null;
    let cachedBuildTime = 0;

    app.disable("x-powered-by");
    app.use((req, res, nextMiddleware) => {
        const hostname = String(req.hostname || "").toLowerCase();
        if (!["127.0.0.1", "localhost", "::1"].includes(hostname)) {
            return res.status(403).json({ error: "Local access only" });
        }
        res.setHeader("X-Content-Type-Options", "nosniff");
        res.setHeader("Referrer-Policy", "no-referrer");
        res.setHeader("X-Frame-Options", "DENY");
        res.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
        res.setHeader("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'");
        nextMiddleware();
    });
    app.use(express.json({ limit: "16kb", strict: true }));
    app.use("/api", (req, res, nextMiddleware) => {
        res.setHeader("Cache-Control", "no-store");
        const now = Date.now();
        const key = `${req.ip}:${req.method}`;
        const bucket = rateBuckets.get(key) || { start: now, count: 0 };
        if (now - bucket.start > 60_000) {
            bucket.start = now;
            bucket.count = 0;
        }
        bucket.count += 1;
        rateBuckets.set(key, bucket);
        const limit = req.method === "GET" ? 180 : 30;
        if (bucket.count > limit) return res.status(429).json({ error: "Rate limit exceeded" });
        nextMiddleware();
    });
    app.use((req, res, nextMiddleware) => {
        if (["POST", "PUT", "PATCH", "DELETE"].includes(req.method)
            && req.get("X-CSRF-Token") !== CSRF_TOKEN) {
            return res.status(403).json({ error: "Invalid CSRF token" });
        }
        nextMiddleware();
    });

    app.use("/cache", express.static(path.join(PROJECT_ROOT, "Picture", "cache"), {
        fallthrough: false,
        dotfiles: "deny",
        index: false,
        maxAge: 0,
    }));

    app.get("/api/session", (_req, res) => res.json({ csrf_token: CSRF_TOKEN }));
    app.get("/api/snapshot", (_req, res) => res.json(getSnapshot()));
    app.get("/api/metrics", (_req, res) => res.json(getSnapshot().metrics));
    app.get("/api/router", (_req, res) => res.json(getSnapshot().router));
    app.get("/api/telemetry", (_req, res) => res.json(getSnapshot().telemetry));
    app.get("/api/cam-feed", (_req, res) => res.json(getSnapshot().camera));

    app.get("/api/settings", (_req, res) => {
        res.json(publicSettings(readJson(ENGINE_CONFIG_FILE, {})));
    });
    app.put("/api/settings", (req, res) => {
        try {
            const current = readJson(ENGINE_CONFIG_FILE, {});
            const updated = mergeValidatedSettings(current, req.body);
            writeJsonAtomic(ENGINE_CONFIG_FILE, updated);
            res.json({ settings: publicSettings(updated), restart_required: true });
        } catch (error) {
            res.status(400).json({ error: error.message });
        }
    });

    app.get("/api/build", (_req, res) => {
        try {
            const now = Date.now();
            if (cachedBuild && now - cachedBuildTime < 15_000) return res.json(cachedBuild);
            const config = readJson(JARVIS_CONFIG_FILE, {});
            const configuredPath = String(config.project_path || PROJECT_ROOT);
            const projectPath = path.isAbsolute(configuredPath)
                ? path.resolve(configuredPath)
                : path.resolve(JARVIS_ROOT, configuredPath);
            let gitBranch = "N/A";
            let gitStatus = "";
            let fileCount = 0;
            if (fs.existsSync(projectPath)) {
                try {
                    gitBranch = execFileSync("git", ["rev-parse", "--abbrev-ref", "HEAD"], { cwd: projectPath, stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
                    gitStatus = execFileSync("git", ["status", "--short"], { cwd: projectPath, stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
                } catch {}
                const countFiles = directory => {
                    let count = 0;
                    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
                        if (["node_modules", ".git", ".next", "dist"].includes(entry.name)) continue;
                        const fullPath = path.join(directory, entry.name);
                        if (entry.isDirectory()) count += countFiles(fullPath);
                        else if (/\.(ts|tsx|js|jsx|json|py|css|html|md)$/.test(entry.name)) count += 1;
                    }
                    return count;
                };
                try { fileCount = countFiles(projectPath); } catch {}
            }
            cachedBuild = { repo: path.basename(projectPath), files: fileCount, branch: gitBranch, status: gitStatus ? "MODIFIED" : "CLEAN" };
            cachedBuildTime = now;
            res.json(cachedBuild);
        } catch (error) {
            res.status(500).json({ error: "Build status unavailable" });
        }
    });

    app.get("/api/posts", (_req, res) => {
        const posts = readJson(POSTS_FILE, []);
        res.json(Array.isArray(posts) ? posts.slice(0, 200) : []);
    });
    app.post("/api/posts", (req, res) => {
        try {
            const content = boundedString(req.body?.content, "content", 500);
            const platform = ALLOWED_PLATFORMS.has(req.body?.platform) ? req.body.platform : "Twitter";
            const posts = readJson(POSTS_FILE, []);
            const safePosts = Array.isArray(posts) ? posts : [];
            const newPost = { id: crypto.randomUUID(), content, platform, timestamp: new Date().toISOString() };
            writeJsonAtomic(POSTS_FILE, [newPost, ...safePosts].slice(0, 200));
            res.status(201).json(newPost);
        } catch (error) {
            res.status(400).json({ error: error.message });
        }
    });

    app.all("*", (req, res) => handle(req, res));
    const server = app.listen(PORT, HOST, () => {
        writeJsonAtomic(PID_FILE, { pid: process.pid, started_at: new Date().toISOString(), command: "jarvis/index.js" });
        logger.info(`Dashboard listening on http://${HOST}:${PORT}`);
    });

    const shutdown = signal => {
        logger.info(`Received ${signal}; shutting down Jarvis.`);
        try { fs.unlinkSync(PID_FILE); } catch {}
        server.close(() => process.exit(0));
        setTimeout(() => process.exit(1), 5000).unref();
    };
    process.on("SIGINT", () => shutdown("SIGINT"));
    process.on("SIGTERM", () => shutdown("SIGTERM"));
}).catch(error => {
    logger.error(`Next.js initialization error: ${error.message}`);
    process.exitCode = 1;
});
