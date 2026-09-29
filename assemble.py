"""Сборка ролика по монтажному листу.

Читает монтаж.md, нормализует фрагменты, склеивает, кладёт музыку и текст на экран.
Зависимости: только ffmpeg в PATH и стандартная библиотека Python.

Использование:
    python assemble.py "путь\\к\\проекту"
    python assemble.py "путь\\к\\проекту" --dry-run
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# Без этого скрипт падает с UnicodeEncodeError, если его запустить не через run.ps1:
# консоль может быть в cp1251, и любой символ вне неё роняет печать отчёта.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):  # перенаправленный поток
        pass

FPS = 30
FONT = Path(r"C:\Windows\Fonts\segoeui.ttf")
FONT_FALLBACK = Path(r"C:\Windows\Fonts\arial.ttf")

# Кегль привязан к ширине кадра, поэтому на телефоне текст выглядит одинаково
# во всех форматах. 46/1080 — спокойный субтитр; крупнее начинает забивать кадр.
FONT_RATIO = 46 / 1080
MAX_LINE = 44  # символов в строке при этом кегле

FORMATS = {
    "вертикаль": (1080, 1920),
    "горизонталь": (1920, 1080),
    "квадрат": (1080, 1080),
}
FORMAT_ALIASES = {
    "9:16": "вертикаль", "вертикальный": "вертикаль", "vertical": "вертикаль",
    "16:9": "горизонталь", "горизонтальный": "горизонталь", "horizontal": "горизонталь",
    "1:1": "квадрат", "square": "квадрат",
}
# README на английском: те же строки листа можно писать по-английски
TRACK_LABELS_EN = {"Музыка": "Music", "Озвучка": "Voiceover"}
AUDIO_FADE = 1.5  # секунд затухания музыки в конце
MUSIC_UNDER_VOICE = 0.25  # во сколько раз тише музыка, когда поверх идёт озвучка


class MontageError(Exception):
    """Понятная человеку ошибка в монтажном листе или входных файлах."""


@dataclass
class Clip:
    number: str
    path: Path
    duration: float | None = None  # None → берём фрагмент целиком
    start: float = 0.0  # с какой секунды фрагмента начинать
    text: str = ""
    actual_duration: float = 0.0


@dataclass
class Montage:
    clips: list[Clip] = field(default_factory=list)
    format: str = "вертикаль"
    width: int = 1080
    height: int = 1920
    music: Path | None = None
    music_start: float = 0.0
    voice: Path | None = None
    voice_start: float = 0.0


# --- разбор монтажного листа -------------------------------------------------


def _clean(cell: str) -> str:
    """Снимает markdown-выделение по краям ячейки.

    Именно по краям: имена генераций сплошь с подчёркиваниями внутри
    (Girl_crossing_sea_in_boat.mp4), и вырезать их нельзя.
    """
    return cell.strip().strip("*_").strip()


def _parse_timing(cell: str) -> tuple[float | None, float]:
    """Ячейка длительности.

    «3»       → взять 3 секунды с начала фрагмента;
    «3 с 1.5» → взять 3 секунды, начиная с 1.5 секунды фрагмента.

    Второе нужно, когда генерация длиннее нужного куска: модели выдают 5–15 секунд,
    а в монтаж идут лучшие 3–4, и они редко в самом начале.
    """
    cell = _clean(cell).replace(",", ".")
    start_match = re.search(r"(?:с|from)\s+(\d+(?:\.\d+)?)", cell)
    start = float(start_match.group(1)) if start_match else 0.0
    head = cell[: start_match.start()] if start_match else cell
    match = re.search(r"\d+(?:\.\d+)?", head)
    return (float(match.group()) if match else None), start


def _parse_format(text: str) -> tuple[str, int, int]:
    """Строка вида: - **Формат:** горизонталь. Без неё — вертикаль, как раньше."""
    match = re.search(r"\*\*(?:Формат|Format):\*\*(.+)", text)
    if not match:
        return "вертикаль", *FORMATS["вертикаль"]
    value = _clean(match.group(1)).lower().strip(" .")
    value = FORMAT_ALIASES.get(value, value)
    if value not in FORMATS:
        raise MontageError(
            f"Не поняла формат «{value}». Можно так: "
            + ", ".join(FORMATS)
            + " (или 9:16, 16:9, 1:1)."
        )
    return value, *FORMATS[value]


def _parse_track(text: str, project: Path, label: str) -> tuple[Path | None, float]:
    """Строка вида: - **Музыка:** track.mp3, с 12 сек"""
    match = re.search(rf"\*\*(?:{label}|{TRACK_LABELS_EN[label]}):\*\*(.+)", text)
    if not match:
        return None, 0.0
    value = _clean(match.group(1))
    if not value or value.startswith("_") or set(value) <= set("_ -"):
        return None, 0.0

    start = 0.0
    start_match = re.search(r"(?:с|from)\s+(\d+(?:[.,]\d+)?)\s*(?:сек|s\b)", value)
    if start_match:
        start = float(start_match.group(1).replace(",", "."))

    name = re.split(r",|\s+(?:с|from)\s+\d", value)[0].strip()
    if not name:
        return None, 0.0

    candidates = [
        project / name,
        project / "музыка" / name,
        project / "озвучка" / name,
        project / "финал" / name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate, start
    raise MontageError(
        f"{label} «{name}» не найдена. Искала тут:\n  "
        + "\n  ".join(str(c) for c in candidates)
    )


def parse_montage(path: Path, project: Path) -> Montage:
    """path — сам монтажный лист, project — корень проекта (пути в листе от него)."""
    # utf-8-sig: Блокнот и PowerShell дописывают BOM в начало файла,
    # из-за него первая строка таблицы перестаёт распознаваться.
    text = path.read_text(encoding="utf-8-sig")

    rows: list[list[str]] = []
    header_seen = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if header_seen and rows:
                break  # таблица кончилась
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not header_seen:
            if any("файл" in c.lower() or "file" in c.lower() for c in cells):
                header_seen = True
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue  # разделитель таблицы
        rows.append(cells)

    if not header_seen:
        raise MontageError(
            "В монтажном листе нет таблицы с колонкой «Файл». "
            "Возьми таблицу из README или из примера."
        )

    montage = Montage()
    montage.format, montage.width, montage.height = _parse_format(text)
    for cells in rows:
        cells += [""] * (4 - len(cells))
        number, filename, duration, on_screen = cells[0], _clean(cells[1]), cells[2], cells[3]
        if not filename:
            continue

        clip_path = project / filename
        if not clip_path.exists():
            clip_path = project / "видео" / filename
        if not clip_path.exists():
            raise MontageError(
                f"Фрагмент «{filename}» (строка {_clean(number) or '?'}) не найден "
                f"ни в {project}, ни в папке «видео»."
            )

        seconds, start = _parse_timing(duration)
        montage.clips.append(
            Clip(
                number=_clean(number) or str(len(montage.clips) + 1),
                path=clip_path,
                duration=seconds,
                start=start,
                # \n в ячейке таблицы — перенос строки на экране
                text=_clean(on_screen).replace("\\n", "\n"),
            )
        )

    if not montage.clips:
        raise MontageError("В таблице нет ни одной заполненной строки с файлом.")

    montage.music, montage.music_start = _parse_track(text, project, "Музыка")
    montage.voice, montage.voice_start = _parse_track(text, project, "Озвучка")
    return montage


# --- ffmpeg ------------------------------------------------------------------


def run(cmd: list[str], what: str) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        tail = "\n".join((result.stderr or "").strip().splitlines()[-12:])
        raise MontageError(f"ffmpeg не справился на шаге «{what}»:\n{tail}")
    return result


def probe_duration(path: Path) -> float:
    result = run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        f"чтение длительности {path.name}",
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise MontageError(f"Не смогла прочитать длительность файла {path.name}.")


def _escape_drawtext(path: Path) -> str:
    """Путь внутри фильтра ffmpeg: экранируем разделители и двоеточие диска."""
    return str(path).replace("\\", "/").replace(":", r"\:")


def build_filters(
    clip: Clip, montage: Montage, font: Path | None, text_file: Path | None
) -> str:
    width, height = montage.width, montage.height
    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        f"fps={FPS}",
        "setsar=1",
    ]
    if clip.text and font and text_file:
        size = round(width * FONT_RATIO)
        filters.append(
            "drawtext="
            f"fontfile='{_escape_drawtext(font)}':"
            f"textfile='{_escape_drawtext(text_file)}':"
            f"fontcolor=white:fontsize={size}:line_spacing=12:text_align=C:"
            "borderw=3:bordercolor=black@0.55:"
            # прижимаем блок к низу: так вторая строка не уезжает за кадр
            "x=(w-text_w)/2:y=h-text_h-h*0.12"
        )
    return ",".join(filters)


def normalize_clip(
    clip: Clip, montage: Montage, workdir: Path, index: int, font: Path | None
) -> Path:
    out = workdir / f"norm-{index:03d}.mp4"
    text_file = None
    if clip.text:
        text_file = workdir / f"text-{index:03d}.txt"
        # newline="\n": иначе Windows пишет CRLF, и drawtext рисует лишнюю пустую строку
        text_file.write_text(clip.text, encoding="utf-8", newline="\n")

    cmd = ["ffmpeg", "-y", "-v", "error"]
    if clip.start:
        cmd += ["-ss", f"{clip.start:.3f}"]  # до -i: быстрая перемотка, но кадр точный
    cmd += ["-i", str(clip.path)]
    if clip.duration:
        cmd += ["-t", f"{clip.duration:.3f}"]
    cmd += [
        "-vf", build_filters(clip, montage, font, text_file),
        "-an",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(out),
    ]
    run(cmd, f"подготовка фрагмента {clip.number}")
    return out


def concat(parts: list[Path], workdir: Path) -> Path:
    listing = workdir / "concat.txt"
    listing.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in parts) + "\n", encoding="utf-8"
    )
    out = workdir / "склейка.mp4"
    run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(out)],
        "склейка фрагментов",
    )
    return out


def add_audio(video: Path, montage: Montage, length: float, out: Path) -> None:
    """Кладёт на видео музыку, голос или то и другое (музыка уходит под голос)."""
    fade_at = max(0.0, length - AUDIO_FADE)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video)]
    chains, mix_inputs = [], []

    if montage.music:
        cmd += ["-ss", f"{montage.music_start:.3f}", "-i", str(montage.music)]
        index = len(mix_inputs) + 1
        # под голосом музыка звучит фоном, без голоса — в полную силу
        volume = MUSIC_UNDER_VOICE if montage.voice else 1.0
        chains.append(
            f"[{index}:a]atrim=0:{length:.3f},asetpts=N/SR/TB,volume={volume},"
            f"afade=t=out:st={fade_at:.3f}:d={AUDIO_FADE}[m]"
        )
        mix_inputs.append("[m]")

    if montage.voice:
        cmd += ["-ss", f"{montage.voice_start:.3f}", "-i", str(montage.voice)]
        index = len(mix_inputs) + 1
        chains.append(f"[{index}:a]atrim=0:{length:.3f},asetpts=N/SR/TB[v]")
        mix_inputs.append("[v]")

    if len(mix_inputs) == 2:
        chains.append(f"{''.join(mix_inputs)}amix=inputs=2:normalize=0[a]")
        out_label = "[a]"
    else:
        out_label = mix_inputs[0]

    cmd += [
        "-filter_complex", ";".join(chains),
        "-map", "0:v", "-map", out_label,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(out),
    ]
    run(cmd, "наложение звука")


# --- сценарий работы ---------------------------------------------------------


def resolve_font() -> Path | None:
    for candidate in (FONT, FONT_FALLBACK):
        if candidate.exists():
            return candidate
    return None


def report(montage: Montage) -> float:
    total = 0.0
    print(f"Монтажный лист ({montage.format}, {montage.width}x{montage.height}):\n")
    for clip in montage.clips:
        clip.actual_duration = probe_duration(clip.path)
        if clip.start >= clip.actual_duration:
            raise MontageError(
                f"Фрагмент {clip.number}: просишь начать с {clip.start:g} сек, "
                f"а в файле «{clip.path.name}» всего {clip.actual_duration:.2f} сек."
            )
        available = clip.actual_duration - clip.start
        used = clip.duration or available
        note = ""
        if clip.duration and clip.duration > available + 0.05:
            used = available
            note = f"  <- в листе {clip.duration:g} сек, а осталось только {available:.2f}"
        total += used
        offset = f" (с {clip.start:g})" if clip.start else ""
        shown = clip.text.replace("\n", " / ")
        text = f'  текст: «{shown}»' if clip.text else ""
        print(f"  {clip.number:>3}  {clip.path.name:<28} {used:5.2f} сек{offset}{text}{note}")
        for line in clip.text.splitlines():
            if len(line) > MAX_LINE:
                print(
                    f"       ! строка длиннее {MAX_LINE} символов — вылезет за кадр. "
                    f"Разбей её через \\n в монтажном листе."
                )

    print(f"\nИтого: {total:.2f} сек")
    for label, track, start in (
        ("Музыка", montage.music, montage.music_start),
        ("Озвучка", montage.voice, montage.voice_start),
    ):
        if track:
            offset = f", с {start:g} сек" if start else ""
            print(f"{label}: {track.name}{offset}")
    if not montage.music and not montage.voice:
        print("Звука нет — ролик будет немой")
    elif montage.music and montage.voice:
        print(f"Музыка уйдёт фоном под голос (громкость x{MUSIC_UNDER_VOICE:g})")
    return total


def assemble(project: Path, output: Path | None, dry_run: bool) -> int:
    candidates = [project / "монтаж.md", project / "сценарий" / "монтаж.md"]
    sheet = next((c for c in candidates if c.exists()), None)
    if sheet is None:
        raise MontageError(
            "Не нашла монтажный лист. Искала тут:\n  "
            + "\n  ".join(str(c) for c in candidates)
            + "\nПоложи файл «монтаж.md» с таблицей из README или из примера."
        )

    montage = parse_montage(sheet, project)
    total = report(montage)

    if dry_run:
        print("\nЭто проверка (--dry-run). Ничего не собирала.")
        return 0

    font = resolve_font()
    if not font and any(c.text for c in montage.clips):
        print("\nШрифт не найден — текст на экране пропущу.", file=sys.stderr)

    out = output or (project / "финал" / "ролик.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    workdir = Path(tempfile.mkdtemp(prefix="reel-"))
    try:
        print()
        parts = []
        for index, clip in enumerate(montage.clips, start=1):
            print(f"  готовлю фрагмент {clip.number}…")
            parts.append(normalize_clip(clip, montage, workdir, index, font))

        print("  склеиваю…")
        video = concat(parts, workdir)

        if montage.music or montage.voice:
            print("  кладу звук…")
            add_audio(video, montage, total, out)
        else:
            shutil.copy(video, out)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print(f"\nГотово: {out}")
    print(f"{montage.width}x{montage.height}, {probe_duration(out):.2f} сек")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Собирает вертикальный ролик по монтажному листу «монтаж.md»."
    )
    parser.add_argument("project", type=Path, help="папка проекта с монтаж.md")
    parser.add_argument("-o", "--output", type=Path, help="куда сохранить (по умолчанию финал/ролик.mp4)")
    parser.add_argument("--dry-run", action="store_true", help="только показать план, не собирать")
    args = parser.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("Не нашла ffmpeg в PATH. Установи ffmpeg и повтори.", file=sys.stderr)
        return 2
    if not args.project.is_dir():
        print(f"Папка проекта не найдена: {args.project}", file=sys.stderr)
        return 2

    try:
        return assemble(args.project, args.output, args.dry_run)
    except MontageError as error:
        print(f"\n{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
