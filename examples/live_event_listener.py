from __future__ import annotations

import time

from arctis_nova_api import AncStatus, ArctisNovaProApi, BatteryStatus, HeadsetConnectionStatus, MicStatus, SidetoneStatus, VolumeKnobEvent


def main() -> None:
    api = ArctisNovaProApi()
    api.base_station.connect()
    print("Listening for base-station events. Press Ctrl+C to stop.")

    try:
        while True:
            events = api.base_station.get_pending_events()
            for event in events:
                print(_format_event(event))
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        api.base_station.close()


def _format_event(event: object) -> str:
    if isinstance(event, VolumeKnobEvent):
        return f"[volume] headset_volume={event.volume}"
    if isinstance(event, AncStatus):
        return f"[anc] mode={event.mode.value}"
    if isinstance(event, MicStatus):
        return f"[mic] muted={not event.enabled}"
    if isinstance(event, SidetoneStatus):
        return f"[sidetone] level={event.level}"
    if isinstance(event, BatteryStatus):
        return f"[battery] headset={event.headset} base_station={event.charging}"
    if isinstance(event, HeadsetConnectionStatus):
        return (
            f"[connection] wireless={event.wireless} bluetooth={event.bluetooth} "
            f"bluetooth_on={event.bluetooth_on}"
        )
    return f"[event] {event}"


if __name__ == "__main__":
    main()
