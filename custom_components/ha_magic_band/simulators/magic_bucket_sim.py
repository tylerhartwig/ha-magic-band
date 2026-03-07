"""Standalone MagicBand+ / Popcorn Bucket BLE Simulator."""
import asyncio
import logging
from bless import (
    BlessServer,
    BlessGATTCharacteristic,
    GATTCharacteristicProperties,
    GATTAttributePermissions
)

# Constants from Disney's MagicBand+ Protocol
SERVICE_UUID = "0000fee7-0000-1000-8000-00805f9b34fb"
CHAR_UUID = "0000fee8-0000-1000-8000-00805f9b34fb"

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
    logger.info("Initializing Virtual MagicBand+ / Popcorn Bucket...")
    
    server = BlessServer(name="MagicBucket_SIM")
    server.read_request_func = lambda char: char.value
    server.write_request_func = write_callback

    # Add the MagicBand+ Service
    await server.add_new_service(SERVICE_UUID)
    
    # Add the Write/Notify Characteristic
    await server.add_new_characteristic(
        SERVICE_UUID,
        CHAR_UUID,
        (
            GATTCharacteristicProperties.write |
            GATTCharacteristicProperties.notify |
            GATTCharacteristicProperties.read
        ),
        b"\x00",  # Initial state
        (
            GATTAttributePermissions.readable |
            GATTAttributePermissions.writable
        )
    )

    logger.info(f"Simulator is now ADVERTISING as '{server.name}'")
    logger.info(f"Service: {SERVICE_UUID}")
    logger.info(f"Waiting for Home Assistant to connect...")
    
    await server.start()
    
    # Keep the simulator running
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(run_sim())
    except KeyboardInterrupt:
        logger.info("Simulator stopped.")
