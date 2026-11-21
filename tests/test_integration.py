"""End-to-end through HA: config flow, light commands, services, expiry (fake ESPHome action)."""
import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType

from custom_components.disney_glow import transmitter as tx_module
from custom_components.disney_glow.const import DOMAIN

LIGHT = "light.ferris_wheel"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
async def sent(hass: HomeAssistant, enable_bluetooth, monkeypatch):
    """Register a fake disney_tx advertise action; collect the manufacturer data it gets."""
    monkeypatch.setattr(tx_module, "MIN_AIR_S", 0)
    calls: list[str] = []

    async def advertise(call: ServiceCall) -> None:
        assert call.data["duration_ms"] == 1500 and call.data["interval_ms"] == 30
        calls.append(call.data["data"])

    hass.services.async_register("esphome", "disney_tx_advertise", advertise)
    return calls


async def _setup(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"transmitter": "disney_tx", "name": "Ferris Wheel"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def _call(hass, domain, service, **data):
    await hass.services.async_call(domain, service, {"entity_id": data.pop("entity_id", LIGHT), **data}, blocking=True)
    await hass.async_block_till_done()


async def test_no_transmitter_aborts(hass: HomeAssistant, enable_bluetooth) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_transmitter"


async def test_light(hass: HomeAssistant, sent) -> None:
    await _setup(hass)
    assert hass.states.get(LIGHT).state == "off"

    await _call(hass, "light", "turn_on", rgb_color=[255, 0, 0])
    assert sent[-1] == "8301E908008E0ED2557E0000B0"
    state = hass.states.get(LIGHT)
    assert state.state == "on" and state.attributes["assumed_state"]

    await _call(hass, "light", "turn_on", brightness=128)
    assert sent[-1] == "8301E908008E0ED2554000" "00B0"  # 32/63 red

    await _call(hass, "light", "turn_on", effect="Chase")
    assert sent[-1] == "8301E906008E0F55A230"  # red + default secondary azure, chase

    await _call(hass, "select", "select_option", entity_id="select.ferris_wheel_secondary_colour", option="green")
    await _call(hass, "light", "turn_on", effect="Crossfade")
    assert sent[-1] == "8301E100E911008E0F555958F4488" "2D1460208D06500B0"

    await _call(hass, "light", "turn_off")
    assert sent[-1] == "8301E905008E0EFDB0"
    assert hass.states.get(LIGHT).state == "off"

    await _call(hass, "button", "press", entity_id="button.ferris_wheel_return_to_idle")
    assert sent[-1] == "8301E90500010EFDB0"
    assert hass.states.get(LIGHT).attributes["effect"] == "Idle"


async def test_services(hass: HomeAssistant, sent) -> None:
    await _setup(hass)
    await _call(hass, DOMAIN, "play_effect", effect="Twinkle", colors=["red", "white"], duration=0)
    assert sent[-1] == "8301E906008E0F55BC31"
    await _call(hass, DOMAIN, "set_zones", bottom="red", left_right="azure")
    assert sent[-1] == "8301E907008E0F75BDA2B0"  # 3 colours: red, (dark), azure
    await _call(hass, DOMAIN, "send_raw", data="e905002e0ef9b0")
    assert sent[-1] == "8301E905002E0EF9B0"


async def test_timed_command_expires(hass: HomeAssistant, sent, freezer) -> None:
    await _setup(hass)
    await _call(hass, "select", "select_option", entity_id="select.ferris_wheel_duration", option="5 s")
    await _call(hass, "light", "turn_on", rgb_color=[0, 0, 255])
    assert sent[-1] == "8301E9080003" "0ED25500007EB0"
    assert hass.states.get(LIGHT).state == "on"
    from pytest_homeassistant_custom_component.common import async_fire_time_changed
    import datetime as dt
    from homeassistant.util import dt as dt_util

    freezer.tick(dt.timedelta(seconds=5))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get(LIGHT).state == "off"
