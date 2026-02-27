"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.BackendBridge = void 0;
const node_child_process_1 = require("node:child_process");
const fs = __importStar(require("node:fs"));
const path = __importStar(require("node:path"));
const node_events_1 = require("node:events");
const settings_js_1 = require("../../shared/settings.js");
class BackendBridge extends node_events_1.EventEmitter {
    child = null;
    pending = "";
    scriptPath;
    projectRoot;
    launchedWith = "";
    lastState = (0, settings_js_1.mergeState)();
    lastPresets = {};
    constructor(scriptPath, projectRoot) {
        super();
        this.scriptPath = path.normalize(scriptPath);
        this.projectRoot = path.normalize(projectRoot);
    }
    start() {
        if (this.child) {
            return;
        }
        this.child = this.spawnPython();
        this.child.stdout.setEncoding("utf-8");
        this.child.stdout.on("data", (chunk) => this.onStdout(chunk));
        this.child.stderr.setEncoding("utf-8");
        this.child.stderr.on("data", (chunk) => this.emit("error", chunk.toString().trim()));
        this.child.on("exit", (code) => {
            const codeText = String(code ?? "unknown");
            if (code !== 0) {
                this.emit("error", `backend exited with code ${codeText} (${this.launchedWith})`);
            }
            else {
                this.emit("status", `backend exited with code ${codeText}`);
            }
            this.child = null;
        });
    }
    stop() {
        if (!this.child) {
            return;
        }
        this.child.kill();
        this.child = null;
    }
    send(cmd) {
        if (!this.child) {
            return;
        }
        this.child.stdin.write(`${JSON.stringify(cmd)}\n`);
    }
    getState() {
        return this.lastState;
    }
    getPresets() {
        return this.lastPresets;
    }
    spawnPython() {
        if (!fs.existsSync(this.scriptPath)) {
            throw new Error(`Backend bridge script not found: ${this.scriptPath}`);
        }
        const candidates = [];
        const venvCandidates = [
            path.join(this.projectRoot, ".venv", "Scripts", "python.exe"),
            path.join(path.resolve(this.projectRoot, ".."), ".venv", "Scripts", "python.exe"),
        ];
        for (const venvPython of venvCandidates) {
            if (fs.existsSync(venvPython)) {
                candidates.push(venvPython);
            }
        }
        candidates.push("python", "py");
        for (const bin of candidates) {
            const args = bin === "py" ? ["-3", "-u", this.scriptPath] : ["-u", this.scriptPath];
            if (!this.canSpawn(bin)) {
                continue;
            }
            const child = (0, node_child_process_1.spawn)(bin, args, {
                stdio: "pipe",
                windowsHide: true,
                cwd: this.projectRoot,
                env: {
                    ...process.env,
                    PYTHONPATH: this.joinPythonPath([
                        path.join(this.projectRoot, "src", "APIs", "arctis_nova_api", "src"),
                        path.join(this.projectRoot, "src"),
                        this.projectRoot,
                        process.env.PYTHONPATH ?? "",
                    ]),
                },
            });
            this.launchedWith = `${bin} ${args.join(" ")}`;
            this.emit("status", `starting backend (${this.launchedWith})`);
            child.on("error", (err) => this.emit("error", `backend process failed: ${err.message}`));
            return child;
        }
        throw new Error("Unable to start Python backend bridge. Ensure Python is installed.");
    }
    canSpawn(bin) {
        try {
            const probeArgs = bin === "py" ? ["-3", "--version"] : ["--version"];
            const probe = (0, node_child_process_1.spawnSync)(bin, probeArgs, { windowsHide: true, stdio: "pipe" });
            return probe.status === 0;
        }
        catch {
            return false;
        }
    }
    joinPythonPath(parts) {
        return parts.filter((x) => x.trim().length > 0).join(path.delimiter);
    }
    onStdout(chunk) {
        this.pending += chunk;
        let idx = this.pending.indexOf("\n");
        while (idx >= 0) {
            const line = this.pending.slice(0, idx).trim();
            this.pending = this.pending.slice(idx + 1);
            if (line) {
                this.consumeLine(line);
            }
            idx = this.pending.indexOf("\n");
        }
    }
    consumeLine(line) {
        try {
            const event = JSON.parse(line);
            if (event.type === "state") {
                this.lastState = (0, settings_js_1.mergeState)(event.payload);
                this.emit("state", this.lastState);
                return;
            }
            if (event.type === "presets") {
                this.lastPresets = event.payload ?? {};
                this.emit("presets", this.lastPresets);
                return;
            }
            this.emit(event.type, event.payload);
        }
        catch {
            this.emit("status", line);
        }
    }
}
exports.BackendBridge = BackendBridge;
