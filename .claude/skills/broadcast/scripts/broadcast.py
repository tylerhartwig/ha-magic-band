"""Drive the ESP32 BLE advertiser (esp32/main.py) over serial.

    broadcast.py ping
    broadcast.py send CC0300000 [--seconds 2] [--interval-ms 30] [--no-cid]
    broadcast.py raw 0201060aff8301... [--seconds 2]
    broadcast.py stop
    broadcast.py seq "CC03000000:0.5" "E905002E0EF5B0:3"   # payload:seconds, run back to back

Payloads for send/seq are the bytes after Disney's company ID; 83 01 (0x0183) is prepended
unless --no-cid. Each step prints one JSON line.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time

import serial

DISNEY_CID = "8301"


def emit(**obj) -> None:
    print(json.dumps(obj, sort_keys=True), flush=True)


def find_port() -> str:
    ports = sorted(glob.glob("/dev/cu.usbserial-*") + glob.glob("/dev/cu.usbmodem*"))
    if not ports:
        emit(error="no_port", hint="plug in the ESP32 (UART port) or pass --port")
        sys.exit(2)
    return ports[0]


def open_port(path: str) -> serial.Serial:
    # Keep DTR/RTS low: on CP2102 dev boards toggling them resets the ESP32.
    port = serial.Serial()
    port.port, port.baudrate, port.timeout = path, 115200, 2
    port.dtr = port.rts = False
    port.open()
    # Opening the CP2102 still resets this board, so wait for main.py's banner. If nothing
    # arrives quickly the board wasn't reset and is already listening.
    deadline, quiet = time.monotonic() + 4, time.monotonic() + 0.5
    while time.monotonic() < deadline:
        line = port.readline().decode(errors="replace").strip()
        if line == "ok ready":
            break
        if line:
            quiet = time.monotonic() + 0.5
        elif time.monotonic() > quiet:
            break
    return port


def command(port: serial.Serial, line: str) -> str:
    port.write((line + "\r\n").encode())
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        reply = port.readline().decode(errors="replace").strip()
        if reply.startswith(("ok", "err")) and reply != "ok ready":  # skip the boot banner
            return reply
    return "err timeout (is esp32/main.py running? re-upload esp32/main.py with mpremote, see SKILL.md)"


def clean_hex(payload: str) -> str:
    h = payload.replace(" ", "").replace(":", "").lower()
    bytes.fromhex(h)  # validate
    return h


def send(port, payload: str, seconds: float, interval_ms: int, cid: bool, raw: bool = False) -> bool:
    h = clean_hex(payload)
    if cid and not raw:
        h = DISNEY_CID + h
    reply = command(port, f"{'raw' if raw else 'adv'} {h} {int(seconds * 1000)} {interval_ms}")
    emit(cmd="raw" if raw else "adv", data=h, seconds=seconds, reply=reply)
    return reply.startswith("ok")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping")
    sub.add_parser("stop")
    for name in ("send", "raw"):
        p = sub.add_parser(name)
        p.add_argument("hex")
        p.add_argument("--seconds", type=float, default=2.0, help="0 = until stop")
        p.add_argument("--interval-ms", type=int, default=30)
        p.add_argument("--no-cid", action="store_true")
        p.add_argument("--wait", action="store_true", help="block until the advertisement ends")
    seq = sub.add_parser("seq")
    seq.add_argument("steps", nargs="+", help="HEX:SECONDS")
    seq.add_argument("--interval-ms", type=int, default=30)
    seq.add_argument("--no-cid", action="store_true")
    args = parser.parse_args()

    port = open_port(args.port or find_port())
    if args.cmd in ("ping", "stop"):
        reply = command(port, args.cmd)
        emit(cmd=args.cmd, reply=reply)
        return 0 if reply.startswith("ok") else 1
    if args.cmd in ("send", "raw"):
        ok = send(port, args.hex, args.seconds, args.interval_ms, not args.no_cid, raw=args.cmd == "raw")
        if ok and args.wait and args.seconds > 0:
            time.sleep(args.seconds)
        return 0 if ok else 1
    for step in args.steps:
        payload, _, secs = step.partition(":")
        seconds = float(secs or 2)
        if not send(port, payload, seconds, args.interval_ms, not args.no_cid):
            return 1
        time.sleep(seconds)
    command(port, "stop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
