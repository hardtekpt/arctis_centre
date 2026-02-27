import { Menu, Tray, nativeImage } from "electron";

interface TrayOptions {
  onToggle: () => void;
  onSettings: () => void;
  onAbout: () => void;
  onQuit: () => void;
}

export function createTray(options: TrayOptions): Tray {
  const icon = buildTrayIcon();
  const tray = new Tray(icon);
  tray.setToolTip("Arctis Centre");
  tray.on("click", options.onToggle);
  tray.on("double-click", options.onToggle);
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Open", click: options.onToggle },
      { label: "Settings", click: options.onSettings },
      { label: "About", click: options.onAbout },
      { type: "separator" },
      { label: "Quit", click: options.onQuit },
    ]),
  );
  return tray;
}

export function buildTrayIcon() {
  const svg = `
  <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
    <path d="M7 12h5l6-5v18l-6-5H7z" fill="#ffffff"/>
    <path d="M21 11c2 1.6 3 3.4 3 5s-1 3.4-3 5" fill="none" stroke="#ffffff" stroke-width="2.4" stroke-linecap="round"/>
    <path d="M24 8.5c2.8 2.2 4.2 4.8 4.2 7.5s-1.4 5.3-4.2 7.5" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round"/>
  </svg>
  `;
  return nativeImage
    .createFromDataURL(`data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`)
    .resize({ width: 16, height: 16 });
}
