import { useEffect, useState } from "react";
import { CHANNELS, type ChannelKey, type UiSettings } from "@shared/types";

interface SettingsProps {
  settings: UiSettings;
  onUpdate: (partial: Partial<UiSettings>) => void;
}

export default function SettingsPage({ settings, onUpdate }: SettingsProps) {
  const [shortcutDraft, setShortcutDraft] = useState(settings.toggleShortcut);
  useEffect(() => setShortcutDraft(settings.toggleShortcut), [settings.toggleShortcut]);

  const toggleChannel = (channel: ChannelKey, enabled: boolean) => {
    const next = enabled
      ? Array.from(new Set([...settings.visibleChannels, channel]))
      : settings.visibleChannels.filter((value) => value !== channel);
    onUpdate({ visibleChannels: next });
  };

  return (
    <section className="card settings-page">
      <h3>Settings</h3>
      <label className="form-row">
        <span>Theme</span>
        <select value={settings.themeMode} onChange={(e) => onUpdate({ themeMode: e.currentTarget.value as UiSettings["themeMode"] })}>
          <option value="system">System</option>
          <option value="dark">Dark</option>
          <option value="light">Light</option>
        </select>
      </label>
      <label className="form-row">
        <span>Accent color</span>
        <div className="accent-row">
          <input type="color" value={settings.accentColor || "#6ab7ff"} onChange={(e) => onUpdate({ accentColor: e.currentTarget.value })} />
          <button className="button" onClick={() => onUpdate({ accentColor: "" })}>
            System
          </button>
        </div>
      </label>
      <label className="form-row">
        <span>Text size</span>
        <input
          type="range"
          min={80}
          max={140}
          value={settings.textScale}
          onChange={(e) => onUpdate({ textScale: Number(e.currentTarget.value) })}
        />
      </label>
      <label className="form-row">
        <span>Show battery %</span>
        <input
          type="checkbox"
          checked={settings.showBatteryPercent}
          onChange={(e) => onUpdate({ showBatteryPercent: e.currentTarget.checked })}
        />
      </label>
      <label className="form-row">
        <span>Toggle shortcut</span>
        <input
          className="text-input"
          value={shortcutDraft}
          onChange={(e) => setShortcutDraft(e.currentTarget.value)}
          onBlur={() => onUpdate({ toggleShortcut: shortcutDraft })}
          placeholder="CommandOrControl+Shift+A"
        />
      </label>
      <label className="form-row">
        <span>Close on blur</span>
        <input type="checkbox" checked={settings.closeOnBlur} onChange={(e) => onUpdate({ closeOnBlur: e.currentTarget.checked })} />
      </label>
      <div className="visible-channels">
        <div className="visible-title">Visible Sonar Channels</div>
        <div className="visible-grid">
          {CHANNELS.map((channel) => {
            const enabled = settings.visibleChannels.includes(channel);
            return (
              <label key={channel} className="visible-item">
                <input type="checkbox" checked={enabled} onChange={(e) => toggleChannel(channel, e.currentTarget.checked)} />
                <span>{channel}</span>
              </label>
            );
          })}
        </div>
      </div>
      <p className="hint">Settings are saved in %APPDATA% userData JSON.</p>
    </section>
  );
}
