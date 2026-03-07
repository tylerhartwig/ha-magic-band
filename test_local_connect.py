import asyncio
from bleak import BleakScanner, BleakClient

async def run():
    address = "E691E098-1DFE-8EB6-9FCA-53D54C5690F3"
    print(f"Attempting to connect to {address}...")
    try:
        async with BleakClient(address) as client:
            print(f"Connected: {client.is_connected}")
            services = await client.get_services()
            for s in services:
                print(f"Service: {s.uuid}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(run())
