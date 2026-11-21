"""Per-zone colour timeline from probe frames, by unmixing against single-zone templates.

    zones.py --templates TPL_DIR --dark DARK_DIR DIR [DIR ...]

TPL_DIR holds z5w-slot1..5 probe dirs (each zone lit white alone, hold timing); DARK_DIR is a
probe dir whose last frame is the toy fully off. Every frame's (frame - dark) image is fit, per
colour channel, as a non-negative mix of the five zone templates. That gives an RGB estimate per
zone, printed as letters: R O Y G C B P M W, '.' = off. Zones: 1 bottom, 2 LL+UR, 3 L+R, 4 UL+LR, 5 top.
"""
import argparse
import colorsys
import glob
import os

import numpy as np
from PIL import Image
from scipy.optimize import nnls

# Crop of the wheel (x0, y0, x1, y1). Override with ZONES_BOX="x0,y0,x1,y1" when the framing changes.
BOX = tuple(float(v) for v in os.environ.get("ZONES_BOX", "0.31,0.42,0.64,0.99").split(","))
SIZE = (48, 48)


def load(path):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    im = im.crop((int(BOX[0] * W), int(BOX[1] * H), int(BOX[2] * W), int(BOX[3] * H))).resize(SIZE)
    return np.asarray(im, dtype=float)


def last(d):
    return sorted(glob.glob(os.path.join(d, "frame-*.jpg")))[-1]


def letter(rgb):
    r, g, b = (min(max(c, 0), 255) / 255 for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if v < 0.18:
        return "."
    if s < 0.30:
        return "W"
    deg = h * 360
    for limit, name in ((15, "R"), (40, "O"), (70, "Y"), (160, "G"), (200, "C"), (255, "B"), (290, "P"), (340, "M"), (361, "R")):
        if deg < limit:
            return name


ZONE_NAMES = ["bottom", "LL+UR", "L+R", "UL+LR", "top"]


def build_model(templates, dark_dir):
    """Templates are scaled so a zone as bright as its white template unmixes to ~255 (diffused LEDs are dim)."""
    dark = load(last(dark_dir))
    tpl = []
    for k in range(1, 6):
        rgb = (load(last(os.path.join(templates, f"z5w-slot{k}"))) - dark).clip(0)
        t = rgb.mean(axis=2)
        tpl.append(t.ravel() / 255)
    return dark, (np.stack(tpl, axis=1))


def unmix(path, dark, model):
    """Return a 5x3 array: estimated RGB per zone for one frame."""
    A = model
    diff = (load(path) - dark).clip(0)
    return np.array([nnls(A, diff[:, :, c].ravel())[0] for c in range(3)]).T


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--templates", required=True)
    p.add_argument("--dark", required=True)
    p.add_argument("--rgb", action="store_true", help="also print per-zone RGB of the last frame")
    p.add_argument("dirs", nargs="+")
    a = p.parse_args()
    dark, A = build_model(a.templates, a.dark)
    for d in a.dirs:
        frames = sorted(glob.glob(os.path.join(d, "frame-*.jpg")))
        est = [unmix(f, dark, A) for f in frames]
        print("==", os.path.basename(d.rstrip("/")), f"({len(frames)} frames)")
        for k, name in enumerate(ZONE_NAMES):
            print(f"  {name:>6} " + "".join(letter(e[k]) for e in est))
        if a.rgb:
            print("  last-frame rgb:", [[int(v) for v in z] for z in est[-1]])


if __name__ == "__main__":
    main()
