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
const electron_1 = require("electron");
const fs = __importStar(require("node:fs"));
const os = __importStar(require("node:os"));
const path = __importStar(require("node:path"));
const node_child_process_1 = require("node:child_process");
const backend_1 = require("./services/backend");
const window_1 = require("./window");
const tray_1 = require("./tray");
const settings_js_1 = require("../shared/settings.js");
let mainWindow = null;
let settingsWindow = null;
let aboutWindow = null;
let notificationWindows = [];
let tray = null;
let settings = settings_js_1.DEFAULT_SETTINGS;
let cachedState = (0, settings_js_1.mergeState)();
let cachedPresets = {};
let backend = null;
let lastStatusText = "ready";
let lastErrorText = null;
let logBuffer = [];
let mixerOutputId = null;
let mixerAppVolume = {};
let mixerAppMuted = {};
let persistTimer = null;
let mainWindowLoaded = false;
let pendingFlyoutOpen = false;
let isQuitting = false;
let isOpeningFlyout = false;
let suppressBlurUntil = 0;
let hasSeenLiveState = false;
const APP_STATE_VERSION = 1;
if (!electron_1.app.isPackaged) {
    const devSessionPath = path.join(os.tmpdir(), `arctis-centre-session-${process.pid}`);
    electron_1.app.setPath("sessionData", devSessionPath);
}
function getUserFile(name) {
    return path.join(electron_1.app.getPath("userData"), name);
}
function readJsonFile(filePath, fallback) {
    try {
        const raw = fs.readFileSync(filePath, "utf-8");
        return JSON.parse(raw);
    }
    catch {
        return fallback;
    }
}
function writeJsonFile(filePath, value) {
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    const tempPath = `${filePath}.tmp`;
    fs.writeFileSync(tempPath, JSON.stringify(value, null, 2), "utf-8");
    fs.renameSync(tempPath, filePath);
}
function getPersistedStateFile() {
    return getUserFile("app-state.json");
}
function persistNow() {
    const snapshot = {
        version: APP_STATE_VERSION,
        state: cachedState,
        presets: cachedPresets,
        settings,
        statusText: lastStatusText,
        errorText: lastErrorText,
        logs: logBuffer,
        mixerOutputId,
        mixerAppVolume,
        mixerAppMuted,
    };
    writeJsonFile(getPersistedStateFile(), snapshot);
}
function schedulePersist() {
    if (persistTimer) {
        clearTimeout(persistTimer);
    }
    persistTimer = setTimeout(() => {
        persistTimer = null;
        persistNow();
    }, 80);
}
function loadPersistedSnapshot() {
    const fallback = {
        version: APP_STATE_VERSION,
        state: (0, settings_js_1.mergeState)(),
        presets: {},
        settings: settings_js_1.DEFAULT_SETTINGS,
        statusText: "ready",
        errorText: null,
        logs: [],
        mixerOutputId: null,
        mixerAppVolume: {},
        mixerAppMuted: {},
    };
    const loaded = readJsonFile(getPersistedStateFile(), fallback);
    cachedState = (0, settings_js_1.mergeState)(loaded.state);
    cachedPresets = loaded.presets ?? {};
    settings = (0, settings_js_1.mergeSettings)(loaded.settings);
    lastStatusText = loaded.statusText ?? "ready";
    lastErrorText = loaded.errorText ?? null;
    logBuffer = Array.isArray(loaded.logs) ? loaded.logs.slice(0, 200) : [];
    mixerOutputId = loaded.mixerOutputId ?? null;
    mixerAppVolume = loaded.mixerAppVolume ?? {};
    mixerAppMuted = loaded.mixerAppMuted ?? {};
}
function pushLog(text) {
    const line = `${new Date().toLocaleTimeString()}  ${text}`;
    logBuffer = [line, ...logBuffer].slice(0, 200);
}
function isNotifEnabled(key) {
    return settings.notifications?.[key] !== false;
}
function showSystemNotification(title, body) {
    if (!title.trim() && !body.trim()) {
        return;
    }
    void showNotificationWindow(title, body);
}
function applyWindowBackgroundMaterial(win) {
    if (!win || win.isDestroyed()) {
        return;
    }
}
function applyBackgroundMaterialToAllWindows() {
    for (const win of allWindows()) {
        applyWindowBackgroundMaterial(win);
    }
}
function toPercentLabel(value) {
    if (value == null || Number.isNaN(value)) {
        return "N/A";
    }
    return `${Math.max(0, Math.min(100, Math.round(value)))}%`;
}
function channelDisplayName(channel) {
    if (channel === "chatRender")
        return "CHAT";
    if (channel === "chatCapture")
        return "MIC";
    return String(channel || "").toUpperCase();
}
function getPresetDisplayName(channel, presetId) {
    const presets = cachedPresets[channel] ?? [];
    const match = presets.find(([id]) => id === presetId);
    return match?.[1] ?? presetId;
}
function notifyStateChanges(previous, next) {
    if (isNotifEnabled("connectivity")) {
        if (previous.connected !== next.connected && next.connected != null) {
            showSystemNotification("Arctis Centre", next.connected ? "Headset connected" : "Headset disconnected");
        }
    }
    if (isNotifEnabled("ancMode") && previous.anc_mode !== next.anc_mode && next.anc_mode != null) {
        showSystemNotification("Arctis Centre", `ANC mode: ${next.anc_mode}`);
    }
    if (isNotifEnabled("oled") && previous.oled_brightness !== next.oled_brightness && next.oled_brightness != null) {
        showSystemNotification("Arctis Centre", `OLED brightness: ${next.oled_brightness}`);
    }
    if (isNotifEnabled("sidetone") && previous.sidetone_level !== next.sidetone_level && next.sidetone_level != null) {
        showSystemNotification("Arctis Centre", `Sidetone: ${next.sidetone_level}`);
    }
    if (isNotifEnabled("micMute") && previous.mic_mute !== next.mic_mute && next.mic_mute != null) {
        showSystemNotification("Arctis Centre", `Mic ${next.mic_mute ? "muted" : "live"}`);
    }
    if (isNotifEnabled("chatMix") && previous.chat_mix_balance !== next.chat_mix_balance && next.chat_mix_balance != null) {
        showSystemNotification("Arctis Centre", `Chat mix: ${toPercentLabel(next.chat_mix_balance)}`);
    }
    if (isNotifEnabled("headsetVolume") && previous.headset_volume_percent !== next.headset_volume_percent && next.headset_volume_percent != null) {
        showSystemNotification("Arctis Centre", `Headset volume: ${toPercentLabel(next.headset_volume_percent)}`);
    }
    if (isNotifEnabled("battery")) {
        const prevHeadset = previous.headset_battery_percent;
        const nextHeadset = next.headset_battery_percent;
        if (prevHeadset != null && nextHeadset != null) {
            if (prevHeadset > 20 && nextHeadset <= 20) {
                showSystemNotification("Arctis Centre", `Headset battery low (${toPercentLabel(nextHeadset)})`);
            }
            else if (prevHeadset < 95 && nextHeadset >= 95) {
                showSystemNotification("Arctis Centre", `Headset battery charged (${toPercentLabel(nextHeadset)})`);
            }
        }
        const prevBase = previous.base_battery_percent;
        const nextBase = next.base_battery_percent;
        if (prevBase != null && nextBase != null) {
            if (prevBase > 20 && nextBase <= 20) {
                showSystemNotification("Arctis Centre", `Base battery low (${toPercentLabel(nextBase)})`);
            }
            else if (prevBase < 95 && nextBase >= 95) {
                showSystemNotification("Arctis Centre", `Base battery charged (${toPercentLabel(nextBase)})`);
            }
        }
    }
    if (isNotifEnabled("presetChange")) {
        const prevPreset = previous.channel_preset ?? {};
        const nextPreset = next.channel_preset ?? {};
        for (const [channel, nextValue] of Object.entries(nextPreset)) {
            const prevValue = prevPreset[channel];
            if (nextValue !== prevValue && nextValue != null && String(nextValue).trim()) {
                showSystemNotification("Arctis Centre", `${channelDisplayName(channel)} preset: ${getPresetDisplayName(channel, String(nextValue))}`);
            }
        }
    }
}
function detectWorkspaceRoot() {
    const seeds = [process.cwd(), electron_1.app.getAppPath()];
    const seen = new Set();
    for (const seed of seeds) {
        let current = path.resolve(seed);
        while (true) {
            const normalized = path.normalize(current);
            if (!seen.has(normalized)) {
                seen.add(normalized);
                const apiDir = path.join(normalized, "src", "APIs", "arctis_nova_api", "src", "arctis_nova_api");
                if (fs.existsSync(apiDir)) {
                    return normalized;
                }
            }
            const parent = path.dirname(current);
            if (parent === current) {
                break;
            }
            current = parent;
        }
    }
    return path.resolve(process.cwd(), "..", "..");
}
function migrateLegacyState() {
    if (fs.existsSync(getPersistedStateFile())) {
        return;
    }
    const oldStateCache = getUserFile("state-cache.json");
    if (fs.existsSync(oldStateCache)) {
        cachedState = (0, settings_js_1.mergeState)(readJsonFile(oldStateCache, {}));
    }
    else {
        const legacyCandidates = [
            path.resolve(electron_1.app.getAppPath(), "..", "..", "APIs", "arctis_nova_api", "tools", "tray_dashboard_state.json"),
            path.resolve(electron_1.app.getAppPath(), "..", "tools", "tray_dashboard_state.json"),
            path.resolve(electron_1.app.getAppPath(), "..", "..", "..", "src", "APIs", "arctis_nova_api", "tools", "tray_dashboard_state.json"),
        ];
        for (const legacy of legacyCandidates) {
            if (fs.existsSync(legacy)) {
                const migrated = readJsonFile(legacy, {});
                cachedState = (0, settings_js_1.mergeState)(migrated);
                break;
            }
        }
    }
    const oldSettings = getUserFile("settings.json");
    if (fs.existsSync(oldSettings)) {
        settings = (0, settings_js_1.mergeSettings)(readJsonFile(oldSettings, {}));
    }
    persistNow();
}
async function getWindowsAccentColor() {
    if (process.platform !== "win32") {
        return "#6ab7ff";
    }
    return new Promise((resolve) => {
        (0, node_child_process_1.execFile)("reg", ["query", "HKCU\\Software\\Microsoft\\Windows\\DWM", "/v", "ColorizationColor"], { windowsHide: true }, (err, stdout) => {
            if (err || !stdout) {
                resolve("#6ab7ff");
                return;
            }
            const match = stdout.match(/0x([0-9A-Fa-f]{8})/);
            if (!match) {
                resolve("#6ab7ff");
                return;
            }
            const argb = match[1];
            const rrggbb = argb.slice(2);
            resolve(`#${rrggbb}`);
        });
    });
}
async function getThemePayload() {
    return {
        isDark: electron_1.nativeTheme.shouldUseDarkColors,
        accent: await getWindowsAccentColor(),
    };
}
function showFlyout() {
    if (!mainWindow) {
        return;
    }
    if (!mainWindowLoaded) {
        pendingFlyoutOpen = true;
        return;
    }
    if (mainWindow.isVisible() || isOpeningFlyout) {
        mainWindow.focus();
        return;
    }
    isOpeningFlyout = true;
    suppressBlurUntil = Date.now() + 450;
    const fitPromise = Promise.race([
        fitWindowToMainContent(),
        new Promise((resolve) => setTimeout(resolve, 140)),
    ]);
    void fitPromise.finally(() => {
        if (!mainWindow) {
            isOpeningFlyout = false;
            return;
        }
        (0, window_1.positionBottomRight)(mainWindow);
        mainWindow.show();
        mainWindow.focus();
        isOpeningFlyout = false;
    });
}
function hideFlyout() {
    if (!mainWindow) {
        return;
    }
    mainWindow.hide();
}
function toggleFlyout() {
    if (!mainWindow) {
        return;
    }
    if (isOpeningFlyout) {
        return;
    }
    if (mainWindow.isVisible()) {
        hideFlyout();
    }
    else {
        showFlyout();
    }
}
function loadSettings() {
    loadPersistedSnapshot();
}
function persistSettings(next) {
    settings = (0, settings_js_1.mergeSettings)(next);
    schedulePersist();
    return settings;
}
function harmonizeLiveState(previous, incoming) {
    const next = (0, settings_js_1.mergeState)(incoming);
    const keep = (newValue, oldValue) => newValue === null || newValue === undefined ? oldValue : newValue;
    return {
        ...previous,
        ...next,
        headset_battery_percent: keep(next.headset_battery_percent, previous.headset_battery_percent),
        base_battery_percent: keep(next.base_battery_percent, previous.base_battery_percent),
        headset_volume_percent: keep(next.headset_volume_percent, previous.headset_volume_percent),
        anc_mode: keep(next.anc_mode, previous.anc_mode),
        mic_mute: keep(next.mic_mute, previous.mic_mute),
        sidetone_level: keep(next.sidetone_level, previous.sidetone_level),
        connected: keep(next.connected, previous.connected),
        wireless: keep(next.wireless, previous.wireless),
        bluetooth: keep(next.bluetooth, previous.bluetooth),
        chat_mix_balance: keep(next.chat_mix_balance, previous.chat_mix_balance),
        oled_brightness: keep(next.oled_brightness, previous.oled_brightness),
        updated_at: keep(next.updated_at, previous.updated_at),
        channel_volume: { ...previous.channel_volume, ...next.channel_volume },
        channel_mute: { ...previous.channel_mute, ...next.channel_mute },
        channel_preset: { ...previous.channel_preset, ...next.channel_preset },
        channel_apps: { ...previous.channel_apps, ...next.channel_apps },
    };
}
function allWindows() {
    const wins = [];
    for (const win of [mainWindow, settingsWindow, aboutWindow, ...notificationWindows]) {
        if (win && !win.isDestroyed()) {
            wins.push(win);
        }
    }
    return wins;
}
function relayoutNotificationWindows() {
    const display = electron_1.screen.getPrimaryDisplay();
    const workArea = display.workArea;
    const margin = 12;
    let y = workArea.y + margin;
    for (const win of notificationWindows.filter((candidate) => !candidate.isDestroyed())) {
        const bounds = win.getBounds();
        const x = workArea.x + workArea.width - bounds.width - margin;
        win.setPosition(x, y, false);
        y += bounds.height + 10;
    }
    notificationWindows = notificationWindows.filter((candidate) => !candidate.isDestroyed());
}
function clampPercent(value) {
    return Math.max(0, Math.min(100, Math.round(value)));
}
function getMixerApps() {
    const controls = new Map([
        ["__device_volume__", "Device Volume"],
        ["__main_system__", "Main System Volume"],
        ["__system_sounds__", "System Sounds"],
    ]);
    const appNames = new Set();
    for (const list of Object.values(cachedState.channel_apps ?? {})) {
        if (!Array.isArray(list)) {
            continue;
        }
        for (const app of list) {
            const trimmed = String(app || "").trim();
            if (trimmed) {
                appNames.add(trimmed);
            }
        }
    }
    for (const app of appNames) {
        controls.set(app, app);
    }
    for (const app of Object.keys(mixerAppVolume)) {
        const trimmed = String(app || "").trim();
        if (trimmed) {
            controls.set(trimmed, trimmed);
        }
    }
    for (const app of Object.keys(mixerAppMuted)) {
        const trimmed = String(app || "").trim();
        if (trimmed) {
            controls.set(trimmed, trimmed);
        }
    }
    return Array.from(controls.entries())
        .sort((a, b) => a[1].localeCompare(b[1]))
        .map(([id, name]) => ({
        id,
        name,
        volume: clampPercent(mixerAppVolume[id] ?? 100),
        muted: Boolean(mixerAppMuted[id]),
    }));
}
async function getMixerOutputs() {
    if (process.platform !== "win32") {
        return [{ id: "default", name: "System Default Output" }];
    }
    return new Promise((resolve) => {
        (0, node_child_process_1.execFile)("powershell", [
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance Win32_SoundDevice | Select-Object -ExpandProperty Name",
        ], { windowsHide: true }, (err, stdout) => {
            if (err || !stdout) {
                resolve([{ id: "default", name: "System Default Output" }]);
                return;
            }
            const names = stdout
                .split(/\r?\n/)
                .map((line) => line.trim())
                .filter(Boolean);
            const unique = Array.from(new Set(names));
            const outputs = unique.map((name) => ({ id: name, name }));
            resolve(outputs.length ? outputs : [{ id: "default", name: "System Default Output" }]);
        });
    });
}
function wireBackend() {
    if (!backend) {
        return;
    }
    backend.on("state", (state) => {
        const previous = cachedState;
        cachedState = harmonizeLiveState(cachedState, state);
        if (hasSeenLiveState) {
            notifyStateChanges(previous, cachedState);
        }
        else {
            hasSeenLiveState = true;
        }
        schedulePersist();
        for (const win of allWindows()) {
            win.webContents.send("backend:state", cachedState);
        }
    });
    backend.on("presets", (presets) => {
        cachedPresets = presets;
        schedulePersist();
        for (const win of allWindows()) {
            win.webContents.send("backend:presets", presets);
        }
    });
    backend.on("status", (text) => {
        lastStatusText = text;
        lastErrorText = null;
        pushLog(text);
        if (isNotifEnabled("appInfo")) {
            const lower = text.toLowerCase();
            if (lower.includes("starting backend") || lower.includes("backend exited") || lower.includes("ready")) {
                showSystemNotification("Arctis Centre", text);
            }
        }
        schedulePersist();
        for (const win of allWindows()) {
            win.webContents.send("backend:status", text);
        }
    });
    backend.on("error", (text) => {
        lastErrorText = text;
        lastStatusText = text;
        pushLog(`ERROR: ${text}`);
        if (isNotifEnabled("appInfo")) {
            showSystemNotification("Arctis Centre Error", text);
        }
        schedulePersist();
        for (const win of allWindows()) {
            win.webContents.send("backend:error", text);
        }
    });
    backend.start();
}
function wireIpc() {
    if (!backend) {
        return;
    }
    electron_1.ipcMain.handle("app:get-initial", async () => {
        return {
            state: cachedState,
            presets: cachedPresets,
            settings,
            theme: await getThemePayload(),
            status: lastStatusText,
            error: lastErrorText,
            logs: logBuffer,
        };
    });
    electron_1.ipcMain.on("backend:command", (_evt, cmd) => backend.send(cmd));
    electron_1.ipcMain.on("window:hide", () => hideFlyout());
    electron_1.ipcMain.on("window:open-settings", () => {
        void showSettingsWindow();
    });
    electron_1.ipcMain.on("window:open-about", () => {
        void showAboutWindow();
    });
    electron_1.ipcMain.on("window:close-current", (evt) => {
        const win = electron_1.BrowserWindow.fromWebContents(evt.sender);
        if (!win) {
            return;
        }
        if (win === mainWindow) {
            hideFlyout();
            return;
        }
        win.close();
    });
    electron_1.ipcMain.handle("settings:set", (_evt, partial) => {
        const next = persistSettings({ ...settings, ...partial });
        registerToggleShortcut(next.toggleShortcut);
        applyBackgroundMaterialToAllWindows();
        for (const win of allWindows()) {
            win.webContents.send("settings:update", next);
        }
        return next;
    });
    electron_1.ipcMain.handle("app:open-gg", async () => {
        const candidates = [
            "C:\\Program Files\\SteelSeries\\GG\\SteelSeriesGGClient.exe",
            "C:\\Program Files\\SteelSeries\\GG\\SteelSeriesGG.exe",
            "C:\\Program Files (x86)\\SteelSeries\\GG\\SteelSeriesGG.exe",
        ];
        for (const exe of candidates) {
            if (fs.existsSync(exe)) {
                const result = await electron_1.shell.openPath(exe);
                return { ok: result === "", detail: result || exe };
            }
        }
        const uriResult = await electron_1.shell.openExternal("steelseriesgg://", { activate: true });
        return { ok: uriResult, detail: "steelseriesgg://" };
    });
    electron_1.ipcMain.handle("app:notify-custom", async (_evt, payload) => {
        const title = String(payload?.title || "").trim() || "Arctis Centre";
        const body = String(payload?.body || "").trim() || "Notification";
        showSystemNotification(title, body);
        return { ok: true };
    });
    electron_1.ipcMain.handle("mixer:get-data", async () => {
        const outputs = await getMixerOutputs();
        const selectedOutputId = mixerOutputId && outputs.some((o) => o.id === mixerOutputId) ? mixerOutputId : outputs[0]?.id ?? "default";
        if (selectedOutputId !== mixerOutputId) {
            mixerOutputId = selectedOutputId;
            schedulePersist();
        }
        return { outputs, selectedOutputId, apps: getMixerApps() };
    });
    electron_1.ipcMain.handle("mixer:set-output", (_evt, outputId) => {
        mixerOutputId = String(outputId || "").trim() || null;
        schedulePersist();
        return { ok: true };
    });
    electron_1.ipcMain.handle("mixer:set-app-volume", (_evt, payload) => {
        const appId = String(payload?.appId || "").trim();
        if (!appId) {
            return { ok: false };
        }
        mixerAppVolume[appId] = clampPercent(Number(payload.volume));
        schedulePersist();
        return { ok: true };
    });
    electron_1.ipcMain.handle("mixer:set-app-mute", (_evt, payload) => {
        const appId = String(payload?.appId || "").trim();
        if (!appId) {
            return { ok: false };
        }
        mixerAppMuted[appId] = Boolean(payload.muted);
        schedulePersist();
        return { ok: true };
    });
}
async function loadWindowPage(win, page) {
    if (process.env.VITE_DEV_SERVER_URL) {
        await win.loadURL(`${process.env.VITE_DEV_SERVER_URL}?window=${page}`);
    }
    else {
        await win.loadFile(path.join(electron_1.app.getAppPath(), "dist", "index.html"), { query: { window: page } });
    }
}
async function createCenteredWindow(page, width, height, title) {
    const win = new electron_1.BrowserWindow({
        width,
        height,
        minWidth: width,
        minHeight: height,
        show: false,
        center: true,
        frame: false,
        transparent: true,
        hasShadow: true,
        resizable: false,
        skipTaskbar: false,
        title,
        backgroundColor: "#00000000",
        webPreferences: {
            preload: path.join(__dirname, "preload.js"),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });
    applyWindowBackgroundMaterial(win);
    await loadWindowPage(win, page);
    return win;
}
async function showNotificationWindow(title, body) {
    const theme = await getThemePayload();
    const isDark = settings.themeMode === "system" ? theme.isDark : settings.themeMode === "dark";
    const accent = settings.accentColor.trim() || theme.accent;
    const shellBg = isDark ? "rgba(24,24,24,0.86)" : "rgba(248,248,248,0.92)";
    const textColor = isDark ? "#ffffff" : "#111111";
    const subText = isDark ? "rgba(255,255,255,0.78)" : "rgba(0,0,0,0.72)";
    const borderColor = isDark ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.28)";
    const cardBg = isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.45)";
    const blurCss = settings.micaBlur ? "backdrop-filter: blur(18px) saturate(125%); -webkit-backdrop-filter: blur(18px) saturate(125%);" : "";
    const esc = (value) => String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;");
    const html = `<!doctype html>
  <html>
    <head>
      <meta charset="utf-8" />
      <meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline' data:;" />
      <style>
        html, body {
          margin: 0;
          width: 100%;
          height: 100%;
          overflow: hidden;
          background: transparent;
          font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
        }
        body {
          color: ${textColor};
          padding: 0;
        }
        .shell {
          margin: 0;
          width: 100%;
          height: 100%;
          box-sizing: border-box;
          border-radius: 12px;
          background: ${shellBg};
          border: 1px solid ${borderColor};
          box-shadow: 0 10px 24px rgba(0,0,0,0.28), inset 0 0 0 0.5px ${borderColor};
          ${blurCss}
          display: grid;
          grid-template-columns: auto 1fr;
          gap: 10px;
          align-items: start;
          padding: 10px 12px;
        }
        .mark {
          width: 30px;
          height: 30px;
          border-radius: 999px;
          display: grid;
          place-items: center;
          background: color-mix(in srgb, ${accent} 24%, transparent);
          color: ${accent};
          font-size: 14px;
          font-weight: 700;
          box-shadow: inset 0 0 0 1px color-mix(in srgb, ${accent} 46%, transparent);
        }
        .copy {
          min-width: 0;
        }
        .title {
          font-size: 14px;
          font-weight: 700;
          line-height: 1.2;
          margin-bottom: 4px;
        }
        .body {
          font-size: 12px;
          line-height: 1.35;
          color: ${subText};
          white-space: pre-wrap;
          word-break: break-word;
        }
        .body-card {
          background: ${cardBg};
          border-radius: 8px;
          padding: 8px 9px;
        }
      </style>
    </head>
    <body>
      <div class="shell">
        <div class="mark">A</div>
        <div class="copy">
          <div class="title">${esc(title)}</div>
          <div class="body-card">
            <div class="body">${esc(body)}</div>
          </div>
        </div>
      </div>
    </body>
  </html>`;
    const win = new electron_1.BrowserWindow({
        width: 340,
        height: 108,
        show: false,
        frame: false,
        transparent: true,
        backgroundColor: "#00000000",
        resizable: false,
        movable: false,
        minimizable: false,
        maximizable: false,
        fullscreenable: false,
        skipTaskbar: true,
        alwaysOnTop: true,
        focusable: true,
        hasShadow: true,
    });
    applyWindowBackgroundMaterial(win);
    await win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    notificationWindows.push(win);
    relayoutNotificationWindows();
    win.setAlwaysOnTop(true, "screen-saver");
    win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
    const showNotification = () => {
        if (win.isDestroyed()) {
            return;
        }
        relayoutNotificationWindows();
        win.show();
        win.setFocusable(false);
        win.setIgnoreMouseEvents(true);
        setTimeout(() => {
            if (!win.isDestroyed()) {
                win.close();
            }
        }, Math.max(2, settings.notificationTimeout) * 1000);
    };
    win.once("ready-to-show", showNotification);
    win.webContents.once("did-finish-load", () => {
        if (!win.isVisible()) {
            showNotification();
        }
    });
    win.on("closed", () => {
        notificationWindows = notificationWindows.filter((candidate) => candidate !== win);
        relayoutNotificationWindows();
    });
}
async function showSettingsWindow() {
    if (!settingsWindow || settingsWindow.isDestroyed()) {
        settingsWindow = await createCenteredWindow("settings", 580, 520, "Arctis Centre - Settings");
        settingsWindow.on("closed", () => {
            settingsWindow = null;
        });
    }
    settingsWindow.center();
    settingsWindow.show();
    settingsWindow.focus();
}
async function showAboutWindow() {
    if (!aboutWindow || aboutWindow.isDestroyed()) {
        aboutWindow = await createCenteredWindow("about", 580, 520, "Arctis Centre - About");
        aboutWindow.on("closed", () => {
            aboutWindow = null;
        });
    }
    aboutWindow.center();
    aboutWindow.show();
    aboutWindow.focus();
}
function registerToggleShortcut(accelerator) {
    electron_1.globalShortcut.unregisterAll();
    if (!accelerator.trim()) {
        return;
    }
    try {
        const ok = electron_1.globalShortcut.register(accelerator, () => toggleFlyout());
        if (!ok) {
            mainWindow?.webContents.send("backend:error", `Unable to register shortcut: ${accelerator}`);
            if (isNotifEnabled("appInfo")) {
                showSystemNotification("Arctis Centre Error", `Unable to register shortcut: ${accelerator}`);
            }
        }
        else {
            mainWindow?.webContents.send("backend:status", `Shortcut registered: ${accelerator}`);
            if (isNotifEnabled("appInfo")) {
                showSystemNotification("Arctis Centre", `Shortcut registered: ${accelerator}`);
            }
        }
    }
    catch (err) {
        mainWindow?.webContents.send("backend:error", `Invalid shortcut: ${accelerator} (${String(err)})`);
        if (isNotifEnabled("appInfo")) {
            showSystemNotification("Arctis Centre Error", `Invalid shortcut: ${accelerator}`);
        }
    }
}
async function fitWindowToMainContent() {
    if (!mainWindow || mainWindow.webContents.isLoading()) {
        return;
    }
    try {
        const [contentW, contentH] = (await mainWindow.webContents.executeJavaScript(`(async () => {
        const root = document.querySelector('.window-base');
        if (!root) {
          return [320, 260];
        }
        const sonarTab = document.querySelector('.tab-selector .tab-btn');
        if (sonarTab) {
          sonarTab.dispatchEvent(new MouseEvent('click', { bubbles: true }));
          await new Promise((resolve) => requestAnimationFrame(() => resolve(undefined)));
        }
        const titlebar = document.querySelector('.titlebar');
        const rootStyle = window.getComputedStyle(root);
        const px = (v) => Number.parseFloat(v || '0') || 0;
        const padW = px(rootStyle.paddingLeft) + px(rootStyle.paddingRight) + 2;
        const padH = px(rootStyle.paddingTop) + px(rootStyle.paddingBottom) + 2;
        const titleHeight = titlebar ? Math.ceil(titlebar.getBoundingClientRect().height) : 0;
        const dashboard = document.querySelector('.dashboard-page');

        const innerWidth = dashboard ? Math.ceil(dashboard.scrollWidth) : Math.ceil(root.scrollWidth);
        const dashboardHeight = dashboard ? Math.ceil(dashboard.scrollHeight) : Math.ceil(root.scrollHeight);
        return [Math.ceil(innerWidth + padW), Math.ceil(titleHeight + dashboardHeight + padH)];
      })()`, true));
        const display = electron_1.screen.getPrimaryDisplay();
        const wa = display.workArea;
        const targetW = Math.max(320, Math.min(wa.width - 16, contentW + 2));
        const targetH = Math.max(260, Math.min(wa.height - 16, contentH + 2));
        mainWindow.setContentSize(targetW, targetH, false);
        persistSettings((0, window_1.saveWindowBounds)(mainWindow, settings));
    }
    catch {
        return;
    }
}
async function createApp() {
    loadSettings();
    migrateLegacyState();
    const workspaceRoot = detectWorkspaceRoot();
    const projectRoot = electron_1.app.isPackaged ? process.resourcesPath : workspaceRoot;
    const scriptPathCandidates = electron_1.app.isPackaged
        ? [
            path.join(process.resourcesPath, "app.asar.unpacked", "scripts", "backend_bridge.py"),
            path.join(process.resourcesPath, "scripts", "backend_bridge.py"),
        ]
        : [
            path.join(process.cwd(), "scripts", "backend_bridge.py"),
            path.join(electron_1.app.getAppPath(), "scripts", "backend_bridge.py"),
            path.join(path.resolve(electron_1.app.getAppPath(), ".."), "scripts", "backend_bridge.py"),
            path.join(workspaceRoot, "src", "Apps", "arctis-centre-app", "scripts", "backend_bridge.py"),
        ];
    const scriptPath = scriptPathCandidates.find((candidate) => fs.existsSync(candidate)) ?? scriptPathCandidates[0];
    backend = new backend_1.BackendBridge(scriptPath, projectRoot);
    wireIpc();
    wireBackend();
    mainWindow = (0, window_1.createFlyoutWindow)(settings);
    applyWindowBackgroundMaterial(mainWindow);
    mainWindow.on("close", (evt) => {
        if (isQuitting) {
            return;
        }
        evt.preventDefault();
        hideFlyout();
    });
    mainWindow.on("closed", () => {
        mainWindow = null;
    });
    await loadWindowPage(mainWindow, "dashboard");
    mainWindowLoaded = true;
    await fitWindowToMainContent();
    (0, window_1.positionBottomRight)(mainWindow);
    if (pendingFlyoutOpen) {
        pendingFlyoutOpen = false;
        showFlyout();
    }
    settingsWindow = await createCenteredWindow("settings", 580, 520, "Arctis Centre - Settings");
    aboutWindow = await createCenteredWindow("about", 580, 520, "Arctis Centre - About");
    settingsWindow.on("closed", () => {
        settingsWindow = null;
    });
    aboutWindow.on("closed", () => {
        aboutWindow = null;
    });
    mainWindow.on("blur", () => {
        if (Date.now() < suppressBlurUntil) {
            return;
        }
        if (settings.closeOnBlur && mainWindow?.isVisible()) {
            hideFlyout();
        }
    });
    mainWindow.on("resized", () => {
        if (!mainWindow) {
            return;
        }
        persistSettings((0, window_1.saveWindowBounds)(mainWindow, settings));
    });
    mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
    tray = (0, tray_1.createTray)({
        onToggle: () => toggleFlyout(),
        onSettings: () => {
            void showSettingsWindow();
        },
        onAbout: () => {
            void showAboutWindow();
        },
        onQuit: () => electron_1.app.quit(),
    });
    tray.setImage((0, tray_1.buildTrayIcon)());
    electron_1.nativeTheme.on("updated", async () => {
        tray?.setImage((0, tray_1.buildTrayIcon)());
        const payload = await getThemePayload();
        for (const win of allWindows()) {
            win.webContents.send("theme:update", payload);
        }
    });
    registerToggleShortcut(settings.toggleShortcut);
    if (isNotifEnabled("appInfo")) {
        showSystemNotification("Arctis Centre", "App started");
    }
}
electron_1.app.whenReady().then(createApp);
electron_1.app.on("window-all-closed", () => { });
electron_1.app.on("before-quit", () => {
    isQuitting = true;
    if (persistTimer) {
        clearTimeout(persistTimer);
        persistTimer = null;
    }
    persistNow();
    electron_1.globalShortcut.unregisterAll();
    backend?.stop();
});
