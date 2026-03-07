import asyncio
from bleak import BleakScanner

async def run():
    print("Scanning for BLE devices...")
    devices = await BleakScanner.discover()
    for d in devices:
        name = d.name if d.name else "Unknown"
        print(f"{d.address} ({name})")
        if "Magic" in name:
            print(f"  FOUND: {d.address}")

if __name__ == "__main__":
    asyncio.run(run())
