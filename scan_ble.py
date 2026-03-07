import asyncio
from bleak import BleakScanner

async def run():
    print("Listing ALL BLE devices and their UUIDs...")
    devices = await BleakScanner.discover(return_adv=True)
    for d, adv in devices.values():
        name = d.name if d.name else "Unknown"
        print(f"DEVICE: {d.address} ({name}) UUIDs: {adv.service_uuids}")

if __name__ == "__main__":
    asyncio.run(run())
