# -*- coding: utf-8 -*-
"""MONARCH V3 음원 — 직접 합성한 오리지널(결과 mp3 는 로컬 전용).
흐름(초): 0.5 어둠 속 계수기(팀파니 눈금 · 속삭임) → 7.8 번개 → 10.4 섬광 · 별 → 11.0 만세 셋 → 13.6 섬광 → 13.8 공허(오르간 · 합창) → 20.6 · 21.3 · 22.0 상징의 일격 셋 → 22.6 이름 → 26 끝
페이지(monarch3_gl.html)의 시각표와 같은 값을 쓴다."""
import os, subprocess
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR, END = 44100, 26.0
N = int(END * SR)
PUB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public") + os.sep
rs = np.random.RandomState(11)
T = dict(BG=.5, POP=1.0, CNT=1.4, W0=2.0, LIGHT=7.8, ZERO=10.2, FLASH1=10.4, HAIL=11.0, FLASH2=13.6, REVEAL=13.8, S2=16.6, S3=18.6, HERO=20.6, TITLE=22.6)
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


# 페이지와 같은 시각표(monarch3_gl.html) — 인구 계수기 눈금 · 속삭이는 말 · 번개
K = 28; TICKS = [T["CNT"] + (T["ZERO"] - T["CNT"]) * (k / K) ** .6 for k in range(K + 1)]
WORDS = [T["W0"] + k * .42 for k in range(16)]
BOLTS = [7.8, 8.25, 8.6, 8.9, 9.15, 9.4, 9.6, 9.78, 9.95, 10.08, 10.2, 10.3, 14.4, 17.3, 19.9, 22.8]
HAILS = [T["HAIL"] + k * .8 for k in range(3)]                                  # 고리가 한 바퀴 돌 때마다 '만세'

M = np.zeros((N, 2)); FX = np.zeros((N, 2)); t_all = np.arange(N) / SR
# 0.5 ~ 10.4 어둠 속의 계수: 낮은 울림 · 거꾸로 부푸는 합창 · 심장 같은 팀파니(계수기 눈금마다)
drone = np.sin(2 * np.pi * mid(25) * t_all) * .5 + np.sin(2 * np.pi * mid(32) * t_all) * .22 + np.sin(2 * np.pi * mid(26) * t_all) * .12 * np.clip((t_all - 5) / 5, 0, 1)   # 반음 부딪힘이 점점
drone *= np.clip((t_all - T["BG"]) / 1.5, 0, 1) * np.clip((T["FLASH1"] + .05 - t_all) / .05, 0, 1)
M[:, 0] += drone * .38; M[:, 1] += drone * .38
add(M, choir([49, 52, 56], 9.2, .3, (400, 800, 2400), att=6., rel=.3), T["BG"] + .6)
for k, tk in enumerate(TICKS[:-1]):
    add(M, timpani(mid(25), .35 + .45 * k / K), tk, .15 * np.sin(k)); add(FX, hp(2500, rs.randn(int(.05 * SR))) * np.exp(-np.arange(int(.05 * SR)) / SR * 90) * .15, tk + .01, -.4 + .8 * rs.rand())   # 숫자가 넘어가는 딸깍
# 속삭임: 말이 하나씩 떠오를 때마다(모음 필터를 지난 숨소리)
for k, tw in enumerate(WORDS):
    n = int(.9 * SR); tt = np.arange(n) / SR; nz = rs.randn(n); f1 = 500 + 900 * rs.rand()
    w = (bp(f1 * .8, f1 * 1.3, nz) + .7 * bp(1800, 3200, nz) + .4 * bp(4000, 7000, nz)) * np.sin(np.pi * tt / .9) ** 2 * (.6 + .4 * np.sin(2 * np.pi * (5 + 3 * rs.rand()) * tt)) * .5
    add(FX, w, tw, -.8 + 1.6 * rs.rand())
    add(M, bell(mid(73 + [0, 3, 7, -2][k % 4]), .05, 2.), tw + .05, -.5 + rs.rand())
# 7.8 ~ 10.4 번개 · 떨리는 현 · 상승
for i, tb in enumerate(BOLTS[:12]): add(FX, thunder(.35 + .5 * i / 11, 1.6, 10 + i), tb, -.6 + 1.2 * rs.rand())
n = int((T["FLASH1"] - T["LIGHT"]) * SR); ts = np.arange(n) / SR; u = ts / ts[-1]; st = np.zeros(n)
for m in (49, 50, 56, 61): st += saw(mid(m) * 2 ** (u * 2 / 12), ts + rs.rand())
add(M, lp(3200, st) * (.5 + .5 * np.sign(np.sin(2 * np.pi * 14 * ts))) * u ** 1.5 * .09, T["LIGHT"]); add(M, riser(T["FLASH1"] - T["LIGHT"], 1.2), T["LIGHT"])
# 10.4 흰 섬광 → 눈의 룬 뒤에서 도는 별: 총주 일격 · 유리 같은 종
add(M, brass([37, 44, 49, 52, 56], 1.8, 1.0, att=.02, rel=1.2, bright=1.2), T["FLASH1"]); add(M, taiko(1.1, 48), T["FLASH1"]); add(M, gong(.8, 4.), T["FLASH1"]); add(FX, thunder(.9, 3., 30), T["FLASH1"])
for i, m in enumerate((85, 88, 92, 97)): add(M, bell(mid(m), .12, 3.), T["FLASH1"] + .1 + i * .06, -.4 + .27 * i)
# 11.0 ~ 13.6 만세: 세 바퀴 도는 고리 · 합창의 외침 두 음절(올 · 헤일) · 북
for k, th in enumerate(HAILS):
    ch = [[61, 64, 68, 73], [62, 66, 69, 74], [64, 68, 71, 76]][k]; v = .55 + .2 * k
    add(M, choir(ch, .32, v, (750, 1200, 2600), att=.02, rel=.18), th); add(M, choir(ch, .6, v, (400, 2000, 2800), att=.02, rel=.35), th + .34)
    add(M, taiko(.9, 52), th); add(M, taiko(.6, 70), th + .34); add(M, brass([ch[0] - 24, ch[0] - 12], .7, .5 + .15 * k, att=.03, rel=.3), th)
add(M, riser(T["FLASH2"] - 12.6, 1.4), 12.6); tr = 13.0
while tr < T["FLASH2"] - .03: add(M, taiko(.25 + .5 * (tr - 13.) / .6, 76), tr); tr += .075
# 13.6 섬광 → 모나크: 지배자의 화음 · 징 · 오르간과 합창의 진행
add(M, brass([37, 44, 49, 52, 56, 61], 2.6, 1.0, att=.02, rel=1.6, bright=1.3), T["FLASH2"]); add(M, gong(1.1, 5.), T["FLASH2"]); add(M, taiko(1.2, 46), T["FLASH2"]); add(M, timpani(mid(25), 1.), T["FLASH2"])
add(FX, thunder(1.0, 4., 31), T["FLASH2"] + .05)
for i, (tc, ch) in enumerate(((T["REVEAL"], [49, 52, 56, 61]), (15.2, [45, 52, 57, 61]), (T["S2"], [42, 49, 54, 57]), (17.6, [44, 51, 56, 60]), (T["S3"], [49, 52, 56, 61]), (19.6, [47, 54, 59, 63]))):
    add(M, organ([ch[0] - 12] + ch, 1.5, .6, att=.1, rel=.5), tc); add(M, choir([c + 12 for c in ch[1:]], 1.5, .5, att=.2, rel=.6), tc, .1 * (i - 2.5))
n = int(2.2 * SR); tw = np.arange(n) / SR; add(FX, bp(1200, 5000, rs.randn(n)) * np.sin(np.pi * tw / 2.2) ** 2 * (.5 + .5 * np.sin(2 * np.pi * 7 * tw)) * .2, T["S2"] + .2, .5)   # 차원문의 눈
for tb in BOLTS[12:]: add(FX, thunder(.5, 2.5, int(tb * 10)), tb, -.5 + rs.rand())
add(M, bell(mid(61), .3), T["S3"], -.3); add(M, bell(mid(68), .25), T["S3"] + .5, .3)
add(M, organ([25, 37, 44, 49, 52, 56, 61], 5., .55, att=.05, rel=2.4), T["HERO"]); add(M, choir([61, 64, 68, 73, 75], 5., .5, att=.08, rel=2.4), T["HERO"])
add(M, brass([37, 44, 49, 56], 4., .7, att=.03, rel=2.2, bright=1.), T["HERO"]); add(M, gong(1.0, 5.), T["HERO"]); add(M, taiko(1.2, 46), T["HERO"])
for i, tp in enumerate((21.3, 22.0)):                                                                   # 상징이 두 번 더 뜬다(20.6 의 일격과 합쳐 셋)
    add(M, taiko(1.0 + .1 * i, 46), tp); add(M, brass([37 + 2 * i, 44 + 2 * i, 49 + 2 * i, 56 + 2 * i], 1.0, .8 + .1 * i, att=.02, rel=.6, bright=1.1), tp); add(M, gong(.55 + .1 * i, 3.), tp); add(FX, thunder(.55, 2.5, 40 + i), tp)
add(M, bell(mid(73), .35), T["TITLE"], .2); add(M, bell(mid(80), .22), T["TITLE"] + .02, -.2)

def verb(buf, sec=3.6, dec=1.7, wet=.32, seed=3):                                  # 큰 궁전의 잔향
    r = np.random.RandomState(seed); n = int(sec * SR); e = np.exp(-np.arange(n) / SR * dec); L = lp(5200, r.randn(n) * e); R = lp(5200, r.randn(n) * e)
    pre = int(.03 * SR); L = np.concatenate([np.zeros(pre), L]); R = np.concatenate([np.zeros(pre), R])
    out = buf.copy(); out[:, 0] += fftconvolve(buf[:, 0], L)[:N] * wet * .02; out[:, 1] += fftconvolve(buf[:, 1], R)[:N] * wet * .02; return out
mix = verb(M) + verb(FX, 2.4, 2.4, .2, 7) * .9
mix[:int(.4 * SR)] *= np.linspace(0, 1, int(.4 * SR))[:, None]
fo = S(24.9); mix[fo:] *= np.linspace(1, 0, N - fo)[:, None] ** 2
pk = np.max(np.abs(mix)); mix = (np.tanh(mix / pk * 1.6) / np.tanh(1.6) * .7).astype(np.float32)
p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "224k", PUB + "monarch3_cut.mp3"], input=mix.tobytes())
print("mp3", p.returncode, round(len(mix) / SR, 2), "peak", round(float(pk), 3))
