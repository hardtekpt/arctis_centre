"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DEFAULT_SETTINGS = exports.DEFAULT_STATE = exports.DEFAULT_CHANNELS = void 0;
exports.DEFAULT_CHANNELS = ["master", "game", "chatRender", "media", "aux", "chatCapture"];
exports.DEFAULT_STATE = {
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
exports.DEFAULT_SETTINGS = {
    themeMode: "system",
    accentColor: "",
    textScale: 100,
    showBatteryPercent: true,
    closeOnBlur: true,
    flyoutWidth: 760,
    flyoutHeight: 520,
    toggleShortcut: "CommandOrControl+Shift+A",
    visibleChannels: [...exports.DEFAULT_CHANNELS],
    lastPage: "dashboard",
};
