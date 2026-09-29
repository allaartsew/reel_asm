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
.\run.ps1 "D:\Videos\My Project"             # → финал\rолик.mp4
```

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
# 1. Create a project folder with a montage.md (table below) and a видеo/ folder
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
to the voice — then replace `video/` files with your own generations and re-run.

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
- `/voice` — rebuild a voiceover track (XTTS-based, see `CLAUDE.md`);
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
| "Clip … not found" | check the name in the sheet vs. the `video/` folder |
| "Music … not found" | put the track in the project root or drop the Music line |
| "you ask to start at Ns, the file has only…" | the `from N` offset exceeds the clip — reduce it |
| "Could not find ffmpeg in PATH" | install ffmpeg |
| A cell with `_underscores_` lost markdown | `_clean` strips emphasis only at cell edges, by design — generation filenames are full of underscores |

## License

[MIT](LICENSE). No per-render fees, no cloud dependency.