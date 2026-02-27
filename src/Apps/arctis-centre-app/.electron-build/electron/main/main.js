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
const backend_1 = require("../services/backend");
const flyoutWindow_1 = require("./windows/flyoutWindow");
const trayController_1 = require("./tray/trayController");
const settings_1 = require("../../shared/settings");
const storage_1 = require("../../shared/settings/storage");
const constants_1 = require("../../shared/constants");
const windowsTheme_1 = require("../platform/windowsTheme");
const ipcMainRouter_1 = require("./ipc/ipcMainRouter");
const appLifecycle_1 = require("./appLifecycle");
let mainWindow = null;
let settingsWindow = null;
let aboutWindow = null;
let tray = null;
let settings = settings_1.DEFAULT_SETTINGS;
let cachedState = (0, settings_1.mergeState)();
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
if (!electron_1.app.isPackaged) {
    const devSessionPath = path.join(os.tmpdir(), `arctis-centre-session-${process.pid}`);
    electron_1.app.setPath("sessionData", devSessionPath);
}
function getUserFile(name) {
    return path.join(electron_1.app.getPath("userData"), name);
}
function getPersistedStateFile() {
    return getUserFile(constants_1.APP_STATE_FILE);
}
function persistNow() {
    const snapshot = {
        version: constants_1.APP_STATE_VERSION,
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
    (0, storage_1.writeJsonFile)(getPersistedStateFile(), snapshot);
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
        version: constants_1.APP_STATE_VERSION,
        state: (0, settings_1.mergeState)(),
        presets: {},
        settings: settings_1.DEFAULT_SETTINGS,
        statusText: "ready",
        errorText: null,
        logs: [],
        mixerOutputId: null,
        mixerAppVolume: {},
        mixerAppMuted: {},
    };
    const loaded = (0, storage_1.readJsonFile)(getPersistedStateFile(), fallback);
    cachedState = (0, settings_1.mergeState)(loaded.state);
    cachedPresets = loaded.presets ?? {};
    settings = (0, settings_1.mergeSettings)(loaded.settings);
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
function detectWorkspaceRoot() {
    const candidates = [
        process.cwd(),
        path.resolve(process.cwd(), ".."),
        electron_1.app.getAppPath(),
        path.resolve(electron_1.app.getAppPath(), ".."),
    ];
    for (const candidate of candidates) {
        const pyproject = path.join(candidate, "pyproject.toml");
        const apiDir = path.join(candidate, "src", "arctis_nova_api");
        if (fs.existsSync(pyproject) && fs.existsSync(apiDir)) {
            return candidate;
        }
    }
    return path.resolve(process.cwd(), "..");
}
function migrateLegacyState() {
    if (fs.existsSync(getPersistedStateFile())) {
        return;
    }
    const oldStateCache = getUserFile(constants_1.LEGACY_STATE_CACHE_FILE);
    if (fs.existsSync(oldStateCache)) {
        cachedState = (0, settings_1.mergeState)((0, storage_1.readJsonFile)(oldStateCache, {}));
    }
    else {
        const legacy = path.resolve(electron_1.app.getAppPath(), "..", "tools", "tray_dashboard_state.json");
        if (fs.existsSync(legacy)) {
            const migrated = (0, storage_1.readJsonFile)(legacy, {});
            cachedState = (0, settings_1.mergeState)(migrated);
        }
    }
    const oldSettings = getUserFile(constants_1.LEGACY_SETTINGS_FILE);
    if (fs.existsSync(oldSettings)) {
        settings = (0, settings_1.mergeSettings)((0, storage_1.readJsonFile)(oldSettings, {}));
    }
    persistNow();
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
    const fitPromise = Promise.race([fitWindowToMainContent(), new Promise((resolve) => setTimeout(resolve, 140))]);
    void fitPromise.finally(() => {
        if (!mainWindow) {
            isOpeningFlyout = false;
            return;
        }
        (0, flyoutWindow_1.positionBottomRight)(mainWindow);
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
    settings = (0, settings_1.mergeSettings)(next);
    schedulePersist();
    return settings;
}
function harmonizeLiveState(previous, incoming) {
    const next = (0, settings_1.mergeState)(incoming);
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
    for (const win of [mainWindow, settingsWindow, aboutWindow]) {
        if (win && !win.isDestroyed()) {
            wins.push(win);
        }
    }
    return wins;
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
        for (const appName of list) {
            const trimmed = String(appName || "").trim();
            if (trimmed) {
                appNames.add(trimmed);
            }
        }
    }
    for (const appName of appNames) {
        controls.set(appName, appName);
    }
    for (const appName of Object.keys(mixerAppVolume)) {
        const trimmed = String(appName || "").trim();
        if (trimmed) {
            controls.set(trimmed, trimmed);
        }
    }
    for (const appName of Object.keys(mixerAppMuted)) {
        const trimmed = String(appName || "").trim();
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
        cachedState = harmonizeLiveState(cachedState, state);
        schedulePersist();
        for (const win of allWindows()) {
            win.webContents.send(constants_1.IPC_CHANNELS.event.backendState, cachedState);
        }
    });
    backend.on("presets", (presets) => {
        cachedPresets = presets;
        schedulePersist();
        for (const win of allWindows()) {
            win.webContents.send(constants_1.IPC_CHANNELS.event.backendPresets, presets);
        }
    });
    backend.on("status", (text) => {
        lastStatusText = text;
        lastErrorText = null;
        pushLog(text);
        schedulePersist();
        for (const win of allWindows()) {
            win.webContents.send(constants_1.IPC_CHANNELS.event.backendStatus, text);
        }
    });
    backend.on("error", (text) => {
        lastErrorText = text;
        lastStatusText = text;
        pushLog(`ERROR: ${text}`);
        schedulePersist();
        for (const win of allWindows()) {
            win.webContents.send(constants_1.IPC_CHANNELS.event.backendError, text);
        }
    });
    backend.start();
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
        backgroundColor: "#1f1f1f",
        webPreferences: {
            preload: path.join(__dirname, "..", "preload", "preload.js"),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });
    await loadWindowPage(win, page);
    return win;
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
            mainWindow?.webContents.send(constants_1.IPC_CHANNELS.event.backendError, `Unable to register shortcut: ${accelerator}`);
        }
        else {
            mainWindow?.webContents.send(constants_1.IPC_CHANNELS.event.backendStatus, `Shortcut registered: ${accelerator}`);
        }
    }
    catch (err) {
        mainWindow?.webContents.send(constants_1.IPC_CHANNELS.event.backendError, `Invalid shortcut: ${accelerator} (${String(err)})`);
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
        persistSettings((0, flyoutWindow_1.saveWindowBounds)(mainWindow, settings));
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
            path.join(workspaceRoot, "arctis-centre-app", "scripts", "backend_bridge.py"),
        ];
    const scriptPath = scriptPathCandidates.find((candidate) => fs.existsSync(candidate)) ?? scriptPathCandidates[0];
    backend = new backend_1.BackendBridge(scriptPath, projectRoot);
    (0, ipcMainRouter_1.registerIpcMainHandlers)({
        backend,
        mainWindowRef: () => mainWindow,
        allWindows,
        hideFlyout,
        showSettingsWindow,
        showAboutWindow,
        getInitialPayload: async () => ({
            state: cachedState,
            presets: cachedPresets,
            settings,
            theme: await (0, windowsTheme_1.getThemePayload)(),
            status: lastStatusText,
            error: lastErrorText,
            logs: logBuffer,
        }),
        getSettings: () => settings,
        persistSettingsPartial: (partial) => persistSettings(partial),
        registerToggleShortcut,
        openGGCandidates: [
            "C:\\Program Files\\SteelSeries\\GG\\SteelSeriesGGClient.exe",
            "C:\\Program Files\\SteelSeries\\GG\\SteelSeriesGG.exe",
            "C:\\Program Files (x86)\\SteelSeries\\GG\\SteelSeriesGG.exe",
        ],
        getMixerData: async () => {
            const outputs = await getMixerOutputs();
            const selectedOutputId = mixerOutputId && outputs.some((output) => output.id === mixerOutputId) ? mixerOutputId : outputs[0]?.id ?? "default";
            if (selectedOutputId !== mixerOutputId) {
                mixerOutputId = selectedOutputId;
                schedulePersist();
            }
            return { outputs, selectedOutputId, apps: getMixerApps() };
        },
        setMixerOutput: (outputId) => {
            mixerOutputId = String(outputId || "").trim() || null;
            schedulePersist();
            return { ok: true };
        },
        setMixerAppVolume: (payload) => {
            const appId = String(payload?.appId || "").trim();
            if (!appId) {
                return { ok: false };
            }
            mixerAppVolume[appId] = clampPercent(Number(payload.volume));
            schedulePersist();
            return { ok: true };
        },
        setMixerAppMute: (payload) => {
            const appId = String(payload?.appId || "").trim();
            if (!appId) {
                return { ok: false };
            }
            mixerAppMuted[appId] = Boolean(payload.muted);
            schedulePersist();
            return { ok: true };
        },
    });
    wireBackend();
    mainWindow = (0, flyoutWindow_1.createFlyoutWindow)(settings);
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
    (0, flyoutWindow_1.positionBottomRight)(mainWindow);
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
        persistSettings((0, flyoutWindow_1.saveWindowBounds)(mainWindow, settings));
    });
    mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
    tray = (0, trayController_1.createTray)({
        onToggle: () => toggleFlyout(),
        onSettings: () => {
            void showSettingsWindow();
        },
        onAbout: () => {
            void showAboutWindow();
        },
        onQuit: () => electron_1.app.quit(),
    });
    tray.setImage((0, trayController_1.buildTrayIcon)());
    electron_1.nativeTheme.on("updated", async () => {
        tray?.setImage((0, trayController_1.buildTrayIcon)());
        const payload = await (0, windowsTheme_1.getThemePayload)();
        for (const win of allWindows()) {
            win.webContents.send(constants_1.IPC_CHANNELS.event.themeUpdate, payload);
        }
    });
    registerToggleShortcut(settings.toggleShortcut);
}
electron_1.app.whenReady().then(createApp);
(0, appLifecycle_1.registerAppLifecycle)({
    onBeforeQuit: () => {
        isQuitting = true;
        if (persistTimer) {
            clearTimeout(persistTimer);
            persistTimer = null;
        }
        persistNow();
        backend?.stop();
    },
});
