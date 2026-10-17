#!/usr/bin/env bash
# Запекает матовое стекло hero в видео и постер, чтобы браузер не делал это через backdrop-filter.
# Повторяет CSS: backdrop-filter: blur(5.4px) saturate(125%) + background: rgba(255, 255, 255, 0.09).
#
# Размытие в CSS задано в пикселях экрана, а видео растягивается по ширине сцены (object-fit: cover).
# Поэтому сигма в пикселях видео зависит от ширины экрана. Значения подобраны сравнением
# со старым рендером в Chrome: 1920 → 4.0 (вариант -wide), 1440–1600 → 5.0.
# Если поменяется blur, размер сцены или исходник, подбирать заново.
#
# Запуск из frontend/: bash scripts/bake-hero.sh
set -euo pipefail
cd "$(dirname "$0")/../public/img"

# Матрица saturate(1.25) из спецификации Filter Effects. eq=saturation в ffmpeg считает иначе (в YUV).
SAT="colorchannelmixer=rr=1.19675:rg=-0.17875:rb=-0.018:gr=-0.05325:gg=1.07125:gb=-0.018:br=-0.05325:bg=-0.17875:bb=1.232"
# Белая вуаль 9% поверх: c · 0.91 + 255 · 0.09
VEIL="lutrgb=r='val*0.91+22.95':g='val*0.91+22.95':b='val*0.91+22.95'"
# После размытия мелких деталей нет, поэтому 960px по ширине неотличимы от исходных 1280px.
frost() { echo "format=gbrp,gblur=sigma=$1:steps=6,${SAT},${VEIL},scale=960:-2:flags=area"; }

video() { # $1 сигма, $2 суффикс файла
  ffmpeg -v error -y -i hero-loop.webm -an -vf "$(frost "$1")" \
    -c:v libvpx-vp9 -b:v 0 -crf 32 -row-mt 1 -deadline good -pix_fmt yuv420p "hero-loop-frost$2.webm"
  ffmpeg -v error -y -i hero-loop.webm -an -vf "$(frost "$1"),format=yuv420p" \
    -c:v libx264 -crf 24 -preset slow -movflags +faststart "hero-loop-frost$2.mp4"
}

video 5.0 "" &
video 4.0 "-wide" &
# Постер 2200px против 1280px у видео: сигма ×1.72. Берём середину между вариантами (4.5 → 7.7).
ffmpeg -v error -y -i hero-stage.jpg -vf "$(frost 7.7)" -q:v 3 hero-stage-frost.jpg &
wait
ls -la hero-loop-frost* hero-stage-frost.jpg
