import { contextBridge, ipcRenderer } from "electron";
import type { AppState, BackendCommand, PresetMap, UiSettings } from "@shared/types";

interface InitialPayload {
  state: AppState;
  presets: PresetMap;
  settings: UiSettings;
  theme: { isDark: boolean; accent: string };
  status: string;
  error: string | null;
  logs: string[];
}

interface MixerDataPayload {
  outputs: Array<{ id: string; name: string }>;
  selectedOutputId: string;
  apps: Array<{ id: string; name: string; volume: number; muted: boolean }>;
}

const api = {
  getInitial: (): Promise<InitialPayload> => ipcRenderer.invoke("app:get-initial"),
  openGG: (): Promise<{ ok: boolean; detail: string }> => ipcRenderer.invoke("app:open-gg"),
  notifyCustom: (title: string, body: string): Promise<{ ok: boolean }> => ipcRenderer.invoke("app:notify-custom", { title, body }),
  getMixerData: (): Promise<MixerDataPayload> => ipcRenderer.invoke("mixer:get-data"),
  setMixerOutput: (outputId: string): Promise<{ ok: boolean }> => ipcRenderer.invoke("mixer:set-output", outputId),
  setMixerAppVolume: (appId: string, volume: number): Promise<{ ok: boolean }> =>
    ipcRenderer.invoke("mixer:set-app-volume", { appId, volume }),
  setMixerAppMute: (appId: string, muted: boolean): Promise<{ ok: boolean }> =>
    ipcRenderer.invoke("mixer:set-app-mute", { appId, muted }),
  sendCommand: (cmd: BackendCommand): void => ipcRenderer.send("backend:command", cmd),
  hideFlyout: (): void => ipcRenderer.send("window:hide"),
  closeCurrentWindow: (): void => ipcRenderer.send("window:close-current"),
  openSettingsWindow: (): void => ipcRenderer.send("window:open-settings"),
  openAboutWindow: (): void => ipcRenderer.send("window:open-about"),
  setSettings: (settings: Partial<UiSettings>): Promise<UiSettings> => ipcRenderer.invoke("settings:set", settings),
  onState: (cb: (state: AppState) => void): (() => void) => {
    const fn = (_: unknown, payload: AppState) => cb(payload);
    ipcRenderer.on("backend:state", fn);
    return () => ipcRenderer.removeListener("backend:state", fn);
  },
  onPresets: (cb: (presets: PresetMap) => void): (() => void) => {
    const fn = (_: unknown, payload: PresetMap) => cb(payload);
    ipcRenderer.on("backend:presets", fn);
    return () => ipcRenderer.removeListener("backend:presets", fn);
  },
  onStatus: (cb: (text: string) => void): (() => void) => {
    const fn = (_: unknown, payload: string) => cb(payload);
    ipcRenderer.on("backend:status", fn);
    return () => ipcRenderer.removeListener("backend:status", fn);
  },
  onError: (cb: (text: string) => void): (() => void) => {
    const fn = (_: unknown, payload: string) => cb(payload);
    ipcRenderer.on("backend:error", fn);
    return () => ipcRenderer.removeListener("backend:error", fn);
  },
  onTheme: (cb: (payload: { isDark: boolean; accent: string }) => void): (() => void) => {
    const fn = (_: unknown, payload: { isDark: boolean; accent: string }) => cb(payload);
    ipcRenderer.on("theme:update", fn);
    return () => ipcRenderer.removeListener("theme:update", fn);
  },
  onSettings: (cb: (payload: UiSettings) => void): (() => void) => {
    const fn = (_: unknown, payload: UiSettings) => cb(payload);
    ipcRenderer.on("settings:update", fn);
    return () => ipcRenderer.removeListener("settings:update", fn);
  },
};

contextBridge.exposeInMainWorld("arctisBridge", api);
