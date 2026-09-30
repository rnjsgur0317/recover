# -*- coding: utf-8 -*-
"""MONARCH V3 음원 — 직접 합성한 오리지널(결과 mp3 는 로컬 전용). 하이브리드 트랩 · 오케스트라: 펀치 있는 킥 · 808 · 스네어/클랩 · 하이햇 롤
· 브라암 · 슈퍼소우 패드 · 아르페지오 · 합창 · 라이저 · 역재생 스웰 · 임팩트 · 사이드체인. 150 BPM(한 박 .4 초) — 13.8 에서 거꾸로 센 격자.
흐름(초): 0.5 어둠(드론 · 심장 박동 킥이 계수기 눈금마다, 점점 빨라짐 · 속삭임) → 7.8 번개(스네어 롤 · 라이저) → 10.2 정적 → 10.4 섬광 일격
→ 11.0 · 11.8 · 12.6 ALL HAIL(808 · 합창 외침) → 13.6 섬광 → 13.8 드롭(C#m · A · D · G#) → 16.6 아르페지오 → 20.2 빌드
→ 20.6 · 21.4 · 22.2 상징의 일격 셋 → 23.0 이름(마지막 화음) → 26 끝. 페이지(monarch3_gl.html)의 시각표와 같은 값을 쓴다."""
import os, subprocess
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR, END = 44100, 26.0
N = int(END * SR)
PUB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public") + os.sep
rs = np.random.RandomState(7)
T = dict(BG=.5, POP=1.0, CNT=1.4, W0=2.0, LIGHT=7.8, ZERO=10.2, FLASH1=10.4, HAIL=11.0, FLASH2=13.6, REVEAL=13.8, S2=16.6, S3=18.6, HERO=20.6, TITLE=23.0)
SYMS = [20.6, 21.4, 22.2]
K = 28; TICKS = [T["CNT"] + (T["ZERO"] - T["CNT"]) * (k / K) ** .6 for k in range(K + 1)]
WORDS = [T["W0"] + k * .42 for k in range(16)]
BOLTS = [7.8, 8.25, 8.6, 8.9, 9.15, 9.4, 9.6, 9.78, 9.95, 10.08, 10.2, 10.3, 14.4, 17.3, 19.9, 22.8]
HAILS = [T["HAIL"] + k * .8 for k in range(3)]

def S(t): return int(round(t * SR))
def _sos(kind, f, o=2): return butter(o, f, kind, fs=SR, output="sos")
def lp(f, x, o=2): return sosfilt(_sos("lowpass", min(f, SR * .45), o), x)
def hp(f, x, o=2): return sosfilt(_sos("highpass", f, o), x)
def bp(lo, hi, x, o=2): return sosfilt(_sos("bandpass", [lo, min(hi, SR * .45)], o), x)
def tt(d): return np.arange(int(d * SR)) / SR
def env(n, a, r): t = np.arange(n) / SR; d = n / SR; return np.minimum(1, t / max(a, 1e-4)) * np.clip((d - t) / max(r, 1e-4), 0, 1)
def add(buf, x, t, pan=0., v=1.):
    i = S(t)
    if i >= N or i + len(x) <= 0: return
    if i < 0: x = x[-i:]; i = 0
    j = min(N, i + len(x)); x = x[: j - i] * v; buf[i:j, 0] += x * np.sqrt(.5 - pan * .5); buf[i:j, 1] += x * np.sqrt(.5 + pan * .5)
def addw(buf, x, t, v=1., d=.013): add(buf, x, t, -.4, v); add(buf, x, t + d, .4, v)     # 넓게: 한쪽을 살짝 늦춘다
mid = lambda m: 440 * 2 ** ((m - 69) / 12)
def saw(ph): return 2 * (ph % 1) - 1

# ── 소리 ──
def kick(v=1., tone=50):
    t = tt(.55); x = np.sin(2 * np.pi * np.cumsum(tone + 160 * np.exp(-t * 38)) / SR) * np.exp(-t * 6.5) + hp(2000, rs.randn(len(t))) * np.exp(-t * 320) * .35
    return np.tanh(x * 1.9) * v
def k808(f, dur, v=1., glide=0.):                                   # 808: 머리에서 살짝 높게 → 음, 긴 꼬리 · 포화
    t = tt(dur + .25); fr = f * (1 + glide * np.exp(-t * 9)) * (1 + .9 * np.exp(-t * 60)); ph = np.cumsum(fr) / SR
    x = np.sin(2 * np.pi * ph) + .22 * np.sin(4 * np.pi * ph); e = np.minimum(1, t / .004) * np.exp(-t * .8) * np.clip((dur + .25 - t) / .25, 0, 1)
    return np.tanh(x * e * 2.8) * .8 * v
def snare(v=1.):
    t = tt(.45); body = np.sin(2 * np.pi * np.cumsum(185 + 60 * np.exp(-t * 50)) / SR) * np.exp(-t * 22) * .7
    return np.tanh((body + bp(1200, 9000, rs.randn(len(t))) * np.exp(-t * 16) * .9) * 1.6) * v
def clap(v=1.):
    t = tt(.4); e = sum(np.exp(-np.maximum(t - d, 0) * 120) * (t >= d) for d in (0, .011, .022, .034)) + np.exp(-t * 13) * .5 * (t >= .034)
    return np.tanh(bp(900, 3500, rs.randn(len(t))) * e * 1.5) * v * .8
def hat(v=1., op=False): t = tt(.5 if op else .08); return hp(7500, rs.randn(len(t)), 3) * np.exp(-t * (7 if op else 70)) * v * .5
def crash(v=1., d=3.): t = tt(d); n = rs.randn(len(t)); return (hp(3500, n) * .8 + bp(5000, 12000, n) * .5) * np.exp(-t * 1.3) * v * .5
def impact(v=1.):
    t = tt(3.); boom = np.sin(2 * np.pi * np.cumsum(28 + 90 * np.exp(-t * 5)) / SR) * np.exp(-t * 1.1) * 1.4
    return np.tanh((boom + lp(1200, rs.randn(len(t))) * np.exp(-t * 3) * .8 + hp(2500, rs.randn(len(t))) * np.exp(-t * 9) * .5) * 1.5) * v
def braam(notes, dur, v=1.):                                         # 거대한 금관 같은 톱니 뭉치 · 열리는 필터 · 일그러짐
    t = tt(dur); x = np.zeros(len(t))
    for m in notes:
        for d in np.linspace(-.18, .18, 7): x += saw(mid(m) * 2 ** (d / 12) * t + rs.rand())
    e = np.minimum(1, t / .03) * np.exp(-t * .9); out = np.zeros(len(t)); zi = None
    for i in range(0, len(t), 512):
        so = _sos("lowpass", 150 + 4000 * e[i] ** 1.5)
        if zi is None: zi = np.zeros((so.shape[0], 2))
        out[i:i + 512], zi = sosfilt(so, x[i:i + 512], zi=zi)
    out += np.sin(2 * np.pi * mid(notes[0] - 12) * t) * 3
    return np.tanh(out * e * .35) * v
def supersaw(notes, dur, v=1., cut=2200, att=.2, rel=.5):
    t = tt(dur); x = np.zeros(len(t))
    for m in notes:
        for d in np.linspace(-.22, .22, 7): x += saw(mid(m) * 2 ** (d / 12) * t + rs.rand())
    return lp(cut, x) * env(len(t), att, rel) * v / len(notes) / 7 * 2.4
def pluck(m, v=1., dur=.35):
    t = tt(dur); f = mid(m); x = np.zeros(len(t))
    for k in range(1, 18):
        if f * k > 15000: break
        x += np.sin(2 * np.pi * f * k * t + k) / k * np.exp(-t * (6 + k * 4.5))
    return x * v * .6
def choir(notes, dur, v, vowel=(700, 1150, 2600), att=.3, rel=.6):
    t = tt(dur); src = np.zeros(len(t))
    for m in notes:
        for k in range(6):
            f = mid(m) * 2 ** (rs.uniform(-.12, .12) / 12); vib = 1 + .006 * np.sin(2 * np.pi * (5 + rs.rand()) * t + rs.rand() * 6); src += saw(np.cumsum(f * vib) / SR + rs.rand())
    x = bp(vowel[0] * .75, vowel[0] * 1.3, src) + .8 * bp(vowel[1] * .8, vowel[1] * 1.25, src) + .35 * bp(vowel[2] * .85, vowel[2] * 1.2, src) + lp(500, src) * .15
    return x * env(len(t), att, rel) * v / (len(notes) * 6) * 3.2
def riser(d, v=1.):
    t = tt(d); u = t / d; return lp(9000, hp(600, rs.randn(len(t))) * u ** 2.2 * .6 + saw(np.cumsum(90 * 2 ** (5 * u ** 1.6)) / SR) * u ** 2 * .25) * v
def swell(d, v=1.): t = tt(d); return (bp(300, 7000, rs.randn(len(t))) * np.exp(-t * 4))[::-1] * v   # 역재생 스웰
def bell(f, v, dur=3.):
    t = tt(dur); x = sum(np.sin(2 * np.pi * f * r * t) * a * np.exp(-t * dc) for r, a, dc in ((.5, .5, .6), (1, 1, .9), (1.19, .45, 1.4), (1.56, .5, 1.1), (2, .35, 1.6), (2.51, .3, 2.2)))
    return x * np.minimum(1, t / .002) * v
def tick(v=1.): t = tt(.05); return (hp(3000, rs.randn(len(t))) * np.exp(-t * 400) + np.sin(2 * np.pi * 2100 * t) * np.exp(-t * 200) * .5) * v
def crack(v=1.):
    t = tt(1.6); return (hp(1800, rs.randn(len(t))) * np.exp(-t * 20) * .8 + lp(180, rs.randn(len(t))) * np.exp(-t * 2.2) * 2.5) * v
def whisper(v=1.):
    t = tt(.9); nz = rs.randn(len(t)); f1 = 500 + 900 * rs.rand()
    return (bp(f1 * .8, f1 * 1.3, nz) + .7 * bp(1800, 3200, nz) + .4 * bp(4000, 7000, nz)) * np.sin(np.pi * t / .9) ** 2 * (.6 + .4 * np.sin(2 * np.pi * (5 + 3 * rs.rand()) * t)) * v

DR, BS, MU, FX = (np.zeros((N, 2)) for _ in range(4)); KICKS = []
def K_(t, v=1., tone=50): add(DR, kick(v, tone), t); KICKS.append((t, v))
tA = np.arange(N) / SR

# ── 0.5 ~ 10.4 어둠 속의 계수 ──
drone = np.sin(2 * np.pi * mid(25) * tA) * .55 + np.sin(2 * np.pi * mid(37) * tA) * .18
drone *= np.clip((tA - T["BG"]) / 1.5, 0, 1) * np.clip((T["ZERO"] - tA) / .03, 0, 1); BS += drone[:, None] * .5
addw(MU, supersaw([37, 40, 44, 49], 5.2, .5, cut=500, att=2.5, rel=.4), T["BG"])
addw(MU, supersaw([37, 40, 44, 49, 50], 4.9, .6, cut=1300, att=.4, rel=.05), 5.3)                    # 반음이 부딪히며 필터가 열린다
st = tt(5.2); addw(MU, (np.sin(2 * np.pi * mid(73) * st) + np.sin(2 * np.pi * mid(74) * st)) * np.clip(st / 5, 0, 1) ** 2 * .05, 5.0)
for k, tk in enumerate(TICKS[:-1]):                                     # 심장 박동 킥(쿵-쿵)과 시계 딸깍 — 눈금이 빨라질수록 몰아친다
    v = .45 + .5 * k / K; K_(tk, v, 46); add(DR, kick(v * .5, 46), tk + .13); add(FX, tick(.35), tk + .01, -.6 + 1.2 * rs.rand())
for tw in WORDS: add(FX, whisper(.5), tw, -.8 + 1.6 * rs.rand()); add(MU, bell(mid(73 + int(rs.choice([0, 3, 7, -2]))), .05, 2.), tw + .05, -.5 + rs.rand())
for i, tb in enumerate(BOLTS[:12]): add(FX, crack(.35 + .45 * i / 11), tb, -.6 + 1.2 * rs.rand())
tr, gap = T["LIGHT"], .2                                               # 7.8 ~ 10.2 점점 빨라지는 스네어 롤 · 라이저
while tr < T["ZERO"] - .02: add(DR, snare(.2 + .8 * (tr - T["LIGHT"]) / 2.4), tr); tr += gap; gap = max(.028, gap * .9)
add(FX, riser(T["ZERO"] - T["LIGHT"], 1.1), T["LIGHT"])
# 10.2 정적 → 10.4 섬광: 일격 · 브라암 · 808
add(FX, impact(1.3), T["FLASH1"]); add(MU, braam([37, 44, 49], 2.2, 1.2), T["FLASH1"]); add(DR, crash(.9), T["FLASH1"]); add(BS, k808(mid(37), 1.3, 1.1, .3), T["FLASH1"]); K_(T["FLASH1"], 1.2)
for i, m in enumerate((85, 88, 92, 97)): add(MU, bell(mid(m), .1, 2.5), T["FLASH1"] + .12 + i * .07, -.4 + .27 * i)
add(FX, swell(.55, .6), T["HAIL"] - .55)

# ── 11.0 ~ 13.6 ALL HAIL ──
for i, h in enumerate(HAILS):
    r = [25, 26, 28][i]; K_(h, 1.1); add(BS, k808(mid(r + 12), .7, 1.1, .35), h); add(DR, clap(1.), h); add(DR, crash(.5 + .2 * i, 2.), h)
    ch = [r + 36, r + 39, r + 43, r + 48]; add(MU, choir(ch, .32, 1.2 + .2 * i, (750, 1200, 2600), .01, .15), h); add(MU, choir(ch, .55, 1.2 + .2 * i, (400, 2000, 2800), .01, .3), h + .34)
    add(MU, braam([r + 12, r + 19, r + 24], .7, .9 + .1 * i), h)
    add(DR, snare(.8), h + .4); add(DR, clap(.6), h + .4)
x = 11.0
while x < 13.0 - .01: add(DR, hat(.35 + .25 * ((round((x - 11.0) / .1)) % 2 == 0)), x, .3); x += .1
tr, gap = 13.0, .1
while tr < T["FLASH2"] - .03: add(DR, snare(.35 + .6 * (tr - 13.) / .6), tr); tr += gap; gap = max(.025, gap * .85)
add(FX, riser(.6, 1.), 13.0); add(FX, swell(.5, .6), T["FLASH2"] - .5)
add(FX, impact(1.2), T["FLASH2"]); add(DR, crash(.8), T["FLASH2"])

# ── 13.8 ~ 20.2 드롭: C#m · A · D · G# ──
BAR = 1.6
BARS = [(13.8, 25, [49, 52, 56]), (15.4, 33, [45, 49, 52]), (17.0, 26, [50, 54, 57]), (18.6, 32, [44, 48, 51])]
for bi, (b0, root, ch) in enumerate(BARS):
    K_(b0, 1.15); K_(b0 + 1.0, .9); K_(b0 + 1.4, .55)
    add(BS, k808(mid(root + 12), .85, 1.05, .25 if bi else .5), b0); add(BS, k808(mid(root + 12), .35, .9, .4), b0 + 1.0); add(BS, k808(mid(root + 24), .18, .6), b0 + 1.4)
    add(DR, snare(.95), b0 + .8); add(DR, clap(.8), b0 + .8)
    for s8 in range(8):
        tq = b0 + s8 * .2
        if s8 == 7:
            for r3 in range(4): add(DR, hat(.3 + .1 * r3), tq + r3 * .05, .3)          # 마디 끝의 32분 롤
        else: add(DR, hat(.45 if s8 % 2 == 0 else .3), tq, .3)
    add(DR, hat(.35, True), b0 + .6, -.3); add(DR, hat(.3, True), b0 + 1.4, -.3)
    add(DR, crash(.7 if bi == 0 else .45, 2.2), b0)
    addw(MU, supersaw(ch + [ch[0] + 12], BAR + .1, .75, cut=2400 if bi < 2 else 3800, att=.02, rel=.1), b0)
    add(MU, choir([c + 12 for c in ch], BAR, .7 + .15 * bi, att=.08, rel=.3), b0)
    add(MU, braam([ch[0] - 12, ch[0] - 5, ch[0]], .45, .75), b0); add(MU, braam([ch[0] - 12, ch[0] - 5, ch[0]], .3, .55), b0 + 1.0)
    if b0 + BAR > T["S2"]:                                               # 16.6 부터 16분 아르페지오
        pat = [0, 1, 2, 3, 2, 1, 2, 3]; notes = ch + [ch[0] + 12]
        for s16 in range(16):
            tq = b0 + s16 * .1
            if tq >= T["S2"] - .01: add(MU, pluck(notes[pat[s16 % 8]] + 12, .55 + .2 * (s16 % 4 == 0)), tq, .35 * np.sin(s16))
add(FX, crash(.6), T["S2"]); add(FX, swell(.4, .5), T["S2"] - .4); add(DR, crash(.9), T["S3"]); add(MU, choir([56, 61, 64, 68], 1.6, .9, att=.05, rel=.4), T["S3"])
tr = 20.2                                                                # 20.2 빌드
while tr < T["HERO"] - .02: add(DR, snare(.45 + .5 * (tr - 20.2) / .4), tr); tr += .05
add(FX, riser(.4, 1.2), 20.2)

# ── 20.6 · 21.4 · 22.2 상징의 일격 셋 ──
for i, (tp, r) in enumerate(zip(SYMS, (25, 26, 32))):
    v = 1. + .15 * i; K_(tp, 1.3); add(BS, k808(mid(r + 12), .75, 1.25, .45), tp); add(FX, impact(v), tp); add(DR, crash(.7 + .15 * i, 2.5), tp)
    add(MU, braam([r + 12, r + 19, r + 24, r + 28], .75, v), tp); add(MU, choir([r + 36, r + 40, r + 43, r + 48], .6, 1.3 * v, (650, 1100, 2600), .01, .35), tp)
    if i < 2: add(FX, swell(.35, .45), tp + .8 - .35)
# 23.0 이름: 마지막 화음
t0 = T["TITLE"]; K_(t0, 1.2); add(BS, k808(mid(37), 2.6, 1.1, .3), t0); add(FX, impact(1.1), t0); add(DR, crash(1., 3.5), t0)
add(MU, braam([37, 44, 49, 52], 3., 1.1), t0); addw(MU, supersaw([49, 52, 56, 61, 63], 3., .9, cut=3000, att=.02, rel=1.4), t0); add(MU, choir([61, 64, 68, 73, 75], 3., 1.1, att=.05, rel=1.4), t0)
for i, m in enumerate((73, 80, 85)): add(MU, bell(mid(m), .3, 3.), t0 + .05 + i * .12, -.3 + .3 * i)

# ── 믹스: 사이드체인 · 잔향 · 마스터 ──
KE = np.zeros(N)
for tk, v in KICKS:
    i = S(tk); n = min(N - i, int(.35 * SR))
    if n > 0: KE[i:i + n] = np.maximum(KE[i:i + n], np.exp(-np.arange(n) / SR * 11) * min(1, v))
MU *= (1 - .55 * KE)[:, None]; FX *= (1 - .25 * KE)[:, None]
def verb(buf, sec=2.8, dec=1.8, wet=.3, seed=3):
    r = np.random.RandomState(seed); n = int(sec * SR); e = np.exp(-np.arange(n) / SR * dec); pre = np.zeros(int(.025 * SR))
    L = np.concatenate([pre, lp(6000, r.randn(n) * e)]); R = np.concatenate([pre, lp(6000, r.randn(n) * e)])
    out = buf.copy(); out[:, 0] += fftconvolve(buf[:, 0], L)[:N] * wet * .02; out[:, 1] += fftconvolve(buf[:, 1], R)[:N] * wet * .02; return out
mix = verb(DR, .7, 6., .12, 5) + BS * .95 + verb(MU, 2.8, 1.8, .35, 3) * .8 + verb(FX, 2.2, 2.2, .25, 7) * .9
mix[:int(.3 * SR)] *= np.linspace(0, 1, int(.3 * SR))[:, None]
fo = S(25.2); mix[fo:] *= np.linspace(1, 0, N - fo)[:, None] ** 2
pk = np.max(np.abs(mix)); mix = (np.tanh(mix / pk * 2.) / np.tanh(2.) * .7).astype(np.float32)
p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "256k", PUB + "monarch3_cut.mp3"], input=mix.tobytes())
print("mp3", p.returncode, round(len(mix) / SR, 2), "peak", round(float(pk), 3))
