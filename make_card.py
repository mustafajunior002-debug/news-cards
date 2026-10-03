#!/usr/bin/env python3
"""Urdu news card generator (1080x1350 JPEG/PNG) for Instagram/Facebook.

Usage:
  python3 make_card.py --headline "..." --summary "..." --source "ڈان نیوز" \
      --date "3 اکتوبر 2026" --category "قومی" --out cards/2026-10-03-1200-1.jpg

Prints "OK <file>" or "OVERFLOW (shorten text) <file>"; on OVERFLOW shorten the
summary and render again. Requires Python Playwright with Chromium.

Fonts are read from ./fonts next to this script:
  NotoNastaliqUrdu.ttf (headline), NotoNaskhArabic.ttf (body)
"""
import argparse
import html
import pathlib

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
FONTS = HERE / "fonts"

TEMPLATE = """<!doctype html>
<html lang="ur" dir="rtl"><head><meta charset="utf-8">
<style>
@font-face {{ font-family: 'Nastaliq'; src: url('{nastaliq}'); }}
@font-face {{ font-family: 'Naskh'; src: url('{naskh}'); }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:1080px; height:1350px; }}
body {{
  background: #0b1a2e;
  background-image: radial-gradient(circle at 85% 10%, #163a63 0%, rgba(11,26,46,0) 55%),
                    radial-gradient(circle at 10% 95%, #0f5132 0%, rgba(11,26,46,0) 50%);
  color:#f5f7fa; font-family:'Naskh', serif; display:flex; flex-direction:column; overflow:hidden;
}}
.top {{ display:flex; justify-content:space-between; align-items:center; padding:64px 72px 0; }}
.tag {{ background:#e11d2e; color:#fff; font-family:'Naskh'; font-weight:700; font-size:40px;
        padding:10px 34px 18px; border-radius:14px; }}
.cat {{ color:#9fb3c8; font-size:34px; font-weight:600; }}
.flagbar {{ height:10px; margin:44px 72px 0; border-radius:6px;
            background:linear-gradient(to left, #01411c 0 75%, #ffffff 75% 100%); }}
.main {{ flex:1; display:flex; flex-direction:column; justify-content:center; padding:10px 72px 30px; overflow:hidden; }}
.headline {{ font-family:'Nastaliq'; font-weight:700; font-size:{hsize}px; line-height:2.05; color:#ffffff; }}
.summary {{ font-family:'Naskh'; font-size:{ssize}px; line-height:1.85; color:#d6e1ec;
            padding-top:28px; }}
.foot {{ padding:30px 72px 48px;
         display:flex; justify-content:space-between; align-items:center;
         border-top:2px solid rgba(255,255,255,0.12); color:#9fb3c8; font-size:32px; }}
.foot b {{ color:#ffffff; font-weight:700; }}
</style></head>
<body>
  <div class="top"><div class="tag">تازہ خبر</div><div class="cat">{category}</div></div>
  <div class="flagbar"></div>
  <div class="main"><div class="headline">{headline}</div>
  <div class="summary">{summary}</div></div>
  <div class="foot"><div>ذریعہ: <b>{source}</b></div><div>{date}</div></div>
</body></html>"""


def sizes(headline: str, summary: str):
    h = len(headline)
    hsize = 76 if h <= 45 else 66 if h <= 70 else 58 if h <= 95 else 50
    s = len(summary)
    ssize = 40 if s <= 160 else 36 if s <= 240 else 32
    return hsize, ssize


def render(headline, summary, source, date, category, out):
    hsize, ssize = sizes(headline, summary)
    page_html = TEMPLATE.format(
        nastaliq=(FONTS / "NotoNastaliqUrdu.ttf").as_uri(),
        naskh=(FONTS / "NotoNaskhArabic.ttf").as_uri(),
        headline=html.escape(headline), summary=html.escape(summary),
        source=html.escape(source), date=html.escape(date),
        category=html.escape(category), hsize=hsize, ssize=ssize,
    )
    tmp = pathlib.Path(out).with_suffix(".html")
    tmp.write_text(page_html, encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        pg.goto(tmp.resolve().as_uri())
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        # Overflow check: summary must end above the footer
        overflow = pg.evaluate(
            "(() => { const m = document.querySelector('.main'); return m.scrollHeight > m.clientHeight + 2; })()"
        )
        if str(out).lower().endswith((".jpg", ".jpeg")):
            pg.screenshot(path=str(out), type="jpeg", quality=90)
        else:
            pg.screenshot(path=str(out), type="png")
        b.close()
    tmp.unlink(missing_ok=True)
    return not overflow


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--headline", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--category", default="پاکستان")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ok = render(a.headline, a.summary, a.source, a.date, a.category, a.out)
    print(("OK " if ok else "OVERFLOW (shorten text) ") + a.out)
