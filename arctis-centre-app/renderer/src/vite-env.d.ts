/// <reference types="vite/client" />

import type { AppState, BackendCommand, PresetMap, UiSettings } from "@shared/types";

declare global {
  interface Window {
    arctisBridge: {
      getInitial: () => Promise<{
        state: AppState;
        presets: PresetMap;
        settings: UiSettings;
        theme: { isDark: boolean; accent: string };
        status: string;
        error: string | null;
        logs: string[];
      }>;
      openGG: () => Promise<{ ok: boolean; detail: string }>;
      getMixerData: () => Promise<{
        outputs: Array<{ id: string; name: string }>;
        selectedOutputId: string;
        apps: Array<{ id: string; name: string; volume: number; muted: boolean }>;
      }>;
      setMixerOutput: (outputId: string) => Promise<{ ok: boolean }>;
      setMixerAppVolume: (appId: string, volume: number) => Promise<{ ok: boolean }>;
      setMixerAppMute: (appId: string, muted: boolean) => Promise<{ ok: boolean }>;
      sendCommand: (cmd: BackendCommand) => void;
      hideFlyout: () => void;
      closeCurrentWindow: () => void;
      openSettingsWindow: () => void;
      openAboutWindow: () => void;
      setSettings: (settings: Partial<UiSettings>) => Promise<UiSettings>;
      onState: (cb: (state: AppState) => void) => () => void;
      onPresets: (cb: (presets: PresetMap) => void) => () => void;
      onStatus: (cb: (text: string) => void) => () => void;
      onError: (cb: (text: string) => void) => () => void;
      onTheme: (cb: (payload: { isDark: boolean; accent: string }) => void) => () => void;
      onSettings: (cb: (payload: UiSettings) => void) => () => void;
    };
  }
}

export {};
