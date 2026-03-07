"""Support for Disney MagicBand+ & Bucket binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ADVERTISEMENT_TIMEOUT
import time

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MagicBand binary sensors."""
    if config_entry.data.get("mode") == "broadcaster":
        return

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([
        MagicBandPresenceSensor(coordinator, config_entry),
        MagicBandConnectionSensor(coordinator, config_entry),
    ])


class MagicBandPresenceSensor(CoordinatorEntity, BinarySensorEntity):
    """Sensor that indicates if the bucket is nearby."""

    _attr_device_class = BinarySensorDeviceClass.PRESENCE
    _attr_has_entity_name = True
    _attr_name = "Presence"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_presence"

    @property
    def is_on(self) -> bool:
        """Return true if the bucket was seen recently."""
        # If seen in the last 3 minutes
        return (time.time() - self.coordinator.last_seen) < ADVERTISEMENT_TIMEOUT


class MagicBandConnectionSensor(CoordinatorEntity, BinarySensorEntity):
    """Sensor that indicates if the BLE connection is active."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_name = "Connected"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_connection"

    @property
    def is_on(self) -> bool:
        """Return true if connected."""
        return self.coordinator.connected
