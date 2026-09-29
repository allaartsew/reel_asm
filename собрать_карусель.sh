#!/usr/bin/env bash
#
# собрать_карусель.sh — карусель (PNG-слайды) → вертикальный клип 1080×1920.
#
# Отличие от assemble.py: тот собирает ролик из видеофрагментов по монтажному листу,
# а этот берёт готовые слайды-картинки, добавляет медленный зум и перетекания.
# Финальным кадром можно подставить «ожившую» версию последнего слайда.
#
# Запуск:   bash собрать_карусель.sh
# Править:  блок НАСТРОЙКИ ниже — пути, порядок слайдов, длительности, трек.
#
set -euo pipefail

# ───────────────────────────── НАСТРОЙКИ ─────────────────────────────

# Папка со слайдами
SRC="F:/ART/Adv/AI CAMP/AI Camp Obs/assets/Mascot/сказка оживает/publish"

# Куда положить готовый клип
OUT="F:/ART/Adv/AI CAMP/AI Camp Obs/assets/Mascot/сказка оживает/финал/клип.mp4"

# Слайды по порядку:  файл | длительность в секундах | направление зума (in / out)
# Плотным слайдам с мелким текстом давай на секунду больше.
SLIDES=(
  "Group 1.png|4.5|in"
  "Group 3.png|4.5|out"
  "Group 2.png|4.5|in"
  "Group 4.png|4.5|out"
  "Group 5.png|5.5|in"
)

# Видеофинал — путь к mp4 или пустая строка, если клип только из картинок.
# Ищется в SRC, если указано одно имя файла.
VIDEO="b236dd75-6ba0-41f6-af4e-915cf9e1713d.mp4"

# Музыка — путь к mp3/wav или пустая строка (тогда клип будет немой,
# музыку наложишь прямо в редакторе Reels).
MUSIC="F:/ART/Adv/AI CAMP/AI Camp Obs/reel_assembler/пример/медовик/Honey Kitchen.mp3"
MUSIC_START=0        # с какой секунды трека брать
MUSIC_FADE_IN=0.8    # плавное появление в начале
MUSIC_FADE_OUT=1.8   # затухание в конце

TRANS=0.5            # длительность перетекания между слайдами
ZOOM=0.09            # насколько сильно наезжает камера (0.09 = 9 %)
FPS=30
W=1080
H=1920

# ─────────────────────────── КОНЕЦ НАСТРОЕК ───────────────────────────

for cmd in ffmpeg ffprobe awk; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Не нашёлся $cmd — поставь его или добавь в PATH."; exit 1; }
done

[ -d "$SRC" ] || { echo "Нет папки со слайдами: $SRC"; exit 1; }

OUTDIR=$(dirname "$OUT")
TMP="$OUTDIR/_сборка"
mkdir -p "$OUTDIR" "$TMP"
trap 'rm -rf "$TMP"' EXIT
rm -f "$TMP"/seg*.mp4

# Фон — размытая обрезка того же кадра: слайды не 9:16 не обрезаются по краям,
# а получают мягкие поля сверху и снизу. Всё считаем в 2×, чтобы зум не мылил.
BG="scale=$((W*2)):$((H*2)):force_original_aspect_ratio=increase,crop=$((W*2)):$((H*2)),boxblur=60:2,eq=brightness=-0.06:saturation=1.1"
FG="scale=$((W*2)):$((H*2)):force_original_aspect_ratio=decrease:flags=lanczos"

DURS=()
i=0

for s in "${SLIDES[@]}"; do
  i=$((i+1))
  IFS='|' read -r file dur dir <<<"$s"
  [ -f "$SRC/$file" ] || { echo "Нет слайда: $SRC/$file"; exit 1; }

  frames=$(awk -v d="$dur" -v f="$FPS" 'BEGIN{printf "%d", d*f}')
  if [ "$dir" = "out" ]; then
    Z="$(awk -v z="$ZOOM" 'BEGIN{printf "%.4f", 1+z}')-$ZOOM*on/$frames"
  else
    Z="1+$ZOOM*on/$frames"
  fi

  echo ">>> слайд $i: $file — $dur с, зум $dir"
  ffmpeg -y -v error -loop 1 -framerate "$FPS" -t "$dur" -i "$SRC/$file" \
    -filter_complex "[0:v]$BG[bg];[0:v]$FG[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,\
zoompan=z='$Z':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=${W}x${H}:fps=$FPS,\
format=yuv420p,setsar=1" \
    -an -c:v libx264 -preset medium -crf 17 -r "$FPS" "$TMP/seg$i.mp4"

  DURS+=("$dur")
done

if [ -n "$VIDEO" ]; then
  [ -f "$VIDEO" ] || VIDEO="$SRC/$VIDEO"
  [ -f "$VIDEO" ] || { echo "Нет видеофинала: $VIDEO"; exit 1; }
  i=$((i+1))
  echo ">>> финал: видео $(basename "$VIDEO")"
  ffmpeg -y -v error -i "$VIDEO" \
    -vf "scale=$W:$H:force_original_aspect_ratio=increase:flags=lanczos,crop=$W:$H,format=yuv420p,setsar=1" \
    -an -c:v libx264 -preset medium -crf 17 -r "$FPS" "$TMP/seg$i.mp4"
  vdur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$TMP/seg$i.mp4" | tr -d '\r')
  DURS+=("$vdur")
fi

N=$i
[ "$N" -ge 2 ] || { echo "Нужно минимум два фрагмента."; exit 1; }

# Цепочка xfade: каждое следующее перетекание начинается за TRANS до конца собранного куска.
INPUTS=()
for n in $(seq 1 "$N"); do INPUTS+=(-i "$TMP/seg$n.mp4"); done

FILTER=""
CUR="[0:v]"
LEN="${DURS[0]}"
for n in $(seq 1 $((N-1))); do
  OFF=$(awk -v l="$LEN" -v t="$TRANS" 'BEGIN{printf "%.3f", l-t}')
  FILTER+="$CUR[$n:v]xfade=transition=fade:duration=$TRANS:offset=$OFF[x$n];"
  LEN=$(awk -v l="$LEN" -v d="${DURS[$n]}" -v t="$TRANS" 'BEGIN{printf "%.3f", l+d-t}')
  CUR="[x$n]"
done
FILTER+="${CUR}fps=$FPS,format=yuv420p[v]"

MAPS=(-map "[v]")
AUDIO=()
if [ -n "$MUSIC" ]; then
  [ -f "$MUSIC" ] || { echo "Нет трека: $MUSIC"; exit 1; }
  FOUT=$(awk -v l="$LEN" -v f="$MUSIC_FADE_OUT" 'BEGIN{printf "%.3f", l-f}')
  MEND=$(awk -v s="$MUSIC_START" -v l="$LEN" 'BEGIN{printf "%.3f", s+l}')
  FILTER+=";[${N}:a]atrim=$MUSIC_START:$MEND,asetpts=N/SR/TB,\
afade=t=in:st=0:d=$MUSIC_FADE_IN,afade=t=out:st=$FOUT:d=$MUSIC_FADE_OUT,aresample=48000[a]"
  INPUTS+=(-i "$MUSIC")
  MAPS+=(-map "[a]")
  AUDIO=(-c:a aac -b:a 192k -ar 48000 -ac 2)
else
  AUDIO=(-an)
fi

echo ">>> сборка, длительность ${LEN} с"
ffmpeg -y -v error "${INPUTS[@]}" \
  -filter_complex "$FILTER" \
  "${MAPS[@]}" \
  -c:v libx264 -preset slow -crf 18 -profile:v high -level 4.1 -pix_fmt yuv420p \
  "${AUDIO[@]}" \
  -movflags +faststart -shortest \
  "$OUT"

echo ">>> готово: $OUT"
ffprobe -v error -show_entries format=duration,size \
  -show_entries stream=codec_name,width,height,r_frame_rate -of default=nw=1 "$OUT"
