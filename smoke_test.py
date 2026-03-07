"""Revised Smoke Test to verify the integration files are loadable."""
import sys
import os
from types import ModuleType

# Create dummy homeassistant modules
def mock_module(name):
    m = ModuleType(name)
    sys.modules[name] = m
    return m

# Mock everything required by the imports
ha = mock_module("homeassistant")
ha_const = mock_module("homeassistant.const")
ha_const.CONF_ADDRESS = "address"
ha_const.CONF_NAME = "name"
ha_const.Platform = ModuleType("Platform")
ha_const.Platform.LIGHT = "light"
ha_const.Platform.SENSOR = "sensor"
ha_const.Platform.BINARY_SENSOR = "binary_sensor"

mock_module("homeassistant.components")
mock_module("homeassistant.components.light")
mock_module("homeassistant.components.sensor")
mock_module("homeassistant.components.binary_sensor")
mock_module("homeassistant.components.bluetooth")
mock_module("homeassistant.helpers")
mock_module("homeassistant.helpers.update_coordinator")
mock_module("homeassistant.config_entries")
mock_module("homeassistant.core")
mock_module("homeassistant.data_entry_flow")
mock_module("voluptuous")

def test_imports():
    try:
        # Add the current directory to sys.path
        sys.path.append(os.getcwd())
        
        from custom_components.ha_magic_band import const
        from custom_components.ha_magic_band import config_flow
        from custom_components.ha_magic_band import light
        from custom_components.ha_magic_band import sensor
        from custom_components.ha_magic_band import binary_sensor
        print("✅ SUCCESS: All integration files imported correctly.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ FAILURE: Import error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_imports()
