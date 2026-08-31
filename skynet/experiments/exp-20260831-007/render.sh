#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
swift_dir="$root/runtime/swift-exp007"
module_cache="$swift_dir/module-cache"
temporary_dir="$swift_dir/tmp"
renderer="$swift_dir/render-exp007"
png="$script_dir/renders/cand-20260831-007-g-v1.png"
jpg="$script_dir/renders/cand-20260831-007-g-v1.jpg"

mkdir -p "$swift_dir" "$script_dir/renders"

if [ ! -x "$renderer" ] || [ "$script_dir/render.swift" -nt "$renderer" ]; then
  mkdir -p "$module_cache" "$temporary_dir"
  TMPDIR="$temporary_dir" \
  SWIFT_MODULECACHE_PATH="$module_cache" \
  CLANG_MODULE_CACHE_PATH="$module_cache" \
  /usr/bin/swiftc -module-cache-path "$module_cache" \
    "$script_dir/render.swift" -o "$renderer"
fi

"$renderer" "$png"

ffmpeg -hide_banner -loglevel error -y \
  -i "$png" -frames:v 1 -q:v 2 -pix_fmt yuvj420p "$jpg"
