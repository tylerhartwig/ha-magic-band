"""The Disney MagicBand+ & Bucket integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, ADVERTISEMENT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Disney MagicBand+ from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    if entry.data.get("mode") == "broadcaster":
        # Global broadcaster setup logic
        _LOGGER.info("Setting up MagicBand Broadcaster")
        hass.data[DOMAIN][entry.entry_id] = {"mode": "broadcaster"}
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.LIGHT])
        return True

    # Connected mode setup
    address = entry.data.get(CONF_ADDRESS)
    _LOGGER.info("Setting up MagicBand+ at %s", address)

    # Initialize the coordinator which will manage the BLE connection
    coordinator = MagicBandCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class MagicBandCoordinator(DataUpdateCoordinator):
    """Class to manage fetching MagicBand data and connection."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data.get(CONF_ADDRESS)}",
        )
        self.address = entry.data.get(CONF_ADDRESS)
        self.connected = False
        self.last_seen = 0.0
        self.rssi = -100

    def update_advertisement(self, service_info):
        """Update state from a new BLE advertisement."""
        self.rssi = service_info.rssi
        self.last_seen = service_info.time
        self.async_set_updated_data({"rssi": self.rssi, "last_seen": self.last_seen})
