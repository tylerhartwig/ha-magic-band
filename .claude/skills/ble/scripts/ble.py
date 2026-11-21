"""BLE debugging CLI for Disney MagicBand+ / Popcorn Buckets (Amazon Gadgets protocol).

Uses the Mac's own Bluetooth adapter via bleak. On macOS, device addresses are
CoreBluetooth UUIDs (not MACs) and are stable only on this machine.

    ble.py scan [--time 8] [--all] [--name SUBSTR]
    ble.py inspect ADDRESS
    ble.py color ADDRESS R G B [--brightness 255] [--no-handshake] [--listen 2]
    ble.py write ADDRESS HEX [--char UUID] [--listen 2]
    ble.py listen ADDRESS [--time 10]

Output is one JSON object per line so results are easy to parse and compare.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

from bleak import BleakClient, BleakScanner

# Mirrors custom_components/ha_magic_band/const.py and light.py
SERVICE_UUID = "0000fee8-0000-1000-8000-00805f9b34fb"
CHAR_WRITE_UUID = "f04eb177-3005-43a7-ac61-a390ddf83076"
CHAR_NOTIFY_UUID = "2beea05b-1879-4bb4-8a2f-72641f82420b"
# Disney's registered company ID is 0x0183 (used by park/MagicBand+ broadcasts);
# 0x01E5 is what const.py currently uses, kept until verified against hardware.
DISNEY_MANUFACTURER_IDS = (0x0183, 0x01E5)
GADGET_DISCOVER = b"\xfe\x03\x01\x00\x00"


def emit(**obj) -> None:
    print(json.dumps(obj, sort_keys=True), flush=True)


def color_packet(r: int, g: int, b: int, brightness: int) -> bytes:
    payload = bytes([0x01, r, g, b, brightness])
    return b"\xfe\x03\x04" + bytes([len(payload)]) + payload


def is_candidate(adv) -> bool:
    uuids = [u.lower() for u in adv.service_uuids]
    return (
        SERVICE_UUID in uuids
        or any(cid in adv.manufacturer_data for cid in DISNEY_MANUFACTURER_IDS)
        or any(SERVICE_UUID in u.lower() for u in adv.service_data)
    )


async def cmd_scan(args) -> int:
    found = await BleakScanner.discover(timeout=args.time, return_adv=True)
    shown = 0
    for device, adv in sorted(found.values(), key=lambda item: -item[1].rssi):
        candidate = is_candidate(adv)
        name = adv.local_name or device.name or ""
        if args.name and args.name.lower() not in name.lower():
            continue
        if not (candidate or args.all or args.name):
            continue
        shown += 1
        emit(
            address=device.address,
            name=name,
            rssi=adv.rssi,
            magicband=candidate,
            service_uuids=adv.service_uuids,
            manufacturer_data={f"0x{k:04X}": v.hex() for k, v in adv.manufacturer_data.items()},
            service_data={k: v.hex() for k, v in adv.service_data.items()},
        )
    emit(summary="scan", total_seen=len(found), shown=shown, seconds=args.time)
    return 0


async def find(address: str, timeout: float):
    device = await BleakScanner.find_device_by_address(address, timeout=timeout)
    if device is None:
        emit(error="not_found", address=address, hint="run scan; device must be advertising and in range")
        sys.exit(2)
    return device


async def with_client(args, body) -> int:
    device = await find(args.address, args.scan_timeout)
    started = time.monotonic()
    async with BleakClient(device, timeout=args.connect_timeout) as client:
        emit(event="connected", address=args.address, seconds=round(time.monotonic() - started, 2))
        await body(client)
    emit(event="disconnected", address=args.address)
    return 0


async def subscribe(client: BleakClient) -> bool:
    char = client.services.get_characteristic(CHAR_NOTIFY_UUID)
    if char is None or not ({"notify", "indicate"} & set(char.properties)):
        return False

    def on_notify(_char, data: bytearray) -> None:
        emit(event="notify", hex=data.hex())

    await client.start_notify(CHAR_NOTIFY_UUID, on_notify)
    return True


async def write(client: BleakClient, char: str, data: bytes, label: str) -> None:
    props = client.services.get_characteristic(char).properties
    response = "write" in props
    await client.write_gatt_char(char, data, response=response)
    emit(event="write", what=label, char=char, hex=data.hex(), with_response=response)


async def cmd_inspect(args) -> int:
    async def body(client: BleakClient) -> None:
        for service in client.services:
            for char in service.characteristics:
                value = None
                if "read" in char.properties:
                    try:
                        value = (await client.read_gatt_char(char)).hex()
                    except Exception as e:  # noqa: BLE001 - report and keep going
                        value = f"<read failed: {e}>"
                emit(service=service.uuid, char=char.uuid, properties=char.properties, value=value)

    return await with_client(args, body)


async def cmd_color(args) -> int:
    async def body(client: BleakClient) -> None:
        listening = await subscribe(client)
        if not args.no_handshake:
            await write(client, CHAR_WRITE_UUID, GADGET_DISCOVER, "handshake")
        await write(client, CHAR_WRITE_UUID, color_packet(args.r, args.g, args.b, args.brightness), "color")
        if listening:
            await asyncio.sleep(args.listen)

    return await with_client(args, body)


async def cmd_write(args) -> int:
    async def body(client: BleakClient) -> None:
        listening = await subscribe(client)
        await write(client, args.char, bytes.fromhex(args.hex.replace(" ", "")), "raw")
        if listening:
            await asyncio.sleep(args.listen)

    return await with_client(args, body)


async def cmd_listen(args) -> int:
    async def body(client: BleakClient) -> None:
        if not await subscribe(client):
            emit(error="no_notify_char", char=CHAR_NOTIFY_UUID)
            return
        await asyncio.sleep(args.time)

    return await with_client(args, body)


def byte(value: str) -> int:
    n = int(value, 0)
    if not 0 <= n <= 255:
        raise argparse.ArgumentTypeError("must be 0-255")
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="find MagicBand/bucket advertisements")
    scan.add_argument("--time", type=float, default=8.0)
    scan.add_argument("--all", action="store_true", help="show every device, not just MagicBand candidates")
    scan.add_argument("--name", help="show devices whose name contains this")

    def connected(name: str, help: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help)
        p.add_argument("address")
        p.add_argument("--scan-timeout", type=float, default=10.0)
        p.add_argument("--connect-timeout", type=float, default=10.0)
        return p

    connected("inspect", "connect and dump services/characteristics")

    color = connected("color", "handshake + set RGB color")
    for c in ("r", "g", "b"):
        color.add_argument(c, type=byte)
    color.add_argument("--brightness", type=byte, default=255)
    color.add_argument("--no-handshake", action="store_true")
    color.add_argument("--listen", type=float, default=2.0, help="seconds to wait for notifications")

    raw = connected("write", "write raw hex to a characteristic")
    raw.add_argument("hex")
    raw.add_argument("--char", default=CHAR_WRITE_UUID)
    raw.add_argument("--listen", type=float, default=2.0)

    listen = connected("listen", "print notifications")
    listen.add_argument("--time", type=float, default=10.0)

    args = parser.parse_args()
    handler = {"scan": cmd_scan, "inspect": cmd_inspect, "color": cmd_color,
               "write": cmd_write, "listen": cmd_listen}[args.cmd]
    try:
        return asyncio.run(handler(args))
    except Exception as e:  # noqa: BLE001 - surface BLE errors as JSON
        emit(error=type(e).__name__, message=str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
