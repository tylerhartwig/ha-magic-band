---
name: broadcast
description: Broadcast arbitrary BLE advertisements (Disney 0x0183 manufacturer data by default) from the attached ESP32-C6 without re-flashing, and run closed-loop probes that measure the Disney ferris wheel / MagicBand-style toy's reaction with the camera. Use to test Broadcaster-mode packets, explore the protocol, or verify a command lights the toy.
---

# Broadcast (ESP32 advertiser + closed-loop probe)

The ESP32-C6 on `/dev/cu.usbserial-*` (CP2102 UART port) runs MicroPython with `esp32/main.py`,
which advertises whatever it's told over serial. **No re-flashing is needed for new packets.**
Verified findings about the toy are in `docs/ferris_wheel_protocol.md`. Read that first and
append to it when you learn something new.

```bash
B=.claude/skills/broadcast/scripts/broadcast        # run from the repo root
$B ping                                             # {"reply": "ok pong"}
$B send E905000E0EF5B0 --seconds 2 --wait           # 83 01 prepended -> solid red ~22 s
$B send E905008E0EFDB0                              # off and hold
$B seq "E905002E0EE2B0:1.5" "E905002E0EF5B0:3"      # back-to-back steps on one connection
$B raw 0201060aff8301e905002e0ef5b0                 # full advertising payload
$B stop
```

Opening the serial port **resets the board** (about 1.2 s; the CLI waits for `ok ready`), and the reset
ends any ongoing advertisement. For multi-step sequences use `seq` or `probe.py`, which keep one
connection open.

## Closed-loop probe

```bash
export PROBE_OUT=<scratchpad>/probe
.venv/bin/python .claude/skills/broadcast/scripts/probe.py --name red "E905002E0EF5B0:3"
.venv/bin/python .claude/skills/broadcast/scripts/probe.py --batch trials.jsonl --series
#   trials.jsonl: {"name": "...", "steps": ["HEX:SECONDS", "wait:SECONDS", ...]} per line
.venv/bin/python .claude/skills/broadcast/scripts/contact_sheet.py sheet.jpg $PROBE_OUT/a $PROBE_OUT/b
.venv/bin/python .claude/skills/broadcast/scripts/contact_sheet.py t.jpg $PROBE_OUT/a --timeline 6:24:2
```

- `probe.py` takes `--pre` baseline frames, broadcasts while the camera keeps capturing, and prints
  one JSON line per trial: `steady_rgb` (median after `--settle` s), `steady_spread` (high means
  animated), `peak`, and `changed`. Results are also appended to `$PROBE_OUT/results.jsonl`.
- `--roi` defaults to the toy's hub at its current position (`0.32,0.44,0.31,0.53`, whole wheel since the 2026-11-20 reframe). Re-check the
  framing with a camera photo first; the laptop gets bumped.
- **Animations**: `scripts/anim.sh OUT NAME PAYLOAD [SECONDS]` broadcasts (use a hold timing such
  as `8F`) and saves 10 fps video stills. `scripts/zones.py --templates <probe dir with z5w-slot1..5>
  --dark <dir of an all-off probe> DIRS…` unmixes each frame into per-zone colours (bottom, LL+UR,
  L+R, UL+LR, top) and prints one letter per frame. Rebuild the templates if the camera or toy moves
  (probe `E909008E0F` + a single `BC` slot with the others `BD`, and an OFF frame).
- **Unattended script lab**: `scripts/script_lab.py --templates T --dark D --batch trials.jsonl --out DIR`
  (trials: `{"name", "hex"}`) logs an activity score (animated if >10) plus per-zone letters to
  `DIR/results.jsonl`, about 10.5 s per trial.
- `Read` one **contact sheet** rather than many frames: `--timeline` shows animations over time.
- The toy idles through blue/white colours by itself, so trust steady, saturated colours.
  Dark reads as about `[141,128,114]` (the wall).
- Broadcast for **≥1 s**. Shorter broadcasts land only about half the time.

## Custom animations
```bash
.venv/bin/python .claude/skills/broadcast/scripts/anim.py chase 15 19 02 11 --send 3   # red/green/blue/yellow chase
.venv/bin/python .claude/skills/broadcast/scripts/anim.py twinkle 15 1B --slow
```
Palette indices (hex 00-1F) are in `docs/ferris_wheel_protocol.md`. `script_lab.py` (`--reset HEX --preroll 3.5
--series`) runs unattended accept/reject and timeline batches.

## Re-installing the firmware

```bash
.venv/bin/esptool --port /dev/cu.usbserial-10 erase-flash
.venv/bin/esptool --port /dev/cu.usbserial-10 --baud 460800 write-flash 0x0 ESP32_GENERIC_C6-<ver>.bin
.venv/bin/mpremote connect /dev/cu.usbserial-10 fs cp .claude/skills/broadcast/esp32/main.py :main.py + reset
```
MicroPython builds: https://micropython.org/download/ESP32_GENERIC_C6/ (v1.29.0 used).
