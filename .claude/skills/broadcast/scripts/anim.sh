#!/bin/bash
# Record an animation: broadcast PAYLOAD (after 83 01) then capture SECONDS of video at 10 fps stills.
#   anim.sh OUT_DIR NAME PAYLOAD [SECONDS]
# Frames land in OUT_DIR/NAME/frame-NNN.jpg (same layout as probe.py, so zones.py/contact_sheet.py work).
set -euo pipefail
out="$1"; name="$2"; payload="$3"; secs="${4:-6}"
root="$(cd "$(dirname "$0")/../../../.." && pwd)"
mkdir -p "$out/$name"
rm -f "$out/$name"/frame-*.jpg
"$root/.claude/skills/broadcast/scripts/broadcast" send "$payload" --seconds 1.5 --wait >/dev/null
"$root/.claude/skills/camera/scripts/camera" video --duration "$secs" --frames "$(python3 -c "print(int($secs*10))")" \
  --warmup 0.5 -o "$out/$name/clip.mov" >/dev/null
for f in "$out/$name"/clip-frame-*.jpg; do mv "$f" "$out/$name/frame-${f##*-frame-}"; done
rm -f "$out/$name/clip.mov"
