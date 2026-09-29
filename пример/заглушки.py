"""Заглушки для проекта: тестовые клипы и звук вместо настоящих генераций.

Читает монтаж.md и создаёт всё, на что он ссылается: цветные тестовые клипы
нужной длины в «видео», тон вместо музыки в «музыка», тон потише вместо голоса
в «озвучка». Так пример собирается сразу после клонирования, и видно весь путь
от монтажного листа до ролика. Уже лежащие файлы не трогает.

Использование:
    python пример/заглушки.py "пример/Проект — мини-сказка"
    .\\run.ps1 "пример\\Проект — мини-сказка"
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from assemble import MontageError, _clean, _parse_format, _parse_timing  # noqa: E402

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

MIN_CLIP = 10.0  # генерации обычно приходят по 10 секунд


def read_sheet(project: Path) -> tuple[str, dict[str, float]]:
    """Текст листа и нужная длина каждого файла: самое дальнее окно + запас."""
    candidates = [project / "монтаж.md", project / "сценарий" / "монтаж.md"]
    sheet = next((c for c in candidates if c.exists()), None)
    if sheet is None:
        raise MontageError(f"Не нашла монтаж.md в {project} и в {project / 'сценарий'}.")
    text = sheet.read_text(encoding="utf-8-sig")

    lengths: dict[str, float] = {}
    header_seen = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not header_seen:
            header_seen = any("файл" in c.lower() for c in cells)
            continue
        if all(set(c) <= set("-: ") for c in cells) or len(cells) < 3:
            continue
        name = _clean(cells[1])
        if not name:
            continue
        seconds, start = _parse_timing(cells[2])
        need = max(MIN_CLIP, start + (seconds or 0) + 1)
        lengths[name] = max(lengths.get(name, 0.0), need)
    return text, lengths


def track_name(text: str, label: str) -> str | None:
    match = re.search(rf"\*\*{label}:\*\*(.+)", text)
    if not match:
        return None
    name = re.split(r",|\s+с\s+\d", _clean(match.group(1)))[0].strip()
    return name or None


def ffmpeg(args: list[str], what: str) -> None:
    result = subprocess.run(["ffmpeg", "-y", "-v", "error", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise MontageError(f"ffmpeg не справился с «{what}»:\n{result.stderr.strip()[-600:]}")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    project = Path(sys.argv[1])
    try:
        text, lengths = read_sheet(project)
        _, width, height = _parse_format(text)
        total = sum(lengths.values())

        (project / "видео").mkdir(parents=True, exist_ok=True)
        for index, (name, seconds) in enumerate(lengths.items()):
            out = project / "видео" / name
            if out.exists() or (project / name).exists():
                print(f"  есть     {name}")
                continue
            ffmpeg(
                ["-f", "lavfi", "-i", f"testsrc2=s={width}x{height}:r=30:d={seconds:g}",
                 "-vf", f"hue=h={index * 70}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
                name,
            )
            print(f"  создала  {name} ({seconds:g} сек)")

        for label, folder, freq, volume in (("Музыка", "музыка", 220, 0.3), ("Озвучка", "озвучка", 440, 0.15)):
            name = track_name(text, label)
            if not name:
                continue
            out = project / folder / name
            if out.exists() or (project / name).exists():
                print(f"  есть     {name}")
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            ffmpeg(
                ["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={total + 5:g}",
                 "-af", f"volume={volume}", str(out)],
                name,
            )
            print(f"  создала  {folder}/{name} (тон {freq} Гц)")
    except MontageError as error:
        print(error, file=sys.stderr)
        return 1

    print("\nГотово. Теперь можно собирать — это заглушки, а не ролик.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
