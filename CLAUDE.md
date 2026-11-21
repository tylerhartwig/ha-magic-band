# Disney Glow Toys — Home Assistant Integration

Custom HA integration (domain `disney_glow`, installed through HA's Marketplace from GitHub) that
drives Disney 0x0183 light toys (the Mickey ferris wheel) by BLE advertisements. HA calls the
`esphome.disney_tx_advertise` action on an ESP32-C6 running `esphome/disney-tx.yaml`.
Code lives in `custom_components/disney_glow/`. Design: `docs/integration_v2_design.md`.

## Current state
- Version **2.0.1** on `main` (replaces the v1 GATT/`ha_magic_band` integration, now deleted).
- Bump `version` in `manifest.json` with every user-visible change. Commit messages use
  `feat:` / `fix:` / `debug:` / `chore:` prefixes.

## Layout
- `protocol.py`: all packet bytes, no HA imports. `tests/test_protocol.py` holds golden packets
  copied from `docs/ferris_wheel_protocol.md`. Any new builder needs a camera-verified golden.
- `transmitter.py`: calls the ESPHome action; one command on air at a time, latest pending wins,
  `MIN_AIR_S` between commands.
- `light.py` (RGB, effects, entity services `play_effect`/`set_zones`/`send_raw`; assumed state, timed
  commands expire), `select.py` (secondary colour/duration/fade), `button.py` (return to idle),
  `binary_sensor.py` + `sensor.py` (beacon presence/RSSI via HA's bluetooth callbacks).
- Tests: `.venv-ha/bin/python -m pytest` (Python 3.13 venv with
  `pytest-homeassistant-custom-component` plus the bluetooth integration's requirements).

## Gotchas
- `esphome` is an `after_dependency`, not a dependency (a hard dependency drags in the
  assist_pipeline/ffmpeg chain and breaks tests).
- Don't `match` on imported constants (bare names capture); use a dict.
- HA access: `HA_URL`/`HA_TOKEN` in the gitignored `.env`. The Marketplace's websocket API mirrors the old
  HACS one under `marketplace/*` (e.g. `marketplace/repositories/list`).

## Hardware feedback loop
- **`ble` skill** (`.claude/skills/ble/`): scan, inspect, and send handshake/color/raw packets from
  this Mac's Bluetooth via bleak in `.venv` (Python 3.12, created with `uv`).
- **`camera` skill** (`.claude/skills/camera/`): photograph the bucket/band and get mean RGB over a
  region of interest, so before/after can be compared numerically as well as by eye.
- **ESP32-C6 transmitter** (`esphome/disney-tx.yaml`): ESPHome on Wi-Fi (`disney-tx.local`) acting as a HA Bluetooth
  proxy plus the `disney_tx` component, whose API action `advertise(data, duration_ms, interval_ms)` puts
  any Disney packet on air. Secrets (Wi-Fi, API key) live in the gitignored `esphome/secrets.yaml`. Compile
  before `esphome upload` (upload alone reflashes the last build). Logs go to UART0 (the CP2102 port).
- **`broadcast` skill** (`.claude/skills/broadcast/`): `probe.py` for broadcast→camera trials. Its serial
  scripts target the old MicroPython firmware and need porting to the ESPHome API (aioesphomeapi).
- **Verified protocol for the ferris wheel toy: `docs/ferris_wheel_protocol.md`.** Key point: it's
  controlled by Broadcaster-mode advertisements under company ID **0x0183** (`const.py`'s `0x01E5` is
  wrong), with `E9 05 …` single-colour / `E9 08 …` RGB packets. There's no GATT to connect to.
- A Mac can't see its own BLE advertisements, so the macOS simulator can't stand in for hardware
  in this loop. Broadcaster (manufacturer-data) payloads can't be advertised from macOS either.

## Secrets & hygiene
- HA URLs and long-lived access tokens must never be committed (they were purged from history once).
  Keep them in `.env` or `.claude/settings.local.json`, both gitignored.
- The old Gemini `ha-dev-toolkit` skill (HA logs/states/services) lived in the gitignored `.gemini/`
  and is not present on this machine. Recreate it under `.claude/skills/` if it's needed.

## Future work
1. RSSI smoothing (moving average).
2. Battery level via GATT.
3. Verify the device's identification response during the handshake.
