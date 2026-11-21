---
name: camera
description: Take a photo, a burst of photos, or a short video with the MacBook's built-in camera (or another attached camera) and look at the result. Use when you need to visually check something in the physical world, especially whether a MagicBand+ or Popcorn Bucket's lights changed color/turned on after sending a BLE command, or when the user asks you to "take a picture", "look at the bucket", or "record a video".
---

# Camera

`scripts/camera` is a small AVFoundation CLI (Swift, no dependencies). It compiles itself into
`scripts/.build/` on first run or after `camera.swift` is edited, which takes about 20s.

```bash
CAM=.claude/skills/camera/scripts/camera   # run from the repo root
$CAM list                                  # list cameras (* = default)
$CAM photo -o "$OUT/before.jpg"            # one still
$CAM burst --count 5 --interval 1 -o "$OUT/burst"   # N stills, frame-000.jpg ...
$CAM video --duration 5 --frames 4 -o "$OUT/clip.mov" # movie + N evenly spaced stills
```

Set `$OUT` to the session scratchpad directory. Without `-o`, files go to `$TMPDIR/claude-camera/`.

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--warmup s` | 1.5 | Time for auto-exposure and white balance to settle before capturing |
| `--max-width px` | 1280 | Downscale saved stills (0 = full 1920x1080) |
| `--roi x,y,w,h` | whole frame | Normalized region (top-left origin) used for the color stats |
| `--device name\|id` | system default | Camera to use (substring of the name, or the unique ID) |

## Output

Every saved still prints one JSON line to stdout:

```json
{"path":".../before.jpg","mean_rgb":[166,151,135],"luma":153.7,"roi":[0.4,0.3,0.2,0.3],"width":1920,"height":1080,"time":"..."}
```

`width`/`height` give the source resolution. `mean_rgb`/`luma` are averages over the ROI. Video
mode first prints `{"path":...,"duration":...}` and then one line per extracted frame, each with
`video_time`.

**To actually see an image, `Read` the `.jpg` path.** You can't view a `.mov` directly, so pass
`--frames N` to get stills from it.

## Feedback loop: did the bucket change?

1. **Frame it.** Take a `photo` and `Read` it to find the bucket/band. Estimate a tight `--roi`
   around the light area and reuse that ROI for the rest of the session.
2. **Baseline.** `photo --roi ... -o $OUT/before.jpg`.
3. **Act.** Send the BLE command (simulator, bleak script, or HA service call).
4. **Observe.** Allow about 0.5–1s for the device to react, then `photo --roi ... -o $OUT/after.jpg`.
   For animations or flashes, use `burst --interval 0.3` or `video --frames N`.
5. **Compare.** Treat a large jump in `mean_rgb`/`luma` (more than ~15 on any channel) as a change.
   The dominant channel should match the color you sent. Small drift (±5) is just auto-exposure
   noise. If the numbers are ambiguous, `Read` both images.

Tips:
- Auto-exposure will partially "correct" a bright LED. If changes look muted, compare the
  per-channel ratios, not just luma, or take the after-shot right away with `--warmup 0.5`.
- Lowering the room light makes the LEDs dominate the frame and the stats much clearer.
- The camera is single-user. If another app (FaceTime, Zoom, Photo Booth) holds it, capture fails
  with "could not open".

## Troubleshooting

- **"camera access denied"**: the terminal app running Claude Code needs Camera permission
  (System Settings → Privacy & Security → Camera). Restart the terminal after granting it. The
  first ever run triggers the macOS permission prompt, which the user has to accept.
- **"no frames received"**: the camera is in use or asleep. Retry once, then ask the user.
