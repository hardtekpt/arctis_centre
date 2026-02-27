"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ipcClient = void 0;
const electron_1 = require("electron");
const constants_1 = require("../../shared/constants");
exports.ipcClient = {
    getInitial: () => electron_1.ipcRenderer.invoke(constants_1.IPC_CHANNELS.invoke.appGetInitial),
    openGG: () => electron_1.ipcRenderer.invoke(constants_1.IPC_CHANNELS.invoke.appOpenGG),
    getMixerData: () => electron_1.ipcRenderer.invoke(constants_1.IPC_CHANNELS.invoke.mixerGetData),
    setMixerOutput: (outputId) => electron_1.ipcRenderer.invoke(constants_1.IPC_CHANNELS.invoke.mixerSetOutput, outputId),
    setMixerAppVolume: (appId, volume) => electron_1.ipcRenderer.invoke(constants_1.IPC_CHANNELS.invoke.mixerSetAppVolume, { appId, volume }),
    setMixerAppMute: (appId, muted) => electron_1.ipcRenderer.invoke(constants_1.IPC_CHANNELS.invoke.mixerSetAppMute, { appId, muted }),
    sendCommand: (cmd) => electron_1.ipcRenderer.send(constants_1.IPC_CHANNELS.send.backendCommand, cmd),
    hideFlyout: () => electron_1.ipcRenderer.send(constants_1.IPC_CHANNELS.send.windowHide),
    closeCurrentWindow: () => electron_1.ipcRenderer.send(constants_1.IPC_CHANNELS.send.windowCloseCurrent),
    openSettingsWindow: () => electron_1.ipcRenderer.send(constants_1.IPC_CHANNELS.send.windowOpenSettings),
    openAboutWindow: () => electron_1.ipcRenderer.send(constants_1.IPC_CHANNELS.send.windowOpenAbout),
    setSettings: (settings) => electron_1.ipcRenderer.invoke(constants_1.IPC_CHANNELS.invoke.settingsSet, settings),
    onState: (cb) => {
        const fn = (_, payload) => cb(payload);
        electron_1.ipcRenderer.on(constants_1.IPC_CHANNELS.event.backendState, fn);
        return () => electron_1.ipcRenderer.removeListener(constants_1.IPC_CHANNELS.event.backendState, fn);
    },
    onPresets: (cb) => {
        const fn = (_, payload) => cb(payload);
        electron_1.ipcRenderer.on(constants_1.IPC_CHANNELS.event.backendPresets, fn);
        return () => electron_1.ipcRenderer.removeListener(constants_1.IPC_CHANNELS.event.backendPresets, fn);
    },
    onStatus: (cb) => {
        const fn = (_, payload) => cb(payload);
        electron_1.ipcRenderer.on(constants_1.IPC_CHANNELS.event.backendStatus, fn);
        return () => electron_1.ipcRenderer.removeListener(constants_1.IPC_CHANNELS.event.backendStatus, fn);
    },
    onError: (cb) => {
        const fn = (_, payload) => cb(payload);
        electron_1.ipcRenderer.on(constants_1.IPC_CHANNELS.event.backendError, fn);
        return () => electron_1.ipcRenderer.removeListener(constants_1.IPC_CHANNELS.event.backendError, fn);
    },
    onTheme: (cb) => {
        const fn = (_, payload) => cb(payload);
        electron_1.ipcRenderer.on(constants_1.IPC_CHANNELS.event.themeUpdate, fn);
        return () => electron_1.ipcRenderer.removeListener(constants_1.IPC_CHANNELS.event.themeUpdate, fn);
    },
    onSettings: (cb) => {
        const fn = (_, payload) => cb(payload);
        electron_1.ipcRenderer.on(constants_1.IPC_CHANNELS.event.settingsUpdate, fn);
        return () => electron_1.ipcRenderer.removeListener(constants_1.IPC_CHANNELS.event.settingsUpdate, fn);
    },
};
