"""Disney 0x0183 light-toy packets (pure Python, no Home Assistant imports).

Everything here was verified against the ferris wheel toy; see docs/ferris_wheel_protocol.md.
Builders return the command bytes that follow the company ID; `manufacturer_data()` adds it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

COMPANY_ID = 0x0183
COMPANY_ID_BYTES = bytes([0x83, 0x01])  # little-endian on air
BEACON_PREFIX = bytes([0xF1, 0x0F, 0x03])  # the toy's own (rotating) beacon
MAX_ADV_PAYLOAD = 31
# 02 01 06 (flags) + <len> FF (AD header) + company ID
_ADV_OVERHEAD = 3 + 2 + 2

PAD = 0xB0
UNIT_SECONDS = 1.5  # one timing unit; bit 6 doubles it


class Fade(IntEnum):
    """Fade-out at expiry (timing bits 5-4)."""

    NONE = 0
    SHORT = 1  # ~0.25 s
    MEDIUM = 2  # ~0.5 s
    LONG = 3  # ~0.75 s


class Zone(IntEnum):
    """Single-colour zone select (colour byte high 3 bits)."""

    ALL = 7
    LL_UR = 1
    L_R = 2
    UL_LR = 3
    TOP = 4


def timing(seconds: float | None = None, fade: Fade = Fade.NONE) -> int:
    """Encode the timing byte. None = hold until replaced (bit 7)."""
    if seconds is None:
        return 0x80 | fade << 4 | 0x0E
    units = round(seconds / UNIT_SECONDS)
    if units <= 15:
        return fade << 4 | max(units, 1)
    return 0x40 | fade << 4 | min(round(seconds / (2 * UNIT_SECONDS)), 15)


def timing_seconds(t: int) -> float | None:
    """Decode a timing byte to seconds (None = hold)."""
    if t & 0x80:
        return None
    return (t & 0x0F) * UNIT_SECONDS * (2 if t & 0x40 else 1)


@dataclass(frozen=True)
class PaletteColor:
    index: int
    name: str
    rgb: tuple[int, int, int]


# Names come from the camera sweep; RGB values are approximations for nearest-colour matching.
PALETTE: tuple[PaletteColor, ...] = tuple(
    PaletteColor(i, name, rgb)
    for i, (name, rgb) in enumerate(
        [
            ("aqua", (0, 255, 230)),
            ("light_sky_blue", (120, 200, 255)),
            ("azure", (0, 120, 255)),
            ("indigo", (60, 0, 200)),
            ("deep_blue", (0, 0, 255)),
            ("violet", (160, 100, 255)),
            ("pale_lavender", (200, 170, 255)),
            ("purple", (128, 0, 200)),
            ("purple_magenta", (170, 0, 200)),
            ("pink_lavender", (230, 150, 255)),
            ("pink_violet", (220, 80, 230)),
            ("magenta_pink", (255, 60, 180)),
            ("magenta", (255, 0, 255)),
            ("hot_pink", (255, 40, 150)),
            ("crimson", (220, 20, 60)),
            ("yellow_orange", (255, 180, 0)),
            ("warm_white", (255, 220, 150)),
            ("amber", (255, 190, 0)),
            ("lime", (180, 255, 0)),
            ("orange", (255, 128, 0)),
            ("red_orange", (255, 69, 0)),
            ("red", (255, 0, 0)),
            ("cyan_blue", (0, 180, 255)),
            ("cyan", (0, 230, 255)),
            ("cyan_2", (0, 255, 255)),
            ("green", (0, 255, 0)),
            ("lime_green", (100, 255, 50)),
            ("cool_white", (220, 235, 255)),
            ("white", (255, 255, 255)),
            ("off", (0, 0, 0)),
            ("unique", (120, 160, 255)),
            ("random", (128, 128, 128)),
        ]
    )
)
OFF = 0x1D
RANDOM = 0x1F
# Entries that are real, steady colours (usable for matching and pickers)
SOLID_COLORS: tuple[PaletteColor, ...] = tuple(c for c in PALETTE if c.index < OFF and c.name != "cyan_2")
COLOR_BY_NAME = {c.name: c for c in PALETTE}


def nearest_color(rgb: tuple[int, int, int]) -> int:
    """Palette index closest to `rgb`, compared on hue/chroma so brightness doesn't dominate."""
    peak = max(rgb) or 1
    r, g, b = (v * 255 / peak for v in rgb)
    best = min(
        SOLID_COLORS,
        key=lambda c: (c.rgb[0] - r) ** 2 + (c.rgb[1] - g) ** 2 + (c.rgb[2] - b) ** 2,
    )
    return best.index


def _e9(body: list[int], prefix: bytes = b"", length: int | None = None) -> bytes:
    """E9 <len> <body>. `length` overrides the length byte (it may exclude trailing padding)."""
    n = len(body) if length is None else length
    if n > len(body):
        raise ValueError("E9 length runs past the data")
    return prefix + bytes([0xE9, n, *body])


def _check_color(index: int) -> int:
    if not 0 <= index < 32:
        raise ValueError(f"palette index {index} out of range 0-31")
    return index


def solid(index: int, t: int, zone: Zone = Zone.ALL) -> bytes:
    """One palette colour on a zone: E9 05 00 T 0E <zone<<5|idx> B0."""
    return _e9([0x00, t, 0x0E, zone << 5 | _check_color(index), PAD])


def off(hold: bool = True) -> bytes:
    """All LEDs dark; with hold they stay dark."""
    return solid(OFF, timing(None) if hold else 0x01)


def release() -> bytes:
    """Short command so the toy expires (~20 s dark) and returns to its own idle cycle."""
    return solid(OFF, 0x01)


def rgb(r: int, g: int, b: int, t: int) -> bytes:
    """Custom colour, 6 bits per channel (0-63): E9 08 00 T 0E D2 55 r<<1 g<<1 b<<1 B0."""
    for v in (r, g, b):
        if not 0 <= v <= 63:
            raise ValueError("RGB channels are 6-bit (0-63)")
    # Verified form: the length byte excludes the trailing B0.
    return _e9([0x00, t, 0x0E, 0xD2, 0x55, r << 1, g << 1, b << 1, PAD], length=8)


def rgb_from_8bit(color: tuple[int, int, int], brightness: int = 255) -> tuple[int, int, int]:
    """Scale an 8-bit colour by HA brightness (0-255) down to the toy's 6-bit channels."""
    scaled = [round(v * brightness / 255 * 63 / 255) for v in color]
    if brightness > 0 and max(color) > 0 and max(scaled) == 0:
        # Keep the dominant channel lit at the lowest level instead of going dark
        scaled[color.index(max(color))] = 1
    return scaled[0], scaled[1], scaled[2]


def _color_list(colors: list[int]) -> list[int]:
    """Multi-zone colour list: first byte carries the count in its high 3 bits."""
    if not 1 <= len(colors) <= 5:
        raise ValueError("1-5 colours")
    first, *rest = (_check_color(c) for c in colors)
    return [len(colors) << 5 | first, *(0xA0 | c for c in rest)]


def zones(colors: list[int], t: int) -> bytes:
    """Per-zone colours (bottom, LL+UR, L+R, UL+LR, top): E9 len 00 T 0F <list> B0."""
    return _e9([0x00, t, 0x0F, *_color_list(colors), PAD])


def chase(colors: list[int], t: int, slow: bool = False) -> bytes:
    """Colours rotate around the zones (op 30); 7B slows it about 3x."""
    return _e9([0x00, t, 0x0F, *_color_list(colors), 0x30, *([0x7B] if slow else [])])


def twinkle(colors: list[int], t: int) -> bytes:
    """Random-looking twinkle over the colours (op 31)."""
    return _e9([0x00, t, 0x0F, *_color_list(colors), 0x31])


def sparkle(burst: int, background: int, t: int) -> bytes:
    """`background` on every zone with short `burst` flashes hopping between zones."""
    return _e9(
        [0x0B, t, 0x0F, 0x40 | _check_color(burst), 0x40 | _check_color(background),
         0x48, 0xA5, 0xD1, 0x45, 0x32, PAD]
    )


def crossfade(c1: int, c2: int, t: int) -> bytes:
    """Smooth wave between two colours, zones out of phase (~2.7 s period)."""
    return _e9(
        [0x00, t, 0x0F, 0x40 | _check_color(c1), 0x40 | _check_color(c2),
         0x58, 0xF4, 0x48, 0x82, 0xD1, 0x46, 0x02, 0x08, 0xD0, 0x65, 0x00, PAD],
        prefix=bytes([0xE1, 0x00]),
    )


def rainbow(t: int) -> bytes:
    """'Taste the Rainbow' park show: full hue cycle rotating around the zones."""
    return _e9(
        [0x00, t, 0x0F, 0x5D, 0x46, 0x5B, 0xF0, 0x05, 0x32, 0x37, 0x48, PAD],
        prefix=bytes([0xE1, 0x00]),
    )


def random_color(t: int) -> bytes:
    """The toy picks colours itself and keeps changing them."""
    return solid(RANDOM, t)


def show_white(t: int) -> bytes:
    """Fixed pastel 'show white' pattern (type 13, body ignored)."""
    return _e9([0x00, t, 0x13, PAD])


def manufacturer_data(command: bytes) -> bytes:
    """Prefix the company ID and check the whole advertisement fits in 31 bytes."""
    if len(command) + _ADV_OVERHEAD > MAX_ADV_PAYLOAD:
        raise ValueError(f"command is {len(command)} bytes; max {MAX_ADV_PAYLOAD - _ADV_OVERHEAD}")
    return COMPANY_ID_BYTES + command


def is_beacon(data: bytes) -> bool:
    """True for the toy's own advertisement body (manufacturer data after the company ID)."""
    return data.startswith(BEACON_PREFIX)
