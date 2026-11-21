"""Signal strength of the toy's beacon and the last packet sent."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GlowConfigEntry
from .const import SIGNAL_BEACON
from .entity import GlowEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: GlowConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([BeaconRssiSensor(entry)])


class BeaconRssiSensor(GlowEntity, SensorEntity):
    _attr_translation_key = "beacon_rssi"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: GlowConfigEntry) -> None:
        super().__init__(entry, "beacon_rssi")

    @property
    def native_value(self) -> int | None:
        return self.data.rssi

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_BEACON.format(self.entry.entry_id), self.async_write_ha_state
            )
        )
