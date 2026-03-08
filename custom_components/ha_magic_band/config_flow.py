"""Config flow for Disney MagicBand+ & Bucket integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, MAGICBAND_SERVICE_UUID, DISNEY_MANUFACTURER_ID

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Disney MagicBand+ & Bucket."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Handle broadcaster setup
            address = user_input.get(CONF_ADDRESS)
            if address == "broadcaster":
                await self.async_set_unique_id("global_broadcaster")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="MagicBand Broadcaster", data={"mode": "broadcaster"}
                )

            if address == "manual":
                return await self.async_step_manual()
            
            if address == "scan_all":
                return await self.async_step_user({"show_all": True})

            # Handle device connection
            if address in self._discovered_devices:
                discovery_info = self._discovered_devices[address]
                await self.async_set_unique_id(discovery_info.address, raise_on_progress=False)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=discovery_info.name or "MagicBand+",
                    data={
                        "mode": "connected",
                        CONF_ADDRESS: discovery_info.address,
                        CONF_NAME: discovery_info.name,
                    },
                )

        show_all = user_input.get("show_all", False) if user_input else False
        
        # Scan for devices
        current_addresses = self._async_current_ids()
        _LOGGER.error("DEBUG [v1.2.6]: Current Configured IDs: %s", current_addresses)
        
        for discovery_info in async_discovered_service_info(self.hass):
            lowered_uuids = [u.lower() for u in discovery_info.service_uuids]
            has_uuid = MAGICBAND_SERVICE_UUID.lower() in lowered_uuids
            has_manuf_data = DISNEY_MANUFACTURER_ID in discovery_info.manufacturer_data
            
            # Match based on Disney IDs OR show everything if requested
            is_match = has_uuid or has_manuf_data or show_all
            is_new = discovery_info.address not in current_addresses
            
            _LOGGER.error("DEBUG [v1.2.6]: Eval %s (%s) - Match: %s, UUIDs: %s, Manuf: %s", 
                         discovery_info.address, discovery_info.name, is_match, lowered_uuids, list(discovery_info.manufacturer_data.keys()))
            
            if is_match and is_new:
                self._discovered_devices[discovery_info.address] = discovery_info

        # Build options list
        device_options = {
            addr: f"{info.name or 'Unknown'} ({addr})"
            for addr, info in self._discovered_devices.items()
        }
        device_options["broadcaster"] = "Setup Global Broadcaster Mode"
        device_options["manual"] = "Manual Address Entry"
        if not show_all:
            device_options["scan_all"] = "-- SHOW ALL NEARBY DEVICES --"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS, default="broadcaster"): vol.In(device_options),
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle manual address entry."""
        errors = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, "Manual MagicBand+"),
                data={
                    "mode": "connected",
                    CONF_ADDRESS: address,
                    CONF_NAME: user_input.get(CONF_NAME),
                },
            )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                    vol.Optional(CONF_NAME, default="MagicBand+"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        # Store discovery info for the confirm step
        self.context["address"] = discovery_info.address
        self.context["name"] = discovery_info.name or "MagicBand+"
        
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.context["name"],
                data={
                    "mode": "connected",
                    CONF_ADDRESS: self.context["address"],
                    CONF_NAME: self.context["name"],
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self.context["name"]},
        )
