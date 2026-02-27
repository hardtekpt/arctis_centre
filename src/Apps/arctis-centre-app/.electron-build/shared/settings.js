"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DEFAULT_SETTINGS = exports.DEFAULT_STATE = void 0;
exports.mergeState = mergeState;
exports.mergeSettings = mergeSettings;
const DEFAULT_CHANNELS = ["master", "game", "chatRender", "media", "aux", "chatCapture"];
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
    micaBlur: true,
    notificationTimeout: 5,
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
function mergeState(partial) {
    return {
        ...exports.DEFAULT_STATE,
        ...(partial ?? {}),
        channel_volume: {
            ...exports.DEFAULT_STATE.channel_volume,
            ...(partial?.channel_volume ?? {}),
        },
        channel_mute: {
            ...exports.DEFAULT_STATE.channel_mute,
            ...(partial?.channel_mute ?? {}),
        },
        channel_preset: {
            ...exports.DEFAULT_STATE.channel_preset,
            ...(partial?.channel_preset ?? {}),
        },
        channel_apps: {
            ...exports.DEFAULT_STATE.channel_apps,
            ...(partial?.channel_apps ?? {}),
        },
    };
}
function mergeSettings(partial) {
    const visibleChannels = partial?.visibleChannels?.filter((channel) => DEFAULT_CHANNELS.includes(channel)) ??
        exports.DEFAULT_SETTINGS.visibleChannels;
    return {
        ...exports.DEFAULT_SETTINGS,
        ...(partial ?? {}),
        notificationTimeout: clamp((partial?.notificationTimeout ?? exports.DEFAULT_SETTINGS.notificationTimeout), 2, 30),
        flyoutWidth: clamp((partial?.flyoutWidth ?? exports.DEFAULT_SETTINGS.flyoutWidth), 320, 1000),
        flyoutHeight: clamp((partial?.flyoutHeight ?? exports.DEFAULT_SETTINGS.flyoutHeight), 260, 1200),
        visibleChannels,
        notifications: {
            ...exports.DEFAULT_SETTINGS.notifications,
            ...(partial?.notifications ?? {}),
        },
    };
}
function clamp(value, low, high) {
    return Math.min(high, Math.max(low, value));
}
