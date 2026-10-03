#!/usr/bin/env python3
"""Neurafy "AI prompt" Shorts maker (v2: more motion and punch).

Renders a 1080x1920 MP4 (about 25 s) from a JSON spec:
  hook (price stamp + flash) -> chat screen where the prompt types itself,
  with step labels and a timer -> AI reply -> result with confetti -> follow CTA.
Background audio (pad, 120 bpm beat, bass, typing clicks, impacts, dings) is
synthesized, so no music licence is needed.

Usage:
  python3 make_short.py spec.json out.mp4 [--preview preview.jpg]

Spec keys: hook1, hook2 (big stamp), sub, tool, prompt, reply (list of lines;
a line starting with "!" is drawn bold/yellow), steps (3 labels), result1,
chips (list), cta1, cta2, cta3.
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
body{background:#07051a;font-family:'Inter','Noto Color Emoji',sans-serif;color:#fff}
#bg{position:absolute;inset:0;overflow:hidden;background:#07051a}
.blob{position:absolute;width:1100px;height:1100px;border-radius:50%;filter:blur(40px);opacity:.75}
.b1{background:radial-gradient(circle,#7c3aed 0%,rgba(124,58,237,0) 65%);left:-350px;top:-300px}
.b2{background:radial-gradient(circle,#0891b2 0%,rgba(8,145,178,0) 65%);left:350px;top:1100px}
.b3{background:radial-gradient(circle,#db2777 0%,rgba(219,39,119,0) 65%);left:450px;top:200px;opacity:.35}
#grid{position:absolute;inset:-100px;background-image:linear-gradient(rgba(255,255,255,.06) 2px,transparent 2px),
 linear-gradient(90deg,rgba(255,255,255,.06) 2px,transparent 2px);background-size:90px 90px}
.dot{position:absolute;width:8px;height:8px;border-radius:50%;background:#e9d5ff}
#prog{position:absolute;top:0;left:0;right:0;height:12px;background:rgba(255,255,255,.12)}
#bar{height:100%;width:0;background:linear-gradient(90deg,#a78bfa,#fde047)}
.brand{position:absolute;top:96px;left:0;right:0;text-align:center;font:700 34px 'Poppins';letter-spacing:10px;color:#ddd6fe}
.scene{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:0 70px;opacity:0}
.hook1{font:700 92px/1.15 'Poppins','Noto Color Emoji';text-align:center}
.stamp{margin-top:40px;font:700 230px/1 'Poppins','Noto Color Emoji';color:#fde047;text-shadow:0 0 60px rgba(253,224,71,.55),0 10px 0 #b45309}
.sub{margin-top:70px;font:600 56px/1.3 'Poppins','Noto Color Emoji';color:#fff;text-align:center;
 background:rgba(124,58,237,.55);padding:18px 40px;border-radius:24px}
.step{font:700 46px 'Poppins','Noto Color Emoji';color:#1e1b4b;background:#fde047;padding:16px 40px;border-radius:999px;
 box-shadow:0 10px 30px rgba(253,224,71,.35);margin-bottom:46px}
.card{width:940px;background:rgba(17,12,40,.78);border:3px solid rgba(167,139,250,.45);border-radius:44px;padding:36px 38px 42px;
 box-shadow:0 30px 80px rgba(0,0,0,.5)}
.cardhead{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}
.pill{font:700 36px 'Poppins','Noto Color Emoji';background:#a78bfa;color:#1e1b4b;padding:12px 30px;border-radius:999px}
.timer{font:700 40px 'Poppins','Noto Color Emoji';color:#fde047;font-variant-numeric:tabular-nums}
.msg{font:500 38px/1.45 'Inter','Noto Color Emoji';border-radius:30px;padding:26px 32px;white-space:pre-wrap}
.me{background:linear-gradient(135deg,#7c3aed,#6d28d9);margin-left:40px;min-height:100px}
.ai{background:#0f172a;border:3px solid #334155;margin-top:8px;margin-right:30px;font-size:34px;min-height:100px}
.ai b{color:#fde047;font-weight:800}
.label{font:700 26px 'Inter';color:#c4b5fd;margin:0 0 10px 8px;letter-spacing:2px}
.r{text-align:right;margin-right:8px}
.caret{display:inline-block;width:5px;height:1em;background:#fff;vertical-align:-0.15em;margin-left:4px}
.big{font:700 120px/1.15 'Poppins','Noto Color Emoji';text-align:center}
.mid{font:600 62px/1.3 'Poppins','Noto Color Emoji';text-align:center;color:#e9d5ff}
.yel{color:#fde047;text-shadow:0 0 40px rgba(253,224,71,.4)}
.chips{display:flex;gap:26px;margin-top:60px}
.chip{font:700 50px 'Poppins','Noto Color Emoji';background:rgba(255,255,255,.12);border:3px solid rgba(255,255,255,.25);
 padding:18px 34px;border-radius:24px}
.follow{margin-top:60px;font:700 64px 'Poppins','Noto Color Emoji';background:#ef4444;color:#fff;padding:22px 60px;border-radius:999px;
 box-shadow:0 12px 40px rgba(239,68,68,.5)}
.cf{position:absolute;width:18px;height:30px;border-radius:4px}
#flash{position:absolute;inset:0;background:#fff;opacity:0;pointer-events:none}
</style></head><body>
<div id="bg"><div class="blob b1" id="b1"></div><div class="blob b2" id="b2"></div><div class="blob b3" id="b3"></div><div id="grid"></div></div>
<div id="prog"><div id="bar"></div></div><div class="brand">NEURAFY</div>
<div id="s1" class="scene"><div class="hook1" id="h1"></div><div class="stamp" id="h2"></div><div class="sub" id="sub"></div></div>
<div id="s2" class="scene" style="justify-content:flex-start;padding-top:230px"><div class="step" id="step"></div>
 <div id="wrap"><div class="card"><div class="cardhead"><span class="pill" id="tool"></span><span class="timer" id="timer"></span></div>
 <div class="label r">YOU</div><div class="msg me" id="me"></div>
 <div class="label" style="margin-top:26px">AI</div><div class="msg ai" id="ai"></div></div></div></div>
<div id="s3" class="scene"><div class="big" id="r1"></div><div class="chips" id="chips"></div></div>
<div id="conf"></div>
<div id="s4" class="scene"><div class="mid" id="c1"></div><div class="big yel" id="c2" style="margin-top:40px;font-size:98px"></div><div class="follow" id="c3"></div></div>
<div id="flash"></div>
<script>
let S, DOTS=[], CONF=[];
const $=id=>document.getElementById(id);
const clamp=x=>Math.max(0,Math.min(1,x));
const eob=x=>{const c1=1.70158,c3=c1+1;return 1+c3*Math.pow(x-1,3)+c1*Math.pow(x-1,2)};
const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;');
let seed=11;const rnd=()=>{seed=(seed*16807)%2147483647;return seed/2147483647};
function pop(el,t,t0,from=0.6){const p=clamp((t-t0)/0.3);el.style.opacity=p;el.style.transform=`scale(${from+(1-from)*eob(p)})`}
function scene(el,t,a,b){const o=Math.min(clamp((t-a)/0.22),clamp((b-t)/0.22));el.style.opacity=o;el.style.transform=`scale(${0.94+0.06*o})`}
function reply(m){let out=[],left=m;for(const raw of S.reply){if(left<=0)break;const bold=raw.startsWith('!');const line=bold?raw.slice(1):raw;
 const part=esc(line.slice(0,left));left-=line.length+1;out.push(bold?`<b>${part}</b>`:part)}return out.join('\n')}
window.setup=function(spec){S=spec;$('h1').textContent=S.hook1;$('h2').textContent=S.hook2;$('sub').textContent=S.sub;
 const L=[...S.hook2].length;$('h2').style.fontSize=(L<=6?230:Math.max(120,Math.floor(1400/L)))+'px';
 $('tool').textContent=S.tool;$('r1').textContent=S.result1;
 $('chips').innerHTML=S.chips.map((c,i)=>`<div class="chip" id="chip${i}">${esc(c)}</div>`).join('');
 $('c1').textContent=S.cta1;$('c2').textContent=S.cta2;$('c3').textContent=S.cta3;
 S.replyLen=S.reply.reduce((a,l)=>a+(l.startsWith('!')?l.length-1:l.length)+1,0);
 for(let i=0;i<26;i++){const d=document.createElement('div');d.className='dot';$('bg').appendChild(d);
  DOTS.push({el:d,x:rnd()*1080,y:rnd()*1920,v:40+rnd()*90,s:0.5+rnd()*1.2,ph:rnd()*6})}
 const cols=['#fde047','#a78bfa','#22d3ee','#f472b6','#4ade80','#fb923c'];
 for(let i=0;i<80;i++){const d=document.createElement('div');d.className='cf';d.style.background=cols[i%cols.length];$('conf').appendChild(d);
  CONF.push({el:d,x:rnd()*1080,vy:700+rnd()*700,vx:(rnd()-.5)*300,d:rnd()*0.35,r:rnd()*360,vr:(rnd()-.5)*900})}}
window.render=function(t){const T=S.T;
 // living background
 $('b1').style.transform=`translate(${Math.sin(t*.5)*160}px,${Math.cos(t*.4)*120}px)`;
 $('b2').style.transform=`translate(${Math.cos(t*.45)*180}px,${Math.sin(t*.35)*140}px)`;
 $('b3').style.transform=`translate(${Math.sin(t*.3+1)*200}px,${Math.cos(t*.5+2)*220}px)`;
 $('grid').style.transform=`translateY(${(t*45)%90}px)`;
 for(const d of DOTS){const y=((d.y-t*d.v)%1920+1920)%1920;d.el.style.transform=`translate(${d.x}px,${y}px) scale(${d.s})`;
  d.el.style.opacity=0.25+0.35*Math.sin(t*2+d.ph)}
 $('bar').style.width=(100*clamp(t/T.end))+'%';
 // hook
 scene($('s1'),t,-1,T.chat);pop($('h1'),t,0.08);
 const h2=$('h2'),p=clamp((t-T.stamp)/0.22);h2.style.opacity=p;
 const shake=t>T.stamp?Math.exp(-(t-T.stamp)*6)*Math.sin((t-T.stamp)*70)*14:0;
 h2.style.transform=`translate(${shake}px,0) rotate(-6deg) scale(${2.4-1.4*eob(p)})`;
 pop($('sub'),t,T.stamp+0.7);
 // chat
 scene($('s2'),t,T.chat,T.result);
 const steps=S.steps,st=$('step');let k=0,k0=T.chat;if(t>=T.type1){k=1;k0=T.type1}if(t>=T.reply0){k=2;k0=T.reply0}
 st.textContent=steps[k];pop(st,t,k0+0.05,0.5);
 $('wrap').style.transform=`translateY(${Math.sin(t*1.6)*8}px) scale(${1+0.035*clamp((t-T.chat)/(T.result-T.chat))})`;
 const el=Math.max(0,Math.min(t,T.reply1)-T.type0);$('timer').textContent='⏱ 00:'+String(Math.floor(el)).padStart(2,'0');
 const n=Math.floor(clamp((t-T.type0)/(T.type1-T.type0))*S.prompt.length);
 const caret=t<T.type1?true:(t<T.type1+0.6&&Math.floor(t*3)%2==0);
 const me=$('me');me.innerHTML=esc(S.prompt.slice(0,n))+(caret?'<span class="caret"></span>':'');
 const sp=clamp((t-T.type1)/0.45);me.style.boxShadow=t>T.type1?`0 0 0 ${sp*36}px rgba(167,139,250,${0.6*(1-sp)})`:'none';
 const ai=$('ai');
 if(t<T.reply0){ai.style.opacity=clamp((t-T.type1-0.2)/0.2);const q=1+Math.floor(t*5)%3;ai.innerHTML='<span style="opacity:.75">'+'● '.repeat(q)+'</span>';ai.style.borderColor='#334155';ai.style.boxShadow='none'}
 else{ai.style.opacity=1;ai.innerHTML=reply(Math.floor(clamp((t-T.reply0)/(T.reply1-T.reply0))*S.replyLen));
  if(t>T.reply1){const g=0.5+0.5*Math.sin((t-T.reply1)*8);ai.style.borderColor='#fde047';ai.style.boxShadow=`0 0 ${20+30*g}px rgba(253,224,71,${0.35+0.25*g})`}
  else{ai.style.borderColor='#334155';ai.style.boxShadow='none'}}
 // result + confetti
 scene($('s3'),t,T.result,T.cta);pop($('r1'),t,T.result+0.08,0.3);
 S.chips.forEach((c,i)=>pop($('chip'+i),t,T.result+0.55+0.25*i,0.4));
 for(const c of CONF){const dt=t-T.result-c.d;if(dt<0||t>T.cta+0.3){c.el.style.opacity=0;continue}
  const y=-60+c.vy*dt+380*dt*dt,x=c.x+c.vx*dt;c.el.style.opacity=clamp((T.cta+0.3-t)/0.4);
  c.el.style.transform=`translate(${x}px,${y}px) rotate(${c.r+c.vr*dt}deg)`}
 // CTA
 scene($('s4'),t,T.cta,T.end+1);pop($('c1'),t,T.cta+0.08);pop($('c2'),t,T.cta+0.45);
 const f=$('c3');pop(f,t,T.cta+0.9,0.4);if(t>T.cta+1.2)f.style.transform=`scale(${1+0.06*Math.sin((t-T.cta)*7)})`;
 // flashes
 let fl=0;for(const [a,s] of [[T.stamp,0.55],[T.result,0.35]]){if(t>=a)fl=Math.max(fl,s*Math.exp(-(t-a)*9))}$('flash').style.opacity=fl}
</script></body></html>"""


def timeline(spec):
    reply_len = sum(len(l.lstrip("!")) + 1 for l in spec["reply"])
    T = {"stamp": 0.9, "chat": 3.6}
    T["type0"] = T["chat"] + 0.45
    T["type1"] = T["type0"] + len(spec["prompt"]) / 32.0          # 32 chars/sec
    T["reply0"] = T["type1"] + 0.9                                  # "thinking" dots
    T["reply1"] = T["reply0"] + reply_len / 80.0                    # 80 chars/sec
    T["result"] = T["reply1"] + 1.4
    T["cta"] = T["result"] + 2.8
    T["end"] = T["cta"] + 3.4
    return T


def _place(out, sig, at):
    i = int(at * SR)
    if i >= len(out) or i < 0:
        return
    m = min(len(sig), len(out) - i)
    out[i:i + m] += sig[:m]


def synth_audio(T, path):
    n = int(T["end"] * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    rng = np.random.default_rng(7)
    beat = 0.5                                                     # 120 bpm
    roots = [110.0, 87.31, 130.81, 98.0]                           # A2 F2 C3 G2
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (261.63, 329.63, 392.0), (196.0, 246.94, 293.66)]
    bar = 4 * beat
    # pad
    for i in range(int(T["end"] / bar) + 1):
        a, b = i * bar, min((i + 1) * bar + 0.4, T["end"])
        m = (t >= a) & (t < b)
        tt = t[m] - a
        env = np.minimum(1, tt / 0.3) * np.minimum(1, (b - t[m]) / 0.4)
        for f in chords[i % 4]:
            out[m] += 0.035 * env * (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 1.004 * tt))
    drop = T["stamp"]
    # riser into the drop
    m = t < drop
    out[m] += 0.10 * rng.standard_normal(m.sum()) * (t[m] / drop) ** 2
    # impact at the drop
    k = np.arange(int(0.8 * SR)) / SR
    _place(out, 0.9 * np.sin(2 * np.pi * (45 + 60 * np.exp(-k * 8)) * k) * np.exp(-k * 4.5), drop)
    _place(out, 0.25 * rng.standard_normal(int(0.25 * SR)) * np.exp(-np.arange(int(0.25 * SR)) / SR * 14), drop)
    # drums + bass from the drop
    kk = np.arange(int(0.2 * SR)) / SR
    kick = 0.55 * np.sin(2 * np.pi * (48 + 90 * np.exp(-kk * 30)) * kk) * np.exp(-kk * 16)
    hh = np.arange(int(0.035 * SR)) / SR
    cl = np.arange(int(0.15 * SR)) / SR
    x, b = drop, 0
    end = T["end"] - 0.6
    while x < end:
        _place(out, kick, x)
        if b % 2 == 1:
            clap = 0.18 * rng.standard_normal(len(cl)) * np.exp(-cl * 28)
            _place(out, np.convolve(clap, np.ones(4) / 4, mode="same"), x)
        root = roots[int(x / bar) % 4]
        for e in (0, beat / 2):
            bt = np.arange(int(0.22 * SR)) / SR
            env = np.exp(-bt * 9)
            bass = sum(np.sin(2 * np.pi * root * h * bt) / h for h in (1, 2, 3))
            _place(out, 0.12 * env * bass, x + e)
        x += beat
        b += 1
    # hats on off-beats
    x = drop + beat / 2
    while x < end:
        _place(out, 0.045 * rng.standard_normal(len(hh)) * np.exp(-hh * 120), x)
        x += beat
    # typing clicks
    c = np.arange(int(0.012 * SR)) / SR
    x = T["type0"]
    while x < T["type1"]:
        _place(out, 0.09 * rng.standard_normal(len(c)) * np.exp(-c * 400), x)
        x += 1 / 16.0 + rng.uniform(-0.01, 0.01)
    # dings: send and result
    d = np.arange(int(0.7 * SR)) / SR
    ding = (np.sin(2 * np.pi * 1318.5 * d) + 0.6 * np.sin(2 * np.pi * 1975.5 * d)) * np.exp(-d * 6)
    _place(out, 0.18 * ding, T["type1"])
    _place(out, 0.28 * ding, T["result"])
    # riser before the result
    rr = np.arange(int(1.0 * SR)) / SR
    _place(out, 0.08 * rng.standard_normal(len(rr)) * (rr / rr[-1]) ** 3, T["result"] - 1.0)
    # whooshes on scene changes
    w = np.arange(int(0.35 * SR)) / SR
    for s in (T["chat"], T["cta"]):
        wh = 0.14 * rng.standard_normal(len(w)) * np.sin(np.pi * w / w[-1]) ** 2
        _place(out, np.convolve(wh, np.ones(30) / 30, mode="same"), s - 0.12)
    out *= np.minimum(1, (T["end"] - t) / 0.8)                      # fade out
    out = np.tanh(out * 1.4)                                        # gentle glue/limit
    out = out / max(1e-9, np.abs(out).max()) * 0.85
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
         "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.set_content(HTML)
        pg.evaluate("document.fonts.ready")
        pg.evaluate("s => setup(s)", spec)
        for f in range(frames):
            pg.evaluate("t => render(t)", f / FPS)
            ff.stdin.write(pg.screenshot(type="jpeg", quality=90))
            if preview and f == int((T["reply1"] + 0.6) * FPS):
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
