"""Puts packets on air through an ESPHome node running the disney_tx component."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import protocol
from .const import ADV_INTERVAL_MS, AIR_TIME_MS, MIN_AIR_S

_LOGGER = logging.getLogger(__name__)

ESPHOME_DOMAIN = "esphome"


def advertise_service(node: str) -> str:
    return f"{node}_advertise"


def find_transmitters(hass: HomeAssistant) -> list[str]:
    """ESPHome nodes that expose the disney_tx `advertise` action."""
    suffix = "_advertise"
    return sorted(
        name[: -len(suffix)]
        for name in hass.services.async_services_for_domain(ESPHOME_DOMAIN)
        if name.endswith(suffix)
    )


class Transmitter:
    """One radio, one advertisement at a time; a newer command replaces a pending one."""

    def __init__(self, hass: HomeAssistant, node: str) -> None:
        self.hass = hass
        self.node = node
        self.last_packet: str | None = None
        self._pending: bytes | None = None
        self._wake = asyncio.Event()

    @property
    def available(self) -> bool:
        return self.hass.services.has_service(ESPHOME_DOMAIN, advertise_service(self.node))

    def send(self, command: bytes) -> None:
        """Queue a command (bytes after the company ID). Latest wins while waiting."""
        protocol.manufacturer_data(command)  # validate now, so callers get the error
        self._pending = command
        self._wake.set()

    async def async_send_now(self, command: bytes) -> None:
        """Advertise immediately and wait for ESPHome to accept it (used by send_raw)."""
        await self._advertise(command)

    async def run(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            command, self._pending = self._pending, None
            if command is None:
                continue
            try:
                await self._advertise(command)
            except HomeAssistantError as err:
                _LOGGER.warning("Transmitter %s failed: %s", self.node, err)
                continue
            # Let it land before anything replaces it
            await asyncio.sleep(MIN_AIR_S)

    async def _advertise(self, command: bytes) -> None:
        data = protocol.manufacturer_data(command).hex().upper()
        if not self.available:
            raise HomeAssistantError(f"ESPHome node {self.node} has no advertise action")
        await self.hass.services.async_call(
            ESPHOME_DOMAIN,
            advertise_service(self.node),
            {"data": data, "duration_ms": AIR_TIME_MS, "interval_ms": ADV_INTERVAL_MS},
            blocking=True,
        )
        self.last_packet = data
        _LOGGER.debug("Advertised %s via %s", data, self.node)
