# -*- coding: utf-8 -*-
"""MONARCH 컷씬 음원 — 받은 음원을 쓰지 않고 직접 합성한 오리지널(결과 mp3 는 로컬 전용, 이 스크립트로 언제든 다시 만든다)
장엄하고 어두운 지배자의 곡: 낮은 울림 · 천둥 · 합창(모음 포먼트) · 파이프 오르간 · 금관 · 팀파니 · 타이코 · 종.
흐름(초): 0 어둠 · 0.6 / 2.9 천둥 → 4.0 차원문 · 5.1 눈이 뜨임(속삭임 · 유리 울림) → 7.5 금관 동기 · 팀파니 → 11.5 떨리는 현 → 12.6 오른눈 점화(총주 일격)
→ 14.5 오르간 · 합창 진행(C#m A F#m G#) · 종 → 18.5 타이코 · 금관 전면 · 20.5 네 개의 눈(일격) → 22.5 상승 → 23.8 충격파 → 26.0 마지막 화음 · 징 → 30.0 끝
페이지(monarch_gl.html)의 시각 상수 T 와 같은 값을 쓴다."""
import os, subprocess
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR, END = 44100, 30.0
N = int(END * SR)
PUB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public") + os.sep
rs = np.random.RandomState(11)
T = dict(L1=.6, L2=2.9, PORT=4.0, EYEO=5.1, EYEC=7.0, RISE=7.5, FACE=11.5, IGNITE=12.6, HALO=14.5, WIDE=18.5, STARE=20.5, POWER=22.5, SHOCK=23.8, HERO=26.0, TITLE=26.6)
def S(t): return int(round(t * SR))
def bp(lo, hi, x, order=2): return sosfilt(butter(order, [lo, hi], "bandpass", fs=SR, output="sos"), x)
def lp(f, x, order=2): return sosfilt(butter(order, f, "lowpass", fs=SR, output="sos"), x)
def hp(f, x, order=2): return sosfilt(butter(order, f, "highpass", fs=SR, output="sos"), x)
def add(buf, x, t, pan=0.):
    i = S(t)
    if i >= N: return
    j = min(N, i + len(x)); x = x[: j - i]; buf[i:j, 0] += x * np.sqrt(.5 - pan * .5); buf[i:j, 1] += x * np.sqrt(.5 + pan * .5)
mid = lambda m: 440 * 2 ** ((m - 69) / 12)
def saw(f, t): return 2 * ((t * f) % 1) - 1
def env(n, a, r, hold=None):
    t = np.arange(n) / SR; e = np.minimum(1, t / max(a, 1e-4)); d = n / SR; return e * np.minimum(1, np.maximum(0, (d - t) / max(r, 1e-4)))

# ── 음색 ──
def choir(notes, dur, v, vowel=(700, 1150, 2600), att=.8, rel=1.2):          # 합창: 목소리마다 흔들리는 톱니 → 모음 포먼트
    n = int(dur * SR); t = np.arange(n) / SR; src = np.zeros(n)
    for m in notes:
        for k in range(5):
            f = mid(m) * 2 ** (rs.uniform(-.14, .14) / 12); vib = 1 + .006 * np.sin(2 * np.pi * (5 + rs.rand()) * t + rs.rand() * 6)
            src += saw(1, np.cumsum(f * vib) / SR + rs.rand())
    x = bp(vowel[0] * .75, vowel[0] * 1.3, src) + .8 * bp(vowel[1] * .8, vowel[1] * 1.25, src) + .35 * bp(vowel[2] * .85, vowel[2] * 1.2, src)
    x += lp(500, src) * .15; return x * env(n, att, rel) * v / (len(notes) * 5) * 3
def organ(notes, dur, v, att=.25, rel=1.):                                   # 파이프 오르간: 8' 4' 2' 2⅔' + 약한 떨림
    n = int(dur * SR); t = np.arange(n) / SR; x = np.zeros(n); trem = 1 + .05 * np.sin(2 * np.pi * 5.6 * t)
    for m in notes:
        f = mid(m)
        for mul, a in ((1, 1), (2, .6), (3, .35), (4, .3), (6, .12), (8, .1)): x += np.sin(2 * np.pi * f * mul * t + rs.rand() * 6) * a
    x += bp(900, 4000, rs.randn(n)) * .03
    return x * trem * env(n, att, rel) * v / len(notes)
def brass(notes, dur, v, att=.12, rel=.5, bright=1.):                        # 금관: 겹친 톱니, 소리가 커질수록 필터가 열린다
    n = int(dur * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for m in notes:
        for d in (-.07, 0, .07): x += saw(mid(m) * 2 ** (d / 12), t + rs.rand())
    e = env(n, att, rel); out = np.zeros(n); blk = 512; zi = None
    for i in range(0, n, blk):
        fc = 180 + 2600 * bright * e[min(i, n - 1)] ** 1.5; sos = butter(2, min(fc, 12000), "lowpass", fs=SR, output="sos")
        if zi is None: zi = np.zeros((sos.shape[0], 2))
        out[i:i + blk], zi = sosfilt(sos, x[i:i + blk], zi=zi)
    return np.tanh(out * e * 1.2) * v / len(notes) * 1.3
def timpani(f, v):
    n = int(2.2 * SR); t = np.arange(n) / SR; x = sum(np.sin(2 * np.pi * f * r * t * (1 + .03 * np.exp(-t * 8))) * a * np.exp(-t * (1.6 + i)) for i, (r, a) in enumerate(((1, 1), (1.5, .5), (1.98, .35), (2.44, .2))))
    x += lp(900, rs.randn(n)) * np.exp(-t * 30) * .5; return x * v
def taiko(v, f=58):
    n = int(1.4 * SR); t = np.arange(n) / SR; x = np.sin(2 * np.pi * np.cumsum(f + 90 * np.exp(-t * 22)) / SR) * np.exp(-t * 4.5) * 1.2
    x += bp(200, 1500, rs.randn(n)) * np.exp(-t * 25) * .6; return np.tanh(x * 1.4) * v
def bell(f, v, dur=4.):                                                        # 관종: 어긋난 배음
    n = int(dur * SR); t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * r * t) * a * np.exp(-t * dcy) for r, a, dcy in ((.5, .5, .6), (1, 1, .9), (1.19, .45, 1.4), (1.56, .5, 1.1), (2, .35, 1.6), (2.51, .3, 2.2), (3.01, .2, 2.8)))
    return x * np.minimum(1, t / .002) * v
def thunder(v, dur=3.5, seed=0):
    r = np.random.RandomState(seed); n = int(dur * SR); t = np.arange(n) / SR; crack = hp(1500, r.randn(n)) * np.exp(-t * 18) * .6
    rum = lp(160, r.randn(n)) * (np.exp(-t * 1.1) * (1 + .6 * np.sin(2 * np.pi * 1.7 * t + r.rand() * 6))) * 3.; body = lp(700, r.randn(n)) * np.exp(-t * 3) * .8
    return (crack + rum + body) * v
def gong(v, dur=6.):
    n = int(dur * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for f in (62, 97, 133, 181, 227, 310, 402, 533): x += np.sin(2 * np.pi * f * (1 + .01 * np.exp(-t * 2)) * t + rs.rand() * 6) * np.exp(-t * (.5 + f / 900)) * (.6 + .4 * rs.rand())
    x += bp(300, 3000, rs.randn(n)) * np.exp(-t * 1.2) * .15 * np.minimum(1, t / .3); return x * v * .4
def riser(dur, v):
    n = int(dur * SR); t = np.arange(n) / SR; u = t / dur; x = hp(800, rs.randn(n)) * u ** 2.5 * .5 + np.sin(2 * np.pi * np.cumsum(80 * 2 ** (4 * u ** 1.5)) / SR) * u ** 2 * .3
    return x * v

M = np.zeros((N, 2))          # 음악
FX = np.zeros((N, 2))         # 효과(천둥 · 속삭임 · 충격)

# 0 ~ 4 어둠: 낮은 울림 · 바람 · 천둥
t_all = np.arange(N) / SR
drone = (np.sin(2 * np.pi * mid(25) * t_all) * .5 + np.sin(2 * np.pi * mid(32) * t_all) * .25 + np.sin(2 * np.pi * mid(37) * t_all + np.sin(2 * np.pi * .1 * t_all)) * .15)
drone *= np.minimum(1, t_all / 2.5) * (1 - .5 * np.clip((t_all - T["HALO"]) / 4, 0, 1)) * np.clip((29.6 - t_all) / 2, 0, 1)
wind = lp(420, rs.randn(N)) * (.25 + .2 * np.sin(2 * np.pi * .13 * t_all)) * np.clip(1 - (t_all - 8) / 6, .25, 1)
M[:, 0] += drone * .35 + wind * .5; M[:, 1] += drone * .35 + wind[::-1] * .5
for tl, s in ((T["L1"], 1), (T["L2"], 2)): add(FX, thunder(.7, seed=s), tl, (-.3 if s == 1 else .4))
add(M, choir([49, 56], 4.5, .25, (400, 800, 2400), att=2.5, rel=1.5), 1.2)                            # 멀리서 낮게 부르는 소리
# 4 ~ 7.5 차원문과 눈: 속삭임 · 유리 울림
add(M, choir([61, 64, 68], 4.2, .22, (300, 870, 2240), att=1.2, rel=1.), T["PORT"], .4)
n = int(2.2 * SR); tw = np.arange(n) / SR; wh = bp(1200, 5000, rs.randn(n)) * (np.sin(np.pi * tw / 2.2) ** 2) * (.5 + .5 * np.sin(2 * np.pi * 7 * tw)) * .22; add(FX, wh, T["EYEO"], .6)
gl = np.sin(2 * np.pi * 1318 * tw) * .06 + np.sin(2 * np.pi * 1975 * tw * (1 - .02 * tw)) * .04; add(M, gl * np.sin(np.pi * tw / 2.2), T["EYEO"], -.2)
# 7.5 ~ 11.5 왕좌가 드러남: 금관 동기 · 팀파니
for tn, m, d in ((7.5, 37, 1.6), (9.1, 38, .8), (9.9, 37, .6), (10.5, 32, 1.4)): add(M, brass([m, m - 12], d + .4, .55, att=.18, rel=.5, bright=.8), tn)
for tn, v in ((7.5, .9), (9.5, .6), (10.5, .8)): add(M, timpani(mid(25), v), tn)
tr = 11.0
while tr < T["IGNITE"] - .05: add(M, timpani(mid(25), .1 + .3 * (tr - 11) / 1.6), tr); tr += .09       # 팀파니 롤
# 11.5 ~ 12.6 떨리는 현(긴장)
n = int((T["IGNITE"] - T["FACE"]) * SR); ts = np.arange(n) / SR; u = ts / ts[-1]; st = np.zeros(n)
for m in (49, 56, 61, 62): st += saw(mid(m) * 2 ** (u * 1 / 12), ts + rs.rand())
st = lp(3000, st) * (.5 + .5 * np.sign(np.sin(2 * np.pi * 13 * ts))) * u ** 1.5 * .08; add(M, st, T["FACE"])
# 12.6 오른눈 점화: 총주 일격
add(M, brass([37, 44, 49, 52, 56], 2.6, 1.0, att=.02, rel=1.6, bright=1.2), T["IGNITE"]); add(M, taiko(1.1, 50), T["IGNITE"]); add(M, choir([61, 64, 68, 73], 2.4, .5, att=.03, rel=1.4), T["IGNITE"])
add(FX, thunder(1.0, 4., 3), T["IGNITE"] + .02); add(M, gong(.9, 5.), T["IGNITE"])
# 14.5 ~ 18.5 왕관과 후광: 오르간 · 합창 진행 · 종
for i, (tc, ch) in enumerate(((14.5, [49, 52, 56, 61]), (15.5, [45, 52, 57, 61]), (16.5, [42, 49, 54, 57]), (17.5, [44, 51, 56, 60]))):
    add(M, organ([c - 12 for c in ch[:1]] + ch, 1.25 if i < 3 else 1.4, .7, att=.08, rel=.4), tc); add(M, choir([c + 12 for c in ch[1:]], 1.3, .6, att=.15, rel=.5), tc, .1 * (i - 1.5))
add(M, bell(mid(61), .35), 14.5, -.3); add(M, bell(mid(68), .28), 16.5, .3); add(M, bell(mid(73), .22), 17.5, 0)
# 18.5 ~ 22.5 압도: 타이코 · 금관 전면 · 네 개의 눈(일격)
BT = .6667; pat = [1, 0, .5, 0, 1, .5, 1, 0]
for i in range(int((T["POWER"] - T["WIDE"]) / (BT / 2))):
    tb = T["WIDE"] + i * BT / 2; a = pat[i % 8]
    if a: add(M, taiko(.7 * a, 58 if i % 4 == 0 else 72), tb, .3 * np.sin(i))
for tn, m, d in ((18.5, 37, 1.3), (19.85, 40, .65), (20.5, 44, 1.2), (21.8, 42, .7)): add(M, brass([m, m + 7, m - 12], d + .3, .75, att=.06, rel=.4, bright=1.1), tn)
add(M, choir([61, 64, 68], 4., .35, att=.4, rel=.6), T["WIDE"]); add(M, organ([37, 49, 56], 4., .3, att=.5, rel=.5), T["WIDE"])
add(M, taiko(1.1, 48), T["STARE"]); add(FX, thunder(.8, 3., 4), T["STARE"] + .05); add(M, bell(mid(56), .3), T["STARE"])
# 22.5 ~ 26 권능: 상승 → 충격파 → 두 배 빠른 북
add(M, riser(T["SHOCK"] - T["POWER"], 1.5), T["POWER"]); add(M, choir([61, 65, 68, 72], T["SHOCK"] - T["POWER"], .35, att=1.1, rel=.05), T["POWER"])
n = int(3.5 * SR); tq = np.arange(n) / SR; boom = np.sin(2 * np.pi * np.cumsum(40 + 80 * np.exp(-tq * 6)) / SR) * np.exp(-tq * 1.4) * 1.3 + lp(300, rs.randn(n)) * np.exp(-tq * 2) * .8
add(FX, np.tanh(boom * 1.3), T["SHOCK"]); add(FX, thunder(1.1, 4., 5), T["SHOCK"] + .1); add(M, brass([37, 44, 49, 52, 56, 61], 2.2, 1.0, att=.02, rel=1.4, bright=1.3), T["SHOCK"])
for i in range(int((T["HERO"] - T["SHOCK"] - .2) / (BT / 4))):
    tb = T["SHOCK"] + .35 + i * BT / 4
    if tb < T["HERO"] - .15: add(M, taiko(.45 + .35 * (i % 4 == 0), 60 if i % 2 else 74), tb, .4 * np.sin(i * 1.3))
# 26 ~ 30 마지막: 지배자의 화음 · 징
add(M, organ([25, 37, 44, 49, 52, 56, 61], 3.9, .55, att=.05, rel=2.2), T["HERO"]); add(M, choir([61, 64, 68, 73, 75], 3.9, .5, att=.08, rel=2.2), T["HERO"])
add(M, brass([37, 44, 49, 56], 3.4, .7, att=.03, rel=2., bright=1.), T["HERO"]); add(M, gong(1.1, 4.), T["HERO"]); add(M, taiko(1.2, 46), T["HERO"]); add(M, timpani(mid(25), 1.), T["HERO"])
add(M, bell(mid(73), .35), T["TITLE"], .2); add(M, bell(mid(80), .22), T["TITLE"] + .02, -.2)

def verb(buf, sec=3.6, dec=1.7, wet=.32, seed=3):                                  # 큰 궁전의 잔향
    r = np.random.RandomState(seed); n = int(sec * SR); e = np.exp(-np.arange(n) / SR * dec); L = lp(5200, r.randn(n) * e); R = lp(5200, r.randn(n) * e)
    pre = int(.03 * SR); L = np.concatenate([np.zeros(pre), L]); R = np.concatenate([np.zeros(pre), R])
    out = buf.copy(); out[:, 0] += fftconvolve(buf[:, 0], L)[:N] * wet * .02; out[:, 1] += fftconvolve(buf[:, 1], R)[:N] * wet * .02; return out
mix = verb(M) + verb(FX, 2.4, 2.4, .2, 7) * .9
mix[:int(.4 * SR)] *= np.linspace(0, 1, int(.4 * SR))[:, None]
fo = S(29.3); mix[fo:] *= np.linspace(1, 0, N - fo)[:, None] ** 2
pk = np.max(np.abs(mix)); mix = (np.tanh(mix / pk * 1.6) / np.tanh(1.6) * .7).astype(np.float32)
p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "224k", PUB + "monarch_cut.mp3"], input=mix.tobytes())
print("mp3", p.returncode, round(len(mix) / SR, 2), "peak", round(float(pk), 3))
