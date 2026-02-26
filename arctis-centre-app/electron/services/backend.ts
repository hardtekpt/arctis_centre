import { ChildProcessWithoutNullStreams, spawn, spawnSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import { EventEmitter } from "node:events";
import type { AppState, BackendCommand, PresetMap } from "../../shared/types";
import { mergeState } from "../../shared/settings";

type BridgeEvent =
  | { type: "state"; payload: AppState }
  | { type: "presets"; payload: PresetMap }
  | { type: "status"; payload: string }
  | { type: "error"; payload: string };

export class BackendBridge extends EventEmitter {
  private child: ChildProcessWithoutNullStreams | null = null;
  private pending = "";
  private scriptPath: string;
  private projectRoot: string;
  private launchedWith = "";
  private lastState: AppState = mergeState();
  private lastPresets: PresetMap = {};

  constructor(scriptPath: string, projectRoot: string) {
    super();
    this.scriptPath = path.normalize(scriptPath);
    this.projectRoot = path.normalize(projectRoot);
  }

  public start(): void {
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
      } else {
        this.emit("status", `backend exited with code ${codeText}`);
      }
      this.child = null;
    });
  }

  public stop(): void {
    if (!this.child) {
      return;
    }
    this.child.kill();
    this.child = null;
  }

  public send(cmd: BackendCommand): void {
    if (!this.child) {
      return;
    }
    this.child.stdin.write(`${JSON.stringify(cmd)}\n`);
  }

  public getState(): AppState {
    return this.lastState;
  }

  public getPresets(): PresetMap {
    return this.lastPresets;
  }

  private spawnPython(): ChildProcessWithoutNullStreams {
    if (!fs.existsSync(this.scriptPath)) {
      throw new Error(`Backend bridge script not found: ${this.scriptPath}`);
    }
    const candidates: string[] = [];
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
      const child = spawn(bin, args, {
        stdio: "pipe",
        windowsHide: true,
        cwd: this.projectRoot,
        env: {
          ...process.env,
          PYTHONPATH: this.joinPythonPath([
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

  private canSpawn(bin: string): boolean {
    try {
      const probeArgs = bin === "py" ? ["-3", "--version"] : ["--version"];
      const probe = spawnSync(bin, probeArgs, { windowsHide: true, stdio: "pipe" });
      return probe.status === 0;
    } catch {
      return false;
    }
  }

  private joinPythonPath(parts: string[]): string {
    return parts.filter((x) => x.trim().length > 0).join(path.delimiter);
  }

  private onStdout(chunk: string): void {
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

  private consumeLine(line: string): void {
    try {
      const event = JSON.parse(line) as BridgeEvent;
      if (event.type === "state") {
        this.lastState = mergeState(event.payload);
        this.emit("state", this.lastState);
        return;
      }
      if (event.type === "presets") {
        this.lastPresets = event.payload ?? {};
        this.emit("presets", this.lastPresets);
        return;
      }
      this.emit(event.type, event.payload);
    } catch {
      this.emit("status", line);
    }
  }
}
