"""ESP32 (MicroPython) BLE advertiser driven by line commands over the UART/USB serial port.

Flash once; after that every advertisement is chosen at runtime from the Mac:
    ping                         -> "ok pong"
    adv <hex> [ms] [interval_ms] -> advertise manufacturer data <hex> (include the company ID,
                                    e.g. 8301cc03000000). ms=0 means until stopped. Default 2000.
    raw <hex> [ms] [interval_ms] -> advertise <hex> as the complete advertising payload
    stop                         -> stop advertising
Every command answers with exactly one line starting with "ok" or "err".
Press Ctrl-C on the serial console to drop to the REPL (e.g. for mpremote).
"""
import sys

import bluetooth
from machine import Timer

ble = bluetooth.BLE()
ble.active(True)
timer = Timer(0)
state = {"payload": None}


def stop(_t=None):
    ble.gap_advertise(None)
    state["payload"] = None


def start(payload, ms, interval_ms):
    if len(payload) > 31:
        raise ValueError("advertisement is %d bytes (max 31)" % len(payload))
    timer.deinit()
    ble.gap_advertise(None)
    ble.gap_advertise(interval_ms * 1000, adv_data=payload, connectable=False)
    state["payload"] = payload
    if ms > 0:
        timer.init(mode=Timer.ONE_SHOT, period=ms, callback=stop)


def handle(line):
    parts = line.split()
    if not parts:
        return None
    cmd, args = parts[0].lower(), parts[1:]
    if cmd == "ping":
        return "ok pong"
    if cmd == "stop":
        timer.deinit()
        stop()
        return "ok stopped"
    if cmd in ("adv", "raw"):
        if not args:
            return "err missing hex"
        data = bytes.fromhex(args[0])
        ms = int(args[1]) if len(args) > 1 else 2000
        interval_ms = int(args[2]) if len(args) > 2 else 30
        if cmd == "adv":
            # Flags (LE general discoverable, no BR/EDR) + manufacturer specific data.
            payload = b"\x02\x01\x06" + bytes([len(data) + 1, 0xFF]) + data
        else:
            payload = data
        start(payload, ms, interval_ms)
        return "ok adv %s ms=%d interval=%d" % (payload.hex(), ms, interval_ms)
    return "err unknown command " + cmd


print("ok ready")
while True:
    line = sys.stdin.readline()
    try:
        reply = handle(line.strip())
    except Exception as e:
        reply = "err %s" % e
    if reply:
        print(reply)
