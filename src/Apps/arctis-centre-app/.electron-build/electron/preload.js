"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const api = {
    getInitial: () => electron_1.ipcRenderer.invoke("app:get-initial"),
    openGG: () => electron_1.ipcRenderer.invoke("app:open-gg"),
    notifyCustom: (title, body) => electron_1.ipcRenderer.invoke("app:notify-custom", { title, body }),
    getMixerData: () => electron_1.ipcRenderer.invoke("mixer:get-data"),
    setMixerOutput: (outputId) => electron_1.ipcRenderer.invoke("mixer:set-output", outputId),
    setMixerAppVolume: (appId, volume) => electron_1.ipcRenderer.invoke("mixer:set-app-volume", { appId, volume }),
    setMixerAppMute: (appId, muted) => electron_1.ipcRenderer.invoke("mixer:set-app-mute", { appId, muted }),
    sendCommand: (cmd) => electron_1.ipcRenderer.send("backend:command", cmd),
    hideFlyout: () => electron_1.ipcRenderer.send("window:hide"),
    closeCurrentWindow: () => electron_1.ipcRenderer.send("window:close-current"),
    openSettingsWindow: () => electron_1.ipcRenderer.send("window:open-settings"),
    openAboutWindow: () => electron_1.ipcRenderer.send("window:open-about"),
    setSettings: (settings) => electron_1.ipcRenderer.invoke("settings:set", settings),
    onState: (cb) => {
        const fn = (_, payload) => cb(payload);
        electron_1.ipcRenderer.on("backend:state", fn);
        return () => electron_1.ipcRenderer.removeListener("backend:state", fn);
    },
    onPresets: (cb) => {
        const fn = (_, payload) => cb(payload);
        electron_1.ipcRenderer.on("backend:presets", fn);
        return () => electron_1.ipcRenderer.removeListener("backend:presets", fn);
    },
    onStatus: (cb) => {
        const fn = (_, payload) => cb(payload);
        electron_1.ipcRenderer.on("backend:status", fn);
        return () => electron_1.ipcRenderer.removeListener("backend:status", fn);
    },
    onError: (cb) => {
        const fn = (_, payload) => cb(payload);
        electron_1.ipcRenderer.on("backend:error", fn);
        return () => electron_1.ipcRenderer.removeListener("backend:error", fn);
    },
    onTheme: (cb) => {
        const fn = (_, payload) => cb(payload);
        electron_1.ipcRenderer.on("theme:update", fn);
        return () => electron_1.ipcRenderer.removeListener("theme:update", fn);
    },
    onSettings: (cb) => {
        const fn = (_, payload) => cb(payload);
        electron_1.ipcRenderer.on("settings:update", fn);
        return () => electron_1.ipcRenderer.removeListener("settings:update", fn);
    },
};
electron_1.contextBridge.exposeInMainWorld("arctisBridge", api);
