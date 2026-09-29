**[Русский](#reel_assembler--сборка-ролика-по-монтажному-листу) · [English](#reel_assembler)**

# reel_assembler — сборка ролика по монтажному листу

**ИИ пишет монтажный лист, один скрипт собирает ролик.**

Маленький инструмент на Python + ffmpeg: из монтажного листа (обычной Markdown-таблицы) получается готовый ролик — вертикальный, горизонтальный или квадратный. Без React, без браузера, без облака и без установки пакетов. Лист пишет ИИ-агент (или вы сами), а `assemble.py` делает остальное: обрезает фрагменты, приводит их к одному размеру и частоте кадров, кладёт текст на экран, сводит музыку и озвучку и выдаёт один MP4.

Сделан под реальность ИИ-генераций: модели выдают клипы по 5–15 секунд с мусорным звуком, а лучшие 3–6 секунд почти никогда не в начале. `reel_assembler` — это шаг, который превращает такие генерации в готовый ролик.

```powershell
.\run.ps1 "D:\Videos\Мой проект" -DryRun     # сначала посмотреть план
.\run.ps1 "D:\Videos\Мой проект"             # → финал\ролик.mp4
```

> 🎬 **Видео-демонстрация работы (35 сек)** — наглядный процесс сборки со сказкой, графическими инфографиками HyperFrames, нарезкой окон `N с M` и сведением музыки.

https://github.com/user-attachments/assets/e0a01435-3f41-4614-91e3-86c78263b422

## Зачем

Нейросети для видео (Kling, Runway, Veo, Sora…) дают короткие клипы, а ролику нужна история. Между ними — настоящая работа:

- выбрать *лучшее окно внутри каждого клипа* — почти никогда не первые секунды;
- привести разные форматы (9:16, 16:9, 1:1, разный fps) к одному кадру;
- выкинуть звук генераций и положить свою музыку и озвучку;
- поставить текст так, чтобы он влезал в кадр на телефоне;
- получать один и тот же результат при каждой пересборке.

`reel_assembler` сводит всё это к **одной таблице** и **одной команде**.

```
видео/
  фрагмент-01.mp4   ← генерации (или любые клипы)
  фрагмент-02.mp4
монтаж.md           ← монтажный лист
track.mp3           ← музыка (по желанию)
голос.mp3           ← озвучка (по желанию)
```

## Быстрый старт

**Нужно:** Python 3.10+, ffmpeg и ffprobe в PATH. Больше ничего ставить не надо.

```powershell
# 1. Папка проекта: монтаж.md (таблица ниже) и папка видео/
# 2. План сборки:
.\run.ps1 "D:\Videos\Мой проект" -DryRun

# 3. Сборка:
.\run.ps1 "D:\Videos\Мой проект"
```

Dry-run показывает, что нашлось и где лист расходится с реальными файлами, и ничего не собирает. Без PowerShell: `python assemble.py "путь\к\проекту" [--dry-run] [-o out.mp4]`.

## Монтажный лист

Markdown-таблица. Это весь интерфейс.

| № | Файл | Длительность | Текст на экране | Примечание |
|---|------|--------------|-----------------|------------|
| 1 | clip-01.mp4 | 2 | Тихое утро | зацепка |
| 2 | clip-02.mp4 | 5 с 2.5 |  | 5 секунд начиная с 2,5-й |
| 3 | clip-03.mp4 |  | Смелость — это когда страшно,\nа ты всё равно идёшь | финал |

И где-нибудь в файле:

```markdown
- **Формат:** вертикаль        → 1080×1920 (по умолчанию) · горизонталь → 1920×1080 · квадрат → 1080×1080
- **Музыка:** track.mp3, с 3 сек
- **Озвучка:** голос.mp3
```

### Запись `5 с 2.5`

`5 с 2.5` в колонке длительности = взять 5 секунд начиная с 2,5-й секунды клипа. Это главный инструмент: генерации приходят по 5–15 секунд, а в монтаж нужны *лучшие* 3–5, и они почти никогда не в начале — первые кадры ещё «собираются», хвост начинает плыть. Одна генерация может дать даже два разных кадра:

| № | Файл | Длительность | Примечание |
|---|------|--------------|------------|
| 3 | seabirds_net.mp4 | 5 с 0.5 | общий план: птицы и сети |
| 4 | seabirds_net.mp4 | 4 с 6 | главный кадр: краб выходит к сети |

### Что важно знать

- **Пустая длительность** = весь клип. Если лист просит больше, чем осталось, скрипт предупредит и возьмёт сколько есть — клипы не растягиваются.
- **`\n` в ячейке** — перенос строки на экране. Строки центрируются. Сам текст не переносится: длиннее 44 символов скрипт предупредит, текст уедет за кадр.
- **Формат ролика должен совпадать с форматом генераций.** Кадр приводится через масштаб + обрезку по центру: 16:9 в вертикальном ролике теряет две трети ширины, и герой не по центру срезается.
- **Звук генераций всегда выкидывается** — там мусор или тишина. В ролике только музыка и озвучка.
- **Музыка обрезается по длине ролика** с затуханием 1,5 сек. Под озвучкой музыка приглушается до 25%.
- Строки «Музыка» и «Озвучка» ищутся по всему файлу — даже в бэктиках и пояснениях. Написать такую строку «для примера» нельзя, она сразу рабочая.

## Живой пример

В папке `пример/` лежит полностью разобранный проект: сказка на 23,5 сек (1920×1080, горизонталь) из пяти генераций. Каждое решение объяснено: `сценарий/монтаж.md` (лист), `промты.md` (промты генераций), `озвучка.md` (реплики). Почитайте, почему выбраны такие окна и как длительности подогнаны под голос, — потом положите свои генерации в `видео/` и соберите заново. Своих клипов пока нет? `python пример/заглушки.py "пример/Проект — мини-сказка"` создаст тестовые клипы и тоны вместо музыки и голоса — весь путь можно пройти за минуту.

## Возможности

- **Окна внутри клипов** — запись `5 с 2.5`, главный инструмент.
- **Три формата** — вертикаль, горизонталь, квадрат (можно писать 9:16, 16:9, 1:1).
- **Текст на экране** — кириллица без проблем, размер шрифта привязан к ширине кадра (на любом телефоне выглядит одинаково), переносы через `\n`.
- **Сведение звука** — музыка + озвучка, под голосом музыка приглушается.
- **Повторяемость** — тот же лист, те же файлы — тот же ролик.
- **Карусель → клип** — `собрать_карусель.sh`: PNG-слайды в вертикальный клип 9:16 с медленным зумом, размытым фоном для слайдов не 9:16, плавными переходами, «ожившим» последним кадром и музыкой по желанию.
- **Понятные ошибки на русском** — текстом, а не трейсбеком.
- **Грабли Windows учтены** — BOM, CRLF, консоль cp1251, ffmpeg без fontconfig, кириллица в именах файлов.

## Для ИИ-агентов

Инструмент рассчитан на работу вместе с ИИ-агентом. В репозитории лежат скиллы для Claude Code (`.claude/skills/`):

- `/frame` — нарезать кадры из генерации, *посмотреть* на них и выбрать окно `с …`;
- `/assemble` — обновить лист, сделать dry-run, собрать;
- `/new-reel` — завести новый проект ролика.

Агент пишет лист, скрипт надёжно собирает. Никаких сервисов и серверов — сборка не сломается из-за того, что упал какой-то сайт.

## Частые ошибки

| Ошибка | Что сделать |
|--------|-------------|
| «нет таблицы с колонкой Файл» | скопировать таблицу из примера, шапка обязательна |
| «Фрагмент … не найден» | сверить имя в листе и в папке `видео/` |
| «Музыка … не найдена» | положить трек в корень проекта или убрать строку «Музыка» |
| «просишь начать с N сек, а в файле только…» | окно `с N` дальше конца клипа — уменьшить |
| «Не нашла ffmpeg в PATH» | установить ffmpeg |

## Лицензия

[MIT](LICENSE). Бесплатно, без облака.

---

# reel_assembler

**Edit-the-editing-sheet. AI writes the cut list, one script assembles the video.**

A zero-dependency Python + ffmpeg tool for turning an *editing decision list* into a finished
vertical, horizontal, or square video — no React, no bundler, no headless browser, no cloud.
The cut list is a simple Markdown table written by an AI agent (or by hand), and `assemble.py`
does the rest: trims clips, normalizes resolution and fps, lays text on screen, mixes music
and voiceover, and renders a single MP4.

Built for the reality of AI-generated footage: models ship 5–15 second clips with garbage
sound, and the best 3–6 seconds are almost never at the start. `reel_assembler` is the layer
that makes that footage publishable.

```powershell
.\run.ps1 "D:\Videos\My Project" -DryRun     # see the plan first
.\run.ps1 "D:\Videos\My Project"             # → финал\ролик.mp4
```

> 🎬 **Watch 35s Showcase Video** — see the real assembly process combining fairytale AI clips with HyperFrames motion graphics, `N from M` window cutting, and music sync.

https://github.com/user-attachments/assets/e0a01435-3f41-4614-91e3-86c78263b422

## Why

Video generation models (Kling, Runway, Veo, Sora…) output short clips. A Reel needs a story.
The gap in between is the actual work:

- pick the *best window inside each clip* — rarely the first seconds;
- normalize wildly different formats (9:16, 16:9, 1:1, mixed fps) to one frame;
- discard the garbage audio models ship with, and lay your own music + voiceover;
- put on-screen text that fits the frame — and doesn't overflow on a phone;
- get a deterministic result you can rebuild after any change.

`reel_assembler` turns that workflow into **one Markdown table** and **one command**.

```
видео/
  фрагмент-01.mp4   ← AI generations (or any clips)
  фрагмент-02.mp4
монтаж.md           ← the edit decision list
track.mp3           ← music (optional)
голос.mp3           ← voiceover (optional)
```

## Quick start

**Requirements:** Python 3.10+, ffmpeg + ffprobe in PATH. Nothing else — no packages to install.

```powershell
# 1. Create a project folder with монтаж.md (table below) and a видео/ folder
# 2. Preview the plan:
.\run.ps1 "D:\Videos\My Project" -DryRun

# 3. Render:
.\run.ps1 "D:\Videos\My Project"
```

The script refuses to build without a dry-run sanity check if something's off, and always
prints what it found and where the sheet disagrees with the real files. To use directly:
`python assemble.py "path\to\project" [--dry-run] [-o out.mp4]`.

## The montage sheet

A Markdown table. That's the whole interface.

| # | File | Duration | On-screen text | Notes |
|---|------|----------|----------------|-------|
| 1 | clip-01.mp4 | 2 | Quiet morning | hook |
| 2 | clip-02.mp4 | 5 from 2.5 |  | take 5s starting at 2.5s |
| 3 | clip-03.mp4 |  | Courage is when you're scared,<br>and you walk anyway | finale |

Then, anywhere in the file:

```markdown
- **Format:** vertical        → 1080×1920 (default) · horizontal → 1920×1080 · square → 1080×1080
- **Music:** track.mp3, from 3s
- **Voiceover:** голос.mp3
```

### The `5 from 2.5` syntax

`5 from 2.5` in the Duration column = take 5 seconds starting at 2.5 seconds of the source
clip. This is the core tool: generations arrive 5–15 seconds long, but the cut needs the
*best* 3–5 seconds, and they're almost never at the beginning — the first frames are still
"assembling", the tail starts to drift. The sheet lets the editor (human or AI) pick the
window, and one generation can even feed two different shots:

| # | File | Duration | Notes |
|---|------|----------|-------|
| 3 | seabirds_net.mp4 | 5 from 0.5 | wide shot: birds and nets |
| 4 | seabirds_net.mp4 | 4 from 6 | hero shot: the crab reaches the net |

### Rules worth knowing

- **Empty duration** = use the whole clip. If the sheet asks for more than remains, the script
  warns and takes what's there — clips are never stretched.
- **`\n` in a cell** is a line break on screen. Lines are centered under each other. Nothing
  wraps by itself: longer than 44 chars the script warns, the text would run off the frame.
- **Format must match your generations.** The frame goes through scale + center crop: a 16:9
  source in a vertical reel loses two thirds of its width, and an off-center hero gets cut.
- **Source audio is always discarded** — generations come with junk sound or none. The track
  is only music and voiceover, by design.
- **Music is trimmed to the video length** with a 1.5s fade-out. With voiceover present, music
  ducks to 25% under the voice.
- Text search for Music/Voiceover lines runs across the whole file — even inside backticks
  and explanations. You can't write one "just as an example"; it becomes live.

## Real example

The `пример/` folder ships a full, documented project: a 23.5s fairy-tale (1920×1080,
horizontal) assembled from five AI generations. Every editing decision is annotated:
`сценарий/монтаж.md` (the sheet), `промты.md` (generation prompts), `озвучка.md`
(voiceover lines). Read it to see why windows were chosen and how durations were tuned
to the voice — then drop your own generations into `видео/` and re-run. No clips yet? `python пример/заглушки.py "пример/Проект — мини-сказка"` fills the project with test clips and tones so you can see the whole pipeline in a minute.

## Features

- **Windows inside clips** — the `5 from 2.5` syntax, the primary tool.
- **Three formats** — vertical, horizontal, square (aliases: 9:16, 16:9, 1:1).
- **On-screen text** — Cyrillic-safe drawtext, font size tied to frame width (so the caption
  looks the same on every phone), manual line breaks via `\n`.
- **Audio mix** — music + voiceover, music under voice ducks to 25%: ducking happens in the
  frequency bands the voice actually occupies.
- **Deterministic renders** — same sheet, same files, same video. Rebuild anytime.
- **Carousel → clip** — `собрать_карусель.sh`: a still carousel (PNG slides) into a vertical
  9:16 clip with slow Ken Burns zoom, blurred self-background for non-9:16 slides, xfade
  transitions, optional "living" last frame and music.
- **Russian-first errors** — `MontageError` messages an editor can understand, not a stack
  trace. A mandatory `--dry-run` plan before every render.
- **Windows gotchas handled** — UTF-8 BOM, CRLF in drawtext, cp1251 consoles, ffmpeg without
  fontconfig (explicit `fontfile=`), Cyrillic filenames as a contract.

## For AI agents

`reel_assembler` is designed to be driven by an AI coding agent in a loop. The repo ships
Claude Code skills that implement the agent side of the workflow:

- `/frame` — pull preview frames from an AI generation, *look* at them (vision), pick the
  `from`-window;
- `/assemble` — regenerate preview frames, run dry-run, assemble;
- `/new-reel` — scaffold a new project.

Agents write the sheet; the script is the reliable offline executor. No SaaS, no external
render servers — the assembly cannot break because a website did.

## Comparison with video frameworks

`reel_assembler` fills a different niche than browser-rendering frameworks.

| | **reel_assembler** | **Remotion** | **HyperFrames** |
|---|---|---|---|
| Authoring | Markdown edit-decision list | React components | HTML + CSS + GSAP/Lottie |
| Runtime | Python stdlib + ffmpeg | Node + bundler + Chrome | Node + Chrome + ffmpeg |
| Install | `pip`? No. ffmpeg only | `npx create-video` | `npx hyperframes init` |
| Best window inside an AI clip | **Native** (`5 from 2.5`) | — | — |
| Discard model audio | Native, by design | manual | manual |
| Phone-native text sizing | Native (width-relative) | manual | manual |
| Render target | Any local machine | Cloud/Lambda | Local/Lambda/AWS |
| License | MIT | source-available | Apache 2.0 |

Remotion and HyperFrames are superb for programmatic motion graphics and UI-driven video.
`reel_assembler` is for the *assembling* step: letting an agent (or a human editor) describe
the cut and getting a deterministic MP4 out of real AI footage — offline, anywhere.

## Gotchas

| Error | Fix |
|-------|-----|
| "no table with a File column" | copy the template table, header is mandatory |
| "Clip … not found" | check the name in the sheet vs. the `видео/` folder |
| "Music … not found" | put the track in the project root or drop the Music line |
| "you ask to start at Ns, the file has only…" | the `from N` offset exceeds the clip — reduce it |
| "Could not find ffmpeg in PATH" | install ffmpeg |
| A cell with `_underscores_` lost markdown | `_clean` strips emphasis only at cell edges, by design — generation filenames are full of underscores |

## License

[MIT](LICENSE). No per-render fees, no cloud dependency.
