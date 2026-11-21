# EPCOT Mickey popcorn bucket: BLE control findings

Living log for the second toy, a popcorn bucket shaped like a Mickey head with the EPCOT
Spaceship Earth geodesic pattern. Same method as `docs/ferris_wheel_protocol.md` (ESP32-C6
broadcaster plus the MacBook camera). Every entry here was **observed** unless marked *unverified*.
Differences from the ferris wheel are called out with **Δ**.

## Setup
- Broadcaster: ESP32-C6 (`.claude/skills/broadcast`), payload `02 01 06 | len FF | 83 01 <bytes>`.
- Camera framing (2026-11-21, no diffuser, dark room): toy box in the frame is about
  `0.37,0.27,0.68,0.79` (x0,y0,x1,y1), i.e. ROI `0.37,0.27,0.31,0.52`.

## Identification
- 2026-11-21, toy on and idle (steady warm white/amber glow), `ble.py scan --all` for 20 s and then
  120 s: **no advertisement with company 0x0183 or 0x01E5, no FEE8 service, and no Disney/Mickey
  name**. 55 devices were seen, all identified as other household gear (Samsung, Govee, Apple, MyQ…).
  - Δ The ferris wheel sent a sporadic `0x0183` beacon (`F1 0F 03 …`) every 5–60 s. This toy sent
    none in 2 minutes of idle, so nothing was connectable either (no address to `inspect`).
  - *Open*: it may only beacon after it receives a command, or when picked up or moved.

## What the product is (public sources, 2026-11-21)
- "Spaceship Earth Mickey Balloon" popcorn bucket, released at EPCOT popcorn carts on 2025-06-04
  ($26, with GEO-82's opening). Press coverage (WDWNT, BlogMickey, AllEars, Laughing Place, WDW Info,
  Disney Food Blog) describes **six colours in sequence (red, light blue, dark blue, purple, blue,
  green), two modes (slow glow or blink), and a battery panel plus on/off switch on the bottom**.
- **No source mentions Bluetooth, MagicBand+, an app, or syncing with Luminous or other shows.** The only
  EPCOT MagicBand+ show tie-in found (2022, Spaceship Earth lighting and Harmonious) is for bands. So
  this looks like a stand-alone light-up toy, unlike the ferris wheel.

## Replay of ferris wheel packets (2026-11-21): **no response**
Camera on the whole toy, dark room, each packet advertised 3 s at 30 ms (`probe.py`, `--pre 4 --post 14`):

| Packet | Company | Result |
|---|---|---|
| `E9 05 00 8E 0E F5/F9/E2/FD B0` (red, green, blue, off, hold) | 0x0183 | no change |
| `E9 08 00 8E 0E D2 55 7E 00 00 B0` (custom RGB red) | 0x0183 | no change |
| `E1 00 E9 0C 00 8F 0F 5D 46 5B F0 05 32 37 48 B0` (Taste the Rainbow) | 0x0183 | no change |
| `CC 03 00 00 00` ping, then E9 red | 0x0183 | no change |
| `E9 05 00 01 0E F5 B0` (short timing) | 0x0183 | no change |
| E9 red, E9 off, E9 green, and `01 00…00` (const.py trigger) | 0x01E5 | no change (18 s video flat at `[130,51,37]` ±1) |

- The toy stayed a steady warm amber the whole time; even "off" did nothing. Per-trial differences were
  the same ~11-point auto-exposure drop after the baseline frames. Checked by eye on a contact sheet.
- Δ The ferris wheel answered every one of these within ~0.5 s.
- Δ Idle here is a **steady** warm amber for minutes, not the six-colour cycle the press describes.
  Probably a switch position; *unverified*.

## Status
No BLE presence (no advertisements) and no reaction to any known Disney broadcast. Most likely the
bucket has no radio. Next check: an FCC ID on the bottom label or battery panel (none = no radio) or
a look inside the battery compartment for an antenna/BLE SoC. Sweeps are on hold until something
shows it can receive.

## Log
- 2026-11-21: web research: no Bluetooth/MagicBand+ feature advertised. Replayed E9 single, RGB, rainbow
  and ping under 0x0183, plus E9/trigger under 0x01E5: no response at all.
- 2026-11-21: started. Scans found no Disney advertising at idle; framing photo taken.
