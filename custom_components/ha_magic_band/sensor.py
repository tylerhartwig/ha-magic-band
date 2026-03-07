"""Support for Disney MagicBand+ & Bucket sensors."""
from __future__ import annotations
import logging
_LOGGER = logging.getLogger(__name__)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    _LOGGER.error("DEBUG: Starting sensor platform setup")
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MagicBand sensors."""
    if config_entry.data.get("mode") == "broadcaster":
        return

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([
        MagicBandRSSISensor(coordinator, config_entry),
    ])


class MagicBandRSSISensor(CoordinatorEntity, SensorEntity):
    """Sensor that reports the signal strength (RSSI)."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_has_entity_name = True
    _attr_name = "Signal Strength"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_rssi"

    @property
    def native_value(self) -> int:
        """Return the current RSSI value."""
        return self.coordinator.rssi
