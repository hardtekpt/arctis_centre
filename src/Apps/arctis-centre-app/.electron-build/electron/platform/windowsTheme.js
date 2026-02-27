"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getWindowsAccentColor = getWindowsAccentColor;
exports.getThemePayload = getThemePayload;
const node_child_process_1 = require("node:child_process");
const electron_1 = require("electron");
const DEFAULT_ACCENT = "#6ab7ff";
async function getWindowsAccentColor() {
    if (process.platform !== "win32") {
        return DEFAULT_ACCENT;
    }
    return new Promise((resolve) => {
        (0, node_child_process_1.execFile)("reg", ["query", "HKCU\\Software\\Microsoft\\Windows\\DWM", "/v", "ColorizationColor"], { windowsHide: true }, (err, stdout) => {
            if (err || !stdout) {
                resolve(DEFAULT_ACCENT);
                return;
            }
            const match = stdout.match(/0x([0-9A-Fa-f]{8})/);
            if (!match) {
                resolve(DEFAULT_ACCENT);
                return;
            }
            const rrggbb = match[1].slice(2);
            resolve(`#${rrggbb}`);
        });
    });
}
async function getThemePayload() {
    return {
        isDark: electron_1.nativeTheme.shouldUseDarkColors,
        accent: await getWindowsAccentColor(),
    };
}
