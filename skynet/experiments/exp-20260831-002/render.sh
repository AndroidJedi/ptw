#!/bin/sh

set -eu

experiment_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skynet_root=$(CDPATH= cd -- "$experiment_root/../.." && pwd)
texture="$experiment_root/assets/native-texture-v1.png"
logo="$skynet_root/assets/natal/logo-natal.png"
font="$skynet_root/assets/natal/inter.ttf"
copy_root="$experiment_root/copy"
render_root="$experiment_root/renders"
master="$render_root/cand-20260831-002-b-v1.png"
delivery="$render_root/cand-20260831-002-b-v1.jpg"

test "$(shasum -a 256 "$logo" | awk '{print $1}')" = \
  "f465a0e11be3c1ff1943bcc1bcd19246a9a54957fd5c1c6162081aec9a59c8ba"
test "$(shasum -a 256 "$font" | awk '{print $1}')" = \
  "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031"

mkdir -p "$experiment_root/assets" "$render_root"

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "gradients=s=1080x1080:r=1:d=1:c0=0x0C0E12:c1=0x17303B:x0=0:y0=1080:x1=920:y1=0:seed=20260831" \
  -filter_complex "[0:v]drawgrid=w=18:h=18:t=1:c=0xF4F6FA@0.010,drawgrid=w=90:h=90:t=1:c=0x87D0DD@0.045,format=rgba" \
  -frames:v 1 -update 1 "$texture"

filter="[0:v]format=rgba,\
drawbox=x=64:y=56:w=224:h=78:color=0xF4F6FA@0.98:t=fill[base];\
[1:v]scale=180:-1:flags=lanczos[mark];\
[base][mark]overlay=84:68,\
drawtext=fontfile='$font':textfile='$copy_root/eyebrow.txt':fontcolor=0x87D0DD:fontsize=23:borderw=0.25:bordercolor=0x87D0DD:x=320:y=82,\
drawtext=fontfile='$font':textfile='$copy_root/headline.txt':fontcolor=0xF4F6FA:fontsize=84:line_spacing=-3:borderw=1.15:bordercolor=0xF4F6FA:x=64:y=184,\
drawtext=fontfile='$font':textfile='$copy_root/primary.txt':fontcolor=0xD9DEE8:fontsize=29:borderw=0.25:bordercolor=0xD9DEE8:x=64:y=390,\
drawbox=x=64:y=490:w=270:h=108:color=0x43BDD3@0.18:t=fill,\
drawbox=x=64:y=490:w=270:h=108:color=0x87D0DD@0.70:t=2,\
drawbox=x=350:y=490:w=270:h=108:color=0xF4F6FA@0.10:t=fill,\
drawbox=x=350:y=490:w=270:h=108:color=0xF4F6FA@0.45:t=2,\
drawbox=x=636:y=490:w=270:h=108:color=0xA3ADBD@0.10:t=fill,\
drawbox=x=636:y=490:w=270:h=108:color=0xA3ADBD@0.38:t=2,\
drawtext=fontfile='$font':textfile='$copy_root/status-active.txt':fontcolor=0x87D0DD:fontsize=27:borderw=0.35:bordercolor=0x87D0DD:x=92:y=530,\
drawtext=fontfile='$font':textfile='$copy_root/status-risk.txt':fontcolor=0xF4F6FA:fontsize=27:borderw=0.35:bordercolor=0xF4F6FA:x=378:y=530,\
drawtext=fontfile='$font':textfile='$copy_root/status-churn.txt':fontcolor=0xA3ADBD:fontsize=27:borderw=0.35:bordercolor=0xA3ADBD:x=664:y=530,\
drawbox=x=64:y=628:w=92:h=5:color=0x43BDD3:t=fill,\
drawbox=x=64:y=656:w=952:h=222:color=0xF4F6FA@0.98:t=fill,\
drawtext=fontfile='$font':textfile='$copy_root/offer-label.txt':fontcolor=0x596274:fontsize=18:borderw=0.2:bordercolor=0x596274:x=92:y=692,\
drawtext=fontfile='$font':textfile='$copy_root/offer.txt':fontcolor=0x0C0E12:fontsize=65:borderw=1.1:bordercolor=0x0C0E12:x=92:y=752,\
drawbox=x=64:y=926:w=460:h=90:color=0x43BDD3@0.99:t=fill,\
drawtext=fontfile='$font':textfile='$copy_root/cta.txt':fontcolor=0x0C0E12:fontsize=28:borderw=0.75:bordercolor=0x0C0E12:x=90:y=956,\
drawtext=fontfile='$font':textfile='$copy_root/support.txt':fontcolor=0xA3ADBD:fontsize=19:line_spacing=7:borderw=0.2:bordercolor=0xA3ADBD:x=565:y=936"

ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -i "$texture" -loop 1 -i "$logo" \
  -filter_complex "$filter" -frames:v 1 -pix_fmt rgba "$master"

ffmpeg -hide_banner -loglevel error -y -i "$master" \
  -frames:v 1 -c:v mjpeg -q:v 2 -pix_fmt yuvj444p "$delivery"

sips -g pixelWidth -g pixelHeight -g format -g hasAlpha "$texture" "$master" "$delivery"
shasum -a 256 "$texture" "$master" "$delivery"
