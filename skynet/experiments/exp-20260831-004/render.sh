#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
cd "$root"

mkdir -p experiments/exp-20260831-004/renders
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=0x071118:s=1080x1080:d=1" \
  -i assets/natal/logo-natal.png \
  -filter_complex_script experiments/exp-20260831-004/filtergraph.ffscript \
  -map '[out]' -frames:v 1 -c:v png -pix_fmt rgb24 \
  experiments/exp-20260831-004/renders/cand-20260831-004-d-v1.png

ffmpeg -hide_banner -loglevel error -y \
  -i experiments/exp-20260831-004/renders/cand-20260831-004-d-v1.png \
  -frames:v 1 -q:v 2 -pix_fmt yuvj420p \
  experiments/exp-20260831-004/renders/cand-20260831-004-d-v1.jpg
