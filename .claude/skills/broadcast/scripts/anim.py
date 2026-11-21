"""Build (and optionally broadcast) a custom ferris-wheel animation packet.

    anim.py chase 15 02 19            # chase red, blue, green (palette indices, hex)
    anim.py twinkle 15 1B --slow       # twinkle red/white
    anim.py chase 15 02 --send 3       # also broadcast for 3 s via the ESP32

Packet: E9 <len> 00 <T> 0F <count<<5|c1> <A0|c2>... <op> [7B]
  op 30 = chase (colours rotate around the zones), 31 = twinkle. 7B slows the chase ~3x.
  T defaults to 8F (hold). Palette indices are in docs/ferris_wheel_protocol.md.
Prints the payload hex (after the 83 01 company ID).
"""
import argparse
import os
import sys

OPS = {"chase": 0x30, "twinkle": 0x31}


def build(effect: str, colours: list[int], timing: int = 0x8F, slow: bool = False) -> bytes:
    if not 1 <= len(colours) <= 5 or any(not 0 <= c < 32 for c in colours):
        raise ValueError("1-5 palette indices, each 00-1F")
    body = [len(colours) << 5 | colours[0]] + [0xA0 | c for c in colours[1:]]
    body += [OPS[effect]] + ([0x7B] if slow else [])
    data = [0x00, timing, 0x0F] + body
    return bytes([0xE9, len(data)] + data)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("effect", choices=OPS)
    p.add_argument("colours", nargs="+", type=lambda s: int(s, 16))
    p.add_argument("--slow", action="store_true")
    p.add_argument("--timing", type=lambda s: int(s, 16), default=0x8F)
    p.add_argument("--send", type=float, metavar="SECONDS", help="broadcast via the ESP32")
    a = p.parse_args()
    packet = build(a.effect, a.colours, a.timing, a.slow)
    print(packet.hex().upper())
    if a.send:
        sys.path.insert(0, os.path.dirname(__file__))
        from broadcast import find_port, open_port, send  # noqa: E402

        send(open_port(find_port()), packet.hex(), a.send, 30, cid=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
