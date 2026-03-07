"""The Disney MagicBand+ & Bucket integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, ADVERTISEMENT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Disney MagicBand+ from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    try:
        _LOGGER.error("DEBUG: Starting async_setup_entry for %s (mode: %s)", entry.entry_id, entry.data.get("mode"))
        
        if entry.data.get("mode") == "broadcaster":
            hass.data[DOMAIN][entry.entry_id] = {"mode": "broadcaster"}
        else:
            address = entry.data.get(CONF_ADDRESS)
            _LOGGER.info("Setting up MagicBand+ at %s", address)
            coordinator = MagicBandCoordinator(hass, entry)
            hass.data[DOMAIN][entry.entry_id] = coordinator

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.error("DEBUG: Successfully set up entry %s", entry.entry_id)
        return True
    except Exception as err:
        _LOGGER.error("Error setting up MagicBand+ integration: %s", err, exc_info=True)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class MagicBandCoordinator(DataUpdateCoordinator):
    """Class to manage fetching MagicBand data and connection."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        _LOGGER.error("DEBUG: Initializing MagicBandCoordinator for %s", entry.data.get(CONF_ADDRESS))
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
