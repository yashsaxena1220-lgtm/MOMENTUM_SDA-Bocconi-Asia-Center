"""Build each part (visuals + voice + subtitles + part label), then join them into one MP4."""
import json, os, re, subprocess, sys
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(__file__))
from script import PARTS

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "parts2"); os.makedirs(OUT, exist_ok=True)
GAP, LEAD, TAIL = 0.45, 1.2, 1.5
SR = 24000
FONT = "Inter"
meta = {(m["part"], m["line"]): m for m in json.load(open(os.path.join(HERE, "audio2/meta.json")))}
only = [int(x) for x in sys.argv[1:]] or None


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-3000:]); raise SystemExit(1)


def ts(t):
    h, rem = divmod(max(t, 0), 3600); m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def chunks(text, maxlen=110):
    """Subtitle chunks: whole sentences where they fit, long sentences split at a comma or the middle word."""
    sents = re.split(r"(?<=[.!?:;])\s+", text.strip())
    out = []
    for snt in sents:
        while len(snt) > maxlen:
            cut = max((m.end() for m in re.finditer(r",\s", snt) if 35 <= m.end() <= maxlen), default=None)
            if cut is None:
                words = snt.split(); half = len(snt) // 2; acc = 0
                for i, w in enumerate(words):
                    acc += len(w) + 1
                    if acc >= half:
                        cut = acc; break
            out.append(snt[:cut].strip()); snt = snt[cut:].strip()
        if out and len(out[-1]) + len(snt) + 1 <= maxlen and (len(snt) < 40 or len(out[-1]) < 40):
            out[-1] = out[-1] + " " + snt
        else:
            out.append(snt)
    return [c for c in out if c]


def ass_file(path, events, label):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT},38,&H00FFFFFF,&H00FFFFFF,&H00000000,&H9A162340,0,0,0,0,100,100,0,0,3,14,0,2,260,260,48,1
Style: Label,{FONT},30,&H00FFFFFF,&H00FFFFFF,&H00F0622E,&H00F0622E,1,0,0,0,100,100,0,0,3,12,0,9,40,40,34,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = [f"Dialogue: 1,{ts(0.2)},{ts(4.5)},Label,,0,0,0,,{label}"]
    for a, b, spk, text in events:
        name = "Anushka" if spk == "A" else "Yash"
        pass                                   # v2: no burned-in captions (a .srt is written for YouTube instead)
    open(path, "w").write(head + "\n".join(rows) + "\n")


def build_part(pi):
    title, vis, lines = PARTS[pi]
    if vis[0] == "app":
        rec = json.load(open(os.path.join(HERE, f"rec2/part_{pi:02d}.json")))
        starts, total = rec["starts"], rec["total"]
    else:
        starts, t = [], LEAD
        for li in range(len(lines)):
            starts.append(t); t += meta[(pi, li)]["dur"] + GAP
        total = t + TAIL - GAP
    # voice track
    audio = np.zeros(int(total * SR) + SR, dtype=np.float32)
    events = []
    for li, line in enumerate(lines):
        spk, text, acts = line[0], line[1], line[2]
        a, sr = sf.read(meta[(pi, li)]["file"], dtype="float32")
        i = int(starts[li] * SR)
        audio[i:i + len(a)] += a[: len(audio) - i]
        d = len(a) / sr
        cs = chunks(text); n = sum(len(c) for c in cs); t = starts[li]
        for c in cs:
            dt = d * len(c) / n
            events.append((t, t + dt, spk, c)); t += dt
    wav = os.path.join(OUT, f"p{pi:02d}.wav"); sf.write(wav, audio[: int(total * SR)], SR)
    ass = os.path.join(OUT, f"p{pi:02d}.ass")
    label = re.sub(r"^\d+\.\s*", "", title)
    ass_file(ass, events, label)
    # slide timeline: (start, slide) changes
    seq = []
    if vis[0] == "slides":
        seq.append((0.0, vis[1][0]))
    for li, line in enumerate(lines):
        spk, text, acts = line[0], line[1], line[2]
        for a in acts:
            if a[0] == "slide":
                seq.append((starts[li], a[1]))
            if a[0] == "app":
                seq.append((starts[li], None))
    out = os.path.join(OUT, f"p{pi:02d}.mp4")
    sub = f"subtitles={ass}:fontsdir=/usr/share/fonts/opentype/inter"
    fade = f"fade=t=in:st=0:d=0.4,fade=t=out:st={total - 0.4:.2f}:d=0.4"
    if vis[0] == "slides" and len(vis[1]) == 1 and False:
        lst = os.path.join(OUT, f"p{pi:02d}_slides.txt")
        with open(lst, "w") as f:
            for j, (t0, s) in enumerate(seq):
                t1 = seq[j + 1][0] if j + 1 < len(seq) else total
                f.write(f"file '{HERE}/slides/s-{s:02d}.png'\nduration {t1 - t0:.3f}\n")
            f.write(f"file '{HERE}/slides/s-{seq[-1][1]:02d}.png'\n")
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
             "-vf", f"fps=30,scale=1920:1080,format=yuv420p,{sub},{fade}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", out])
    else:
        if vis[0] == "slides":
            inputs = ["-loop", "1", "-framerate", "30", "-t", f"{total:.2f}", "-i", f"{HERE}/slides/s-{seq[0][1]:02d}.png", "-i", wav]
            seq = seq[1:]
        else:
            vid = os.path.join(HERE, f"rec2/part_{pi:02d}.webm")
            inputs = ["-ss", f"{rec['trim']:.2f}", "-i", vid, "-i", wav]
        fc = "[0:v]fps=30,scale=1920:1080,setpts=PTS-STARTPTS[v0]"
        last = "v0"; k = 2
        opened = [(t0, s) for t0, s in seq]
        for j, (t0, s) in enumerate(opened):
            if s is None:
                continue
            t1 = opened[j + 1][0] if j + 1 < len(opened) else total
            inputs += ["-loop", "1", "-t", f"{total:.2f}", "-i", f"{HERE}/slides/s-{s:02d}.png"]
            fc += f";[{k}:v]scale=1920:1080,fps=30[s{k}];[{last}][s{k}]overlay=enable='between(t,{t0:.2f},{t1:.2f})'[v{k}]"
            last = f"v{k}"; k += 1
        fc += f";[{last}]format=yuv420p,{sub},{fade}[vout]"
        run(["ffmpeg", "-y", *inputs, "-filter_complex", fc, "-map", "[vout]", "-map", "1:a",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", out])
    print(f"part {pi}: {total:.1f}s", flush=True)
    json.dump({"events": events, "total": total}, open(os.path.join(OUT, f"p{pi:02d}_events.json"), "w"))
    return out


def write_srt():
    def st(t):
        h, rem = divmod(t, 3600); m, sec = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(sec):02d},{int(round((sec % 1) * 1000)) % 1000:03d}"
    off, n, rows = 0.0, 0, []
    for pi in range(len(PARTS)):
        d = json.load(open(os.path.join(OUT, f"p{pi:02d}_events.json")))
        for a, b, spk, text in d["events"]:
            n += 1
            rows.append(f"{n}\n{st(off + a)} --> {st(off + b)}\n{text}\n")
        off += d["total"]
    open(os.path.join(HERE, "BreatheTwin_demo_video_v2.en.srt"), "w").write("\n".join(rows))
    print("srt", n, "captions")


def main():
    outs = [build_part(pi) for pi in range(len(PARTS)) if not only or pi in only]
    if only:
        return
    write_srt()
    lst = os.path.join(OUT, "all.txt")
    open(lst, "w").write("".join(f"file '{o}'\n" for o in outs))
    final = os.path.join(HERE, "BreatheTwin_demo_video_v2.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", final])
    print("done", final)


if __name__ == "__main__":
    main()
