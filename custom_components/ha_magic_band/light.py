"""Support for Disney MagicBand+ & Bucket lights."""
from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, MAGICBAND_CHAR_WRITE_UUID

_LOGGER = logging.getLogger(__name__)

# Alexa Gadget Packet Headers
GADGET_DISCOVER = b"\xfe\x03\x01\x00\x00"
GADGET_STATUS = b"\xfe\x03\x03\x00\x00"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MagicBand lights."""
    if config_entry.data.get("mode") == "broadcaster":
        async_add_entities([MagicBandBroadcaster(config_entry)])
        return

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([MagicBandLight(coordinator, config_entry)])


class MagicBandLight(CoordinatorEntity, LightEntity):
    """Representation of an individual Disney MagicBand+ or Bucket."""

    _attr_has_entity_name = True
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._entry = entry
        self._address = entry.data["address"]
        self._attr_unique_id = f"{entry.unique_id}_light"
        self._attr_name = "Light"
        self._state = False
        self._rgb = (255, 255, 255)
        self._brightness = 255

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the rgb color value."""
        return self._rgb

    @property
    def brightness(self) -> int:
        """Return the brightness value."""
        return self._brightness

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the bucket on."""
        from bleak import BleakClient
        if ATTR_RGB_COLOR in kwargs:
            self._rgb = kwargs[ATTR_RGB_COLOR]
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        self._state = True
        
        # Get the BLE device
        ble_device = async_ble_device_from_address(self.hass, self._address)
        if not ble_device:
            _LOGGER.error("Could not find BLE device for %s. Ensure the bucket is in range and advertising.", self._address)
            return

        try:
            async with BleakClient(ble_device) as client:
                # 1. Handshake (Discovery)
                await client.write_gatt_char(MAGICBAND_CHAR_WRITE_UUID, GADGET_DISCOVER)
                
                # 2. Set Color
                # Packet: FE 03 04 [Length] [Payload...]
                # Payload: 01 [R] [G] [B] [Brightness]
                r, g, b = self._rgb
                payload = bytes([0x01, r, g, b, self._brightness])
                packet = b"\xfe\x03\x04" + bytes([len(payload)]) + payload
                
                await client.write_gatt_char(MAGICBAND_CHAR_WRITE_UUID, packet)
                
                self.coordinator.connected = True
        except Exception as e:
            _LOGGER.error("Failed to connect to MagicBand %s: %s", self._address, e)
            self.coordinator.connected = False

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the bucket off."""
        _LOGGER.info("Turning off bucket %s", self._address)
        self._state = False
        self.async_write_ha_state()


class MagicBandBroadcaster(LightEntity):
    """Representation of the Global Broadcaster."""

    _attr_has_entity_name = True
    _attr_name = "Broadcaster"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the broadcaster."""
        self._entry = entry
        self._attr_unique_id = "magicband_global_broadcaster"
        self._state = False

    @property
    def is_on(self) -> bool:
        """Return true if broadcaster is active."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send a broadcast signal."""
        _LOGGER.info("Sending MagicBand Broadcast signal (Glow with the Show)")
        self._state = True
        
        # Manufacturer Data for Disney (0x01E5)
        # Payload: 01 00 00 00 ... (Trigger Ping)
        # We will use the 'ble_advertiser' service if available or 
        # a standard HA bluetooth broadcast.
        
        # Note: Broadcaster mode often requires specific ESPHome configuration.
        # This integration will log the packet it *wants* to send.
        packet = "0100000000000000000000000000000000000000"
        _LOGGER.info("Broadcast Packet (Company ID 0x01E5): %s", packet)
        
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop broadcasting."""
        _LOGGER.info("Stopping MagicBand Broadcast")
        self._state = False
        self.async_write_ha_state()
