"""Closed-loop probe: broadcast Disney packets from the ESP32 and measure the toy on camera.

    probe.py --name red "CC03000000:0.5" "E905002E0EF5B0:3"
    probe.py --batch trials.jsonl      # one {"name":..., "steps":[...]} per line

Each trial: capture --pre baseline frames, run the broadcast steps (HEX:SECONDS, after the
83 01 company ID) while capturing, then keep capturing. Prints one JSON summary per trial and
appends it to --log. The frames are kept so the interesting ones can be viewed.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(__file__))
from broadcast import DISNEY_CID, command, find_port, open_port  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
CAMERA = os.path.join(ROOT, ".claude/skills/camera/scripts/camera")


def chroma(rgb):
    """RGB normalized to sum 1, so exposure changes don't look like color changes."""
    total = sum(rgb) or 1
    return [round(c / total, 3) for c in rgb]


def run_trial(port, name, steps, args):
    out_dir = os.path.join(args.out, name)
    total = args.pre + args.post
    cam = subprocess.Popen(
        [CAMERA, "burst", "--count", str(total), "--interval", str(args.interval),
         "--roi", args.roi, "--warmup", "1.0", "-o", out_dir],
        stdout=subprocess.PIPE, text=True,
    )
    frames = []
    sent_at = None

    def read_frames():
        for line in cam.stdout:
            d = json.loads(line)
            d["t"] = time.monotonic()
            frames.append(d)

    reader = threading.Thread(target=read_frames)
    reader.start()
    while len(frames) < args.pre and cam.poll() is None:
        time.sleep(0.02)
    sent_at = time.monotonic()
    replies = []
    for step in steps:
        payload, _, secs = step.partition(":")
        seconds = float(secs or 2)
        if payload.lower() == "wait":  # "wait:SECONDS" = silence between steps
            time.sleep(seconds)
            continue
        h = DISNEY_CID + payload.replace(" ", "").lower()
        replies.append(command(port, f"adv {h} {int(seconds * 1000)} {args.adv_interval}"))
        time.sleep(seconds)
    command(port, "stop")
    cam.wait()
    reader.join()

    base = frames[: args.pre]
    base_rgb = [round(sum(f["mean_rgb"][i] for f in base) / len(base), 1) for i in range(3)]
    base_ch = chroma(base_rgb)
    series = []
    peak = {"delta": 0}
    for f in frames:
        rgb = f["mean_rgb"]
        dl = round(f["luma"] - sum(b["luma"] for b in base) / len(base), 1)
        dc = round(sum(abs(a - b) for a, b in zip(chroma(rgb), base_ch)) * 100, 1)
        rel = round(f["t"] - sent_at, 1)
        series.append([rel, rgb, dl, dc])
        score = abs(dl) + 3 * dc
        if rel > 0 and score > peak["delta"]:
            peak = {"delta": round(score, 1), "t": rel, "rgb": rgb, "dluma": dl, "dchroma": dc,
                    "frame": f["path"]}
    # Settled colour: per-channel median of frames from --settle seconds after sending.
    late = sorted((f["mean_rgb"] for f in frames if f["t"] - sent_at >= args.settle), key=sum)
    steady = None
    if late:
        steady = [sorted(c[i] for c in late)[len(late) // 2] for i in range(3)]
        spread = max(max(c[i] for c in late) - min(c[i] for c in late) for i in range(3))
    # Noise floor = spread among baseline frames.
    noise = max((abs(b["luma"] - base[0]["luma"]) for b in base), default=0)
    result = {
        "name": name, "steps": steps, "replies": [r.split(" ms=")[0] for r in replies],
        "baseline_rgb": base_rgb, "noise_luma": round(noise, 1), "peak": peak,
        "changed": peak["delta"] > max(15, 4 * noise + 6),
        "steady_rgb": steady, "steady_chroma": chroma(steady) if steady else None,
        "steady_spread": spread if late else None,
        "series": series if args.series else None,
    }
    print(json.dumps(result), flush=True)
    with open(args.log, "a") as fh:
        fh.write(json.dumps(result) + "\n")
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("steps", nargs="*")
    p.add_argument("--name", default="trial")
    p.add_argument("--batch")
    p.add_argument("--port")
    p.add_argument("--roi", default="0.32,0.44,0.31,0.53")
    p.add_argument("--pre", type=int, default=3)
    p.add_argument("--post", type=int, default=14)
    p.add_argument("--interval", type=float, default=0.35)
    p.add_argument("--adv-interval", type=int, default=30, help="BLE advertising interval ms")
    p.add_argument("--gap", type=float, default=3.0, help="seconds between batch trials")
    p.add_argument("--series", action="store_true", help="include per-frame series")
    p.add_argument("--settle", type=float, default=1.2, help="seconds after send to start 'steady'")
    p.add_argument("--out", default=os.environ.get("PROBE_OUT", "/tmp/probe"))
    p.add_argument("--log", default=None)
    args = p.parse_args()
    args.log = args.log or os.path.join(args.out, "results.jsonl")
    os.makedirs(args.out, exist_ok=True)

    trials = []
    if args.batch:
        with open(args.batch) as fh:
            trials = [json.loads(l) for l in fh if l.strip() and not l.startswith("#")]
    else:
        trials = [{"name": args.name, "steps": args.steps}]

    port = open_port(args.port or find_port())
    for i, t in enumerate(trials):
        if i:
            time.sleep(t.get("gap", args.gap))
        run_trial(port, t["name"], t["steps"], args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
