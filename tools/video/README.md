# Rebuilding the demo video

The demo video (https://youtu.be/l2pGZtYHCFM) is generated from this repo: AI narration, a scripted screen recording of the dashboard, and the deck slides.

| Script | What it does |
|---|---|
| `script.py` | Every narration line, who says it, which slide or dashboard page is shown, and the clicks to make |
| `tts.py` | Voices each line with Kokoro TTS (`af_heart` for Anushka, `am_michael` for Yash), sentence by sentence |
| `record.py` | Opens the local dashboard in Playwright and performs each line's clicks, paced to the voice |
| `assemble.py` | Joins slides, recordings and voice with ffmpeg; writes the MP4 and an `.srt` caption file |

Steps (Python 3.12+, ffmpeg, Playwright with Chromium):

1. `pip install kokoro-onnx soundfile playwright`, then download `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases) into `tts/`.
2. Render the deck to `slides/s-01.png` … at 1920×1080 (for example `pdftoppm -png -scale-to-x 1920 -scale-to-y 1080 docs/BreatheTwin_presentation.pdf slides/s`); `slides/s-90.png` is `docs/flowchart.png` on a plain background.
3. Start the dashboard: `streamlit run app/dashboard.py`.
4. Only if the India map is blank in headless Chromium: save Plotly's `asia_50m.json` (in the `plotly.js` npm package, `dist/topojson/`) as `geo_init.js` one folder up, wrapped as `window.PlotlyGeoAssets={topojson:{"asia_50m": <json>}};`.
5. `python tts.py`, then `python record.py`, then `python assemble.py`.

`DRY=1 python record.py 7` rehearses one part's clicks with short placeholder timings.
