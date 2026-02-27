from __future__ import annotations

from arctis_nova_api import (
    AncMode,
    ArctisNovaProApi,
    ExperimentalCommandProfile,
    OledFrame,
    OledLine,
    PresetChannel,
    SonarChannel,
    StreamerSlider,
    UnsupportedFeatureError,
    UsbInput,
)


def main() -> None:
    # Fill these with packets discovered using src/APIs/arctis_nova_api/tools/hid_sniffer.py if you want active queries.
    profile = ExperimentalCommandProfile(
        battery_query_command=None,
        sidetone_get_command=None,
        sidetone_set_commands=None,
        sidetone_event_command_id=None,
    )
    api = ArctisNovaProApi(command_profile=profile)

    # 1) Sonar presets: list and select preset per channel (via Sonar DB + local Sonar server).
    print("== Sonar presets ==")
    for channel in (PresetChannel.GAMING, PresetChannel.CHAT, PresetChannel.MEDIA):
        presets = api.sonar.list_presets(channel)
        print(f"{channel.name}: {[p.name for p in presets[:5]]} ... ({len(presets)} total)")
        selected = api.sonar.get_selected_preset(channel)
        print(f"Current selected preset: {selected.name if selected else 'None'}")

    gaming_presets = api.sonar.list_presets(PresetChannel.GAMING)
    if gaming_presets:
        chosen = gaming_presets[0]
        api.sonar.select_preset(chosen.preset_id)
        print(f"Switched gaming preset to: {chosen.name}")

    # 2) Sonar channel volume controls.
    print("\n== Sonar channel volume ==")
    volumes = api.sonar.get_volume_data()
    print("Current volume payload keys:", list(volumes.keys()))
    api.sonar.set_channel_volume(SonarChannel.GAME, 0.65)
    api.sonar.set_channel_mute(SonarChannel.CHAT_RENDER, muted=False)
    print("Set GAME to 65% and unmuted CHAT_RENDER")

    # Streamer mode example.
    api.sonar.set_streamer_mode(True)
    api.sonar.set_channel_volume(SonarChannel.MASTER, 0.50, streamer_slider=StreamerSlider.STREAMING, streamer=True)
    api.sonar.set_streamer_mode(False)

    # 3) OLED text and behavior using official GameSense screen handlers.
    print("\n== OLED screen through GameSense ==")
    game = "ARCTIS_DEMO"
    event = "OLED_STATUS"
    api.gamesense.register_game(game, game_display_name="Arctis API Demo", developer="Local Script")
    api.gamesense.register_event(game, event, value_optional=True)

    frames = [
        OledFrame(
            lines=[
                OledLine(text="Now Playing", bold=True, context_frame_key="line1"),
                OledLine(text="", context_frame_key="line2"),
                OledLine(text="", context_frame_key="line3"),
            ],
            icon_id=23,  # music icon
            length_millis=1800,
            repeats=3,
        )
    ]
    api.gamesense.bind_screen_event(game, event, frames=frames, icon_id=23, value_optional=True)
    api.gamesense.send_event(
        game,
        event,
        value=1,
        frame={"line1": "Now Playing", "line2": "Demo Artist", "line3": "Track 01"},
    )
    print("Updated OLED via GameSense screen handler")

    # 4) Base station hardware controls and events.
    print("\n== Base station USB controls ==")
    api.base_station.connect()
    battery = api.base_station.get_battery_status(refresh_timeout_seconds=0.3)
    if battery:
        print(f"Headset battery: {battery.headset}")
        print(f"Charging station battery: {battery.charging}")
    api.base_station.set_brightness(4)
    events = api.base_station.get_pending_events()
    print(f"Received {len(events)} pending base-station events")

    try:
        sidetone = api.base_station.request_sidetone_status(timeout_seconds=0.3)
        print("Sidetone status:", sidetone.level if sidetone else "unavailable")
    except UnsupportedFeatureError as exc:
        print(f"Sidetone query command not configured: {exc}")

    # 5) Additional controls (ANC / USB input): requires experimental command profile.
    try:
        api.base_station.set_anc_mode(AncMode.ANC)
        anc_raw = api.base_station.get_anc_status_raw()
        print("ANC status raw bytes:", anc_raw.hex())
        api.base_station.set_usb_input(UsbInput.USB2)
        print("Switched to USB2 input")
    except UnsupportedFeatureError as exc:
        print(f"ANC/USB input commands are firmware-dependent and not configured: {exc}")

    api.base_station.return_to_steelseries_ui()
    api.base_station.close()


if __name__ == "__main__":
    main()
