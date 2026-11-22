"""Disney Glow Toys: drive Disney 0x0183 light toys through an ESPHome BLE advertiser."""
from __future__ import annotations

from dataclasses import dataclass, field
import time

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import protocol
from .const import COLOR_SLOTS, CONF_TRANSMITTER, DEFAULT_COLORS, DOMAIN, SIGNAL_BEACON
from .transmitter import Transmitter

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.SELECT,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


@dataclass
class GlowData:
    """Shared state for one toy."""

    transmitter: Transmitter
    colors: list[int] = field(default_factory=lambda: list(DEFAULT_COLORS))  # palette index per slot
    colors_on: list[bool] = field(default_factory=lambda: [True] * COLOR_SLOTS)  # slot used by effects
    duration: float | None = None  # None = hold
    fade: protocol.Fade = protocol.Fade.NONE
    speed: str = "Fast"  # a SPEEDS key
    last_seen: float | None = None  # monotonic time of the last beacon
    rssi: int | None = None
    light: object | None = field(default=None, repr=False)

    def active_colors(self) -> list[int]:
        return [c for c, on in zip(self.colors, self.colors_on) if on]


type GlowConfigEntry = ConfigEntry[GlowData]


async def async_setup_entry(hass: HomeAssistant, entry: GlowConfigEntry) -> bool:
    transmitter = Transmitter(hass, entry.data[CONF_TRANSMITTER])
    entry.runtime_data = data = GlowData(transmitter)
    entry.async_create_background_task(hass, transmitter.run(), f"{DOMAIN} transmitter")

    @callback
    def _beacon(info: bluetooth.BluetoothServiceInfoBleak, change: bluetooth.BluetoothChange) -> None:
        payload = info.manufacturer_data.get(protocol.COMPANY_ID, b"")
        if not protocol.is_beacon(payload):
            return
        data.last_seen = time.monotonic()
        data.rssi = info.rssi
        async_dispatcher_send(hass, SIGNAL_BEACON.format(entry.entry_id))

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _beacon,
            bluetooth.BluetoothCallbackMatcher(manufacturer_id=protocol.COMPANY_ID),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GlowConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
