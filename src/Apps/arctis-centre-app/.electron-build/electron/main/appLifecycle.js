"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.registerAppLifecycle = registerAppLifecycle;
const electron_1 = require("electron");
function registerAppLifecycle(deps) {
    electron_1.app.on("window-all-closed", () => { });
    electron_1.app.on("before-quit", () => {
        deps.onBeforeQuit();
        electron_1.globalShortcut.unregisterAll();
    });
}
