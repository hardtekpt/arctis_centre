"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.IPC_CHANNELS = exports.APP_STATE_VERSION = exports.LEGACY_SETTINGS_FILE = exports.LEGACY_STATE_CACHE_FILE = exports.APP_STATE_FILE = void 0;
exports.APP_STATE_FILE = "app-state.json";
exports.LEGACY_STATE_CACHE_FILE = "state-cache.json";
exports.LEGACY_SETTINGS_FILE = "settings.json";
exports.APP_STATE_VERSION = 1;
exports.IPC_CHANNELS = {
    invoke: {
        appGetInitial: "app:get-initial",
        settingsSet: "settings:set",
        appOpenGG: "app:open-gg",
        mixerGetData: "mixer:get-data",
        mixerSetOutput: "mixer:set-output",
        mixerSetAppVolume: "mixer:set-app-volume",
        mixerSetAppMute: "mixer:set-app-mute",
    },
    send: {
        backendCommand: "backend:command",
        windowHide: "window:hide",
        windowOpenSettings: "window:open-settings",
        windowOpenAbout: "window:open-about",
        windowCloseCurrent: "window:close-current",
    },
    event: {
        backendState: "backend:state",
        backendPresets: "backend:presets",
        backendStatus: "backend:status",
        backendError: "backend:error",
        themeUpdate: "theme:update",
        settingsUpdate: "settings:update",
    },
};
