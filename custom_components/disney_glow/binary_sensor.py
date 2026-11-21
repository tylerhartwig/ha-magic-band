"""Presence from the toy's own beacon (new random address every time, so matched by payload)."""
from __future__ import annotations

from datetime import timedelta
import time

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import GlowConfigEntry
from .const import PRESENCE_TIMEOUT_S, SIGNAL_BEACON
from .entity import GlowEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: GlowConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([NearbySensor(entry)])


class NearbySensor(GlowEntity, BinarySensorEntity):
    _attr_translation_key = "nearby"
    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    def __init__(self, entry: GlowConfigEntry) -> None:
        super().__init__(entry, "nearby")

    @property
    def is_on(self) -> bool:
        seen = self.data.last_seen
        return seen is not None and time.monotonic() - seen < PRESENCE_TIMEOUT_S

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_BEACON.format(self.entry.entry_id), self.async_write_ha_state
            )
        )
        self.async_on_remove(
            async_track_time_interval(self.hass, self._tick, timedelta(seconds=30))
        )

    @callback
    def _tick(self, _now) -> None:
        self.async_write_ha_state()
