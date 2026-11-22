"""The toy's light (solid RGB, effects over the colour slots, off, idle) and the colour slots."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity

from . import GlowConfigEntry, protocol
from .const import (
    COLOR_EFFECTS,
    COLOR_SLOTS,
    EFFECT_CHASE,
    EFFECT_CHASE_SLOW,
    EFFECT_CROSSFADE,
    EFFECT_IDLE,
    EFFECT_RAINBOW,
    EFFECT_RANDOM,
    EFFECT_SHOW_WHITE,
    EFFECT_SPARKLE,
    EFFECT_SPIN,
    EFFECT_STATIC,
    EFFECT_TWINKLE,
    EFFECTS,
    SIGNAL_COLORS,
    SIGNAL_LIGHT,
    SPIN_STEP_S,
)
from .entity import GlowEntity

_LOGGER = logging.getLogger(__name__)

COLOR_NAMES = [c.name for c in protocol.SOLID_COLORS]
ZONE_FIELDS = ["bottom", "lower_left_upper_right", "left_right", "upper_left_lower_right", "top"]


async def async_setup_entry(
    hass: HomeAssistant, entry: GlowConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([GlowLight(entry), *(ColorSlot(entry, slot) for slot in range(COLOR_SLOTS))])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "play_effect",
        {
            vol.Required("effect"): vol.In([e for e in EFFECTS if e != EFFECT_IDLE]),
            vol.Optional("colors"): vol.All(cv.ensure_list, [vol.In(COLOR_NAMES)], vol.Length(min=1, max=COLOR_SLOTS)),
            vol.Optional("duration"): vol.All(vol.Coerce(float), vol.Range(min=0, max=45)),
        },
        "async_play_effect",
    )
    platform.async_register_entity_service(
        "set_zones",
        {
            **{vol.Required(ZONE_FIELDS[0]): vol.In(COLOR_NAMES)},
            **{vol.Optional(f, default=None): vol.Any(None, vol.In(COLOR_NAMES)) for f in ZONE_FIELDS[1:]},
            vol.Optional("duration"): vol.All(vol.Coerce(float), vol.Range(min=0, max=45)),
        },
        "async_set_zones",
    )
    platform.async_register_entity_service(
        "set_colors",
        {vol.Required("colors"): vol.All(cv.ensure_list, [vol.In(COLOR_NAMES)], vol.Length(min=1, max=COLOR_SLOTS))},
        "async_set_colors",
    )
    platform.async_register_entity_service(
        "send_raw",
        {vol.Required("data"): vol.All(cv.string, vol.Match(r"^([0-9A-Fa-f]{2})+$"))},
        "async_send_raw",
    )


def _index(name: str) -> int:
    return protocol.COLOR_BY_NAME[name].index


class GlowLight(GlowEntity, LightEntity, RestoreEntity):
    """Assumed state: the toy never reports back, so this is what HA last told it."""

    _attr_name = None  # the device name
    _attr_assumed_state = True
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = EFFECTS

    def __init__(self, entry: GlowConfigEntry) -> None:
        super().__init__(entry, "light")
        self._attr_is_on = False
        self._attr_rgb_color = (255, 255, 255)
        self._attr_brightness = 255
        self._attr_effect = None
        self._expiry: CALLBACK_TYPE | None = None
        self._spin: asyncio.Task | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.data.light = self
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_COLORS.format(self.entry.entry_id), self._colors_changed)
        )
        if (last := await self.async_get_last_state()) is None:
            return
        self._attr_rgb_color = tuple(last.attributes.get(ATTR_RGB_COLOR) or self._attr_rgb_color)
        self._attr_brightness = last.attributes.get(ATTR_BRIGHTNESS) or 255
        self._attr_effect = last.attributes.get(ATTR_EFFECT)
        # Only a held state is still true after a restart; re-assert it in case the toy reset
        if last.state == STATE_ON and self.data.duration is None:
            self._apply(self._frames(None), None)

    async def async_will_remove_from_hass(self) -> None:
        self._stop()
        self.data.light = None

    @property
    def available(self) -> bool:
        return self.data.transmitter.available

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_RGB_COLOR in kwargs:
            self._attr_rgb_color = kwargs[ATTR_RGB_COLOR]
            if ATTR_EFFECT not in kwargs:
                self._attr_effect = None  # picking a colour leaves the effect
        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
        if ATTR_EFFECT in kwargs:
            self._attr_effect = kwargs[ATTR_EFFECT]
        self._apply(self._frames(self.data.duration), self.data.duration)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._stop()
        self.data.transmitter.send(protocol.off())
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_play_effect(
        self, effect: str, colors: list[str] | None = None, duration: float | None = None
    ) -> None:
        seconds = self._seconds(duration)
        indices = [_index(c) for c in colors] if colors else self._colors()
        self._attr_effect = effect
        self._apply(self._effect_frames(effect, indices, self._timing(seconds)), seconds)

    async def async_set_zones(self, duration: float | None = None, **zones: str | None) -> None:
        seconds = self._seconds(duration)
        # Fill the zone list up to the last zone given; skipped zones before it stay dark
        given = [zones.get(f) for f in ZONE_FIELDS]
        last = max(i for i, c in enumerate(given) if c)
        colors = [_index(c) if c else protocol.OFF for c in given[: last + 1]]
        self._attr_effect = None
        self._apply([protocol.zones(colors, self._timing(seconds))], seconds)

    async def async_set_colors(self, colors: list[str]) -> None:
        """Fill the colour slots in order (the rest are switched off); a running effect follows."""
        for slot in range(COLOR_SLOTS):
            if slot < len(colors):
                self.data.colors[slot] = _index(colors[slot])
            self.data.colors_on[slot] = slot < len(colors)
        async_dispatcher_send(self.hass, SIGNAL_COLORS.format(self.entry.entry_id))

    async def async_select_effect(self, effect: str | None) -> None:
        """Play an effect over the colour slots (None = solid light colour)."""
        if effect == EFFECT_IDLE:
            self.release()
            return
        self._attr_effect = effect
        self._apply(self._frames(self.data.duration), self.data.duration)

    async def async_send_raw(self, data: str) -> None:
        """Advertise raw bytes (after the 83 01 company ID); state is left untouched."""
        await self.data.transmitter.async_send_now(bytes.fromhex(data))

    def release(self) -> None:
        """Hand control back to the toy's own idle cycle."""
        self._attr_effect = EFFECT_IDLE
        self._apply([protocol.release()], None)

    @callback
    def async_write_ha_state(self) -> None:
        super().async_write_ha_state()
        async_dispatcher_send(self.hass, SIGNAL_LIGHT.format(self.entry.entry_id))

    @callback
    def _colors_changed(self) -> None:
        """Re-send a running slot-colour effect so the toy shows the new colours."""
        if self._attr_is_on and self._attr_effect in COLOR_EFFECTS:
            self._apply(self._frames(self.data.duration), self.data.duration)

    # -- helpers -----------------------------------------------------------------------------

    def _seconds(self, duration: float | None) -> float | None:
        """Service duration: omitted = the Duration select, 0 = hold."""
        if duration is None:
            return self.data.duration
        return duration or None

    def _timing(self, seconds: float | None) -> int:
        return protocol.timing(seconds, self.data.fade)

    def _colors(self) -> list[int]:
        return self.data.active_colors() or [protocol.nearest_color(self._attr_rgb_color)]

    def _frames(self, seconds: float | None) -> list[bytes]:
        """What to send for the current state: one command, or a cycle of frames."""
        t = self._timing(seconds)
        if self._attr_effect:
            return self._effect_frames(self._attr_effect, self._colors(), t)
        return [protocol.rgb(*protocol.rgb_from_8bit(self._attr_rgb_color, self._attr_brightness), t)]

    @staticmethod
    def _effect_frames(effect: str, colors: list[int], t: int) -> list[bytes]:
        first, second = colors[0], colors[1] if len(colors) > 1 else colors[0]
        if effect == EFFECT_SPIN:
            return protocol.spin_frames(colors, t)
        # Always all five zones (top and bottom matching); a lone colour moves over dark LEDs
        moving = protocol.symmetric(colors if len(colors) > 1 else [first, protocol.OFF])
        builders = {
            EFFECT_STATIC: lambda: protocol.zones(protocol.symmetric(colors), t),
            EFFECT_CHASE: lambda: protocol.chase(moving, t),
            EFFECT_CHASE_SLOW: lambda: protocol.chase(moving, t, slow=True),
            EFFECT_TWINKLE: lambda: protocol.twinkle(moving, t),
            EFFECT_SPARKLE: lambda: protocol.sparkle(first, second, t),
            EFFECT_CROSSFADE: lambda: protocol.crossfade(first, second, t),
            EFFECT_RAINBOW: lambda: protocol.rainbow(t),
            EFFECT_RANDOM: lambda: protocol.random_color(t),
            EFFECT_SHOW_WHITE: lambda: protocol.show_white(t),
            EFFECT_IDLE: protocol.release,
        }
        if effect not in builders:
            raise ValueError(f"unknown effect {effect}")
        return [builders[effect]()]

    def _apply(self, frames: list[bytes], seconds: float | None) -> None:
        self._stop()
        if len(frames) == 1:
            self.data.transmitter.send(frames[0])
        else:
            self._spin = self.entry.async_create_background_task(
                self.hass, self._cycle(frames), f"{self.entity_id} spin"
            )
        self._attr_is_on = True
        if seconds is not None and self._attr_effect != EFFECT_IDLE:
            # The toy stops by itself; follow it (it then idles after ~20 s dark)
            self._expiry = async_call_later(self.hass, seconds, self._expired)
        self.async_write_ha_state()

    async def _cycle(self, frames: list[bytes]) -> None:
        """Step through the frames until another command replaces them."""
        while True:
            for frame in frames:
                self.data.transmitter.send(frame)
                await asyncio.sleep(SPIN_STEP_S)

    @callback
    def _expired(self, _now) -> None:
        self._expiry = None
        if self._spin:
            # The last frame was sent with the same timing, so the toy stops by itself
            self._spin.cancel()
            self._spin = None
        self._attr_is_on = False
        self.async_write_ha_state()

    def _stop(self) -> None:
        """Cancel a pending expiry and any running frame cycle."""
        if self._expiry:
            self._expiry()
            self._expiry = None
        if self._spin:
            self._spin.cancel()
            self._spin = None


class ColorSlot(GlowEntity, LightEntity, RestoreEntity):
    """One of the colours effects use: pick it on the colour wheel, switch it off to leave it out.

    The toy's effects take palette colours, so the picked colour snaps to the nearest one and the
    entity shows that snapped colour.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "color_slot"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_brightness = 255

    def __init__(self, entry: GlowConfigEntry, slot: int) -> None:
        super().__init__(entry, f"color_{slot + 1}")
        self._slot = slot
        self._attr_translation_placeholders = {"number": str(slot + 1)}

    @property
    def _color(self) -> protocol.PaletteColor:
        return protocol.PALETTE[self.data.colors[self._slot]]

    @property
    def is_on(self) -> bool:
        return self.data.colors_on[self._slot]

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        return self._color.rgb

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"palette_color": self._color.name}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_COLORS.format(self.entry.entry_id), self.async_write_ha_state
            )
        )
        last = await self.async_get_last_state()
        if last and (name := last.attributes.get("palette_color")) in protocol.COLOR_BY_NAME:
            self.data.colors[self._slot] = protocol.COLOR_BY_NAME[name].index
            self.data.colors_on[self._slot] = last.state == STATE_ON
            self._changed()

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_RGB_COLOR in kwargs:
            self.data.colors[self._slot] = protocol.nearest_color(kwargs[ATTR_RGB_COLOR])
        self.data.colors_on[self._slot] = True
        self._changed()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.data.colors_on[self._slot] = False
        self._changed()

    def _changed(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_COLORS.format(self.entry.entry_id))
