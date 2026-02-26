import { Notification, app, BrowserWindow, globalShortcut, ipcMain, nativeTheme, screen as electronScreen, shell } from "electron";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { execFile } from "node:child_process";
import { BackendBridge } from "./services/backend";
import { createFlyoutWindow, positionBottomRight, saveWindowBounds } from "./window";
import { buildTrayIcon, createTray } from "./tray";
import { DEFAULT_SETTINGS, mergeSettings, mergeState } from "../shared/settings.js";
import type { AppState, BackendCommand, ChannelKey, PresetMap, UiSettings } from "../shared/types";

let mainWindow: BrowserWindow | null = null;
let settingsWindow: BrowserWindow | null = null;
let aboutWindow: BrowserWindow | null = null;
let tray: Electron.Tray | null = null;
let settings: UiSettings = DEFAULT_SETTINGS;
let cachedState: AppState = mergeState();
let cachedPresets: PresetMap = {};
let backend: BackendBridge | null = null;
let lastStatusText = "ready";
let lastErrorText: string | null = null;
let logBuffer: string[] = [];
let mixerOutputId: string | null = null;
let mixerAppVolume: Record<string, number> = {};
let mixerAppMuted: Record<string, boolean> = {};
let persistTimer: NodeJS.Timeout | null = null;
let mainWindowLoaded = false;
let pendingFlyoutOpen = false;
let isQuitting = false;
let isOpeningFlyout = false;
let suppressBlurUntil = 0;
let hasSeenLiveState = false;

const APP_STATE_VERSION = 1;

if (!app.isPackaged) {
  const devSessionPath = path.join(os.tmpdir(), `arctis-centre-session-${process.pid}`);
  app.setPath("sessionData", devSessionPath);
}

interface PersistedAppState {
  version: number;
  state: AppState;
  presets: PresetMap;
  settings: UiSettings;
  statusText: string;
  errorText: string | null;
  logs: string[];
  mixerOutputId: string | null;
  mixerAppVolume: Record<string, number>;
  mixerAppMuted: Record<string, boolean>;
}

interface MixerOutput {
  id: string;
  name: string;
}

interface MixerApp {
  id: string;
  name: string;
  volume: number;
  muted: boolean;
}

function getUserFile(name: string): string {
  return path.join(app.getPath("userData"), name);
}

function readJsonFile<T>(filePath: string, fallback: T): T {
  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeJsonFile(filePath: string, value: unknown): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tempPath = `${filePath}.tmp`;
  fs.writeFileSync(tempPath, JSON.stringify(value, null, 2), "utf-8");
  fs.renameSync(tempPath, filePath);
}

function getPersistedStateFile(): string {
  return getUserFile("app-state.json");
}

function persistNow(): void {
  const snapshot: PersistedAppState = {
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

function schedulePersist(): void {
  if (persistTimer) {
    clearTimeout(persistTimer);
  }
  persistTimer = setTimeout(() => {
    persistTimer = null;
    persistNow();
  }, 80);
}

function loadPersistedSnapshot(): void {
  const fallback: PersistedAppState = {
    version: APP_STATE_VERSION,
    state: mergeState(),
    presets: {},
    settings: DEFAULT_SETTINGS,
    statusText: "ready",
    errorText: null,
    logs: [],
    mixerOutputId: null,
    mixerAppVolume: {},
    mixerAppMuted: {},
  };
  const loaded = readJsonFile<PersistedAppState>(getPersistedStateFile(), fallback);
  cachedState = mergeState(loaded.state);
  cachedPresets = loaded.presets ?? {};
  settings = mergeSettings(loaded.settings);
  lastStatusText = loaded.statusText ?? "ready";
  lastErrorText = loaded.errorText ?? null;
  logBuffer = Array.isArray(loaded.logs) ? loaded.logs.slice(0, 200) : [];
  mixerOutputId = loaded.mixerOutputId ?? null;
  mixerAppVolume = loaded.mixerAppVolume ?? {};
  mixerAppMuted = loaded.mixerAppMuted ?? {};
}

function pushLog(text: string): void {
  const line = `${new Date().toLocaleTimeString()}  ${text}`;
  logBuffer = [line, ...logBuffer].slice(0, 200);
}

function isNotifEnabled(key: keyof UiSettings["notifications"]): boolean {
  return settings.notifications?.[key] !== false;
}

function showSystemNotification(title: string, body: string): void {
  if (!Notification.isSupported()) {
    return;
  }
  try {
    const notification = new Notification({
      title,
      body,
      icon: buildTrayIcon(),
      silent: false,
    });
    notification.show();
  } catch {
    return;
  }
}

function toPercentLabel(value: number | null): string {
  if (value == null || Number.isNaN(value)) {
    return "N/A";
  }
  return `${Math.max(0, Math.min(100, Math.round(value)))}%`;
}

function channelDisplayName(channel: string): string {
  if (channel === "chatRender") return "CHAT";
  if (channel === "chatCapture") return "MIC";
  return String(channel || "").toUpperCase();
}

function notifyStateChanges(previous: AppState, next: AppState): void {
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
      } else if (prevHeadset < 95 && nextHeadset >= 95) {
        showSystemNotification("Arctis Centre", `Headset battery charged (${toPercentLabel(nextHeadset)})`);
      }
    }
    const prevBase = previous.base_battery_percent;
    const nextBase = next.base_battery_percent;
    if (prevBase != null && nextBase != null) {
      if (prevBase > 20 && nextBase <= 20) {
        showSystemNotification("Arctis Centre", `Base battery low (${toPercentLabel(nextBase)})`);
      } else if (prevBase < 95 && nextBase >= 95) {
        showSystemNotification("Arctis Centre", `Base battery charged (${toPercentLabel(nextBase)})`);
      }
    }
  }
  if (isNotifEnabled("presetChange")) {
    const prevPreset = previous.channel_preset ?? {};
    const nextPreset = next.channel_preset ?? {};
    for (const [channel, nextValue] of Object.entries(nextPreset) as Array<[ChannelKey, string | null | undefined]>) {
      const prevValue = prevPreset[channel];
      if (nextValue !== prevValue && nextValue != null && String(nextValue).trim()) {
        showSystemNotification("Arctis Centre", `${channelDisplayName(channel)} preset: ${String(nextValue)}`);
      }
    }
  }
}

function detectWorkspaceRoot(): string {
  const candidates = [
    process.cwd(),
    path.resolve(process.cwd(), ".."),
    app.getAppPath(),
    path.resolve(app.getAppPath(), ".."),
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

function migrateLegacyState(): void {
  if (fs.existsSync(getPersistedStateFile())) {
    return;
  }
  const oldStateCache = getUserFile("state-cache.json");
  if (fs.existsSync(oldStateCache)) {
    cachedState = mergeState(readJsonFile<Partial<AppState>>(oldStateCache, {}));
  } else {
    const legacy = path.resolve(app.getAppPath(), "..", "tools", "tray_dashboard_state.json");
    if (fs.existsSync(legacy)) {
      const migrated = readJsonFile<Partial<AppState>>(legacy, {});
      cachedState = mergeState(migrated);
    }
  }
  const oldSettings = getUserFile("settings.json");
  if (fs.existsSync(oldSettings)) {
    settings = mergeSettings(readJsonFile<Partial<UiSettings>>(oldSettings, {}));
  }
  persistNow();
}

async function getWindowsAccentColor(): Promise<string> {
  if (process.platform !== "win32") {
    return "#6ab7ff";
  }
  return new Promise((resolve) => {
    execFile(
      "reg",
      ["query", "HKCU\\Software\\Microsoft\\Windows\\DWM", "/v", "ColorizationColor"],
      { windowsHide: true },
      (err, stdout) => {
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
      },
    );
  });
}

async function getThemePayload(): Promise<{ isDark: boolean; accent: string }> {
  return {
    isDark: nativeTheme.shouldUseDarkColors,
    accent: await getWindowsAccentColor(),
  };
}

function showFlyout(): void {
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
    new Promise<void>((resolve) => setTimeout(resolve, 140)),
  ]);
  void fitPromise.finally(() => {
    if (!mainWindow) {
      isOpeningFlyout = false;
      return;
    }
    positionBottomRight(mainWindow);
    mainWindow.show();
    mainWindow.focus();
    isOpeningFlyout = false;
  });
}

function hideFlyout(): void {
  if (!mainWindow) {
    return;
  }
  mainWindow.hide();
}

function toggleFlyout(): void {
  if (!mainWindow) {
    return;
  }
  if (isOpeningFlyout) {
    return;
  }
  if (mainWindow.isVisible()) {
    hideFlyout();
  } else {
    showFlyout();
  }
}

function loadSettings(): void {
  loadPersistedSnapshot();
}

function persistSettings(next: UiSettings): UiSettings {
  settings = mergeSettings(next);
  schedulePersist();
  return settings;
}

function harmonizeLiveState(previous: AppState, incoming: AppState): AppState {
  const next = mergeState(incoming);
  const keep = <T>(newValue: T | null | undefined, oldValue: T | null): T | null =>
    newValue === null || newValue === undefined ? oldValue : newValue;
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

function allWindows(): BrowserWindow[] {
  const wins: BrowserWindow[] = [];
  for (const win of [mainWindow, settingsWindow, aboutWindow]) {
    if (win && !win.isDestroyed()) {
      wins.push(win);
    }
  }
  return wins;
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function getMixerApps(): MixerApp[] {
  const controls = new Map<string, string>([
    ["__device_volume__", "Device Volume"],
    ["__main_system__", "Main System Volume"],
    ["__system_sounds__", "System Sounds"],
  ]);

  const appNames = new Set<string>();
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

async function getMixerOutputs(): Promise<MixerOutput[]> {
  if (process.platform !== "win32") {
    return [{ id: "default", name: "System Default Output" }];
  }
  return new Promise((resolve) => {
    execFile(
      "powershell",
      [
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Get-CimInstance Win32_SoundDevice | Select-Object -ExpandProperty Name",
      ],
      { windowsHide: true },
      (err, stdout) => {
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
      },
    );
  });
}

function wireBackend(): void {
  if (!backend) {
    return;
  }
  backend.on("state", (state: AppState) => {
    const previous = cachedState;
    cachedState = harmonizeLiveState(cachedState, state);
    if (hasSeenLiveState) {
      notifyStateChanges(previous, cachedState);
    } else {
      hasSeenLiveState = true;
    }
    schedulePersist();
    for (const win of allWindows()) {
      win.webContents.send("backend:state", cachedState);
    }
  });
  backend.on("presets", (presets: PresetMap) => {
    cachedPresets = presets;
    schedulePersist();
    for (const win of allWindows()) {
      win.webContents.send("backend:presets", presets);
    }
  });
  backend.on("status", (text: string) => {
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
  backend.on("error", (text: string) => {
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

function wireIpc(): void {
  if (!backend) {
    return;
  }
  ipcMain.handle("app:get-initial", async () => {
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
  ipcMain.on("backend:command", (_evt, cmd: BackendCommand) => backend!.send(cmd));
  ipcMain.on("window:hide", () => hideFlyout());
  ipcMain.on("window:open-settings", () => {
    void showSettingsWindow();
  });
  ipcMain.on("window:open-about", () => {
    void showAboutWindow();
  });
  ipcMain.on("window:close-current", (evt) => {
    const win = BrowserWindow.fromWebContents(evt.sender);
    if (!win) {
      return;
    }
    if (win === mainWindow) {
      hideFlyout();
      return;
    }
    win.hide();
  });
  ipcMain.handle("settings:set", (_evt, partial: Partial<UiSettings>) => {
    const next = persistSettings({ ...settings, ...partial });
    registerToggleShortcut(next.toggleShortcut);
    for (const win of allWindows()) {
      win.webContents.send("settings:update", next);
    }
    return next;
  });
  ipcMain.handle("app:open-gg", async () => {
    const candidates = [
      "C:\\Program Files\\SteelSeries\\GG\\SteelSeriesGGClient.exe",
      "C:\\Program Files\\SteelSeries\\GG\\SteelSeriesGG.exe",
      "C:\\Program Files (x86)\\SteelSeries\\GG\\SteelSeriesGG.exe",
    ];
    for (const exe of candidates) {
      if (fs.existsSync(exe)) {
        const result = await shell.openPath(exe);
        return { ok: result === "", detail: result || exe };
      }
    }
    const uriResult = await shell.openExternal("steelseriesgg://", { activate: true });
    return { ok: uriResult, detail: "steelseriesgg://" };
  });
  ipcMain.handle("app:notify-custom", async (_evt, payload: { title?: string; body?: string }) => {
    const title = String(payload?.title || "").trim() || "Arctis Centre";
    const body = String(payload?.body || "").trim() || "Notification";
    showSystemNotification(title, body);
    return { ok: true };
  });
  ipcMain.handle("mixer:get-data", async () => {
    const outputs = await getMixerOutputs();
    const selectedOutputId = mixerOutputId && outputs.some((o) => o.id === mixerOutputId) ? mixerOutputId : outputs[0]?.id ?? "default";
    if (selectedOutputId !== mixerOutputId) {
      mixerOutputId = selectedOutputId;
      schedulePersist();
    }
    return { outputs, selectedOutputId, apps: getMixerApps() };
  });
  ipcMain.handle("mixer:set-output", (_evt, outputId: string) => {
    mixerOutputId = String(outputId || "").trim() || null;
    schedulePersist();
    return { ok: true };
  });
  ipcMain.handle("mixer:set-app-volume", (_evt, payload: { appId: string; volume: number }) => {
    const appId = String(payload?.appId || "").trim();
    if (!appId) {
      return { ok: false };
    }
    mixerAppVolume[appId] = clampPercent(Number(payload.volume));
    schedulePersist();
    return { ok: true };
  });
  ipcMain.handle("mixer:set-app-mute", (_evt, payload: { appId: string; muted: boolean }) => {
    const appId = String(payload?.appId || "").trim();
    if (!appId) {
      return { ok: false };
    }
    mixerAppMuted[appId] = Boolean(payload.muted);
    schedulePersist();
    return { ok: true };
  });
}

async function loadWindowPage(win: BrowserWindow, page: "dashboard" | "settings" | "about"): Promise<void> {
  if (process.env.VITE_DEV_SERVER_URL) {
    await win.loadURL(`${process.env.VITE_DEV_SERVER_URL}?window=${page}`);
  } else {
    await win.loadFile(path.join(app.getAppPath(), "dist", "index.html"), { query: { window: page } });
  }
}

async function createCenteredWindow(page: "settings" | "about", width: number, height: number, title: string): Promise<BrowserWindow> {
  const win = new BrowserWindow({
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
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  await loadWindowPage(win, page);
  return win;
}

async function showSettingsWindow(): Promise<void> {
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

async function showAboutWindow(): Promise<void> {
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

function registerToggleShortcut(accelerator: string): void {
  globalShortcut.unregisterAll();
  if (!accelerator.trim()) {
    return;
  }
  try {
    const ok = globalShortcut.register(accelerator, () => toggleFlyout());
    if (!ok) {
      mainWindow?.webContents.send("backend:error", `Unable to register shortcut: ${accelerator}`);
      if (isNotifEnabled("appInfo")) {
        showSystemNotification("Arctis Centre Error", `Unable to register shortcut: ${accelerator}`);
      }
    } else {
      mainWindow?.webContents.send("backend:status", `Shortcut registered: ${accelerator}`);
      if (isNotifEnabled("appInfo")) {
        showSystemNotification("Arctis Centre", `Shortcut registered: ${accelerator}`);
      }
    }
  } catch (err) {
    mainWindow?.webContents.send("backend:error", `Invalid shortcut: ${accelerator} (${String(err)})`);
    if (isNotifEnabled("appInfo")) {
      showSystemNotification("Arctis Centre Error", `Invalid shortcut: ${accelerator}`);
    }
  }
}

async function fitWindowToMainContent(): Promise<void> {
  if (!mainWindow || mainWindow.webContents.isLoading()) {
    return;
  }
  try {
    const [contentW, contentH] = (await mainWindow.webContents.executeJavaScript(
      `(async () => {
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
      })()`,
      true,
    )) as [number, number];
    const display = electronScreen.getPrimaryDisplay();
    const wa = display.workArea;
    const targetW = Math.max(320, Math.min(wa.width - 16, contentW + 2));
    const targetH = Math.max(260, Math.min(wa.height - 16, contentH + 2));
    mainWindow.setContentSize(targetW, targetH, false);
    persistSettings(saveWindowBounds(mainWindow, settings));
  } catch {
    return;
  }
}

async function createApp(): Promise<void> {
  loadSettings();
  migrateLegacyState();
  const workspaceRoot = detectWorkspaceRoot();
  const projectRoot = app.isPackaged ? process.resourcesPath : workspaceRoot;
  const scriptPathCandidates = app.isPackaged
    ? [
        path.join(process.resourcesPath, "app.asar.unpacked", "scripts", "backend_bridge.py"),
        path.join(process.resourcesPath, "scripts", "backend_bridge.py"),
      ]
    : [
        path.join(process.cwd(), "scripts", "backend_bridge.py"),
        path.join(app.getAppPath(), "scripts", "backend_bridge.py"),
        path.join(path.resolve(app.getAppPath(), ".."), "scripts", "backend_bridge.py"),
        path.join(workspaceRoot, "arctis-centre-app", "scripts", "backend_bridge.py"),
      ];
  const scriptPath = scriptPathCandidates.find((candidate) => fs.existsSync(candidate)) ?? scriptPathCandidates[0];
  backend = new BackendBridge(scriptPath, projectRoot);
  wireIpc();
  wireBackend();

  mainWindow = createFlyoutWindow(settings);
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
  positionBottomRight(mainWindow);
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
    persistSettings(saveWindowBounds(mainWindow, settings));
  });
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));

  tray = createTray({
    onToggle: () => toggleFlyout(),
    onSettings: () => {
      void showSettingsWindow();
    },
    onAbout: () => {
      void showAboutWindow();
    },
    onQuit: () => app.quit(),
  });
  tray.setImage(buildTrayIcon());

  nativeTheme.on("updated", async () => {
    tray?.setImage(buildTrayIcon());
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

app.whenReady().then(createApp);
app.on("window-all-closed", () => {});
app.on("before-quit", () => {
  isQuitting = true;
  if (persistTimer) {
    clearTimeout(persistTimer);
    persistTimer = null;
  }
  persistNow();
  globalShortcut.unregisterAll();
  backend?.stop();
});
