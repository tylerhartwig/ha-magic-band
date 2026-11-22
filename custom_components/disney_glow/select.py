"""The effect picker, and settings the light uses: speed, duration, fade."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import GlowConfigEntry, protocol
from .const import DURATIONS, EFFECTS, FADES, SIGNAL_LIGHT, SIGNAL_SETTINGS, SPEEDS
from .entity import GlowEntity

OPTION_OFF = "Off"
OPTION_SOLID = "Solid colour"


async def async_setup_entry(
    hass: HomeAssistant, entry: GlowConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([EffectSelect(entry), SpeedSelect(entry), DurationSelect(entry), FadeSelect(entry)])


class _SettingSelect(GlowEntity, SelectEntity, RestoreEntity):
    _attr_entity_category = EntityCategory.CONFIG

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state in self.options:
            self._apply(last.state)

    async def async_select_option(self, option: str) -> None:
        self._apply(option)
        self.async_write_ha_state()

    def _apply(self, option: str) -> None:
        raise NotImplementedError


class EffectSelect(GlowEntity, SelectEntity):
    """What the wheel is doing; picking an option plays it over the colour slots."""

    _attr_translation_key = "effect"
    _attr_options = [OPTION_OFF, OPTION_SOLID, *EFFECTS]

    def __init__(self, entry: GlowConfigEntry) -> None:
        super().__init__(entry, "effect")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_LIGHT.format(self.entry.entry_id), self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        return self.data.light is not None and self.data.light.available

    @property
    def current_option(self) -> str | None:
        light = self.data.light
        if light is None or not light.is_on:
            return OPTION_OFF
        return light.effect or OPTION_SOLID

    async def async_select_option(self, option: str) -> None:
        if option == OPTION_OFF:
            await self.data.light.async_turn_off()
        else:
            await self.data.light.async_select_effect(None if option == OPTION_SOLID else option)


class SpeedSelect(_SettingSelect):
    """Spin's step time and Chase's speed; a running Spin or Chase follows it."""

    _attr_translation_key = "speed"
    _attr_options = list(SPEEDS)

    def __init__(self, entry: GlowConfigEntry) -> None:
        super().__init__(entry, "speed")

    @property
    def current_option(self) -> str:
        return self.data.speed

    def _apply(self, option: str) -> None:
        self.data.speed = option
        async_dispatcher_send(self.hass, SIGNAL_SETTINGS.format(self.entry.entry_id))


class DurationSelect(_SettingSelect):
    _attr_translation_key = "duration"
    _attr_options = list(DURATIONS)

    def __init__(self, entry: GlowConfigEntry) -> None:
        super().__init__(entry, "duration")
        self._option = "Hold"

    @property
    def current_option(self) -> str:
        return self._option

    def _apply(self, option: str) -> None:
        self._option = option
        self.data.duration = DURATIONS[option]


class FadeSelect(_SettingSelect):
    _attr_translation_key = "fade"
    _attr_options = FADES

    def __init__(self, entry: GlowConfigEntry) -> None:
        super().__init__(entry, "fade")

    @property
    def current_option(self) -> str:
        return FADES[self.data.fade]

    def _apply(self, option: str) -> None:
        self.data.fade = protocol.Fade(FADES.index(option))
