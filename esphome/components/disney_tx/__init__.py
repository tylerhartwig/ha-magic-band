"""Raw BLE advertiser for Disney 0x0183 light toys, driven from the ESPHome native API."""
import esphome.codegen as cg
from esphome.components import esp32_ble
from esphome.components.esp32 import request_bluetooth
from esphome.components.esp32_ble import CONF_BLE_ID
import esphome.config_validation as cv
from esphome.const import CONF_ID

AUTO_LOAD = ["esp32_ble"]
DEPENDENCIES = ["esp32"]
CODEOWNERS = ["@tylerhartwig"]

disney_tx_ns = cg.esphome_ns.namespace("disney_tx")
DisneyTx = disney_tx_ns.class_("DisneyTx", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(DisneyTx),
        cv.GenerateID(CONF_BLE_ID): cv.use_id(esp32_ble.ESP32BLE),
    }
).extend(cv.COMPONENT_SCHEMA)

FINAL_VALIDATE_SCHEMA = esp32_ble.validate_variant


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    parent = await cg.get_variable(config[CONF_BLE_ID])
    esp32_ble.register_gap_event_handler(parent, var)
    await cg.register_component(var, config)
    request_bluetooth()
