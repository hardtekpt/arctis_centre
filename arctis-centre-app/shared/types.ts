export const CHANNELS = [
  "master",
  "game",
  "chatRender",
  "media",
  "aux",
  "chatCapture",
] as const;

export type ChannelKey = (typeof CHANNELS)[number];

export interface AppState {
  headset_battery_percent: number | null;
  base_battery_percent: number | null;
  headset_volume_percent: number | null;
  anc_mode: string | null;
  mic_mute: boolean | null;
  sidetone_level: number | null;
  connected: boolean | null;
  wireless: boolean | null;
  bluetooth: boolean | null;
  chat_mix_balance: number | null;
  oled_brightness: number | null;
  channel_volume: Partial<Record<ChannelKey, number>>;
  channel_mute: Partial<Record<ChannelKey, boolean>>;
  channel_preset: Partial<Record<ChannelKey, string | null>>;
  channel_apps: Partial<Record<ChannelKey, string[]>>;
  updated_at: string | null;
}

export interface UiSettings {
  themeMode: "system" | "light" | "dark";
  accentColor: string;
  textScale: number;
  showBatteryPercent: boolean;
  closeOnBlur: boolean;
  flyoutWidth: number;
  flyoutHeight: number;
  toggleShortcut: string;
  visibleChannels: ChannelKey[];
  lastPage: "dashboard" | "settings" | "about";
}

export interface BackendCommand {
  name: "set_channel_volume" | "set_channel_mute" | "set_preset";
  payload: Record<string, unknown>;
}

export interface PresetMap {
  [channel: string]: Array<[string, string]>;
}
