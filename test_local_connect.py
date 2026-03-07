import asyncio
from bleak import BleakScanner, BleakClient

async def run():
    print("Searching for MagicBucket_SIM...")
    device = await BleakScanner.find_device_by_name("MagicBucket_SIM")
    if not device:
        print("Could not find MagicBucket_SIM")
        return
    
    print(f"Found {device.name} at {device.address}. Connecting...")
    try:
        async with BleakClient(device) as client:
            print(f"Connected: {client.is_connected}")
            services = await client.get_services()
            for s in services:
                print(f"Service: {s.uuid}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(run())
