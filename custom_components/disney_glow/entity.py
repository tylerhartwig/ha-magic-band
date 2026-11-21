"""Base entity for Disney Glow Toys."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import GlowConfigEntry
from .const import DOMAIN


class GlowEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: GlowConfigEntry, key: str) -> None:
        self.entry = entry
        self.data = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Disney",
            model="Ferris wheel light toy (BLE 0x0183)",
        )
