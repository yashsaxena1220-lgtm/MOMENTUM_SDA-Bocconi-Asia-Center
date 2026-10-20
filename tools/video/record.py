"""Record each app part of the demo with Playwright, pacing actions to the voice lines.
Writes rec/part_XX.webm and rec/part_XX.json (line start times relative to the trimmed video)."""
import json, os, sys, time
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(__file__))
from script import PARTS

HERE = os.path.dirname(os.path.abspath(__file__))
GEO = os.path.join(HERE, "..", "geo_init.js")
GAP = 0.45                     # pause between lines (s)
LEAD = 1.2                     # video before the first line (s)
DRY = os.environ.get("DRY")
meta = {} if DRY else {(m["part"], m["line"]): m["dur"] for m in json.load(open(os.path.join(HERE, "audio2/meta.json")))}
if DRY:
    meta = {(pi, li): 3.0 for pi, (_, _, ls) in enumerate(PARTS) for li in range(len(ls))}
only = [int(x) for x in sys.argv[1:]] or None

CSS = """
[data-testid="stToolbar"], [data-testid="stStatusWidget"], .stDeployButton {visibility:hidden !important;}
.bt-hl { outline: 3px solid #2E62F0 !important; outline-offset: 4px; border-radius: 16px;
         box-shadow: 0 0 0 10px rgba(46,98,240,0.12) !important; transition: outline-color .3s; }
* { scroll-behavior: auto; }
"""

JS_FIND = """(text) => {
  const all = [...document.querySelectorAll('[data-testid=stMainBlockContainer] *')]
     .filter(e => e.offsetParent !== null && e.children.length < 40 && (e.innerText||'').includes(text));
  if (!all.length) return null;
  all.sort((a,b) => (a.innerText||'').length - (b.innerText||'').length);
  return all[0];
}"""

JS_HL = """(text) => {
  const f = """ + JS_FIND + """; const e = f(text); if (!e) return false;
  const box = e.closest('.kpi, .card, .alert, .vital, .rule, .band, .howto, .dev, .devs, [data-testid=stPlotlyChart], [data-testid=stForm]') ||
              (/^H[1-4]$/.test(e.tagName) ? e : e.closest('h1,h2,h3') || e);
  document.querySelectorAll('.bt-hl').forEach(x => x.classList.remove('bt-hl'));
  box.classList.add('bt-hl');
  const r = box.getBoundingClientRect();
  if (r.top < 70 || r.bottom > window.innerHeight - 140) {
    const c = [...document.querySelectorAll('[data-testid=stMain], section.main, .main')].find(x => x.scrollHeight > x.clientHeight + 5) || document.scrollingElement;
    c.scrollTo({top: c.scrollTop + r.top - 120, behavior: 'smooth'});
  }
  setTimeout(() => box.classList.remove('bt-hl'), 4500);
  return true;
}"""

JS_SCROLL = """(text) => {
  const f = """ + JS_FIND + """; const e = f(text); if (!e) return false;
  const t = e.closest('h1,h2,h3,.kpi,.card,.devs,[data-testid=stPlotlyChart]') || e;
  const c = [...document.querySelectorAll('[data-testid=stMain], section.main, .main')].find(x => x.scrollHeight > x.clientHeight + 5) || document.scrollingElement;
  const r = t.getBoundingClientRect();
  c.scrollTo({top: c.scrollTop + r.top - 90, behavior: 'smooth'});
  return true;
}"""


def settle(pg, timeout=40):
    t = time.time()
    time.sleep(0.6)
    while time.time() - t < timeout:
        running = pg.evaluate("() => !!document.querySelector('[data-testid=stStatusWidget] [data-testid=stSpinner], [data-testid=stStatusWidget] img, .stSpinner')")
        stale = pg.evaluate("() => document.querySelectorAll('[data-stale=true]').length")
        if not running and not stale:
            break
        time.sleep(0.3)
    time.sleep(0.5)
    pg.add_style_tag(content=CSS)


def act(pg, a, out_dir, pi):
    k = a[0]
    if k == "hl":
        if not pg.evaluate(JS_HL, a[1]):
            print("  hl miss:", a[1])
    elif k == "scroll":
        if not pg.evaluate(JS_SCROLL, a[1]):
            print("  scroll miss:", a[1])
        time.sleep(1.0)
    elif k == "click":
        loc = pg.get_by_role("button", name=a[1], exact=True)
        if loc.count() == 0:
            loc = pg.get_by_role("tab", name=a[1], exact=True)
        if loc.count() == 0:
            loc = pg.locator("[data-testid=stMainBlockContainer] label").filter(has_text=a[1])
        loc.first.scroll_into_view_if_needed()
        loc.first.click()
        settle(pg)
    elif k == "fill":
        el = pg.locator(f".st-key-{a[1]} input")
        el.scroll_into_view_if_needed()
        el.fill(a[2], force=True); el.evaluate("e => e.blur()")
        time.sleep(0.3)
    elif k == "fill_label":
        el = pg.get_by_label(a[1], exact=True).first
        el.scroll_into_view_if_needed(); el.fill(a[2], force=True); el.evaluate("e => e.blur()")
        time.sleep(0.35)
    elif k == "select":
        box = pg.locator("[data-testid=stSelectbox]").filter(has=pg.get_by_text(a[1], exact=True)).first
        box.scroll_into_view_if_needed(); box.click(); time.sleep(0.4)
        pg.keyboard.type(a[2], delay=40); time.sleep(0.4)
        opt = pg.get_by_role("option", name=a[2], exact=True)
        if opt.count():
            opt.first.click()
        else:
            pg.keyboard.press("Enter")
        time.sleep(0.35)
    elif k == "submit":
        b = pg.get_by_role("button", name="Create twin and assess")
        b.scroll_into_view_if_needed(); b.click()
        settle(pg)
    elif k == "eos":
        box = pg.locator(".st-key-lab_eos")
        box.scroll_into_view_if_needed(timeout=8000)
        pg.evaluate("() => document.querySelector('.st-key-lab_eos').classList.add('bt-hl')")
        if box.locator("[role=slider]").count():
            s = box.locator("[role=slider]"); s.focus()
            for _ in range(30):
                pg.keyboard.press("ArrowRight"); time.sleep(0.04)
        else:
            i = box.locator("input").first; i.focus()
            for _ in range(29):
                pg.keyboard.press("ArrowRight"); time.sleep(0.05)
        settle(pg)
    elif k == "summary":
        b = pg.get_by_role("button", name="Download visit summary")
        b.scroll_into_view_if_needed(); time.sleep(0.6)
        pg.evaluate("(e) => e.classList.add('bt-hl')", b.element_handle())
        time.sleep(1.2)
        with pg.expect_download() as d:
            b.click()
        f = os.path.join(out_dir, f"summary_{pi}.html")
        d.value.save_as(f)
        pg.goto("file://" + f); time.sleep(1.0)
        pg.evaluate("() => { document.body.style.zoom = '1.25'; }")
        time.sleep(2.5)
        pg.evaluate("() => window.scrollTo({top: 500, behavior: 'smooth'})")
    elif k in ("slide", "app"):
        pass                         # handled when assembling (slide shown over the recording)


def main():
    out_dir = os.path.join(HERE, "rec_dry" if DRY else "rec2"); os.makedirs(out_dir, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for pi, (title, vis, lines) in enumerate(PARTS):
            if vis[0] != "app" or (only and pi not in only):
                continue
            ctx = b.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=out_dir,
                                record_video_size={"width": 1920, "height": 1080}, accept_downloads=True)
            ctx.add_init_script(path=GEO)
            pg = ctx.new_page(); rec0 = time.time()
            pg.goto(vis[1]); pg.wait_for_selector(".band", timeout=240000); settle(pg, 60)
            time.sleep(1.5)
            t0 = time.time() - rec0
            starts = []
            clock = time.time()
            for li, line in enumerate(lines):
                spk, text, acts = line[0], line[1], line[2]
                start = time.time() - rec0
                starts.append(start)
                for a in acts:
                    try:
                        act(pg, a, out_dir, pi)
                    except Exception as e:
                        print(f"  part {pi} line {li} action {a} failed: {e}")
                end_at = rec0 + start + meta[(pi, li)] + GAP
                while time.time() < end_at:
                    time.sleep(0.05)
            time.sleep(1.5)
            total = time.time() - rec0
            vpath = pg.video.path()
            ctx.close()
            trim = max(0.0, starts[0] - LEAD)
            dst = os.path.join(out_dir, f"part_{pi:02d}.webm")
            os.replace(vpath, dst)
            json.dump({"trim": trim, "starts": [s - trim for s in starts], "total": total - trim},
                      open(os.path.join(out_dir, f"part_{pi:02d}.json"), "w"))
            print(f"part {pi} recorded: {total - trim:.0f}s", flush=True)
        b.close()


if __name__ == "__main__":
    main()
