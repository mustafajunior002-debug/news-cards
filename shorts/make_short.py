#!/usr/bin/env python3
"""Neurafy "AI prompt" Shorts maker.

Renders a 1080x1920 MP4 (about 25 s) from a JSON spec:
  hook  -> chat screen where the prompt types itself and the AI reply appears
        -> result line -> follow call-to-action.
Background audio (soft pad, beat, typing clicks) is synthesized, so no music
licence is needed.

Usage:
  python3 make_short.py spec.json out.mp4 [--preview preview.jpg]

Spec keys: hook1, hook2, sub, tool, prompt, reply (list of lines; a line
starting with "!" is drawn bold/yellow), result1, result2, cta1, cta2, cta3.
"""
import json
import pathlib
import subprocess
import sys
import wave

import numpy as np
from playwright.sync_api import sync_playwright

FPS = 30
SR = 44100

HTML = r"""<!doctype html><html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden}
body{background:#0a0820;font-family:'Inter','Noto Color Emoji',sans-serif;color:#fff}
#bg{position:absolute;inset:0;background:
 radial-gradient(circle at 18% 14%, #5b21b6 0%, rgba(10,8,32,0) 46%),
 radial-gradient(circle at 86% 82%, #0e7490 0%, rgba(10,8,32,0) 46%), #0a0820}
.brand{position:absolute;top:120px;left:0;right:0;text-align:center;font:700 34px 'Poppins';letter-spacing:8px;color:#c4b5fd}
.scene{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:0 80px;opacity:0}
.hook1,.hook2{font:700 108px/1.15 'Poppins','Noto Color Emoji';text-align:center}
.hook2{color:#fde047;margin-top:10px}
.sub{margin-top:60px;font:600 54px/1.3 'Poppins','Noto Color Emoji';color:#e9d5ff;text-align:center}
.pill{font:700 40px 'Poppins','Noto Color Emoji';background:#a78bfa;color:#1e1b4b;padding:16px 38px;border-radius:999px;margin-bottom:44px}
.card{width:920px;background:rgba(255,255,255,.06);border:2px solid rgba(255,255,255,.14);border-radius:40px;padding:40px}
.msg{font:500 39px/1.45 'Inter','Noto Color Emoji';border-radius:30px;padding:28px 34px;white-space:pre-wrap}
.me{background:#7c3aed;margin-left:50px;min-height:110px}
.ai{background:#111827;border:2px solid #334155;margin-top:30px;margin-right:30px;font-size:35px;min-height:110px}
.ai b{color:#fde047;font-weight:800}
.label{font:700 28px 'Inter';color:#c4b5fd;margin:0 0 10px 8px;letter-spacing:1px}
.caret{display:inline-block;width:5px;height:1em;background:#fff;vertical-align:-0.15em;margin-left:4px}
.big{font:700 100px/1.15 'Poppins','Noto Color Emoji';text-align:center}
.mid{font:600 60px/1.3 'Poppins','Noto Color Emoji';text-align:center;color:#e9d5ff}
.yel{color:#fde047}
</style></head><body><div id="bg"></div><div class="brand">NEURAFY</div>
<div id="s1" class="scene"><div class="hook1" id="h1"></div><div class="hook2" id="h2"></div><div class="sub" id="sub"></div></div>
<div id="s2" class="scene" style="justify-content:flex-start;padding-top:250px"><div class="pill" id="tool"></div>
 <div class="card"><div class="label" style="text-align:right;margin-right:8px">YOU</div><div class="msg me" id="me"></div>
 <div class="label" style="margin-top:26px">AI</div><div class="msg ai" id="ai"></div></div></div>
<div id="s3" class="scene"><div class="big" id="r1"></div><div class="mid" id="r2" style="margin-top:50px"></div></div>
<div id="s4" class="scene"><div class="mid" id="c1"></div><div class="big yel" id="c2" style="margin-top:50px"></div><div class="mid" id="c3" style="margin-top:50px"></div></div>
<script>
let S;
const $=id=>document.getElementById(id);
const clamp=x=>Math.max(0,Math.min(1,x));
const eob=x=>{const c1=1.70158,c3=c1+1;return 1+c3*Math.pow(x-1,3)+c1*Math.pow(x-1,2)};
const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;');
function pop(el,t,t0){const p=clamp((t-t0)/0.3);el.style.opacity=p;el.style.transform=`scale(${0.7+0.3*eob(p)})`}
function scene(el,t,a,b){el.style.opacity=Math.min(clamp((t-a)/0.25),clamp((b-t)/0.25))}
function reply(m){let out=[],left=m;for(const raw of S.reply){if(left<=0)break;const bold=raw.startsWith('!');const line=bold?raw.slice(1):raw;
 const part=esc(line.slice(0,left));left-=line.length+1;out.push(bold?`<b>${part}</b>`:part)}return out.join('\n')}
window.setup=function(spec){S=spec;$('h1').textContent=S.hook1;$('h2').textContent=S.hook2;$('sub').textContent=S.sub;
 $('tool').textContent=S.tool;$('r1').textContent=S.result1;$('r2').textContent=S.result2;
 $('c1').textContent=S.cta1;$('c2').textContent=S.cta2;$('c3').textContent=S.cta3;
 S.replyLen=S.reply.reduce((a,l)=>a+(l.startsWith('!')?l.length-1:l.length)+1,0)}
window.render=function(t){const T=S.T;
 scene($('s1'),t,-1,T.chat);pop($('h1'),t,0.1);pop($('h2'),t,0.55);pop($('sub'),t,1.4);
 scene($('s2'),t,T.chat,T.result);
 const n=Math.floor(clamp((t-T.type0)/(T.type1-T.type0))*S.prompt.length);
 const caret=t<T.type1?true:(t<T.type1+0.6&&Math.floor(t*3)%2==0);
 $('me').innerHTML=esc(S.prompt.slice(0,n))+(caret?'<span class="caret"></span>':'');
 const ai=$('ai');
 if(t<T.reply0){ai.style.opacity=clamp((t-T.type1-0.2)/0.2);const k=1+Math.floor(t*4)%3;ai.innerHTML='<span style="opacity:.7">'+'● '.repeat(k)+'</span>'}
 else{ai.style.opacity=1;ai.innerHTML=reply(Math.floor(clamp((t-T.reply0)/(T.reply1-T.reply0))*S.replyLen))}
 scene($('s3'),t,T.result,T.cta);pop($('r1'),t,T.result+0.1);pop($('r2'),t,T.result+0.7);
 scene($('s4'),t,T.cta,T.end+1);pop($('c1'),t,T.cta+0.1);pop($('c2'),t,T.cta+0.6);pop($('c3'),t,T.cta+1.1)}
</script></body></html>"""


def timeline(spec):
    reply_len = sum(len(l.lstrip("!")) + 1 for l in spec["reply"])
    T = {"chat": 3.4}
    T["type0"] = T["chat"] + 0.5
    T["type1"] = T["type0"] + len(spec["prompt"]) / 30.0          # 30 chars/sec
    T["reply0"] = T["type1"] + 1.0                                  # "thinking" dots
    T["reply1"] = T["reply0"] + reply_len / 75.0                    # 75 chars/sec
    T["result"] = T["reply1"] + 1.8
    T["cta"] = T["result"] + 2.8
    T["end"] = T["cta"] + 3.6
    return T


def synth_audio(T, path):
    n = int(T["end"] * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    # soft pad: Am - F - C - G, 3 s per chord
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 164.81, 196.0), (196.0, 246.94, 293.66)]
    seg = 3.0
    for i in range(int(T["end"] / seg) + 1):
        a, b = i * seg, min((i + 1) * seg + 0.6, T["end"])
        m = (t >= a) & (t < b)
        tt = t[m] - a
        env = np.minimum(1, tt / 0.6) * np.minimum(1, (b - t[m]) / 0.6)
        for f in chords[i % 4]:
            out[m] += 0.05 * env * (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.003 * tt))
        out[m] += 0.06 * env * np.sin(2 * np.pi * chords[i % 4][0] / 2 * tt)
    # light beat at 100 bpm (kick on beats, hat on off-beats), starts with the chat
    beat = 0.6
    rng = np.random.default_rng(7)
    k = np.arange(int(0.18 * SR)) / SR
    kick = 0.32 * np.sin(2 * np.pi * (50 + 70 * np.exp(-k * 25)) * k) * np.exp(-k * 18)
    h = np.arange(int(0.04 * SR)) / SR
    hat = 0.04 * rng.standard_normal(len(h)) * np.exp(-h * 90)
    x = T["chat"]
    while x < T["end"] - 0.3:
        i = int(x * SR)
        out[i:i + len(kick)] += kick[: n - i]
        j = int((x + beat / 2) * SR)
        if j < n:
            out[j:j + len(hat)] += hat[: n - j]
        x += beat
    # typing clicks
    c = np.arange(int(0.012 * SR)) / SR
    x = T["type0"]
    while x < T["type1"]:
        i = int(x * SR)
        click = 0.07 * rng.standard_normal(len(c)) * np.exp(-c * 400)
        out[i:i + len(click)] += click[: n - i]
        x += 1 / 15.0 + rng.uniform(-0.01, 0.01)
    # whoosh on scene changes
    w = np.arange(int(0.35 * SR)) / SR
    for s in (T["chat"], T["result"], T["cta"]):
        i = int((s - 0.1) * SR)
        whoosh = 0.12 * rng.standard_normal(len(w)) * np.sin(np.pi * w / w[-1]) ** 2
        whoosh = np.convolve(whoosh, np.ones(30) / 30, mode="same")
        out[i:i + len(whoosh)] += whoosh[: n - i]
    out *= np.minimum(1, (T["end"] - t) / 1.0)                      # fade out
    out = out / max(1e-9, np.abs(out).max()) * 0.8
    pcm = (out * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def make(spec, out, preview=None):
    T = timeline(spec)
    spec = dict(spec, T=T)
    out = pathlib.Path(out)
    wav = out.with_suffix(".wav")
    synth_audio(T, wav)
    frames = int(T["end"] * FPS)
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg",
         "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.set_content(HTML)
        pg.evaluate("document.fonts.ready")
        pg.evaluate("s => setup(s)", spec)
        for f in range(frames):
            pg.evaluate("t => render(t)", f / FPS)
            ff.stdin.write(pg.screenshot(type="jpeg", quality=88))
            if preview and f == int((T["reply1"] + 0.5) * FPS):
                pg.screenshot(path=str(preview), type="jpeg", quality=85)
        b.close()
    ff.stdin.close()
    ff.wait()
    wav.unlink(missing_ok=True)
    return T


if __name__ == "__main__":
    args = sys.argv[1:]
    prev = None
    if "--preview" in args:
        i = args.index("--preview")
        prev = args[i + 1]
        del args[i:i + 2]
    spec = json.loads(pathlib.Path(args[0]).read_text(encoding="utf-8"))
    T = make(spec, args[1], prev)
    print(f"OK {args[1]} ({T['end']:.1f}s)")
