#!/bin/sh
set -eu

experiment_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skynet_root=$(CDPATH= cd -- "$experiment_dir/../.." && pwd)
png_path="$experiment_dir/renders/cand-20260831-003-c-v1.png"
jpg_path="$experiment_dir/renders/cand-20260831-003-c-v1.jpg"

cd "$skynet_root"

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "gradients=size=1080x1080:c0=0x0C0E12:c1=0x172934:x0=1030:y0=410:x1=40:y1=1020:type=radial:duration=1:speed=0" \
  -i assets/natal/logo-natal.png \
  -filter_complex_script experiments/exp-20260831-003/filtergraph.ffscript \
  -map '[out]' -frames:v 1 "$png_path"

ffmpeg -hide_banner -loglevel error -y \
  -i "$png_path" -frames:v 1 -q:v 2 -pix_fmt yuvj420p "$jpg_path"
