# -*- coding: utf-8 -*-
"""GLITCH 컷씬 음원 생성 — 받은 음원이 없어 직접 합성한 오리지널 사운드 (결과 mp3 는 로컬 전용, 이 스크립트로 언제든 다시 만든다)
흐름(초): 0 잔잔한 피아노 + 새소리 → 4.75 알람시계 치지직 → 6.45 컵 · 7.45 책장 · 8.5 컴퓨터 오류음 → 11.2 창밖이 갈라짐: 피아노·새소리 뚝 끊기고 전자음·잡음만
→ 13.6 방 전체 → 15.5 눈을 감음: 정적 → 16.8 글리치 세계 드론 → 19.8 거대한 파동 → 21.8 에너지가 모임(상승음) → 24.0 GLITCH 등장(120 BPM 비트) · 25.0 / 26.3 폭발 → 26.6 모든 것이 빨려 들어감(비트가 테이프처럼 느려짐) → 28.9 화면이 먹힘(치지지직) → 29.7 암전 → 30.4 끝
페이지(glitch_gl.html)의 시각 상수 T 와 같은 값을 쓴다."""
import os, subprocess
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR, END = 44100, 30.4
N = int(END * SR)
PUB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public") + os.sep
rs = np.random.RandomState(7)
T = dict(CG=4.75, CUP=6.45, BOOK=7.45, PC=8.5, WINF=10.4, CRACK=11.2, ALL=13.6, DARK=15.5, WAKE=16.8, WAVE=19.8, GATHER=21.8, AURA=24.0, B1=25.0, B2=26.3, DEVOUR=26.6, FINAL=28.9, BLACK=29.7)
def S(t): return int(round(t * SR))
def bp(lo, hi, x, order=4): return sosfilt(butter(order, [lo, hi], "bandpass", fs=SR, output="sos"), x)
def lp(f, x, order=2): return sosfilt(butter(order, f, "lowpass", fs=SR, output="sos"), x)
def hp(f, x, order=2): return sosfilt(butter(order, f, "highpass", fs=SR, output="sos"), x)
def add(buf, x, t, pan=0.):
    i = S(t); j = min(N, i + len(x)); x = x[: j - i]
    buf[i:j, 0] += x * np.sqrt(.5 - pan * .5); buf[i:j, 1] += x * np.sqrt(.5 + pan * .5)
def ir(sec, dec, seed):
    r = np.random.RandomState(seed); n = int(sec * SR); e = np.exp(-np.arange(n) / SR * dec); m = int(.01 * SR)
    L = r.randn(n) * e; R = r.randn(n) * e; L[:m] *= np.linspace(0, 1, m); R[:m] *= np.linspace(0, 1, m); return lp(6000, L), lp(6000, R)
def verb(buf, wet, sec=2.2, dec=2.6, seed=1):
    L, R = ir(sec, dec, seed); out = buf.copy(); out[:, 0] += fftconvolve(buf[:, 0], L)[:N] * wet * .03; out[:, 1] += fftconvolve(buf[:, 1], R)[:N] * wet * .03; return out
def crush(x, hold, bits):
    y = np.repeat(x[::hold], hold)[: len(x)]; q = 2 ** bits; return np.round(y * q) / q
def crackle(dur, dens=1., seed=0, lo=900, hi=7000):   # 치지직: 띄엄띄엄 끊기는 잡음 + 표본율 깎기
    r = np.random.RandomState(seed); n = int(dur * SR); x = bp(lo, hi, r.randn(n)); g = np.repeat(r.rand(n // 220 + 1) < .55 * dens, 220)[:n]
    x = crush(x * g, 1 + r.randint(2, 6), 5); env = np.minimum(1, np.arange(n) / (.004 * SR)) * np.minimum(1, (n - np.arange(n)) / (.01 * SR)); return x * env * .5
mid = lambda m: 440 * 2 ** ((m - 69) / 12)
def saw(f, t): return 2 * ((t * f) % 1) - 1

# ── 1. 아침: 피아노 ──
piano = np.zeros((N, 2))
def pnote(f0, dur, vel):
    n = int(dur * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for k in range(1, 9):
        fk = k * f0 * np.sqrt(1 + .00035 * k * k)
        if fk > 12000: break
        x += np.sin(2 * np.pi * fk * t + k * .7) * (1 / k ** 1.25) * np.exp(-t * (.55 + .55 * k))
    x *= np.minimum(1, t / .004) * vel
    m = int(.012 * SR); x[:m] += bp(1500, 5000, rs.randn(m)) * .015 * vel   # 해머 소리
    return x
CH = [[53, 57, 60, 64, 65], [52, 55, 59, 62, 64], [50, 53, 57, 60, 62], [48, 52, 55, 59, 60]]   # Fmaj7 · Em7 · Dm7 · Cmaj7
e8 = .4167; ci = 0; t = .35
while t < T["CRACK"]:
    c = CH[ci % 4]; add(piano, pnote(mid(c[0] - 12), 3.5, .55), t, -.2)
    for j, m in enumerate([c[1], c[2], c[3], c[4]]):
        tt = t + j * e8
        if tt < T["CRACK"]: add(piano, pnote(mid(m + 12), 2.4, .32 + .06 * (j == 3)), tt, .25 * (j - 1.5) / 1.5)
    t += e8 * 4; ci += 1
piano = verb(piano, 1.3)
def stutter(buf, at, grain, reps, hold=0):   # 글리치가 음악을 먼저 건드린다: 짧게 되풀이 · 표본율 깎기
    a = S(at); g = int(grain * SR); seg = buf[a - g:a].copy()
    if hold: seg = np.stack([crush(seg[:, 0], hold, 6), crush(seg[:, 1], hold, 6)], 1)
    for r in range(reps): buf[a + r * g:a + (r + 1) * g] = seg
for at, gr, rp in ((T["CG"], .045, 4), (T["CUP"], .035, 3), (T["BOOK"], .03, 5), (T["PC"], .05, 5), (T["WINF"], .04, 4)):
    stutter(piano, at, gr, rp, 4 if at > 8 else 0)
cut = S(T["CRACK"]); piano[cut:] = 0                                           # 창밖이 갈라지는 순간 음악이 뚝 끊긴다

# ── 2. 새소리 ──
birds = np.zeros((N, 2)); tb = .5
while tb < T["CRACK"] - .3:
    nsy = rs.randint(2, 6); f0 = rs.uniform(2800, 4200); pan = rs.uniform(-.8, .8); v = rs.uniform(.03, .07) * (1 - .6 * (tb > T["PC"])); tk = tb
    for k in range(nsy):
        d = rs.uniform(.04, .09); n = int(d * SR); tt = np.arange(n) / SR; sw = f0 * (1 + rs.uniform(-.25, .35) * tt / d) * (1 + .04 * np.sin(2 * np.pi * 38 * tt))
        add(birds, np.sin(2 * np.pi * np.cumsum(sw) / SR) * np.sin(np.pi * tt / d) ** 2 * v, tk, pan); tk += d + rs.uniform(.02, .06)
    tb += rs.uniform(.6, 1.5)
birds = verb(birds, .8, 1.4, 3.5, 5); birds[cut:] = 0

# ── 3. 방 공기 · 글리치 효과음 ──
fx = np.zeros((N, 2))
room = lp(900, rs.randn(N)) * .004; fx[:cut, 0] += room[:cut]; fx[:cut, 1] += room[::-1][:cut]
add(fx, crackle(.16, 1, 1), T["CG"]); add(fx, crackle(.1, .8, 2), T["CUP"], .3)
for k in range(14):                                                                                 # 책장 넘어가는 소리
    m = int(.012 * SR); add(fx, bp(2000, 8000, rs.randn(m)) * np.exp(-np.arange(m) / 90) * .25, T["BOOK"] + k * .028, .2)
tn = np.arange(int(.5 * SR)) / SR; ding = (np.sin(2 * np.pi * 880 * tn) * (tn < .12) + np.sin(2 * np.pi * 660 * tn) * (tn >= .12)) * np.exp(-((tn % .12) * 9)) * .12   # 컴퓨터 오류음
add(fx, ding, T["PC"] + .06, .4); add(fx, crackle(.22, 1, 3), T["PC"], .4); add(fx, crackle(.12, 1, 4), T["WINF"])
add(fx, crackle(.7, 1.2, 5, 300, 9000) * 1.6, T["CRACK"])
ts = np.arange(int(1.4 * SR)) / SR; add(fx, np.sin(2 * np.pi * np.cumsum(70 * np.exp(-ts * 1.2) + 25) / SR) * np.exp(-ts * 1.6) * .5, T["CRACK"])
tb = T["CRACK"] + .5                                                                                # 전자음(삐빅)과 잡음만 남는다
while tb < T["DARK"] - .1:
    f = rs.choice([1046, 1568, 2093, 2637, 3136]); d = rs.choice([.03, .05, .08]); n = int(d * SR); tt = np.arange(n) / SR
    add(fx, np.sign(np.sin(2 * np.pi * f * tt)) * .035 * np.minimum(1, (n - np.arange(n)) / 200), tb, rs.uniform(-.6, .6)); tb += rs.uniform(.12, .45) * (1 - .5 * (tb > T["ALL"]))
a0, a1 = S(T["CRACK"] + .6), S(T["DARK"]); hiss = hp(3000, rs.randn(a1 - a0)) * np.linspace(.004, .03, a1 - a0); fx[a0:a1, 0] += hiss; fx[a0:a1, 1] += hiss[::-1]
k = T["ALL"]
while k < T["DARK"] - .05:                                                                          # 방 전체: 점점 커지는 치지직
    grow = (k - T["ALL"]) / (T["DARK"] - T["ALL"]); d = .06 + .25 * grow; add(fx, crackle(d, .6 + .8 * grow, int(k * 100)) * (.4 + 1.1 * grow), k, rs.uniform(-.5, .5)); k += d + .18 * (1 - grow)
fx[S(T["DARK"]):S(T["WAKE"])] = 0                                                                  # 눈을 감는다 — 정적

# ── 4. 글리치 세계 ──
gw = np.zeros((N, 2)); a, b = S(T["WAKE"]), S(T["BLACK"]); n = b - a; tt = np.arange(n) / SR
pad = np.zeros(n)
for m, dt in ((37, 0), (44, .13), (49, -.1), (52, .07), (56, -.05)):
    for det in (-.12, .12): pad += saw(mid(m) * 2 ** (det / 12), tt + dt)
pad = lp(700, pad) * .12 * np.minimum(1, tt / 1.8)
gate = np.ones(n); gi = 0
while gi < n:                                                                                      # 드론이 이따금 끊긴다
    L = int(rs.uniform(.25, 1.1) * SR)
    if rs.rand() < .35: gate[gi:gi + int(.06 * SR)] = 0
    gi += L
pad *= gate; gw[a:b, 0] += pad; gw[a:b, 1] += np.roll(pad, 330)
gr = hp(4000, rs.randn(n)) * .006 * (rs.rand(n // 800 + 1).repeat(800)[:n] > .7); gw[a:b, 0] += gr; gw[a:b, 1] += gr[::-1]
for tw in (17.6, 18.5, 19.1, 20.9, 21.3): add(gw, crackle(.07, .9, int(tw * 10)) * .7, tw, rs.uniform(-.8, .8))
wn = int(1.6 * SR); wt = np.arange(wn) / SR; wh = rs.randn(wn); fc = 200 + 3800 * np.sin(np.pi * wt / 1.6) ** 2; whoosh = np.zeros(wn)
for i0 in range(0, wn, 2048):                                                                      # 거대한 파동: 휩쓸고 지나가는 잡음
    f = fc[i0]; whoosh[i0:i0 + 2048] = bp(max(80, f * .6), min(15000, f * 1.6), wh[i0:i0 + 2048], 2)
add(gw, whoosh * np.sin(np.pi * wt / 1.6) ** 1.5 * .6, T["WAVE"] - .5)
bt = np.arange(int(1.8 * SR)) / SR; add(gw, np.sin(2 * np.pi * np.cumsum(55 * np.exp(-bt * .8) + 22) / SR) * np.exp(-bt * 1.8) * .55, T["WAVE"])
rn = S(T["AURA"] - .12) - S(T["GATHER"]); rt = np.arange(rn) / SR; R = rt[-1]                       # 에너지가 모인다: 상승음 + 점점 빨라지는 끊김
rise = np.sin(2 * np.pi * np.cumsum(180 * 2 ** (3.2 * (rt / R) ** 1.6)) / SR) * .05 + hp(2500, rs.randn(rn)) * .05 * (rt / R) ** 2
rise *= (np.sin(2 * np.pi * np.cumsum(4 + 28 * (rt / R) ** 2) / SR) > -.2) * (rt / R) ** .7
add(gw, rise * 2.4, T["GATHER"]); add(gw, crackle(.18, 1, 99) * .9, T["AURA"] - .6)
beat = .5                                                                                          # 24.0 ~ 27.2 GLITCH: 120 BPM
n2 = int(.45 * SR); t2 = np.arange(n2) / SR; kb = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-t2 * 30)) / SR) * np.exp(-t2 * 6) * .9 + bp(2000, 8000, rs.randn(n2)) * np.exp(-t2 * 300) * .2
tk = T["AURA"]
while tk < T["FINAL"] - .01:
    add(gw, kb, tk)
    for s16 in range(4):
        hn2 = int(.03 * SR); hat = hp(7000, rs.randn(hn2)) * np.exp(-np.arange(hn2) / 250) * (.07 if s16 % 2 else .04)
        for r in range(3 if rs.rand() < .25 else 1): add(gw, hat, tk + s16 * beat / 4 + r * beat / 12, rs.uniform(-.5, .5))
    tk += beat
bn = S(T["FINAL"]) - S(T["AURA"]); btt = np.arange(bn) / SR; ph = (btt % beat) / beat
bass = lp(420, saw(mid(25), btt) + .5 * saw(mid(37), btt)) * .16 * np.minimum(1, ph / .18)          # 킥에 눌리는 베이스
arp = np.zeros(bn); PENT = [61, 64, 66, 68, 71, 73, 76]; q = int(beat / 4 * SR)
for i16 in range(bn // q):
    s0 = i16 * q; tt2 = np.arange(q) / SR; f = mid(PENT[rs.randint(len(PENT))] + 12 * rs.randint(0, 2))
    arp[s0:s0 + q] = np.sign(np.sin(2 * np.pi * f * tt2)) * np.exp(-tt2 * 14) * .05
arp = crush(arp, 3, 5)
gw[S(T["AURA"]):S(T["FINAL"]), 0] += bass + arp; gw[S(T["AURA"]):S(T["FINAL"]), 1] += bass + np.roll(arp, 400)
for tb2 in (T["B1"], T["B2"]):                                                                      # 별이 터진다
    n3 = int(1.2 * SR); t3 = np.arange(n3) / SR; imp = lp(3000, rs.randn(n3)) * np.exp(-t3 * 5) * .35 + np.sin(2 * np.pi * np.cumsum(60 * np.exp(-t3 * 2) + 28) / SR) * np.exp(-t3 * 2.5) * .6
    add(gw, imp, tb2); add(gw, crackle(.3, 1.1, int(tb2 * 7)) * .8, tb2 + .05)
# 26.6 ~ 28.9 모든 것이 빨려 들어간다: 비트가 테이프처럼 느려지고, 빨아들이는 소리와 낮은 울림이 커진다
d0, d1 = S(T["DEVOUR"]), S(T["FINAL"]); segd = gw[d0:d1].copy(); m = d1 - d0; u = np.arange(m) / m; pos = np.cumsum(1 - .72 * u ** 1.4); pos = np.clip(pos.astype(int), 0, m - 1)
gw[d0:d1] = segd[pos] * (1 - .35 * u)[:, None]
ut = np.arange(m) / SR; suck = hp(1500, rs.randn(m)) * (u ** 2.2) * .5; suck = lp(9000, suck); rum = np.sin(2 * np.pi * np.cumsum(28 + 30 * u ** 2) / SR) * (u ** 1.3) * .8
gw[d0:d1, 0] += suck + rum; gw[d0:d1, 1] += suck[::-1] + rum
for k in range(9): add(gw, crackle(.05 + .04 * k / 9, 1, 300 + k) * (.3 + .6 * k / 9), T["DEVOUR"] + .25 + k * .22, rs.uniform(-.7, .7))
gw[S(T["BLACK"]):] = 0
fin = np.zeros((N, 2)); add(fin, crackle(T["BLACK"] - T["FINAL"], 1.4, 1234, 200, 12000) * 2.2, T["FINAL"])   # 치지지직 — 화면이 먹히며 닫힌다
bt2 = np.arange(int(.8 * SR)) / SR; add(fin, np.sin(2 * np.pi * np.cumsum(50 * np.exp(-bt2 * 2) + 24) / SR) * np.exp(-bt2 * 3) * .7, T["FINAL"])

gw[S(T["AURA"]):S(T["DEVOUR"])] *= 1.7; gw[S(T["DEVOUR"]):S(T["FINAL"])] *= 1.5
mix = piano * .38 + birds * .6 + fx + gw + fin
mix[S(T["BLACK"]):] = 0
mix[:int(.3 * SR)] *= np.linspace(0, 1, int(.3 * SR))[:, None]
pk = np.max(np.abs(mix)); mix = (np.tanh(mix / pk * 1.25) * .89).astype(np.float32)
p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "224k", PUB + "glitch_cut.mp3"], input=mix.tobytes())
print("mp3", p.returncode, round(len(mix) / SR, 2), "peak", round(float(pk), 3))
