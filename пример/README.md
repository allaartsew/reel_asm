# Examples

A fully documented real-world project: a 23.5-second horizontal fairy tale
(1920×1080) assembled from five AI generations. The clips, music and voice
are not in the repo (they're heavy AI-generated files) — but every *editing
decision* is, in `сценарий/`:

- **`монтаж.md`** — the edit decision list with annotations. Why each window
  was chosen, how one generation feeds two shots, why durations match the
  voiceover (word timing), and how a re-generated final frame changed the look.
- **`промты.md`** — one generation prompt per shot, the character anchor, the
  style tail (film grain, storybook realism), and notes on what drags a prompt
  toward cheap 3D-style rendering.
- **`озвучка.md`** — 5 voiceover lines, one per shot, timed to the sheet.

To make it yours: drop your own clips into `видео/`, matching filenames in the
sheet, and run:

```powershell
.\run.ps1 "пример\Проект — мини-сказка" -DryRun
.\run.ps1 "пример\Проект — мини-сказка"
```

Read the annotations to see the *reasoning* behind an edit — that's what the
tool is for: the sheet is the interface, the script is the executor.