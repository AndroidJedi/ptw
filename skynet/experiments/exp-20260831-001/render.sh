#!/bin/sh

set -eu

experiment_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skynet_root=$(CDPATH= cd -- "$experiment_root/../.." && pwd)
background="$experiment_root/assets/background-v1.png"
logo="$skynet_root/assets/natal/logo-natal.png"
font="$skynet_root/assets/natal/inter.ttf"
copy_root="$experiment_root/copy"
render_root="$experiment_root/renders"
master="$render_root/cand-20260831-001-a-v1.png"
delivery="$render_root/cand-20260831-001-a-v1.jpg"

test "$(shasum -a 256 "$background" | awk '{print $1}')" = \
  "7e0303fe38679464c47837b2dc6c7505ef871596fd356bba0d0eec26867a16e3"
test "$(shasum -a 256 "$logo" | awk '{print $1}')" = \
  "f465a0e11be3c1ff1943bcc1bcd19246a9a54957fd5c1c6162081aec9a59c8ba"
test "$(shasum -a 256 "$font" | awk '{print $1}')" = \
  "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031"

mkdir -p "$render_root"

filter="[0:v]scale=1080:1080:flags=lanczos,format=rgba[photo];\
gradients=s=1080x1080:c0=0x0C0E12F2:c1=0x0C0E1200:x0=0:y0=0:x1=860:y1=0:d=1,format=rgba[shade];\
[photo][shade]overlay=0:0,\
drawbox=x=64:y=56:w=224:h=78:color=0xF4F6FA@0.96:t=fill[base];\
[1:v]scale=180:-1:flags=lanczos[mark];\
[base][mark]overlay=84:68,\
drawtext=fontfile='$font':textfile='$copy_root/eyebrow.txt':fontcolor=0x87D0DD:fontsize=24:borderw=0.35:bordercolor=0x87D0DD:x=64:y=180,\
drawtext=fontfile='$font':textfile='$copy_root/headline.txt':fontcolor=0xF4F6FA:fontsize=82:line_spacing=-2:borderw=1.1:bordercolor=0xF4F6FA:x=64:y=222,\
drawtext=fontfile='$font':textfile='$copy_root/resolution.txt':fontcolor=0x43BDD3:fontsize=47:borderw=0.8:bordercolor=0x43BDD3:x=64:y=416,\
drawbox=x=64:y=486:w=92:h=5:color=0x43BDD3:t=fill,\
drawtext=fontfile='$font':textfile='$copy_root/primary.txt':fontcolor=0xF4F6FA:fontsize=28:line_spacing=10:borderw=0.25:bordercolor=0xF4F6FA:x=64:y=522,\
drawbox=x=64:y=758:w=390:h=118:color=0xF4F6FA@0.96:t=fill,\
drawtext=fontfile='$font':textfile='$copy_root/offer-label.txt':fontcolor=0x596274:fontsize=18:borderw=0.2:bordercolor=0x596274:x=86:y=775,\
drawtext=fontfile='$font':textfile='$copy_root/offer.txt':fontcolor=0x0C0E12:fontsize=29:borderw=0.75:bordercolor=0x0C0E12:x=86:y=815,\
drawbox=x=64:y=902:w=430:h=92:color=0x43BDD3@0.98:t=fill,\
drawtext=fontfile='$font':textfile='$copy_root/cta.txt':fontcolor=0x0C0E12:fontsize=28:borderw=0.75:bordercolor=0x0C0E12:x=86:y=932"

ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -i "$background" -loop 1 -i "$logo" \
  -filter_complex "$filter" -frames:v 1 -pix_fmt rgba "$master"

ffmpeg -hide_banner -loglevel error -y -i "$master" \
  -frames:v 1 -c:v mjpeg -q:v 2 -pix_fmt yuvj444p "$delivery"

sips -g pixelWidth -g pixelHeight -g format -g hasAlpha "$master" "$delivery"
shasum -a 256 "$master" "$delivery"
