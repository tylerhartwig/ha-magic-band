# Ferris Wheel toy: BLE control findings

Living log of what was verified against the real toy (a Disney Mickey ferris wheel light-up toy)
by broadcasting from an ESP32-C6 (`.claude/skills/broadcast`) and watching it with the MacBook
camera (`.claude/skills/camera`). Every entry here was **observed**, unless marked *unverified*.

## Setup used
- Broadcaster: ESP32-C6, MicroPython, `esp32/main.py`. Non-connectable advertisement, 30 ms
  interval, payload `02 01 06 | len FF | 83 01 <bytes>`.
- Observer: `probe.py` takes camera frames of the hub (ROI `0.37,0.72,0.26,0.28`) before, during
  and after the broadcast.
- Packets below are written **after** the `83 01` company ID unless shown in full.

## Protocol grammar (as reverse-engineered from this toy)

```
advertisement   = 02 01 06 | <len> FF | 83 01 | command*          (company ID 0x0183)
command         = <opcode> <len> <payload[len]>                    (TLV stream, run in order; last wins)
  CC 03 xx xx xx                                                   ping: no visible effect on this toy
  E1|E2|E3 <filter>                                                prefix: filter 00-07 = accepted,
                                                                   >= 08 = rest of packet ignored
  E9 <len> <mode> <T> <type> <entries...> [B0 padding]             light command (only E9 does anything)
    mode    : ignored by this toy (any value works)
    T       : bit7 hold | bit6 x2 unit | bits5-4 fade-out | bits3-0 duration (~1.5 s/unit)
    type 0E : single colour   entries = <zone<<5 | palette>        (zone 0/5/7 = all, 1/6 = LL+UR,
                                                                    2 = L+R, 3 = UL+LR, 4 = top)
              custom RGB      entries = D2 55 <R<<1> <G<<1> <B<<1>  (D2 55 fixed)
    type 0F : multi-zone      entries = <count<<5 | c1> c2 .. c5   (count 1..5: see table)
              sparkle/flash   7 entries (c1 burst colour, c2 background, e3-e7 script)
              crossfade etc.  longer scripted bodies (see effects)
    type 13 : fixed pastel white/pink pattern, body ignored
```
- **Type byte values**: `0E` single, `0F` multi-zone/scripted, **`13` = fixed pastel "show white"**
  (all LEDs white with pink/purple/blue tints, steady for the whole hold, body ignored). Every other
  value tested (`00`–`0D`, `10`–`12`, `14`–`1F`, `20`, `2E`, `4E`, `8E`, `CE`, `EE`, `FE`) is ignored.
- Other opcodes `E0`–`EF` (except E9), `F0`, `F1`, `D9`, `C9`, `A9`, `69` with an `E9`-style body: ignored.
- `<len>` must not run past the end of the data (otherwise the command is dropped). Extra trailing
  bytes are fine, and `B0` is just padding (`E9 04 00 2E 0E F5` with no `B0` works).
- Two commands in one advertisement run in sequence, so the last colour wins.

## Quick reference (for the HA integration)

All packets go in a **non-connectable advertisement**, manufacturer data `83 01 …` (company 0x0183).
Advertise each command for **≥1 s** (30 ms interval). No connection, handshake or ping needed.

| Want | Manufacturer data |
|---|---|
| Solid palette colour `i` (0–31) | `83 01 E9 05 00 <T> 0E <E0\|i> B0` |
| Solid custom RGB (6-bit per channel) | `83 01 E9 08 00 <T> 0E D2 55 <r<<1> <g<<1> <b<<1> B0` |
| Turn off and stay off | `83 01 E9 05 00 8E 0E FD B0` |
| Back to idle animation | any command with a short T (e.g. `01`); after expiry: about 20 s dark, then idle |
| Per-zone colours (bottom, LL+UR, L+R, UL+LR, top) | `83 01 E9 09 00 <T> 0F <A0\|c1> <A0\|c2> … <A0\|c5> B0` (c1 prefix `20`/`40`/`60`/`80` = use 1/2/3/4 colours) |
| Bottom LED c1, rest c2 | `83 01 E9 06 00 <T> 0F <40\|c1> <40\|c2> B0` |
| Two-colour flash/alternate | `83 01 E9 0B 0B 0F 0F <40\|c1> <40\|c2> 48 A5 D1 45 32 B0` |
| Two-colour crossfade | `83 01 E1 00 E9 11 00 6F 0F <40\|c1> <40\|c2> 58 F4 48 82 D1 46 02 08 D0 65 00 B0` |
| Rainbow show | `83 01 E1 00 E9 0C 00 0F 0F 5D 46 5B F0 05 32 37 48 B0` |
| Random colour | `83 01 E9 05 00 <T> 0E FF B0` |

Timing byte `T`: bit7 = hold forever, bit6 = ×2 unit, bits5–4 = fade-out, bits3–0 = duration
(≈1.5 s per unit). E.g. `0E` ≈ 22 s, `8E` = hold.

## Key facts
- **Company ID is `0x0183`** (bytes `83 01` on air). `const.py` currently uses `0x01E5`, which is
  wrong for this toy.
- The toy is **receive-only for control** (no GATT, nothing to connect to). It does broadcast
  its own `0x0183` beacon sporadically, roughly every 5–60 s, **independent of pings** (`CC 03 00 00 00`,
  `CC 03 00 01 00`, `CC 03 13 20 00` tested over 7 rounds; replies weren't correlated with them).
  Every beacon uses a **new random address** and a new payload: `F1 0F 03` + 14 bytes that look
  encrypted or rolling (e.g. `f10f03a20520b699…`, `f10f03a3ffa13521…`, `f10f031d0188d3fd…`). So HA
  can't track it by address; match on manufacturer `0x0183` with a payload starting `f1 0f 03`.
- Idle behaviour: it slowly cycles blue / white / warm by itself. Commanded colours are recognisable
  because they're **steady** and saturated.
- Response latency: about 0.5 s from the start of advertising to the colour change.
- A commanded effect **persists after advertising stops, for as long as the timing byte says**, then
  the toy returns to its idle cycle. A new command replaces the current one immediately.

## Verified commands

| # | Packet (after 83 01) | Effect | Notes |
|---|---|---|---|
| 1 | `CC 03 00 00 00` (0.5 s) then `E9 05 00 2E 0E F5 B0` (4 s) | **Solid red** within about 0.6 s, steady `[190,89,76]` | Single colour, palette index 0x15 (`0xE0 \| 0x15`) |
| 2 | `E9 05 00 2E 0E F9 B0` (no ping) | **Solid green** `[85,173,135]` | **Ping is not required** |
| 3 | `E9 05 00 2E 0E E2 B0` (no ping) | **Solid blue** `[91,126,220]` | Overrides the previous colour directly |
| 4 | `CC 03 00 00 00` alone | No visible change | The ping doesn't reset or wake anything visible |

## Single colour: `E9 05 00 <timing> 0E <0xE0|idx> B0`

All 32 palette indices respond (sweep with timing `2E`, no ping, 2.5 s broadcast each; colour
names come from looking at the camera contact sheet):

| idx | byte | Colour on the toy | idx | byte | Colour on the toy |
|---|---|---|---|---|---|
| 00 | E0 | cyan / aqua | 10 | F0 | warm white (pale yellow) |
| 01 | E1 | light sky blue | 11 | F1 | yellow / amber |
| 02 | E2 | blue (azure) | 12 | F2 | lime / yellow-green |
| 03 | E3 | deep blue / indigo | 13 | F3 | orange |
| 04 | E4 | deep blue | 14 | F4 | red-orange |
| 05 | E5 | violet / lavender | 15 | F5 | **red** |
| 06 | E6 | pale lavender | 16 | F6 | cyan-blue |
| 07 | E7 | purple | 17 | F7 | cyan |
| 08 | E8 | purple-magenta | 18 | F8 | cyan |
| 09 | E9 | pink-lavender | 19 | F9 | **green** |
| 0A | EA | pink-violet | 1A | FA | lime green |
| 0B | EB | magenta-pink | 1B | FB | white (cool) |
| 0C | EC | magenta | 1C | FC | white |
| 0D | ED | magenta-pink | 1D | FD | **OFF (all LEDs dark)** |
| 0E | EE | crimson / pink-red | 1E | FE | "unique": bluish, slightly unsteady |
| 0F | EF | yellow-orange | 1F | FF | **random**: keeps changing colour |

### Colour byte high bits = **zone select** (re-tested with the full view, red, hold timing)

| byte | high bits | LEDs lit |
|---|---|---|
| `15` | `000` | **all** |
| `35` | `001` | lower-left + upper-right (5-colour slot 2) |
| `55` | `010` | left + right (slot 3) |
| `75` | `011` | upper-left + lower-right (slot 4), slight flicker |
| `95` | `100` | top (slot 5) |
| `B5` | `101` | **all** |
| `D5` | `110` | lower-left + upper-right (same as `001`) |
| `F5` | `111` | **all** (the standard `E0\|idx`) |

The bottom LED (slot 1) has no single-colour zone code; it only lights with "all" codes.
(An earlier, partial-view test read these as "ring only"; that was wrong because of the framing.)

### "Vibration" byte (last byte)
- `00 10 20 40 80 90 A0 C0 F0 B5 BF` all gave the same full red. **No visible effect**; the toy has
  no motor, and unlike reports for bands, the colour isn't gated by the `B` high nibble.

Contact sheet frames: `probe/pal-XX/` (scratchpad, not committed).

## LED zones (full-view framing, 2026-11-20)
The LEDs sit in a ring **behind the rays, around Mickey's head**. The five-colour packet addresses five
zones, arranged symmetrically (each test: one slot red or white, the rest `BD` = off, hold timing):

| Slot | LEDs lit |
|---|---|
| 1 (c1) | **bottom** (below the chin) |
| 2 (c2) | **lower-left + upper-right** (opposite pair) |
| 3 (c3) | **left + right** (opposite pair) |
| 4 (c4) | **upper-left + lower-right** (opposite pair) |
| 5 (c5) | **top** (between the ears) |

So there are about 8 LEDs: top, bottom, and three opposite pairs. Single-colour commands drive all of them.

## Multi-zone colour: `E9 09 00 <T> 0F c1 c2 c3 c4 c5 B0`
- Each `cN` low 5 bits = palette colour. **c1's high 3 bits = how many colours are used (layout)**;
  c2–c5 prefixes don't matter (A0 is conventional).
- Zone k (see LED zones) gets colour ck. Slots beyond the count are ignored.

| c1 high bits | Colours used | bottom | LL+UR | L+R | UL+LR | top |
|---|---|---|---|---|---|---|
| `00` | none | nothing lights | | | | |
| `20` | 1 | c1 | off | off | off | off |
| `40` | 2 | c1 | c2 | c2 | c2 | c2 |
| `60` | 3 | c1 | c2 | c3 | off | off |
| `80` | 4 | c1 | c2 | c3 | c4 | off |
| `A0` / `C0` / `E0` | 5 | c1 | c2 | c3 | c4 | c5 |

Verified by lighting one slot at a time (red, the rest `1D` off) for each count, and with all slots red.
- The dual packet (`E9 06`) follows the same rule with 2 colour slots: `20` → bottom only, `40` →
  bottom c1 + rest c2.
- Earlier "animated" impressions for `60`/`80` with all slots coloured were mostly camera
  overexposure from many bright LEDs. With isolation they're steady.

## Animated / multi-colour effects (timeline sheets, 0.25 s per frame, started from OFF)

| Effect | Packet (after 83 01) | What the toy does |
|---|---|---|
| Dual colour | `E9 06 00 22 0F 95 42 B0` or `E9 06 00 22 0F 95 82 B0` | **Steady two-tone split**: centre/top blue, outer ring/sides red-pink. Prefix `40` vs `80` looked the same. |
| Circle | `E9 0B 0B 0F 0F 5C 5D 48 A5 D1 45 32 B0` | **Flashing**: white/blue bursts alternating with fully dark, roughly 0.5–1 s steps |
| Crossfade | `E1 00 E9 11 00 6F 0F 55 42 58 F4 48 82 D1 46 02 08 D0 65 00 B0` | **Smooth fade** between red and blue through magenta/purple, about 2 s period |
| Taste the Rainbow (park show code) | `E1 00 E9 0C 00 0F 0F 5D 46 5B F0 05 32 37 48 B0` | **Fast multi-colour cycling** (pink, cyan, blue, red, …) |
| Five-colour "rainbow" | `E9 09 00 2E 0F AF B5 B9 A2 A7 B0` | **Steady multi-colour** (different colour per zone), slight shimmer |
| Random | `E9 05 00 2E 0E FF B0` | Picks a colour and **changes it** (purple, then cyan) |

- The `E1 00` prefix (crossfade, Taste the Rainbow) is accepted. Its purpose is still unknown.

## Timing byte (`E9 05 00 <T> 0E F5 B0`, red, 1.5 s broadcast, 1 frame/s)

| T | bits | Red lasted (from broadcast start) |
|---|---|---|
| `00` | n=0 | about 2–3 s |
| `01` | n=1 | about 1 s |
| `05` | n=5 | about 8 s |
| `0E` | n=14 | about 22 s |
| `2E` | n=14, bits5-4=10 | about 22 s (same length as `0E`) |
| `4E` | n=14, bit6 | about 43 s (bit 6 roughly **doubles** the unit) |
| `8E` | n=14, bit7 | **stays on**: still red at 46 s (bit 7 = hold/always-on) |

- Low nibble `n` ≈ 1.5 s per unit (bit 6 → about 3 s per unit). After it expires the toy goes back
  to its own idle colour cycle.
- Bit 7 holds the effect indefinitely (see "cancelling" below).
- **Bits 5–4 = fade-out length** at expiry (red, 0.25 s sampling): `0x` hard cut, `1x` ≈ 0.25 s,
  `2x` ≈ 0.5 s, `3x` ≈ 0.75 s dimming before it goes dark.
- **After expiry** the toy goes **dark for about 20 s, then resumes its idle animation**. A timed effect
  sent over a held colour does *not* restore the held colour (held blue → timed red → dark).

## Circle / flash packet anatomy: `E9 0B <mode> 0F 0F e1 e2 e3 e4 e5 e6 e7 B0`
Default body (from esp32_magicband): `5C 5D 48 A5 D1 45 32`.
- `<mode>` (`0B` by default): `00`–`0F` all produce the same flashing, so no visible role.
- **e1, e2 = the two alternating colours** (`0x40|idx`): `55 5D` → red/off flashing, `55 59` →
  red/green alternation, `5C 5C` → steady white. Default `5C 5D` = white/off flash.
- e3 `48` → `40`: the green/off flash became mostly dark (e3 probably sets the on/off duty or speed).
- **e4 `A5` → `A0`: changes into a multi-colour cycle** (white, cyan, red, orange, yellow, blue) instead
  of the two-colour flash.
- e5 `D1`→`D5`, e6 `45`→`4F`, e7 `32`→`3F`: no obvious difference at 0.25 s resolution.
- **Full-view re-test with 10 fps video** (`55 59 48 A5 D1 45 32`, i.e. red/green): it's a **scripted
  sparkle, not a two-colour flash**. The **background is c2 (green) on all LEDs**, and **c1 (red) bursts
  appear on zones in a sequence**: bottom → top → bottom → top → lower-left → (gap) → left+right …,
  each lasting about 0.2–0.5 s. The default white/off version looks like "white with occasional dark
  frames" because the background is off and the white bursts land between camera frames.
- The mode byte (`0B` vs `00`) makes no difference. The timing byte (`0F` vs `2E`) doesn't change the
  sparkle speed. c1 prefix `A0` (5-colour count) turns it into a multicolour sparkle.
- e3–e7 probably encode the sparkle script (zone + duration per step); not decoded.

- **e4 (`A5` default) selects the pattern style**, with e1 = green and e2 = off: `A5` green/off flash;
  `A0`, `85`, `C5`, `A8` cycle through many colours (with dark gaps for `A8`); `A2` mostly dark;
  `AF` fast green flicker.

## Crossfade recolouring
- `E1 00 E9 11 00 6F 0F <40|c1> <40|c2> 58 F4 48 82 D1 46 02 08 D0 65 00 B0`. Replacing c1/c2 with
  green/yellow (`59 51`) fades **green ↔ yellow/orange**. So c1/c2 are the two crossfade colours.

## Dual: `E9 06 00 <T> 0F c1 c2 B0` (re-tested with the full view)
**c1's high 3 bits select the layout; c2's prefix is ignored** (c2's low 5 bits = colour).
Red/green (`x15`, `x19`), each from held OFF:

| c1 high bits | Result |
|---|---|
| `20` (`35 …`) | **bottom LED = c1**; everything else off (c2 unused) |
| `40` (`55 …`) | **bottom LED = c1, all other LEDs = c2** (clean split). Same with c2 prefix 20/60/80/C0 |
| `60`, `80`, `A0`, `C0`, `E0` | colours ignored; a **built-in multicolour pattern** (white-ish with red bottom, purple top, green/cyan sides), slowly animated |
| `00` | nothing lights |

- The red/off and off/green isolation tests confirm c1 → bottom, c2 → rest for prefix `40`.
- The earlier "inconsistent" results came from the `80` prefix used by esp32_magicband, which gives
  the built-in pattern, not the requested colours.

## Scripted animations (type `0F` with more than 5 entries)
Analysed with `zones.py` (per-zone colour unmixing) on 10 fps video. Zones: bottom, LL+UR, L+R, UL+LR, top.

- **Sparkle** (`E9 0B 0B <T> 0F 55 59 48 A5 D1 45 32`, red/green): every zone stays at the c2 background
  (green). Short c1 (red) bursts of 0.1–0.3 s hit one zone at a time in an irregular sequence
  (L+R, bottom, bottom, LL+UR, L+R, bottom, …), so it looks random.
- **Crossfade** (`E1 00 E9 11 00 <T> 0F 55 42 58 F4 48 82 D1 46 02 08 D0 65 00`, red/blue): every zone
  cycles blue → purple → magenta → red → back, with **zones out of phase** (a rotating wave), period ≈ 2.7 s.
- **Taste the Rainbow** (`E1 00 E9 0C 00 <T> 0F 5D 46 5B F0 05 32 37 48`): a full hue cycle rotating
  around the zones, period ≈ 2.5 s.
- **Script structure (crossfade body truncation)**: entries after c1/c2:

  | Script entries kept | Result |
  |---|---|
  | 0–3 (`58`, `58 F4`, `58 F4 48`) | static 2-colour split (bottom c1, rest c2) |
  | 4 (`58 F4 48 82`) | **animation starts** (blue/magenta wave with dark gaps, ~1.5 s period) |
  | 5–6 (`… D1`, `… D1 46`) | static again (an incomplete group invalidates the script) |
  | 8 (`… D1 46 02 08`) | full crossfade wave |
  | 11 (full) | full crossfade wave |

  So the script is made of **4-byte steps**. Trailing extra bytes seem tolerated after at least two
  complete steps (8+3 works, 4+1 doesn't).
- **Single-byte mutations of the step `a b c d` = `58 F4 48 82`** (`E9 09 00 8F 0F 55 42 a b c d`):

  | Byte | Values tried | Result |
  |---|---|---|
  | a (`58`) | 18 38 78 98 5F | all **rejected** (falls back to the static split) |
  | b (`F4`) | F0 → same wave; 74 → bottom blue, rest dark with rare flashes; 04, FF → rejected | partly free |
  | c (`48`) | 08 40 4F 88 | all **rejected** |
  | d (`82`) | 02 → rejected; 80 → mostly dark with one brief burst; 8F / C2 → regular blink cycles (red bottom / blue rest with dark gaps, about 0.5–1 s) | **rhythm / timing** |

  Because a and c accept no change, the step is probably **validated** (a checksum, or a byte that
  depends on the others). Decoding it needs a much larger brute-force search: about 256 values per
  byte, roughly 10 s per trial with video.

## Instruction-stream grammar (from public captures, 2026-11-20)
Sources: the [EMCOT wiki](https://emcot.world/Disney_MagicBand+_Bluetooth_Codes) and
[Magic-bHAnds `docs/commands.md`](https://github.com/Legal-Copy7045/Magic-bHAnds), about 30 captured park
packets, none of them decoded. `scripts/tokenize_corpus.py` holds the corpus and the tokeniser.

**The E9 body after `mode T` is a stream of instructions, and the instruction byte's bits give its argument count.**
The "type byte" `0E`/`0F` is just the first instruction:

| Instruction byte | Arguments | Examples in the corpus |
|---|---|---|
| `0E` | 1 (zone/colour) | `0E FA`, `0E E7` (single colour, can appear mid-stream) |
| `0F` | c1>>5 colours | `0F 5D 46`, `0F BC BD BD BD BD`, `0F 30` (colour list, can be re-set mid-stream) |
| `40`–`5F`, `80`–`9F` | (op & 3) + 1 | `58 F4`, `48 82`, `59 19 02`, `5B F0 05 32 37`, `5C 0A`, `89 83 51` |
| `C0`–`DF` | (op & 3) + 2 | `D0 65 00`, `D1 46 02 08`, `D2 55 R G B` (= custom RGB), `D2 46 00 00 FC` |
| everything else | 0 | `30` chase, `31` twinkle, `7B` slow, `7D`, `7A`, `EC`, `0C`, `3D`, `60`–`7F` statics |

With this rule **29 of the 31 captures split exactly, ending on the trailing `Bx` byte**. The exceptions are `E9 07 …41 B0`
(an "unknown" capture) and one packet ending `…7B 5D B0`. Examples:
```
crossfade  0F 56 48 | 58 F4 | 48 82 | D1 46 02 08 | D0 65 00 | B0
circle     0F 5C 5D | 48 A5 | D1 45 32 B0
rainbow    0F 5D 46 | 5B F0 05 32 37 | 48 B0
lightning  0F 5D 46 | 5B F0 05 32 37 | 48 95
cycle      0F B1 B9 B5 B1 A2 | 30 | 7B | 7D | B0
spin       0F BC BD BD BD BD | 30 | D0 37 F4 | D2 46 00 00 FC | BB
show 0E    0F BD A0 A0 BD A0 | 59 07 00 | 48 AE | B5
show 13 2  D0 37 F0 | D2 3D 05 05 00 | 0E FA | 89 83 51 | 0E E7 | A0 | B0
```
**This explains the lab results**:
- "4-byte steps" are really two 2-byte instructions, `58 F4 | 48 82`.
- Byte c had to be `48`/`4C` because it's an instruction in the same family. Byte d is `48`'s argument (the rhythm),
  and byte b is `58`'s argument (accepted values follow the pattern `x111 0xxx`).
- `30`, `31`, `6x` and `7B` are zero-argument instructions, so `30 F4 48 82` = chase + `F4` + `48 82`.
- `48` alone, and `4A`/`4C`/`4E` alone, are ignored because their argument is missing.
- `D1 46 02 08` alone does nothing. It seems to modify an animation that an earlier instruction set up (`58`/`48`).

Recurring instructions to decode next: `48 xx` (in almost every animation; last argument 82/95/AE/8D/A5/B0/94/96/97/AB),
`58 xx`, `59 xx yy`, `5B F0 xx yy zz`, `D0 65 xx`, `D0 37 Fx`, `D1 46 xx yy`, `D2 46 …`, `89 83 51`.

### Diffused framing + context tests (2026-11-21)
- New framing with a paper-towel diffuser. Zone crop is `ZONES_BOX=0.28,0.25,0.66,0.86`; templates are in `scratchpad/tpl2`.
  `zones.py` now scales the estimates so a zone at its white-template brightness reads about 255. The camera sees the toy's
  white as blue and yellow as red, so decoding runs use red/green/blue/magenta/cyan colour lists.
- `lab_ctx` (c1 red, c2 green; 5-colour and 2-colour lists behave **identically**, so only c1/c2 matter here):

  | Body after the colour list | Result |
  |---|---|
  | `48 82` | static split (bottom c1, rest c2) |
  | `48 A5` | **sparkle**: c2 background, brief c1 bursts in random zones |
  | `48 A5 D1 45 32` | the same sparkle |
  | `58 F4 48 82` | **crossfade**: c1 and c2 alternate across the zones, period about 1 s |
  | `58 F4 48 82 D1 46 02 08 D0 65 00` | the same crossfade |
  | `48 82 D1 46 02 08` | static split |

  So `48`'s argument picks the effect (`A5` sparkle, `82` with `58` crossfade). `D1`/`D0` add little in these contexts.
- The first `48`/`58` sweeps had a wrong E9 length byte, so the argument fell outside the body. Side finding: **`48`
  with its argument missing → sparkle**. The lab now refuses mismatched lengths.
- The corrected sweeps were spoiled by the **toy's battery running flat**. The blue reset stopped showing, `48`
  00–7F and BA–FF read flat green, and the `58` sweep drifted smoothly regardless of value. Only `48` 80–B9
  shows varied, value-dependent behaviour; recheck a few values before trusting it. To rerun once charged:
  `48` 00–7F and BA–FF, then all of `58`. The lab now checks the toy is still responding (`--health`, on by default with
  `--reset --preroll`): it photographs the reset colour at the start and stops if three trials in a row don't show it.

## Animation script decoding (in progress)
Plan: (0) automated accept/reject lab → (1) offline corpus analysis → (2) checksum-vs-grammar tests →
(3) solve the checksum if there is one → (4) field semantics → (5) encoder + round-trip verification.

- **Lab** (`scripts/script_lab.py`): one serial connection, about 10.5 s/trial, per-zone unmixing. The activity
  score cleanly separates **accepted scripts (68–81)** from **rejected / static fallback (~1)**.
- **Known scripts split after c1 c2** (corpus):

  | Script | c1 c2 | Remaining bytes |
  |---|---|---|
  | Crossfade | `55 42` | `58 F4 48 82 · D1 46 02 08 · D0 65 00 B0` |
  | Sparkle/circle | `5C 5D` | `48 A5 D1 45 · 32 B0` |
  | Taste the Rainbow | `5D 46` | `5B F0 05 32 · 37 48 B0` |
  | DCL Rainbow (5 colours) | `A3 AF B5 A3 AF` | `30 7B 7D B7` |

  - Every known script ends in a `Bx` byte. Trailing groups of 2–3 bytes occur, so steps may be
    variable-length. Simple per-step XOR/sum checksums don't fit.

- **Phase 2 results** (base `E9 09 00 8F 0F 55 42 58 F4 48 82`, one byte changed at a time; ACC = animated):
  - **a** (`58`): only `58` accepted; `50 51 52 54 59 5A 5C 48 68` (and earlier `18 38 78 98 5F`) rejected.
  - **c** (`48`): `48`, `4C` accepted; `40 41 42 44 49 4F 50 58 08 88` rejected.
  - **b** (`F4`): `F0 F1 F2 F4 F5 F6 74` accepted; `F8 FF E4 D4 B4 94 54 34 14 04` rejected →
    looks like the pattern `x111 0xxx` (bits 6-4 = 111, bit 3 = 0).
  - **d** (`82`): `80 82 83 84 88 8F 90 A2 C2 E2 42 22 12` accepted; `02` and `81` rejected (81 may be a
    missed reception). d is almost free and changes the rhythm.
  - **No whole-script checksum**: b and d change freely; steps can be **reordered**
    (`D1460208 58F44882` OK) and **repeated** (`58F44882 58F44882` OK).
  - Single steps on their own: `48 A5 D1 45` ✓, `30 7B 7D B7` ✓, `58 F4 48 82` ✓; `D1 46 02 08` ✗,
    `D0 65 00 B0` ✗, `5B F0 05 32` ✗, `32 B0` ✗, `37 48 B0` ✗. But the full sparkle (`48A5D14532B0`)
    and rainbow (`5BF005323748B0`) bodies are accepted, so validity depends on the whole sequence,
    not on each 4-byte group separately.
  - Appending `B0`, `32 B0` or `37 48 B0` after a valid step keeps it valid.
- **Full 256-value sweeps of a and c** (`lab_ac`, 2.5 s of video starting about 1.7 s after reception, no reset between trials):
  - Animated (activity > 10): **a** = `13 30 31 58 7A`; **c** = `10 30 31 48 4A 4C 4D 4E 69 7A 7B`.
  - A third outcome turned up that the activity score had hidden: **a static state that is neither the fallback split nor
    animated**. So a and c are **not validated**. They are interpreted, and most values give the fallback because that
    step decodes to "nothing". Static non-fallback clusters:

    | Values | a (`XX F4 48 82`) | c (`58 F4 XX 82`) |
    |---|---|---|
    | `24 25 26 2C 60 68 72 7C` | all dark | all dark (same set) |
    | `53`–`57` | dim red bottom, blue rest | same (`51`–`57`) |
    | `62 64 66` | bottom only: cyan / red / green | all zones cyan-green / red / green-white |
    | `6A 6C 6E` | everything but bottom: green / red / green-white | LL+UR only: cyan / red / green |
    | odd `61`–`6F` | same as the even value, plus c2 blue on the other zones | same idea |
    | `76` | bottom red only | bottom red only |

    In `0x6X`, bits 2–1 pick a colour (01 cyan, 10 red, 11 green), bit 3 switches the zone group, and bit 0 keeps the
    c2 background. So each step byte looks like **bit fields** (zone, colour, keep-background), not an opaque value.
  - **Timelines with a reset** (`lab_tl1`, 58 trials: hold green first, then record from 3.5 s before the broadcast).
    Corrections to the sweep:
    - **Almost everything is accepted.** Only `a=14` and `c=62` left the green on screen, so those packets were ignored.
      Every other value replaced the green.
    - The non-animated results are **steady states** for the whole 5 s, not a frozen mid-animation frame.
    - Animated: a `30 31 58 7A` (and `13` briefly); c `30 48` (`7A` slow). The rest are static frames, for example
      a `64`/`76` = bottom red only, a `6C` = all but bottom red, a `60 68 7C 24` = all dark,
      a `10` = bottom blue / L+R purple / UL+LR red, c `13` = L+R cyan / UL+LR red.
    - So the step bytes describe **which zones get which colour**, plus colours that are not c1 or c2
      (cyan, green, white), and only some combinations animate.
  - **Colour-source tests** (`lab_tl2`: base `55 42 a F4 48 82` with a = `64`, `6C`, `62`, one field changed at a time):
    - The step colour **doesn't depend on c1 or c2**. Changing c1 to `59`/`4F` or c2 to `59` leaves `64` red and `62` cyan.
      So the colour is encoded in the step bytes.
    - `64` alone (`55 42 64`), `64 F4` or `64 F4 48` → **all zones red**. With the full `64 F4 48 82` → **bottom only**.
      The bottom-only form needs b ∈ {F4, F9, FF}, c ∈ {48, 4C} and d ∈ {82, 8F}. Otherwise it reverts to all red.
      d=`8F` makes it blink.
    - `6C` alone or `6C F4` → LL+UR red. `6C F4 48 82` → all but bottom red. With b=`04`/`E4`, c=`08`/`00` or d=`02`/`00`,
      the result is LL+UR red.
    - `62` alone, or `62` with a changed b/c/d → **ignored** (the green reset stays). Only `62 F4 48 82` → bottom cyan.
    - Reading: the bytes after the first step byte **narrow the zone mask** when they form a valid group. Validity
      depends on the combination of bytes, not on each byte separately.
  - **Single-byte script sweep** (`lab_single`: `E9 06 00 8F 0F 55 42 XX` for all 256 XX, green reset each time):

    | Result | XX |
    |---|---|
    | plain 2-colour split (the byte does nothing) | 201 values, including all of `80`–`F6` |
    | **ignored** (the green reset stays) | `14 48 4A 4C 4E 62` (these need parameters, e.g. `48` = sparkle) |
    | all dark | `24 26 2C 60 68 72 7C` |
    | static zone/colour patterns | `0F 10 13 25 29 2D 53–57 61 63–67 69–6F 74 76 77 79`, and `F7 F8 F9 FB FD FE FF` (small tint change) |
    | **self-contained animations** | **`30` (chase), `31` (twinkle), `7A` (bottom blink)** |

  - **Animation opcodes `30` / `31` use the colour list** (`lab_ops`). The animation cycles through **whatever c1…c5
    are**, so they are directly usable for custom animations:
    - `30` = **chase**: the colours rotate around the zones (5 colours `A3 AF B5 A3 AF` → every colour visits every zone).
      Red/blue, green/yellow and 3-colour lists all work.
    - `31` = **twinkle**: an irregular, random-looking pattern over the same colours.
    - `7A` and `13` = static, colour-list-dependent patterns (not useful animations).
  - **Following bytes are more instructions, not parameters** (`lab_speed`, chase `30` + byte, 5 colours, autocorrelation period):
    - `30` alone, or followed by `00 10 20 40 70 7F 80 FF 3B 5B 73` → period **≈ 1.2 s**.
    - `30 7B` (and `30 7B 7D B7`, the DCL rainbow) → period **≈ 3.7 s**, so **`7B` slows the chase about 3×**.
    - `30 60` → the animation mostly stops (`60` is a "dark" op on its own).
  - **Round-trip verified** (`lab_rt`): `anim.py chase 15 19 02 11` → `E908008F0F95B9A2B130`. Red, green, blue and
    yellow rotate around the wheel. `--slow` → `…307B`, about 3× slower. `twinkle 15 1B` → red/white twinkle.
    `chase 19` → a single green dot running around the ring.
  - **Usable now (encoder: `scripts/anim.py`)**: `E9 <len> 00 <T> 0F <count<<5|c1> c2 … cN 30 [7B]` = chase over N
    palette colours (count 1–5), and `… 31` = twinkle.

## Cancelling / overriding / turning off
- **Persistent OFF**: `E9 05 00 8E 0E FD B0` (hold bit + palette 0x1D) kept the toy dark for 40+ s.
  This is the "light off" for HA. To return to the idle animation, send any short command
  (e.g. timing `01`).
- A ping (`CC 03 00 00 00`) does **not** cancel a held (`8E`) colour.
- Any new colour command replaces it right away. A short one (`E9 05 00 01 0E E2 B0`, about 1 s)
  then expires and the toy **goes back to its idle cycle** (briefly dark first, then blue/white
  cycling). So "return to idle" = send something with a short timing value.

## Custom RGB: `E9 08 00 0E D2 55 R G B B0` (6-bit per channel, value<<1)
- Works: `7E 00 00` red, `00 7E 00` green, `00 00 7E` blue, `7E 20 00` orange, `7E 7E 7E` white,
  `08 00 00` dim red. So **arbitrary RGB is possible** (6 bits per channel).
- Bit 7 of a channel byte (`FE 00 00`, the "flash" bit) left the toy **dark**.
- **`D2 55` are fixed constants**: changing either (`00`, `FF`, `52 59`, `D2 59`, `C2 55`) gets the
  packet **ignored**. The one exception, `52 55`, gave a dim red rather than the requested orange.
  Always send `D2 55`.

## Prefixes and the fifth byte
- `E1 xx` / `E2 xx` / `E3 00` in front of a command: **xx = 00–07 accepted, 08–FF (tested 08 09 0C 0F 10
  18 20 40 7F 80 C0 F0 FE FF) makes the toy ignore the packet**. Probably a group/device-class filter
  (park show packets use `E1 00`).
- **Byte after the length ("mode")**: with single colour, every value tested (`00`–`0F`, `10`, `20`,
  `30`, `40`, `55`, `80`, `A0`, `C0`, `FF`) gave identical steady red. The toy ignores it (probably a
  show/group filter for other devices).
- Fifth byte (after the timing byte) is a **type**, not an LED mask. With the single-colour layout,
  `0E` = single colour. `00`–`0D` and `FF` are **ignored**. `0F` = multi-zone type: sending it with a
  single-colour body produced a multi-colour display (blue centre, pink ring), i.e. the body was
  parsed as zone colours. The 5-colour and dual packets use `0F`.

## Reliability
- The toy **scans with a duty cycle**: 0.1–0.5 s broadcasts land only about 50% of the time, with or
  without silence before them. **≥1 s broadcasts (30 ms advertising interval) were 100% reliable**
  across about 60 trials. Integration: advertise each command for at least 1–1.5 s.
- **No duplicate suppression**: the identical packet is accepted again after another command, and
  after the previous effect expired.

## Open questions
- Byte meanings inside the 4-byte animation script steps (colour/zone/duration/transition?).
- The toy beacon's 14-byte body (looks encrypted/rolling).

## Log
- 2026-11-21: transport moved to ESPHome on Wi-Fi (`esphome/disney-tx.yaml`, Bluetooth proxy + `disney_tx`
  raw advertiser). `advertise` action → held red/green/blue/off all verified on camera with active proxy scanning on.
- 2026-11-20: script opcodes found: 30 = chase, 31 = twinkle over c1..c5; 7B slows; anim.py encoder verified on camera
  (RGBY chase, red/white twinkle, 1-colour running dot). Single-byte sweep + a/c sweeps with reset documented.
- 2026-11-20: 4-byte step mutation: a/c rejected (validated?), b partly, d = rhythm.
- 2026-11-20: zones.py unmixing; scripted animations characterised; script = 4-byte steps.
- 2026-11-20: type byte: only 0E, 0F, 13 valid; 13 = steady pastel pattern.
- 2026-11-20: framing = TLV stream; B0 optional; only E9 lights; E1/E2 filter byte 00-07 accepted, 08+ ignored.
- 2026-11-20: mode byte ignored for single colour; "circle" = c1 sparkle sequence over c2 background.
- 2026-11-20: multi-zone decoded: c1 high bits = colour count; zone k = ck; 2-colour = bottom/rest.
- 2026-11-20: dual decoded: c1 prefix 40 → bottom=c1/rest=c2; 20 → bottom only; others → built-in pattern.
- 2026-11-20: single colour high bits = zone select (all / LL+UR / L+R / UL+LR / top).
- 2026-11-20: reframed (whole toy visible). 5-colour slot → LED zone map: bottom, LL+UR, L+R, UL+LR, top.
- 2026-11-20: toy beacon is spontaneous, rotating address/payload; D2 55 are fixed constants.
- 2026-11-20: circle body = colour list; e1/e2 = alternating colours; e4 changes the pattern style.
- 2026-11-20: fade bits decoded; expiry → ~20 s dark → idle; held state not restored.
- 2026-11-20: fifth byte 0E = single, 0F = multi-zone, others ignored. Persistent off via 8E + FD.
- 2026-11-20: 6-bit RGB works; E1/E2 prefixes OK; ≥1 s broadcast needed; no dedup.
- 2026-11-20: timing byte decoded: low nibble ≈ 1.5 s units, bit6 ×2, bit7 hold; expiry → idle.
- 2026-11-20: dual, circle, crossfade, Taste the Rainbow, 5-colour, random all work.
- 2026-11-20: full 32-entry palette sweep. Every index works; 0x1D = off, 0x1F = random.
- 2026-11-20: ping not required; ping alone is a no-op; colours persist after the broadcast ends.
- 2026-11-20: first response. Solid red via `E9 05` single colour (palette 0x15).
