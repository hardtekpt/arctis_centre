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
exports.createFlyoutWindow = createFlyoutWindow;
exports.positionBottomRight = positionBottomRight;
exports.saveWindowBounds = saveWindowBounds;
const electron_1 = require("electron");
const path = __importStar(require("node:path"));
const MIN_W = 320;
const MAX_W = 4096;
const MIN_H = 260;
const MAX_H = 2160;
function createFlyoutWindow(settings) {
    const win = new electron_1.BrowserWindow({
        width: clamp(settings.flyoutWidth, MIN_W, MAX_W),
        height: clamp(settings.flyoutHeight, MIN_H, MAX_H),
        minWidth: MIN_W,
        maxWidth: MAX_W,
        minHeight: MIN_H,
        maxHeight: MAX_H,
        show: false,
        frame: false,
        transparent: true,
        backgroundColor: "#00000000",
        resizable: false,
        alwaysOnTop: true,
        skipTaskbar: true,
        hasShadow: true,
        webPreferences: {
            preload: path.join(__dirname, "preload.js"),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });
    win.setAlwaysOnTop(true, "pop-up-menu");
    win.setVisibleOnAllWorkspaces(false);
    return win;
}
function positionBottomRight(win) {
    const display = electron_1.screen.getPrimaryDisplay();
    const flyout = win.getBounds();
    const bounds = display.workArea;
    const margin = 8;
    const x = bounds.x + bounds.width - flyout.width - margin;
    const y = bounds.y + bounds.height - flyout.height - margin;
    win.setPosition(x, y, false);
}
function saveWindowBounds(win, settings) {
    const b = win.getBounds();
    return {
        ...settings,
        flyoutWidth: clamp(b.width, MIN_W, MAX_W),
        flyoutHeight: clamp(b.height, MIN_H, MAX_H),
    };
}
function clamp(value, low, high) {
    return Math.min(high, Math.max(low, value));
}
