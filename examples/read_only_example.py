from __future__ import annotations

from arctis_nova_api import ArctisNovaProApi, PresetChannel, SonarChannel
from arctis_nova_api.errors import ArctisNovaError


def main() -> None:
    api = ArctisNovaProApi()

    print("== Read-only Arctis Nova Pro API example ==")

    # Sonar mode and volumes (read-only).
    try:
        streamer_mode = api.sonar.is_streamer_mode()
        print(f"Streamer mode: {streamer_mode}")

        volume_data = api.sonar.get_volume_data(streamer=streamer_mode)
        print(f"Volume payload keys: {list(volume_data.keys())}")

        for channel in (
            SonarChannel.MASTER,
            SonarChannel.GAME,
            SonarChannel.CHAT_RENDER,
            SonarChannel.MEDIA,
            SonarChannel.AUX,
            SonarChannel.CHAT_CAPTURE,
        ):
            try:
                vol = api.sonar.get_channel_volume(channel, streamer=streamer_mode)
                print(f"{channel.value}: {vol:.3f}")
            except ArctisNovaError as exc:
                print(f"{channel.value}: unavailable ({exc})")
    except ArctisNovaError as exc:
        print(f"Sonar read failed: {exc}")

    # Sonar presets (read-only).
    try:
        print("\nPreset channels:")
        for preset_channel in (
            PresetChannel.GAMING,
            PresetChannel.CHAT,
            PresetChannel.MEDIA,
            PresetChannel.MIC,
            PresetChannel.AUX,
            PresetChannel.MASTER,
        ):
            presets = api.sonar.list_presets(preset_channel)
            favorites = api.sonar.list_favorite_presets(preset_channel)
            selected = api.sonar.get_selected_preset(preset_channel)
            selected_name = selected.name if selected else "None"
            favorite_names = [preset.name for preset in favorites]
            print(
                f"{preset_channel.name}: {len(presets)} presets, selected={selected_name}, "
                f"favorites={favorite_names}"
            )
    except ArctisNovaError as exc:
        print(f"Preset read failed: {exc}")

    # Base station events (read-only).
    try:
        print("\nBase station:")
        api.base_station.connect()
        battery = api.base_station.get_battery_status(refresh_timeout_seconds=0.3)
        if battery:
            print(f"Headset battery: {battery.headset}")
            print(f"Charging station battery: {battery.charging}")
        else:
            print("Battery status: unavailable (no battery event received)")
        anc = api.base_station.get_anc_status(refresh_timeout_seconds=0.3)
        if anc:
            print(f"ANC mode: {anc.mode.value}")
        mic = api.base_station.get_mic_status(refresh_timeout_seconds=0.3)
        if mic is not None:
            print(f"MIC enabled: {mic.enabled}")
        sidetone = api.base_station.get_sidetone_status(refresh_timeout_seconds=0.3)
        if sidetone is not None:
            label = api.base_station.get_sidetone_label()
            print(f"Sidetone: {label} (level={sidetone.level})")
        events = api.base_station.get_pending_events()
        print(f"Pending events: {len(events)}")
        for event in events[:10]:
            print(f"- {event}")
    except ArctisNovaError as exc:
        print(f"Base station read failed: {exc}")
    finally:
        try:
            api.base_station.close()
        except ArctisNovaError:
            pass


if __name__ == "__main__":
    main()
