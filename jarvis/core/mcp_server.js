import crypto from "crypto";
import { execFileSync } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";

const JARVIS_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PROJECT_ROOT = path.resolve(JARVIS_ROOT, "..");
const DATA_DIR = path.join(JARVIS_ROOT, "data");
const POSTS_FILE = path.join(DATA_DIR, "social_posts.json");
const CONFIG_FILE = path.join(JARVIS_ROOT, "config.json");
const SNAPSHOT_FILE = path.join(PROJECT_ROOT, "output", "system_snapshot.json");
const VERSION_FILE = path.join(PROJECT_ROOT, "VERSION");
const ALLOWED_PLATFORMS = new Set(["Twitter", "LinkedIn", "Mastodon"]);
const APP_VERSION = readText(VERSION_FILE, "0.0.0-dev").trim();

function readText(file, fallback = "") {
    try { return fs.readFileSync(file, "utf-8"); } catch { return fallback; }
}

function readJson(file, fallback) {
    try {
        const value = JSON.parse(fs.readFileSync(file, "utf-8"));
        return value ?? fallback;
    } catch {
        return fallback;
    }
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

function initData() {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    if (!fs.existsSync(POSTS_FILE)) writeJsonAtomic(POSTS_FILE, []);
}

function getProjectPath(requestedPath) {
    if (typeof requestedPath === "string" && requestedPath.trim()) {
        return path.resolve(requestedPath.trim());
    }
    const configured = readJson(CONFIG_FILE, {}).project_path;
    if (typeof configured !== "string" || !configured.trim()) return PROJECT_ROOT;
    return path.isAbsolute(configured.trim())
        ? path.resolve(configured.trim())
        : path.resolve(JARVIS_ROOT, configured.trim());
}

function getSnapshot() {
    const snapshot = readJson(SNAPSHOT_FILE, null);
    if (!snapshot || snapshot.schema_version !== "1.0" || typeof snapshot.metrics !== "object") {
        throw new Error("Telemetry snapshot is unavailable; start the InfoSphere engine first.");
    }
    return snapshot;
}

function countProjectFiles(directory) {
    let count = 0;
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
        if (["node_modules", ".git", ".next", "dist"].includes(entry.name)) continue;
        const fullPath = path.join(directory, entry.name);
        if (entry.isDirectory()) count += countProjectFiles(fullPath);
        else if (/\.(ts|tsx|js|jsx|json|py|css|html|md)$/i.test(entry.name)) count += 1;
    }
    return count;
}

function gitOutput(targetPath, args) {
    return execFileSync("git", args, {
        cwd: targetPath,
        encoding: "utf-8",
        stdio: ["ignore", "pipe", "ignore"],
        timeout: 5000,
        windowsHide: true,
    }).trim();
}

function validatePost(args) {
    const content = typeof args?.content === "string" ? args.content.trim() : "";
    if (!content || content.length > 500 || /[\0]/.test(content)) {
        throw new Error("content must be 1-500 text characters");
    }
    const platform = ALLOWED_PLATFORMS.has(args?.platform) ? args.platform : "Twitter";
    return { content, platform };
}

export function createMcpServer(logger) {
    initData();

    const server = new Server(
        { name: "infosphere-jarvis", version: APP_VERSION },
        { capabilities: { tools: {} } },
    );

    server.setRequestHandler(ListToolsRequestSchema, async () => ({
        tools: [
            {
                name: "get_system_stats",
                description: "Read the canonical InfoSphere telemetry snapshot, including metric provenance.",
                inputSchema: { type: "object", properties: {}, additionalProperties: false },
            },
            {
                name: "get_build_status",
                description: "Read local Git and source-file status for a selected project directory.",
                inputSchema: {
                    type: "object",
                    properties: {
                        path: { type: "string", maxLength: 1024, description: "Optional local project path." },
                    },
                    additionalProperties: false,
                },
            },
            {
                name: "post_to_social_media",
                description: "Add a local simulated post to the Jarvis dashboard timeline; nothing is published externally.",
                inputSchema: {
                    type: "object",
                    properties: {
                        content: { type: "string", minLength: 1, maxLength: 500 },
                        platform: { type: "string", enum: [...ALLOWED_PLATFORMS] },
                    },
                    required: ["content"],
                    additionalProperties: false,
                },
            },
        ],
    }));

    server.setRequestHandler(CallToolRequestSchema, async request => {
        const { name, arguments: args = {} } = request.params;
        logger.info(`[MCP] Tool invoked: ${name}`);

        try {
            if (name === "get_system_stats") {
                const snapshot = getSnapshot();
                const stats = {
                    schema_version: snapshot.schema_version,
                    app_version: snapshot.app_version,
                    generated_at: snapshot.generated_at,
                    provenance: snapshot.provenance,
                    metrics: snapshot.metrics,
                    system: snapshot.system,
                };
                return { content: [{ type: "text", text: JSON.stringify(stats, null, 2) }] };
            }

            if (name === "get_build_status") {
                const targetPath = getProjectPath(args.path);
                if (!fs.existsSync(targetPath) || !fs.statSync(targetPath).isDirectory()) {
                    throw new Error(`Project directory does not exist: ${targetPath}`);
                }

                let gitBranch = "N/A";
                let gitStatus = "";
                let gitCommits = [];
                try {
                    gitBranch = gitOutput(targetPath, ["rev-parse", "--abbrev-ref", "HEAD"]);
                    gitStatus = gitOutput(targetPath, ["status", "--short"]);
                    const log = gitOutput(targetPath, ["log", "-n", "5", "--oneline"]);
                    gitCommits = log ? log.split(/\r?\n/) : [];
                } catch {
                    gitStatus = "Not a Git repository or Git is unavailable.";
                }

                const result = {
                    project_directory: targetPath,
                    git_branch: gitBranch,
                    file_count: countProjectFiles(targetPath),
                    modified_files: gitStatus ? gitStatus.split(/\r?\n/).slice(0, 200) : [],
                    recent_commits: gitCommits,
                };
                return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
            }

            if (name === "post_to_social_media") {
                const { content, platform } = validatePost(args);
                const existing = readJson(POSTS_FILE, []);
                const post = {
                    id: crypto.randomUUID(),
                    content,
                    platform,
                    timestamp: new Date().toISOString(),
                };
                writeJsonAtomic(POSTS_FILE, [post, ...(Array.isArray(existing) ? existing : [])].slice(0, 200));
                logger.info(`[Social] Added simulated ${platform} post to the local timeline.`);
                return {
                    content: [{ type: "text", text: `Saved simulated ${platform} post locally.` }],
                };
            }

            return { isError: true, content: [{ type: "text", text: `Unknown tool: ${name}` }] };
        } catch (error) {
            logger.error(`[MCP] Tool execution error: ${error.message}`);
            return { isError: true, content: [{ type: "text", text: error.message }] };
        }
    });

    return server;
}
