import type { AppState, ChannelKey, UiSettings } from "./types";

const DEFAULT_CHANNELS: ChannelKey[] = ["master", "game", "chatRender", "media", "aux", "chatCapture"];

export const DEFAULT_STATE: AppState = {
  headset_battery_percent: null,
  base_battery_percent: null,
  headset_volume_percent: null,
  anc_mode: null,
  mic_mute: null,
  sidetone_level: null,
  connected: null,
  wireless: null,
  bluetooth: null,
  chat_mix_balance: null,
  oled_brightness: null,
  channel_volume: {},
  channel_mute: {},
  channel_preset: {},
  channel_apps: {},
  updated_at: null,
};

export const DEFAULT_SETTINGS: UiSettings = {
  themeMode: "system",
  accentColor: "",
  textScale: 100,
  showBatteryPercent: true,
  closeOnBlur: true,
  flyoutWidth: 760,
  flyoutHeight: 520,
  toggleShortcut: "CommandOrControl+Shift+A",
  visibleChannels: [...DEFAULT_CHANNELS],
  lastPage: "dashboard",
  notifications: {
    connectivity: true,
    ancMode: true,
    oled: true,
    sidetone: true,
    micMute: true,
    chatMix: true,
    headsetVolume: true,
    battery: true,
    appInfo: true,
    presetChange: true,
  },
};

export function mergeState(partial?: Partial<AppState>): AppState {
  return {
    ...DEFAULT_STATE,
    ...(partial ?? {}),
    channel_volume: {
      ...DEFAULT_STATE.channel_volume,
      ...(partial?.channel_volume ?? {}),
    },
    channel_mute: {
      ...DEFAULT_STATE.channel_mute,
      ...(partial?.channel_mute ?? {}),
    },
    channel_preset: {
      ...DEFAULT_STATE.channel_preset,
      ...(partial?.channel_preset ?? {}),
    },
    channel_apps: {
      ...DEFAULT_STATE.channel_apps,
      ...(partial?.channel_apps ?? {}),
    },
  };
}

export function mergeSettings(partial?: Partial<UiSettings>): UiSettings {
  const visibleChannels =
    partial?.visibleChannels?.filter((channel): channel is ChannelKey => DEFAULT_CHANNELS.includes(channel)) ??
    DEFAULT_SETTINGS.visibleChannels;
  return {
    ...DEFAULT_SETTINGS,
    ...(partial ?? {}),
    flyoutWidth: clamp((partial?.flyoutWidth ?? DEFAULT_SETTINGS.flyoutWidth), 320, 1000),
    flyoutHeight: clamp((partial?.flyoutHeight ?? DEFAULT_SETTINGS.flyoutHeight), 260, 1200),
    visibleChannels,
    notifications: {
      ...DEFAULT_SETTINGS.notifications,
      ...(partial?.notifications ?? {}),
    },
  };
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}
