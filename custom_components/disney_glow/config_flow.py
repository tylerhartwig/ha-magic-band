"""Config flow: pick the ESPHome transmitter and name the toy."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME

from .const import CONF_TRANSMITTER, DOMAIN
from .transmitter import find_transmitters


class GlowConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        """The toy's beacon was heard. Its address rotates, so one discovery flow covers it."""
        await self.async_set_unique_id(f"{DOMAIN}_beacon")
        self._abort_if_unique_id_configured()
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        transmitters = find_transmitters(self.hass)
        if not transmitters:
            return self.async_abort(reason="no_transmitter")
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_TRANSMITTER], raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_NAME], data={CONF_TRANSMITTER: user_input[CONF_TRANSMITTER]}
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TRANSMITTER, default=transmitters[0]): vol.In(transmitters),
                    vol.Required(CONF_NAME, default="Ferris Wheel"): str,
                }
            ),
        )
