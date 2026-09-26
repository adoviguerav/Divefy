# Divefy showreel

A 24.5-second motion-graphics promo for Divefy, aimed at first-time divers. Rendered result: `divefy-showreel.mp4` (1920×1080, 60 fps, H.264 + AAC), plus `divefy-showreel-075x.mp4`, the same cut slowed to 0.75× with ffmpeg (no re-render).

Everything is generated from code: no stock footage, no samples.

| File | What it is |
|---|---|
| `showreel.html` | The animation. One page, `renderFrame(t)` draws any instant deterministically. Open it in a browser to watch it loop live. `?t=12.4` freezes one frame. |
| `soundtrack.py` | The music and SFX, synthesized with numpy/scipy (120 BPM, A minor, low-passed "underwater" intro, drop on the logo). SFX times mirror the page's timeline. |
| `render.mjs` | Captures every frame with headless Chromium and pipes them to ffmpeg. |
| `fonts/` | Inter, Newsreader and JetBrains Mono (SIL OFL), so renders don't depend on the network. |

The on-screen facts come from the corpus: 18 m/min maximum ascent and the 3 min safety stop at 5 m (`data/guardrail/constantes.jsonl`, PADI notes), the Navy manual section 9-6.3, the 84 eval questions.

## Rebuild

```bash
cd docs/showreel
npm install                                                     # playwright-core
uv run --with numpy --with scipy python soundtrack.py soundtrack.wav
node render.mjs video silent.mp4 60                             # needs Chromium + ffmpeg (CHROME=, FFMPEG=)
ffmpeg -i silent.mp4 -i soundtrack.wav -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart divefy-showreel.mp4
ffmpeg -i divefy-showreel.mp4 -filter_complex "[0:v]setpts=PTS/0.75[v];[0:a]atempo=0.75[a]" -map "[v]" -map "[a]" -r 45 divefy-showreel-075x.mp4
```

`node render.mjs stills 5.3 12.4` writes single frames to `stills/` for checking a moment without rendering the whole thing.
