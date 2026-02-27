"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.registerIpcMainHandlers = registerIpcMainHandlers;
const electron_1 = require("electron");
const fs = __importStar(require("node:fs"));
const constants_1 = require("../../../shared/constants");
function registerIpcMainHandlers(deps) {
    electron_1.ipcMain.handle(constants_1.IPC_CHANNELS.invoke.appGetInitial, () => deps.getInitialPayload());
    electron_1.ipcMain.on(constants_1.IPC_CHANNELS.send.backendCommand, (_evt, cmd) => deps.backend.send(cmd));
    electron_1.ipcMain.on(constants_1.IPC_CHANNELS.send.windowHide, () => deps.hideFlyout());
    electron_1.ipcMain.on(constants_1.IPC_CHANNELS.send.windowOpenSettings, () => {
        void deps.showSettingsWindow();
    });
    electron_1.ipcMain.on(constants_1.IPC_CHANNELS.send.windowOpenAbout, () => {
        void deps.showAboutWindow();
    });
    electron_1.ipcMain.on(constants_1.IPC_CHANNELS.send.windowCloseCurrent, (evt) => {
        const win = electron_1.BrowserWindow.fromWebContents(evt.sender);
        if (!win) {
            return;
        }
        if (win === deps.mainWindowRef()) {
            deps.hideFlyout();
            return;
        }
        win.hide();
    });
    electron_1.ipcMain.handle(constants_1.IPC_CHANNELS.invoke.settingsSet, (_evt, partial) => {
        const next = deps.persistSettingsPartial({ ...deps.getSettings(), ...partial });
        deps.registerToggleShortcut(next.toggleShortcut);
        for (const win of deps.allWindows()) {
            win.webContents.send(constants_1.IPC_CHANNELS.event.settingsUpdate, next);
        }
        return next;
    });
    electron_1.ipcMain.handle(constants_1.IPC_CHANNELS.invoke.appOpenGG, async () => {
        for (const exe of deps.openGGCandidates) {
            if (fs.existsSync(exe)) {
                const result = await electron_1.shell.openPath(exe);
                return { ok: result === "", detail: result || exe };
            }
        }
        const uriResult = await electron_1.shell.openExternal("steelseriesgg://", { activate: true });
        return { ok: uriResult, detail: "steelseriesgg://" };
    });
    electron_1.ipcMain.handle(constants_1.IPC_CHANNELS.invoke.mixerGetData, () => deps.getMixerData());
    electron_1.ipcMain.handle(constants_1.IPC_CHANNELS.invoke.mixerSetOutput, (_evt, outputId) => deps.setMixerOutput(outputId));
    electron_1.ipcMain.handle(constants_1.IPC_CHANNELS.invoke.mixerSetAppVolume, (_evt, payload) => deps.setMixerAppVolume(payload));
    electron_1.ipcMain.handle(constants_1.IPC_CHANNELS.invoke.mixerSetAppMute, (_evt, payload) => deps.setMixerAppMute(payload));
}
