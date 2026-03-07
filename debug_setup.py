"""Script to mock Home Assistant setup for debugging."""
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add current directory to path
sys.path.append(os.getcwd())

async def debug_setup():
    print("--- DEBUGGING INTEGRATION SETUP ---")
    
    # Mock Home Assistant and its core components
    hass = MagicMock()
    hass.data = {}
    
    # Mock Config Entry
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {"mode": "broadcaster"}
    entry.unique_id = "test_unique_id"
    
    # Mock the async_forward_entry_setups call
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    
    try:
        from custom_components.ha_magic_band import async_setup_entry
        print("✅ Successfully imported async_setup_entry")
        
        # Attempt to run setup
        result = await async_setup_entry(hass, entry)
        print(f"✅ Setup result: {result}")
        print(f"✅ hass.data[DOMAIN]: {hass.data.get('ha_magic_band')}")
        
    except Exception as e:
        import traceback
        print("❌ SETUP FAILED")
        traceback.print_exc()

if __name__ == "__main__":
    # Mock more Home Assistant modules for the import
    from types import ModuleType
    def mock_ha_module(name):
        m = ModuleType(name)
        sys.modules[name] = m
        return m

    mock_ha_module("homeassistant.helpers")
    mock_ha_module("homeassistant.helpers.update_coordinator")
    mock_ha_module("homeassistant.helpers.entity_platform")
    mock_ha_module("homeassistant.components")
    mock_ha_module("homeassistant.components.light")
    mock_ha_module("homeassistant.components.sensor")
    mock_ha_module("homeassistant.components.binary_sensor")
    mock_ha_module("homeassistant.components.bluetooth")
    mock_ha_module("homeassistant.const")
    mock_ha_module("homeassistant.config_entries")
    mock_ha_module("homeassistant.core")
    
    # Set required constants
    sys.modules["homeassistant.const"].CONF_ADDRESS = "address"
    sys.modules["homeassistant.const"].Platform = MagicMock()
    sys.modules["homeassistant.core"].HomeAssistant = MagicMock()
    sys.modules["homeassistant.config_entries"].ConfigEntry = MagicMock()
    sys.modules["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = MagicMock
    sys.modules["homeassistant.components.light"].LightEntity = MagicMock
    sys.modules["homeassistant.components.light"].ColorMode = MagicMock()
    sys.modules["homeassistant.components.light"].ATTR_RGB_COLOR = "rgb_color"
    sys.modules["homeassistant.components.light"].ATTR_BRIGHTNESS = "brightness"
    
    asyncio.run(debug_setup())
