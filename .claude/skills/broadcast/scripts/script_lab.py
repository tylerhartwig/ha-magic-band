"""Unattended script-decoding lab: broadcast each trial packet, record the toy, score the animation.

    script_lab.py --templates TPL --dark DARK --batch trials.jsonl --out DIR [--secs 4] [--fps 10]

trials.jsonl: {"name": ..., "hex": "<bytes after 83 01>"} per line. Each trial: advertise 1.5 s (one
serial connection for the whole run), record --secs of video, unmix every frame into per-zone
RGB, then append to DIR/results.jsonl:
  activity  - mean per-zone temporal std (high = animated; the static fallback scores low)
  letters   - per-zone colour letter per frame
  mean_rgb  - per-zone mean RGB
Frames are deleted unless --keep.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from broadcast import command, find_port, open_port  # noqa: E402
from zones import ZONE_NAMES, build_model, letter, unmix  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
CAMERA = os.path.join(ROOT, ".claude/skills/camera/scripts/camera")

p = argparse.ArgumentParser()
p.add_argument("--templates", required=True)
p.add_argument("--dark", required=True)
p.add_argument("--batch", required=True)
p.add_argument("--out", required=True)
p.add_argument("--secs", type=float, default=4)
p.add_argument("--fps", type=int, default=10)
p.add_argument("--adv", type=float, default=1.5)
p.add_argument("--keep", action="store_true")
p.add_argument("--reset", help="hex sent (and held --reset-secs) before each trial, e.g. a known colour")
p.add_argument("--reset-secs", type=float, default=1.5)
p.add_argument("--preroll", type=float, default=0,
               help="start recording this many seconds before the broadcast (covers camera start-up)")
p.add_argument("--series", action="store_true", help="store per-frame zone RGB in the results")
p.add_argument("--health", type=int, default=3,
               help="with --reset and --preroll: stop after this many trials in a row whose pre-broadcast frames "
                    "don't show the reset colour (toy off / battery flat). 0 disables")
a = p.parse_args()

dark, A = build_model(a.templates, a.dark)
os.makedirs(a.out, exist_ok=True)
log = open(os.path.join(a.out, "results.jsonl"), "a")
port = open_port(find_port())
trials = [json.loads(l) for l in open(a.batch) if l.strip() and not l.startswith("#")]
for t in trials:  # an E9 length byte that cuts off the body silently changes what's being tested
    b = bytes.fromhex(t["hex"])
    if b[:1] == b"\xe9" and b[1] != len(b) - 2 and not t.get("len_ok"):
        sys.exit(f"{t['name']}: E9 length byte {b[1]:#04x} but {len(b) - 2} body bytes (set len_ok to allow)")


def reset_reference():
    """Show the reset colour once and photograph it, so later trials can check the toy still responds."""
    command(port, "adv 8301%s %d 30" % (a.reset.lower(), int(a.reset_secs * 1000)))
    time.sleep(a.reset_secs + 0.3)
    path = os.path.join(a.out, "reset-reference.jpg")
    subprocess.run([CAMERA, "photo", "--warmup", "1.0", "-o", path], stdout=subprocess.DEVNULL, check=False)
    ref = unmix(path, dark, A)
    if ref.max() < 40:
        sys.exit("toy didn't show the reset colour: is it on and charged?")
    return ref


check = a.health and a.reset and a.preroll
ref = reset_reference() if check else None
misses = 0
for i, t in enumerate(trials):
    d = os.path.join(a.out, t["name"])
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    if a.reset:
        command(port, "adv 8301%s %d 30" % (a.reset.lower(), int(a.reset_secs * 1000)))
        time.sleep(a.reset_secs + 0.3)
    cam = [CAMERA, "video", "--duration", str(a.secs), "--frames", str(int(a.secs * a.fps)),
           "--warmup", "0.5", "--max-width", "640", "-o", os.path.join(d, "clip.mov")]
    if a.preroll:
        rec = subprocess.Popen(cam, stdout=subprocess.DEVNULL)
        time.sleep(a.preroll)
        reply = command(port, "adv 8301%s %d 30" % (t["hex"].lower(), int(a.adv * 1000)))
        rec.wait()
    else:
        reply = command(port, "adv 8301%s %d 30" % (t["hex"].lower(), int(a.adv * 1000)))
        time.sleep(a.adv)
        subprocess.run(cam, stdout=subprocess.DEVNULL, check=False)
    frames = sorted(glob.glob(os.path.join(d, "clip-frame-*.jpg")))
    est = np.array([unmix(f, dark, A) for f in frames]) if frames else np.zeros((1, 5, 3))
    activity = float(est.std(axis=0).sum(axis=1).mean())
    if check:
        # The first frames precede the broadcast, so they should match the reset reference.
        misses = misses + 1 if np.abs(est[:3].mean(axis=0) - ref).max() > 60 else 0
        if misses >= a.health:
            command(port, "stop")
            sys.exit(f"stopped before {t['name']}: the reset colour hasn't shown for {misses} trials "
                     f"(toy off or battery flat?). The last {misses - 1} logged trials are suspect; rerun from {t['name']}'s "
                     f"predecessors.")
    res = {
        "name": t["name"], "hex": t["hex"], "reply": reply.split(" ms=")[0], "activity": round(activity, 1),
        "letters": {z: "".join(letter(e[k]) for e in est) for k, z in enumerate(ZONE_NAMES)},
        "mean_rgb": {z: [int(v) for v in est[:, k].mean(axis=0)] for k, z in enumerate(ZONE_NAMES)},
    }
    if a.series:
        res["series"] = np.clip(est, 0, 255).round().astype(int).tolist()
    log.write(json.dumps(res) + "\n")
    log.flush()
    print(f"[{i + 1}/{len(trials)}] {t['name']:<24} act={res['activity']:6.1f} " +
          " ".join(f"{z[:3]}:{res['letters'][z][::2]}" for z in ZONE_NAMES), flush=True)
    if not a.keep:
        shutil.rmtree(d, ignore_errors=True)
    else:
        os.remove(os.path.join(d, "clip.mov")) if os.path.exists(os.path.join(d, "clip.mov")) else None
command(port, "stop")
