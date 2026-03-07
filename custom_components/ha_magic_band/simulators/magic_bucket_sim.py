"""Standalone MagicBand+ / Popcorn Bucket BLE Simulator - MacOS COMPATIBLE."""
import asyncio
import logging
from typing import Any
from bless import (
    BlessServer,
    BlessGATTCharacteristic,
    GATTCharacteristicProperties,
    GATTAttributePermissions
)

# Constants from Disney's MagicBand+ Protocol (Amazon Gadgets)
SERVICE_UUID = "0000fee8-0000-1000-8000-00805f9b34fb"
CHAR_WRITE_UUID = "f04eb177-3005-43a7-ac61-a390ddf83076"
CHAR_NOTIFY_UUID = "2beea05b-1879-4bb4-8a2f-72641f82420b"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("MagicBucketSim")

def write_callback(characteristic: BlessGATTCharacteristic, value: Any):
    """Log every byte Home Assistant sends to our virtual bucket."""
    hex_val = value.hex()
    logger.info(f"--- [COMMAND RECEIVED] ---")
    logger.info(f"Hex: {hex_val}")
    logger.info(f"Bytes: {list(value)}")
    logger.info(f"--------------------------")

async def run_sim():
    """Start the Virtual Bucket BLE server."""
    logger.info("Initializing Virtual MagicBand+ / Popcorn Bucket (MacOS)...")
    
    server = BlessServer(name="MagicBucket_SIM")
    server.read_request_func = lambda char: char.value
    server.write_request_func = write_callback

    # Add the Amazon Gadgets Service
    await server.add_new_service(SERVICE_UUID)
    
    # MacOS requires writable characteristics to have NO initial value 
    # if they are to be truly writable in CoreBluetooth.
    await server.add_new_characteristic(
        SERVICE_UUID,
        CHAR_WRITE_UUID,
        (
            GATTCharacteristicProperties.write |
            GATTCharacteristicProperties.write_without_response
        ),
        None,
        GATTAttributePermissions.writeable
    )

    await server.add_new_characteristic(
        SERVICE_UUID,
        CHAR_NOTIFY_UUID,
        (
            GATTCharacteristicProperties.notify |
            GATTCharacteristicProperties.read
        ),
        b"", # Read-only can have an initial value
        GATTAttributePermissions.readable
    )

    logger.info(f"Simulator is now ADVERTISING as '{server.name}'")
    logger.info(f"Waiting for Home Assistant to connect...")
    
    await server.start()
    
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(run_sim())
    except KeyboardInterrupt:
        logger.info("Simulator stopped.")
