"""Constants for Disney Glow Toys."""

DOMAIN = "disney_glow"

CONF_TRANSMITTER = "transmitter"  # ESPHome node name running the disney_tx component

# Each command is advertised this long (>= 1 s was 100% reliable; shorter landed ~50%)
AIR_TIME_MS = 1500
ADV_INTERVAL_MS = 30
# Minimum gap before the next command replaces the one on air
MIN_AIR_S = 1.2
# Give up on an advertise call that doesn't return (e.g. ESPHome reconnecting)
CALL_TIMEOUT_S = 5


# The toy drops even a held command after a while (it was only verified to ~46 s), so held
# commands are re-sent this often
HOLD_REFRESH_S = 30

# The toy beacons every 5-60 s from a new random address each time
PRESENCE_TIMEOUT_S = 180

SIGNAL_BEACON = f"{DOMAIN}_beacon_{{}}"
SIGNAL_SETTINGS = f"{DOMAIN}_settings_{{}}"
SIGNAL_COLORS = f"{DOMAIN}_colors_{{}}"  # colour slots changed
SIGNAL_LIGHT = f"{DOMAIN}_light_{{}}"  # main light state written

EFFECT_IDLE = "Idle"
EFFECT_STATIC = "Static"
EFFECT_SPIN = "Spin"
EFFECT_CHASE = "Chase"
EFFECT_TWINKLE = "Twinkle"
EFFECT_SPARKLE = "Sparkle"
EFFECT_CROSSFADE = "Crossfade"
EFFECT_RAINBOW = "Rainbow"
EFFECT_RANDOM = "Random"
EFFECT_SHOW_WHITE = "Show white"
EFFECTS = [
    EFFECT_STATIC,
    EFFECT_SPIN,
    EFFECT_CHASE,
    EFFECT_TWINKLE,
    EFFECT_SPARKLE,
    EFFECT_CROSSFADE,
    EFFECT_RAINBOW,
    EFFECT_RANDOM,
    EFFECT_SHOW_WHITE,
    EFFECT_IDLE,
]

# Effects drawn from the colour slots (or a service's colour list)
COLOR_EFFECTS = {
    EFFECT_STATIC,
    EFFECT_SPIN,
    EFFECT_CHASE,
    EFFECT_TWINKLE,
    EFFECT_SPARKLE,
    EFFECT_CROSSFADE,
}

# Colour slots map to the four positions clockwise from the top: top+bottom, LL+UR, L+R, UL+LR
COLOR_SLOTS = 4
DEFAULT_COLORS = [0x15, 0x0F, 0x02, 0x19]  # red, yellow-orange, azure, green

# Speed select -> (Spin seconds per step, Chase uses the toy's slow modifier). Spin is stepped by
# the integration and can't go faster than MIN_AIR_S; the toy's own chase has only two speeds
# (about 1.2 s and 3.7 s a lap). No speed control is known for the other effects.
SPEEDS: dict[str, tuple[float, bool]] = {
    "Fast": (1.2, False),
    "Medium": (2.0, False),
    "Slow": (3.0, True),
    "Very slow": (5.0, True),
}
SPEED_EFFECTS = {EFFECT_SPIN, EFFECT_CHASE}

# select options -> seconds (None = hold until replaced)
DURATIONS: dict[str, float | None] = {
    "Hold": None,
    "5 s": 4.5,
    "10 s": 10.5,
    "20 s": 21.0,
    "45 s": 45.0,
}
FADES = ["None", "Short", "Medium", "Long"]
