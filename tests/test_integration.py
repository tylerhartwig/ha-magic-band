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
    assert sent[-1] == "8301E908008ED2557E0000B0"
    state = hass.states.get(LIGHT)
    assert state.state == "on" and state.attributes["assumed_state"]

    await _call(hass, "light", "turn_on", brightness=128)
    assert sent[-1] == "8301E908008ED255400000B0"  # 32/63 red

    await _call(hass, "light", "turn_on", effect="Chase")
    # default slots red, yellow-orange, azure, green over all five zones (top = bottom = red)
    assert sent[-1] == "8301E909008E0FB5AFA2B9B530"

    await _call(hass, DOMAIN, "set_colors", colors=["red", "green"])
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
    assert sent[-1] == "8301E909008E0FB5BCB5BCB531"  # red, white repeated over all five zones
    await _call(hass, DOMAIN, "set_zones", bottom="red", left_right="azure")
    assert sent[-1] == "8301E907008E0F75BDA2B0"  # 3 colours: red, (dark), azure
    await _call(hass, DOMAIN, "send_raw", data="e905002e0ef9b0")
    assert sent[-1] == "8301E905002E0EF9B0"


async def test_timed_command_expires(hass: HomeAssistant, sent, freezer) -> None:
    await _setup(hass)
    await _call(hass, "select", "select_option", entity_id="select.ferris_wheel_duration", option="5 s")
    await _call(hass, "light", "turn_on", rgb_color=[0, 0, 255])
    assert sent[-1] == "8301E9080003D25500007EB0"
    assert hass.states.get(LIGHT).state == "on"
    from pytest_homeassistant_custom_component.common import async_fire_time_changed
    import datetime as dt
    from homeassistant.util import dt as dt_util

    freezer.tick(dt.timedelta(seconds=5))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get(LIGHT).state == "off"


async def test_spin_cycles_and_stops(hass: HomeAssistant, sent, monkeypatch) -> None:
    import asyncio

    from custom_components.disney_glow import light as light_module

    monkeypatch.setattr(light_module, "SPIN_STEP_S", 0.01)
    await _setup(hass)
    await _call(hass, DOMAIN, "set_colors", colors=["red", "azure"])
    await _call(hass, "light", "turn_on", effect="Spin")
    for _ in range(50):
        await asyncio.sleep(0.01)
        if len(sent) >= 6:
            break
    # red bar over azure: top+bottom, LL+UR, L+R, UL+LR, then again
    assert sent[:5] == [
        "8301E909008E0FB5A2A2A2B5B0",
        "8301E909008E0FA2B5A2A2A2B0",
        "8301E909008E0FA2A2B5A2A2B0",
        "8301E909008E0FA2A2A2B5A2B0",
        "8301E909008E0FB5A2A2A2B5B0",
    ]
    await _call(hass, "light", "turn_off")
    count = len(sent)
    await asyncio.sleep(0.1)
    assert sent[-1] == "8301E905008E0EFDB0" and len(sent) == count


async def test_color_slots_and_effect_select(hass: HomeAssistant, sent) -> None:
    await _setup(hass)
    effect = "select.ferris_wheel_effect"
    assert hass.states.get(effect).state == "Off"
    slot2 = "light.ferris_wheel_colour_2"
    assert hass.states.get(slot2).attributes["palette_color"] == "yellow_orange"

    await _call(hass, "select", "select_option", entity_id=effect, option="Static")
    assert sent[-1] == "8301E909008E0FB5AFA2B9B5B0"
    assert hass.states.get(LIGHT).attributes["effect"] == "Static"
    assert hass.states.get(effect).state == "Static"

    # Picking a slot colour on the wheel snaps to the palette and re-sends the running effect
    await _call(hass, "light", "turn_on", entity_id=slot2, rgb_color=[0, 0, 250])
    assert hass.states.get(slot2).attributes["palette_color"] == "deep_blue"
    assert sent[-1] == "8301E909008E0FB5A4A2B9B5B0"

    # Slots that are off are left out; the rest repeat round the wheel
    await _call(hass, "light", "turn_off", entity_id="light.ferris_wheel_colour_3")
    await _call(hass, "light", "turn_off", entity_id="light.ferris_wheel_colour_4")
    assert sent[-1] == "8301E909008E0FB5A4B5A4B5B0"

    await _call(hass, "select", "select_option", entity_id=effect, option="Solid colour")
    assert hass.states.get(LIGHT).attributes["effect"] is None
    await _call(hass, "select", "select_option", entity_id=effect, option="Off")
    assert sent[-1] == "8301E905008E0EFDB0"
    assert hass.states.get(effect).state == "Off"


async def test_held_command_is_refreshed(hass: HomeAssistant, sent, freezer) -> None:
    import datetime as dt

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    async def tick(seconds):
        freezer.tick(dt.timedelta(seconds=seconds))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()

    await _setup(hass)
    await _call(hass, "light", "turn_on", rgb_color=[255, 0, 0])
    count = len(sent)
    await tick(31)
    assert len(sent) == count + 1 and sent[-1] == "8301E908008ED2557E0000B0"

    await _call(hass, "light", "turn_off")  # held dark is refreshed too
    await tick(31)
    assert sent[-2:] == ["8301E905008E0EFDB0"] * 2

    await _call(hass, "button", "press", entity_id="button.ferris_wheel_return_to_idle")
    count = len(sent)
    await tick(31)
    assert len(sent) == count  # idle hands control back, nothing to refresh
