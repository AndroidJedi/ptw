#!/bin/sh
set -eu

evaluation_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skynet_root=$(CDPATH= cd -- "$evaluation_dir/../.." && pwd)
thumbnail_dir="$evaluation_dir/thumbnails"

mkdir -p "$thumbnail_dir"

input_a="$skynet_root/experiments/exp-20260831-001/renders/cand-20260831-001-a-v1.png"
input_b="$skynet_root/experiments/exp-20260831-002/renders/cand-20260831-002-b-v1.png"
input_c="$skynet_root/experiments/exp-20260831-003/renders/cand-20260831-003-c-v1.png"
input_d="$skynet_root/experiments/exp-20260831-004/renders/cand-20260831-004-d-v1.png"
input_f="$skynet_root/experiments/exp-20260831-006/renders/cand-20260831-006-f-v1.png"
input_g="$skynet_root/experiments/exp-20260831-007/renders/cand-20260831-007-g-v1.png"

derive_thumbnail() {
  source_path=$1
  output_path=$2
  ffmpeg -hide_banner -loglevel error -y \
    -i "$source_path" \
    -vf 'scale=120:120:flags=lanczos' \
    -frames:v 1 -fflags +bitexact -flags:v +bitexact "$output_path"
}

derive_thumbnail "$input_a" "$thumbnail_dir/cand-a-120.png"
derive_thumbnail "$input_b" "$thumbnail_dir/cand-b-120.png"
derive_thumbnail "$input_c" "$thumbnail_dir/cand-c-120.png"
derive_thumbnail "$input_d" "$thumbnail_dir/cand-d-120.png"
derive_thumbnail "$input_f" "$thumbnail_dir/cand-f-120.png"
derive_thumbnail "$input_g" "$thumbnail_dir/cand-g-120.png"

ffmpeg -hide_banner -loglevel error -y \
  -i "$input_a" -i "$input_b" -i "$input_c" \
  -i "$input_d" -i "$input_f" -i "$input_g" \
  -filter_complex \
  '[0:v]scale=360:360:flags=lanczos[a];[1:v]scale=360:360:flags=lanczos[b];[2:v]scale=360:360:flags=lanczos[c];[3:v]scale=360:360:flags=lanczos[d];[4:v]scale=360:360:flags=lanczos[f];[5:v]scale=360:360:flags=lanczos[g];[a][b][c][d][f][g]xstack=inputs=6:layout=0_0|360_0|720_0|0_360|360_360|720_360[v]' \
  -map '[v]' -frames:v 1 -fflags +bitexact -flags:v +bitexact \
  "$evaluation_dir/contact-360.png"

ffmpeg -hide_banner -loglevel error -y \
  -i "$thumbnail_dir/cand-a-120.png" \
  -i "$thumbnail_dir/cand-b-120.png" \
  -i "$thumbnail_dir/cand-c-120.png" \
  -i "$thumbnail_dir/cand-d-120.png" \
  -i "$thumbnail_dir/cand-f-120.png" \
  -i "$thumbnail_dir/cand-g-120.png" \
  -filter_complex \
  '[0:v][1:v][2:v][3:v][4:v][5:v]xstack=inputs=6:layout=0_0|120_0|240_0|0_120|120_120|240_120[grid];[grid]scale=1080:720:flags=neighbor[v]' \
  -map '[v]' -frames:v 1 -fflags +bitexact -flags:v +bitexact \
  "$evaluation_dir/contact-120-nearest.png"
