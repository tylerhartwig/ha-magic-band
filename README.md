# Disney Glow Toys for Home Assistant

Control Disney light-up toys that listen for park-show Bluetooth broadcasts (company ID `0x0183`),
such as the Mickey ferris wheel. The toys have no Bluetooth connection to open. They only react to
advertisements, so an ESP32 running ESPHome broadcasts the commands for Home Assistant.

## Features
- **Light**: any RGB colour (6 bits per channel) with brightness, plus off (held dark).
- **Effects**: Spin (opposite LEDs, driven by the integration about once a second), Chase, Chase (slow), Twinkle, Sparkle, Crossfade, Rainbow, Random, Show white, and
  Idle (hand control back to the toy's own animation).
- **Settings**: secondary effect colour, duration (hold, or stop by itself after 5–45 s) and fade-out.
- **Services**: `disney_glow.play_effect` (1–5 palette colours), `disney_glow.set_zones` (a colour
  per LED zone) and `disney_glow.send_raw` (protocol experiments).
- **Presence**: "Nearby" and beacon signal strength from the toy's own beacon, heard through any
  Bluetooth adapter or proxy.

The toy never reports back, so the light shows the state Home Assistant last sent (assumed state).

## Requirements
1. **An ESP32 transmitter.** Flash `esphome/disney-tx.yaml` (Bluetooth proxy plus the `disney_tx`
   component in `esphome/components/`) and add it to Home Assistant's ESPHome integration. It adds
   the `esphome.<node>_advertise` action this integration uses. Put Wi-Fi and API secrets in
   `esphome/secrets.yaml`.
2. Home Assistant 2025.1 or newer.

## Installation
1. In **Settings → Marketplace** (or HACS on older versions), add this repository as a custom
   integration repository and download **Disney Glow Toys**.
2. Restart Home Assistant.
3. **Settings → Devices & services → Add integration → Disney Glow Toys** and pick the ESPHome
   transmitter. The integration is also offered automatically when the toy's beacon is heard.

## Protocol
Reverse-engineered and verified on hardware: see `docs/ferris_wheel_protocol.md`. The packet
builders live in `custom_components/disney_glow/protocol.py`, which has no Home Assistant
dependencies. Golden tests in `tests/test_protocol.py` hold every verified packet.

```bash
uv venv --python 3.13 .venv-ha && uv pip install --python .venv-ha/bin/python pytest-homeassistant-custom-component
.venv-ha/bin/python -m pytest
```
