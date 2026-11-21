---
name: ble
description: Talk to Disney MagicBand+ / Popcorn Buckets directly over Bluetooth LE from this Mac - scan for advertisements, dump GATT services, send the handshake and RGB color packets, write raw hex, and listen for notifications. Use when debugging the integration's BLE protocol against real hardware, and pair it with the camera skill to confirm the lights actually changed.
---

# BLE

`scripts/ble` runs `scripts/ble.py` (bleak) using the repo's `.venv`. If the venv is missing it is
created with `uv`. Every result is printed as one JSON object per line.

```bash
BLE=.claude/skills/ble/scripts/ble           # run from the repo root
$BLE scan                         # MagicBand candidates only (FEE8 service or Disney 0x01E5 mfr data)
$BLE scan --all --time 10         # everything nearby, strongest first
$BLE scan --name Magic            # filter by advertised name
$BLE inspect ADDR                 # connect, list services/characteristics, read readable values
$BLE color ADDR 255 0 0           # handshake FE0301 0000, then FE 03 04 05 01 R G B BRIGHT
$BLE color ADDR 0 0 255 --brightness 64 --no-handshake
$BLE write ADDR "fe 03 03 00 00"  # raw bytes to the write char (--char UUID for others)
$BLE listen ADDR --time 15        # print notifications from 2beea05b-...
```

The packets mirror `custom_components/ha_magic_band/light.py` and `const.py`. If those change, update
`ble.py` to match.

- On macOS `ADDR` is a CoreBluetooth UUID, not a MAC address, and it only works on this Mac. Get it
  from `scan`. HA on another host sees the real MAC.
- `color`, `write` and `listen` subscribe to the notify characteristic when it exists, so any
  response from the device shows up as `{"event":"notify","hex":...}` lines.
- Exit code 2 with `"error":"not_found"` means the device isn't advertising or is out of range.
  Real buckets often stop advertising once something else (HA, a phone) is connected to them.

## Hardware feedback loop (with the `camera` skill)

1. `$BLE scan`: find the bucket and note its address and advertisement data.
2. Camera: take a baseline `photo` and choose an `--roi` around the bucket.
3. `$BLE color ADDR R G B`: send a test color. Use saturated primaries (255,0,0 / 0,255,0 / 0,0,255).
4. Camera: take an `after` photo with the same ROI. Check that the dominant channel of `mean_rgb`
   matches the color you sent, and `Read` the image if it's unclear.
5. Change one thing at a time (handshake on/off, brightness, packet bytes) and repeat. Record what
   did and didn't light up.

## Limits on this machine

- A Mac can't scan or connect to **its own** advertisement. Running `simulators/magic_bucket_mac.py`
  here is only useful for testing HA or a phone against it, not this CLI. To test the CLI without
  hardware you need a second host or a phone running a peripheral app (e.g. nRF Connect).
- macOS's `CBPeripheralManager` can only advertise a local name and service UUIDs, not
  manufacturer data. So Broadcaster mode (Disney `0x01E5` payloads) can't be emitted from this Mac.
  That needs an ESPHome proxy or a Linux/ESP32 host.
- The first BLE use from a new terminal app triggers the macOS Bluetooth permission prompt
  (System Settings → Privacy & Security → Bluetooth).
