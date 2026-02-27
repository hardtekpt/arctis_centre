"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const ipcClient_1 = require("./ipcClient");
electron_1.contextBridge.exposeInMainWorld("arctisBridge", ipcClient_1.ipcClient);
