# Integration v2 design draft

Status: **implemented as disney_glow 2.0.1** (2026-11-21), installed from the Marketplace and verified on camera. Built on the verified findings in
`docs/ferris_wheel_protocol.md`. Items marked *unverified* need a hardware check (see §8).

## 1. What changed, and why v1 can't be patched

v1 assumed two things that the hardware disproved:

| v1 assumption | Reality (verified) |
|---|---|
| Toys are GATT peripherals (`FEE8`, Amazon Gadgets handshake) | The ferris wheel has **no GATT**. It is receive-only and listens for advertisements. |
| Broadcaster mode = company `0x01E5`, one "ping" payload | Company **`0x0183`**, with a rich command language (`E9 …`) |
| One RGB light per device address | Commands are **broadcast**, so every toy in range obeys. The toy's own beacon uses a **new random address every time**. |
| HA can send the packet | **HA has no API for advertising arbitrary manufacturer data.** v1's broadcaster only logged the packet. |

So v2 is a rewrite around three ideas:

1. **A transmitter is the hub device.** Something has to put the advertisement on air.
2. **Toys are receivers described by a profile** (zones, palette, effects). They aren't connections.
3. **State is assumed, not read.** The toy never reports back. HA tracks what it last told the
   toy and when timed effects expire.

## 2. Architecture

```
 HA entities (light, select, number, button, binary_sensor)
        │
        ▼
 ToyController (per toy profile)  ── builds intent → packet via protocol.py
        │
        ▼
 TransmitQueue (per transmitter)  ── min air time, coalescing, priorities
        │
        ▼
 Transmitter backend ──┬── SerialEsp32   (USB ESP32 on the HA host, existing line protocol)
                       ├── NetworkEsp32  (same line protocol over TCP/Wi-Fi; ESP sits near the toy)
                       └── BlueZ         (host adapter via D-Bus LEAdvertisingManager1; Linux only)

 HA bluetooth scanner ── passive match on manufacturer 0x0183, payload F1 0F 03 … → presence/RSSI
```

### 2.1 `protocol.py`: pure Python, no HA imports
The one place that knows bytes. It's unit-tested offline and also importable by the skill scripts,
so `anim.py` and the integration can't drift apart.

```python
Timing(seconds: float | None, fade: Fade = Fade.NONE)   # None = hold (bit 7)
  .encode() -> int        # picks n and the x2 bit; ~1.5 s units, max ~45 s timed
Palette                   # 32 entries: name, approximate sRGB, OFF=0x1D, RANDOM=0x1F
  .nearest(rgb) -> int
Zone (ALL, BOTTOM, LL_UR, L_R, UL_LR, TOP)

solid_palette(idx, timing, zone=ALL) -> bytes      # E9 05 00 T 0E <zone<<5|idx>
solid_rgb(r, g, b, timing) -> bytes                # E9 08 00 T 0E D2 55 r' g' b'   (6-bit)
zones(colours[1..5], timing) -> bytes              # E9 len 00 T 0F <n<<5|c1> A0|c2 …
chase(colours, timing, slow=False) -> bytes        # … 0F list 30 [7B]
twinkle(colours, timing) -> bytes                  # … 0F list 31
sparkle(burst, background, timing) -> bytes        # E9 0B 0B T 0F 40|c1 40|c2 48 A5 D1 45 32
crossfade(c1, c2, timing) -> bytes                 # E1 00 E9 11 00 T 0F … 58 F4 48 82 D1 46 02 08 D0 65 00
rainbow(timing) / show_white(timing) / off() / release()
frame(cmd_bytes) -> manufacturer_data              # 83 01 + cmd, length-checked (≤ 31-byte adv)
```

Every builder validates the E9 length byte. A wrong length got a lab sweep silently ignored once.

### 2.2 Transmitter backends

> **Decided 2026-11-21: ESPHome over Wi-Fi.** The ESP32-C6 runs `esphome/disney-tx.yaml`, which is a
> Bluetooth proxy plus the `disney_tx` external component. It exposes the native-API actions
> `advertise(data, duration_ms, interval_ms)` (manufacturer data incl. `8301`), `advertise_raw` and
> `stop_advertising`. Verified end to end: Mac → aioesphomeapi → `advertise` → ferris wheel held
> red/green/blue/off, with the camera checking each. The proxy's active scanning was running at the same time.
> The integration's transmitter is therefore an **ESPHome device chosen in the config flow**, and
> commands go out via the `esphome.disney_tx_advertise` HA service. No serial/TCP code in the
> integration. The table below is kept for history.

One interface: `async advertise(mfr_data: bytes, seconds: float)`, `async stop()`, `available`.

| Backend | Pros | Cons | Proposal |
|---|---|---|---|
| **SerialEsp32** | Firmware already exists and is proven. Testable on this Mac today. | ESP must be USB-attached to the HA host, so range is limited to where HA lives. Opening the port resets the board, so the backend has to keep it open. | **MVP** |
| **NetworkEsp32** | Same line protocol over TCP. Place the ESP next to the toy. Several ESPs can cover several rooms. | Needs the Wi-Fi part of the firmware (C6 has Wi-Fi) and zeroconf discovery. | **Phase 2** |
| **BlueZ** | No extra hardware on HA OS / Linux hosts with an adapter. | Can't be tested on macOS. The adapter is shared with HA's scanner. Non-connectable adverts at 30 ms may be clamped to 100 ms (*unverified*). | Phase 3 / optional |
| ESPHome | Most HA-native. | *Unverified* that ESPHome can change manufacturer data at runtime. Would likely need an external component. | Investigate only |

The ESP line protocol (`adv <hex> [ms] [interval]`, `raw`, `stop`, `ping`) stays as it is and becomes
a documented contract. Firmware additions: `ver`, Wi-Fi config, and a TCP listener on the same
parser.

### 2.3 TransmitQueue: the radio is the bottleneck
- One advert on air at a time per transmitter. Each command gets **≥ 1.2 s air time** (≥ 1 s was
  100% reliable; shorter was about 50%).
- **Coalescing:** a newer command for the same target replaces a *pending* one. Dragging the colour
  wheel sends only the latest colour, not 30 queued ones.
- A command already on air is never cut short before its minimum air time (otherwise it might
  never land).
- Priority: `off` and `release` jump the queue.
- After the HA restart, optionally re-assert the last held state (the toy may have idled out).

## 3. Device and entity model

**Device: Transmitter** (one per ESP/adapter)
- `binary_sensor.<tx>_connected` (diagnostic)
- `sensor.<tx>_last_packet` (diagnostic, hex; handy for debugging)

**Device: Toy** (one per configured toy; v2 ships a `ferris_wheel` profile plus a generic
`magicband_compatible` one with single colour only). Linked to a transmitter via `via_device`.

| Entity | Behaviour |
|---|---|
| `light.<toy>` | Main light. `ColorMode.RGB` + brightness (6-bit custom RGB, brightness scales the channels). `off` = held palette `1D`. **Effects**: Chase, Chase (slow), Twinkle, Sparkle, Crossfade, Rainbow, Random, Show White, *Idle* (release). Effects use the current colour plus the "secondary colour" select. `assumed_state = True`. |
| `light.<toy>_<zone>` ×5 (optional, disabled by default) | Bottom, LL+UR, L+R, UL+LR, top. Changes are merged into **one** 5-zone `0F` packet. Colours snap to the nearest palette entry (multi-zone only takes palette indices, *unless §8 shows RGB works there*). |
| `select.<toy>_secondary_colour` | Palette colour used as c2 for sparkle/crossfade/twinkle. |
| `select.<toy>_duration` | Hold (default), 5 s, 10 s, 20 s, 45 s. Applies to the next command. |
| `select.<toy>_fade_out` | None / short / medium / long (timing bits 5–4). |
| `button.<toy>_return_to_idle` | Sends a short command so the toy drops back to its own idle cycle. |
| `binary_sensor.<toy>_nearby` | Presence from the `F1 0F 03` beacon. The address rotates, so it means "a 0x0183 toy beacon was heard". Beacons come every 5–60 s, so use a ~3 min timeout. |
| `sensor.<toy>_rssi` | RSSI of the last beacon (moving average, from the old "future work" list). |

**Timed effects:** when a command has a finite duration, the controller schedules a state change
for expiry: `off` during the ~20 s dark gap, then "idle". The UI then matches the toy.

## 4. Services (the "full power" layer)

| Service | Fields | Use |
|---|---|---|
| `ha_magic_band.play_effect` | `effect`, `colors` (1–5, names/RGB/index), `duration`, `fade`, `slow` | Everything the light entity can't express, e.g. a 5-colour chase. |
| `ha_magic_band.set_zones` | `bottom`, `ll_ur`, `l_r`, `ul_lr`, `top` | One-shot multi-zone. |
| `ha_magic_band.play_sequence` | `steps: [{effect…, hold: s}]`, `loop` | Choreography from HA scripts, e.g. a doorbell flash then back to a held colour. Runs through the queue. |
| `ha_magic_band.send_raw` | `hex`, `seconds`, `company_id` (default 0x0183) | The escape hatch for protocol experiments from HA. |

Targets are toy entities. Everything goes out through the toy's transmitter.

## 5. Config flow

1. **Add transmitter**: pick a serial port (auto-listed; the flow runs `ping` to verify), or
   enter host:port (or zeroconf later), or a BlueZ adapter.
2. **Add toy**: pick a profile and a transmitter. Unique ID = `profile + transmitter`, because the
   address can't identify a toy.
3. **Bluetooth discovery**: manifest matcher `manufacturer_id: 387` (0x0183) with
   `manufacturer_data_start: [0xF1, 0x0F, 0x03]` opens a "Disney toy detected" flow that leads to
   step 2. One discovery flow total, not one per rotating address.

Dropped: the GATT/`FEE8` connected mode, `0x01E5`, manual address entry, "Scan All" and the
`DEBUG` error-level logging. Nothing real uses them. If a real MagicBand+ turns out to expose
`FEE8`, it comes back as its own profile. Config entry version → 2. Old entries get a repair
issue asking for a re-add (a migration would have nothing meaningful to map).

## 6. Code layout

```
custom_components/ha_magic_band/
  protocol.py        # bytes only, no HA (unit-tested)
  profiles.py        # ferris_wheel, magicband_compatible: zones, palette, effects
  transmitter/       # base.py, serial_esp32.py, network_esp32.py, bluez.py
  queue.py           # TransmitQueue
  controller.py      # ToyController: assumed state, expiry timers, re-assert
  __init__.py  config_flow.py  light.py  select.py  button.py  binary_sensor.py  sensor.py
  services.yaml  strings.json  translations/en.json
tests/               # pytest: protocol golden packets (from the verified table), queue timing
```

Golden tests: every packet in the protocol doc's "Quick reference" and "Verified commands" tables
becomes a test vector, so a builder can't regress without failing.

## 7. Phasing

| Phase | Scope | Done when |
|---|---|---|
| 0 | `protocol.py` + golden tests. Point `anim.py`/`probe.py` at it. | Tests pass and the builders reproduce every verified packet byte for byte. |
| 1 | SerialEsp32 + queue + main light (RGB, off, idle, effects) + config flow | From a dev HA instance (or a harness that drives the entity code), the camera sees each effect. |
| 2 | Zone lights, selects, services, sequences, presence/RSSI | Sequence service plays a 3-step choreography that the camera confirms. |
| 3 | Network ESP32 firmware + backend | Toy controlled with the ESP on Wi-Fi only. |
| 4 | BlueZ backend, HACS release 2.0.0 | Tested on a Linux HA host. |

## 8. Hardware questions to answer first (ESP + camera)

These change the entity design, so they go before Phase 1:

1. **Brightness curve:** sweep `solid_rgb` red at 6-bit levels 1…63. Is it perceptually linear, and
   what's the lowest visible level? This sets how HA brightness maps to the 6 bits.
2. **RGB inside zones/effects:** can a `D2 55 r g b` instruction replace palette entries in a `0F`
   list, or combine with a zone code? If yes, zone lights and effects get true RGB, not palette snapping.
3. **Palette calibration:** photograph all 32 indices next to a white reference to get sRGB values
   for `Palette.nearest`. The camera distorts colour (white reads blue), so correct against the reference.
4. **Minimum reliable air time** at 20 ms interval vs 30 ms. This sets how fast sequences can run.
5. **Back-to-back command rate:** how quickly can held colours change before frames are missed?
6. **Chase/twinkle speed:** anything beyond `7B` (≈3× slower)? A speed select could follow from it.
7. **`E1 xx` filter 00–07:** group addressing? This needs a second 0x0183 toy. Park it until one exists.

## 9. Decisions (2026-11-21)

- **Target toy:** the ferris wheel. The EPCOT Mickey bucket is out of scope (no radio found).
- **Rename:** approved. Proposed domain `disney_glow` ("Disney Glow Toys").
- **Transmitter:** Wi-Fi ESP32 running ESPHome as a Bluetooth proxy plus the `disney_tx`
  advertiser (see §2.2). That ESP also becomes HA's scanner for the toy's beacon.
