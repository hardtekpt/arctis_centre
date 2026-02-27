"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.mergeState = mergeState;
exports.mergeSettings = mergeSettings;
const defaults_1 = require("./defaults");
function clamp(value, low, high) {
    return Math.min(high, Math.max(low, value));
}
function mergeState(partial) {
    return {
        ...defaults_1.DEFAULT_STATE,
        ...(partial ?? {}),
        channel_volume: {
            ...defaults_1.DEFAULT_STATE.channel_volume,
            ...(partial?.channel_volume ?? {}),
        },
        channel_mute: {
            ...defaults_1.DEFAULT_STATE.channel_mute,
            ...(partial?.channel_mute ?? {}),
        },
        channel_preset: {
            ...defaults_1.DEFAULT_STATE.channel_preset,
            ...(partial?.channel_preset ?? {}),
        },
        channel_apps: {
            ...defaults_1.DEFAULT_STATE.channel_apps,
            ...(partial?.channel_apps ?? {}),
        },
    };
}
function mergeSettings(partial) {
    const visibleChannels = partial?.visibleChannels?.filter((channel) => defaults_1.DEFAULT_CHANNELS.includes(channel)) ??
        defaults_1.DEFAULT_SETTINGS.visibleChannels;
    return {
        ...defaults_1.DEFAULT_SETTINGS,
        ...(partial ?? {}),
        flyoutWidth: clamp(partial?.flyoutWidth ?? defaults_1.DEFAULT_SETTINGS.flyoutWidth, 320, 1000),
        flyoutHeight: clamp(partial?.flyoutHeight ?? defaults_1.DEFAULT_SETTINGS.flyoutHeight, 260, 1200),
        visibleChannels,
    };
}
