import json, os, re, sys, numpy as np, soundfile as sf
sys.path.insert(0, ".")
from script import PARTS, VOICE, say
from kokoro_onnx import Kokoro
k = Kokoro("tts/kokoro-v1.0.onnx", "tts/voices-v1.0.bin")
OUT = "audio2"; os.makedirs(OUT, exist_ok=True)
SR = 24000
PAUSE = {".": 0.38, "?": 0.5, "!": 0.42, ":": 0.32}
rng = np.random.default_rng(7)

def trim(a, thr=0.004):
    idx = np.where(np.abs(a) > thr)[0]
    return a[max(0, idx[0] - 240): idx[-1] + 480] if len(idx) else a

meta = []
for pi, (title, vis, lines) in enumerate(PARTS):
    for li, line in enumerate(lines):
        spk, text = line[0], line[1]
        f = f"{OUT}/p{pi:02d}_l{li:02d}.wav"
        if not os.path.exists(f):
            v, lang, base = VOICE[spk]
            pace = line[3] if len(line) > 3 else base
            sents = [s for s in re.split(r"(?<=[.!?:])\s+", say(text).strip()) if s]
            chunks = []
            for j, s in enumerate(sents):
                sp = pace * (0.97 if s.endswith("?") else 1.0) * float(rng.uniform(0.985, 1.02))
                a, _ = k.create(s, voice=v, speed=sp, lang=lang)
                chunks.append(trim(a))
                if j < len(sents) - 1:
                    gap = PAUSE.get(s[-1], 0.3) + (0.1 if len(s) > 90 else 0)
                    chunks.append(np.zeros(int(gap * SR), dtype=np.float32))
            a = np.concatenate(chunks)
            a = a / max(1e-6, np.abs(a).max()) * 0.89
            sf.write(f, a, SR)
        d = sf.info(f).duration
        meta.append({"part": pi, "line": li, "file": f, "dur": d})
        print(pi, li, round(d, 1), flush=True)
json.dump(meta, open(f"{OUT}/meta.json", "w"), indent=1)
print("TOTAL", round(sum(m["dur"] for m in meta) / 60, 1), "min")
