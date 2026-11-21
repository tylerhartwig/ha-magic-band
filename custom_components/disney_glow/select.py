"""Settings the light uses for its next command: secondary colour, duration, fade."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import GlowConfigEntry, protocol
from .const import DURATIONS, FADES
from .entity import GlowEntity

COLOR_NAMES = [c.name for c in protocol.SOLID_COLORS]


async def async_setup_entry(
    hass: HomeAssistant, entry: GlowConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([SecondaryColorSelect(entry), DurationSelect(entry), FadeSelect(entry)])


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


class SecondaryColorSelect(_SettingSelect):
    _attr_translation_key = "secondary_color"
    _attr_options = COLOR_NAMES

    def __init__(self, entry: GlowConfigEntry) -> None:
        super().__init__(entry, "secondary_color")

    @property
    def current_option(self) -> str:
        return protocol.PALETTE[self.data.secondary_color].name

    def _apply(self, option: str) -> None:
        self.data.secondary_color = protocol.COLOR_BY_NAME[option].index


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
