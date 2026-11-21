"""Tile a crop of one frame per probe trial into a labelled contact sheet.

    contact_sheet.py OUT.jpg DIR/name1 DIR/name2 ... [--frame -1] [--box 0.30,0.62,0.40,0.38]
"""
import argparse
import glob
import os

from PIL import Image, ImageDraw

p = argparse.ArgumentParser()
p.add_argument("out")
p.add_argument("dirs", nargs="+")
p.add_argument("--frame", type=int, default=-1, help="frame index within each trial (default last)")
p.add_argument("--box", default="0.31,0.42,0.33,0.57", help="normalized crop x,y,w,h")
p.add_argument("--cols", type=int, default=8)
p.add_argument("--tile", type=int, default=200)
p.add_argument("--timeline", default=None, help="START:END:STEP frames per dir, one row per dir")
p.add_argument("--wrap", type=int, default=0, help="with --timeline: wrap rows at this many columns")
a = p.parse_args()

x, y, w, h = map(float, a.box.split(","))
tiles = []
picks = []
for d in a.dirs:
    frames = sorted(glob.glob(os.path.join(d, "frame-*.jpg")))
    if not frames:
        continue
    if a.timeline:
        start, end, step = (int(v) for v in a.timeline.split(":"))
        chosen = frames[start:end:step]
        a.cols = a.wrap or len(chosen)
        picks += [(f, "%s f%d" % (os.path.basename(d.rstrip("/")), start + i * step)) for i, f in enumerate(chosen)]
    else:
        picks.append((frames[a.frame], os.path.basename(d.rstrip("/"))))
for path, label in picks:
    im = Image.open(path)
    W, H = im.size
    crop = im.crop((int(x * W), int(y * H), int((x + w) * W), int((y + h) * H)))
    crop.thumbnail((a.tile, a.tile))
    tiles.append((label, crop))

rows = (len(tiles) + a.cols - 1) // a.cols
tw, th = tiles[0][1].size
sheet = Image.new("RGB", (a.cols * tw, rows * (th + 18)), "black")
draw = ImageDraw.Draw(sheet)
for i, (name, crop) in enumerate(tiles):
    cx, cy = (i % a.cols) * tw, (i // a.cols) * (th + 18)
    sheet.paste(crop, (cx, cy + 18))
    draw.text((cx + 4, cy + 3), name, fill="white")
sheet.save(a.out, quality=90)
print(a.out)
