"""Golden tests: every expected packet is copied from docs/ferris_wheel_protocol.md (verified on camera)."""
import importlib.util
import pathlib
import sys

import pytest

# Load protocol.py on its own so these tests don't need Home Assistant
_path = pathlib.Path(__file__).parents[1] / "custom_components/disney_glow/protocol.py"
_spec = importlib.util.spec_from_file_location("disney_glow_protocol", _path)
p = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = p
_spec.loader.exec_module(p)


def h(s: str) -> bytes:
    return bytes.fromhex(s.replace(" ", ""))


@pytest.mark.parametrize(
    ("packet", "expected"),
    [
        (lambda: p.solid(0x15, 0x2E), "E9 05 00 2E 0E F5 B0"),  # red
        (lambda: p.solid(0x19, 0x2E), "E9 05 00 2E 0E F9 B0"),  # green
        (lambda: p.solid(0x02, 0x2E), "E9 05 00 2E 0E E2 B0"),  # blue
        (lambda: p.solid(0x15, 0x8E, p.Zone.TOP), "E9 05 00 8E 0E 95 B0"),
        (lambda: p.off(), "E9 05 00 8E 0E FD B0"),
        (lambda: p.release(), "E9 05 00 01 0E FD B0"),
        (lambda: p.rgb(0x3F, 0, 0, 0x0E), "E9 08 00 0E D2 55 7E 00 00 B0"),  # red, timed
        (lambda: p.rgb(0x3F, 0, 0, 0x8E), "E9 08 00 8E D2 55 7E 00 00 B0"),  # red, held
        (lambda: p.rgb(0x3F, 0x10, 0, 0x8E), "E9 08 00 8E D2 55 7E 20 00 B0"),  # orange
        (lambda: p.zones([0x0F, 0x15, 0x19, 0x02, 0x07], 0x2E), "E9 09 00 2E 0F AF B5 B9 A2 A7 B0"),
        (lambda: p.chase([0x15, 0x19, 0x02, 0x11], 0x8F), "E9 08 00 8F 0F 95 B9 A2 B1 30"),
        (lambda: p.chase([0x15, 0x19, 0x02, 0x11], 0x8F, slow=True), "E9 09 00 8F 0F 95 B9 A2 B1 30 7B"),
        (lambda: p.twinkle([0x15, 0x1B], 0x8F), "E9 06 00 8F 0F 55 BB 31"),
        (lambda: p.sparkle(0x15, 0x19, 0x0F), "E9 0B 0B 0F 0F 55 59 48 A5 D1 45 32 B0"),
        (
            lambda: p.crossfade(0x15, 0x02, 0x6F),
            "E1 00 E9 11 00 6F 0F 55 42 58 F4 48 82 D1 46 02 08 D0 65 00 B0",
        ),
        (lambda: p.rainbow(0x0F), "E1 00 E9 0C 00 0F 0F 5D 46 5B F0 05 32 37 48 B0"),
        (lambda: p.random_color(0x2E), "E9 05 00 2E 0E FF B0"),
    ],
)
def test_golden(packet, expected):
    assert packet() == h(expected)


def test_spin_frames():
    # Each frame verified on camera (2026-11-21): the lit pair, rest off, opposite LEDs matching
    assert p.spin_frames([0x15], 0x8E) == [
        h("E9 09 00 8E 0F B5 BD BD BD B5 B0"),  # top + bottom
        h("E9 09 00 8E 0F BD B5 BD BD BD B0"),  # LL + UR
        h("E9 09 00 8E 0F BD BD B5 BD BD B0"),  # L + R
        h("E9 09 00 8E 0F BD BD BD B5 BD B0"),  # UL + LR
    ]


def test_spin_frames_patterns():
    # c1 bar over a c2 background, starting at top+bottom
    assert p.spin_frames([0x15, 0x02], 0x8E)[1] == p.zones([0x02, 0x15, 0x02, 0x02, 0x02], 0x8E)
    # four colours rotate one position per frame; top and bottom always match
    frames = p.spin_frames([1, 2, 3, 4], 0x8E)
    assert frames[0] == p.zones([1, 2, 3, 4, 1], 0x8E)
    assert frames[1] == p.zones([4, 1, 2, 3, 4], 0x8E)


def test_symmetric():
    assert p.symmetric([0x15]) == [0x15] * 5
    assert p.symmetric([1, 2]) == [1, 2, 1, 2, 1]
    assert p.symmetric([1, 2, 3]) == [1, 2, 3, 1, 1]
    assert p.symmetric([1, 2, 3, 4]) == [1, 2, 3, 4, 1]
    with pytest.raises(ValueError):
        p.symmetric([1, 2, 3, 4, 5])


def test_timing():
    assert p.timing(None) == 0x8E
    assert p.timing(21, p.Fade.MEDIUM) == 0x2E  # ~22 s, 0.5 s fade
    assert p.timing(1) == 0x01
    assert p.timing(0.2) == 0x01  # never 0 (that's a 2-3 s blip)
    assert p.timing(45) == 0x4F  # x2 unit
    assert p.timing_seconds(0x0E) == 21.0
    assert p.timing_seconds(0x4E) == 42.0
    assert p.timing_seconds(0x8E) is None


def test_manufacturer_data_and_limits():
    assert p.manufacturer_data(p.off()) == h("83 01 E9 05 00 8E 0E FD B0")
    # The longest builder still fits in one advertisement
    p.manufacturer_data(p.crossfade(0, 1, 0x8E))
    with pytest.raises(ValueError):
        p.manufacturer_data(bytes(25))
    with pytest.raises(ValueError):
        p.chase([], 0x8E)
    with pytest.raises(ValueError):
        p.rgb(64, 0, 0, 0x8E)


def test_colors():
    assert p.nearest_color((255, 0, 0)) == 0x15
    assert p.nearest_color((40, 0, 0)) == 0x15  # dim red is still red
    assert p.nearest_color((0, 255, 0)) == 0x19
    assert p.nearest_color((0, 0, 255)) == 0x04
    assert p.nearest_color((255, 255, 255)) == 0x1C
    assert p.rgb_from_8bit((255, 128, 0)) == (63, 32, 0)
    assert p.rgb_from_8bit((255, 0, 0), 1) == (1, 0, 0)  # lowest brightness stays lit
    assert p.rgb_from_8bit((255, 0, 0), 0) == (0, 0, 0)
    assert p.is_beacon(h("f1 0f 03 a2 05 20 b6 99"))
