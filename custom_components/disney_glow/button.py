"""Return the toy to its own idle animation."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GlowConfigEntry, protocol
from .entity import GlowEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: GlowConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([ReturnToIdleButton(entry)])


class ReturnToIdleButton(GlowEntity, ButtonEntity):
    _attr_translation_key = "return_to_idle"

    def __init__(self, entry: GlowConfigEntry) -> None:
        super().__init__(entry, "return_to_idle")

    async def async_press(self) -> None:
        if self.data.light:
            self.data.light.release()
        else:
            self.data.transmitter.send(protocol.release())
