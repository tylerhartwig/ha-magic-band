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

from .const import DOMAIN, MAGICBAND_CHAR_UUID

_LOGGER = logging.getLogger(__name__)


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
        if ATTR_RGB_COLOR in kwargs:
            self._rgb = kwargs[ATTR_RGB_COLOR]
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        # TODO: Implement the actual BLE write logic here
        # We will use the characteristics from our research
        _LOGGER.info("Turning on bucket %s with RGB %s", self._address, self._rgb)
        self._state = True
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
    _attr_color_mode = ColorMode.ON_OFF
    _attr_supported_color_modes = {ColorMode.ON_OFF}

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
        _LOGGER.info("Sending MagicBand Broadcast signal")
        self._state = True
        # In broadcaster mode, we just fire the packet and stay 'on' briefly
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop broadcasting."""
        self._state = False
        self.async_write_ha_state()
