# -*- coding: utf-8 -*-
"""GLITCH 컷씬 음원 생성 — 받은 음원이 없어 직접 합성한 오리지널 사운드 (결과 mp3 는 로컬 전용, 이 스크립트로 언제든 다시 만든다)
흐름(초): 0 잔잔한 피아노 + 새소리 → 4.75 알람시계 치지직 → 6.45 컵 · 7.45 책장 · 8.5 컴퓨터 오류음 → 11.2 창밖이 갈라짐: 피아노·새소리 뚝 끊기고 전자음·잡음만
→ 13.6 방 전체 → 15.5 눈을 감음: 정적 → 16.8 글리치 세계: 기묘한 종소리 → 18.0 120 BPM 그루브(킥 · 깎인 스네어 · 떨어지는 베이스 · 목소리 조각) → 19.8 거대한 파동 → 21.8 스네어 롤 · 상승음 → 23.0 브레이크 → 24.0 GLITCH 드롭(워블 베이스 · 슈퍼톱니 · 아르페지오) · 25.0 / 26.3 폭발 → 26.6 모든 것이 빨려 들어감(비트가 테이프처럼 느려짐) → 28.9 화면이 먹힘(치지지직) → 29.7 암전 → 30.4 끝
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

# ── 4. 글리치 세계: 기묘하면서 신나게 — 120 BPM, 24.0 드롭과 같은 박자 격자(17.0 부터) ──
gw = np.zeros((N, 2)); a, b = S(T["WAKE"]), S(T["BLACK"]); n = b - a; tt = np.arange(n) / SR
BT = .5; G0 = T["AURA"] - 14 * BT                                                                   # 17.0
def at(k): return G0 + k * BT                                                                         # k 번째 박
def vlp(x, fcs, blk=256):                                                                             # 시간에 따라 바뀌는 저역 필터(블록마다 계수 교체)
    out = np.zeros_like(x); zi = None
    for i in range(0, len(x), blk):
        sos = butter(2, float(np.clip(fcs[min(i, len(fcs) - 1)], 30, 16000)), "lowpass", fs=SR, output="sos")
        if zi is None: zi = np.zeros((sos.shape[0], 2))
        out[i:i + blk], zi = sosfilt(sos, x[i:i + blk], zi=zi)
    return out
def kick(v=1.):
    k = int(.42 * SR); t = np.arange(k) / SR; x = np.sin(2 * np.pi * np.cumsum(47 + 160 * np.exp(-t * 26)) / SR) * np.exp(-t * 5.2); x = np.tanh(x * 2.2) * .95
    c = int(.006 * SR); x[:c] += bp(1500, 7000, rs.randn(c)) * np.linspace(1, 0, c) * .5; return x * v
def snare(v=1., tone=185., seed=0):
    k = int(.24 * SR); t = np.arange(k) / SR; r = np.random.RandomState(seed); x = np.sin(2 * np.pi * tone * t) * np.exp(-t * 22) * .6 + bp(1100, 7500, r.randn(k)) * np.exp(-t * 12) * .9
    x += bp(900, 3000, r.randn(k)) * (np.exp(-t * 60) + .6 * np.exp(-np.maximum(t - .012, 0) * 60) * (t > .012) + .4 * np.exp(-np.maximum(t - .024, 0) * 60) * (t > .024)) * .7   # 박수 겹
    return crush(x, 2, 6) * v
def hat(open_=False, v=1.):
    k = int((.2 if open_ else .035) * SR); return hp(7000, rs.randn(k)) * np.exp(-np.arange(k) / SR * (13 if open_ else 95)) * (.2 if open_ else .12) * v
def bell(f, dur, v, bend=0.):                                                                        # 기묘한 FM 종소리: 어긋난 배음 · 흔들리는 음정 · 끝이 꺾인다
    k = int(dur * SR); t = np.arange(k) / SR; fr = f * (1 + .014 * np.sin(2 * np.pi * 5.3 * t)) * 2 ** (bend * (t / dur) ** 2 / 12); ph = 2 * np.pi * np.cumsum(fr) / SR
    return np.sin(ph + 2.4 * np.exp(-t * 7) * np.sin(ph * 3.51)) * np.exp(-t * 3.2) * np.minimum(1, t / .003) * v
VOW = [(730, 1090), (570, 840), (300, 870), (270, 2290), (530, 1840)]
def vox(f, dur, vw, v):                                                                              # 합성 목소리 조각(모음 포먼트)
    k = int(dur * SR); t = np.arange(k) / SR; s = saw(f * (1 + .02 * np.sin(2 * np.pi * 6 * t)), t) + .5 * saw(f * 1.006, t); f1, f2 = VOW[vw]
    x = bp(f1 * .8, f1 * 1.25, s, 2) + .7 * bp(f2 * .85, f2 * 1.2, s, 2); return x * np.minimum(1, t / .005) * np.minimum(1, (k - np.arange(k)) / (.02 * SR)) * v
def stutter_bus(buf, t0, grain, reps):
    a0 = S(t0); g = int(grain * SR); seg = buf[a0:a0 + g].copy()
    for r in range(1, reps): buf[a0 + r * g:a0 + (r + 1) * g] = seg * (1 - .08 * r)
# 드론(뒤에 깔림) — 눈을 뜬 순간부터
pad = np.zeros(n)
for m, dt in ((37, 0), (44, .13), (49, -.1), (52, .07), (56, -.05)):
    for det in (-.12, .12): pad += saw(mid(m) * 2 ** (det / 12), tt + dt)
pad = lp(700, pad) * .06 * np.minimum(1, tt / 1.2) * (tt < T["AURA"] - T["WAKE"])
gw[a:b, 0] += pad; gw[a:b, 1] += np.roll(pad, 330)
gr = hp(4000, rs.randn(n)) * .006 * (rs.rand(n // 800 + 1).repeat(800)[:n] > .7); gw[a:b, 0] += gr; gw[a:b, 1] += gr[::-1]
# 드럼: 18.0 부터 4박 킥, 19.0 부터 스네어, 16분 하이햇(가끔 셋잇단으로 튄다)
SEC_A, SEC_B, SEC_C = (2, 9.6), (9.6, 14), (14, 14 + (T["FINAL"] - T["AURA"]) / BT)
kicks = [k for k in range(2, 12)] + [13.5] + [k for k in range(14, int(SEC_C[1]))]
for k in kicks: add(gw, kick(1. if k >= 14 else .85), at(k))
for k in range(4, 12, 2): add(gw, snare(.75, seed=k), at(k + 1))
for k in range(14, int(SEC_C[1]), 2): add(gw, snare(.95, seed=k), at(k + 1))
for s16 in range(int(2 * 4), int(SEC_C[1] * 4)):
    k = s16 / 4; tb3 = at(k)
    if at(12) <= tb3 < at(14): continue                                                               # 브레이크
    if s16 % 4 == 2 and k >= 14: add(gw, hat(True, .9), tb3, rs.uniform(-.3, .3))
    elif s16 % 2 == 1 or k >= 6: add(gw, hat(False, .7 + .5 * (s16 % 2)), tb3, rs.uniform(-.6, .6))
    if rs.rand() < .12: [add(gw, hat(False, .6), tb3 + r * BT / 12, rs.uniform(-.8, .8)) for r in range(1, 3)]
# 스네어 롤: 21.8 ~ 23.0 점점 촘촘하고 높게
tr = T["GATHER"]
while tr < at(12) - .01:
    u = (tr - T["GATHER"]) / (at(12) - T["GATHER"]); add(gw, snare(.35 + .6 * u, 185 + 260 * u, int(tr * 100)), tr); tr += BT / (2 if u < .35 else 4 if u < .7 else 8)
# 베이스: 8분음 · 기묘한 음(트라이톤) · 킥에 눌림 · 드롭에서는 흔들리는 워블
BSEQ = [25, 25, 37, 25, 26, 25, 31, 32]; b0, b1 = S(at(2)), S(T["FINAL"]); bn = b1 - b0; btt = np.arange(bn) / SR
fbass = np.zeros(bn)
for i8 in range(int(bn / (SR * BT / 2)) + 1):
    s0 = int(i8 * BT / 2 * SR); fbass[s0:s0 + int(BT / 2 * SR)] = mid(BSEQ[i8 % 8] + (12 if (i8 // 8) % 4 == 3 and i8 % 8 in (2, 6) else 0))
fbass = np.where(fbass > 0, fbass, mid(25)); drop = btt >= (T["AURA"] - at(2)); ph8 = (btt % (BT / 2)) / (BT / 2)
fb = fbass * (1 + .5 * np.exp(-ph8 * 14) * (~drop))                                                   # 음마다 위에서 떨어지는 음정
phb = 2 * np.pi * np.cumsum(fb) / SR; bsrc = (2 * ((phb / (2 * np.pi)) % 1) - 1) + (2 * ((phb * 1.007 / (2 * np.pi)) % 1) - 1) + .6 * np.sin(phb * .5)
lfo_rate = np.where(drop, np.where(((btt - (T["AURA"] - at(2))) // (BT * 4)) % 2 == 0, 4., 6.), 2.)    # 드롭: 8분 ↔ 셋잇단 워블
fcut = np.where(drop, 180 + 1700 * (.5 + .5 * np.sin(2 * np.pi * np.cumsum(lfo_rate) / SR)) ** 2, 220 + 900 * np.exp(-ph8 * 9))
build = (btt >= T["GATHER"] - at(2)) & ~drop; fcut = np.where(build, fcut + 2500 * ((btt - (T["GATHER"] - at(2))) / (T["AURA"] - T["GATHER"])).clip(0, 1) ** 2, fcut)
bass = np.tanh(vlp(bsrc, fcut) * 1.6) * .32
kt = np.array([at(k) for k in kicks]) - at(2); sc = np.ones(bn)
for k0 in kt:
    i0 = int(k0 * SR)
    if 0 <= i0 < bn: e = min(bn, i0 + int(.25 * SR)); sc[i0:e] = np.minimum(sc[i0:e], 1 - .75 * np.exp(-np.arange(e - i0) / SR / .07))
brk = (btt >= at(12) - at(2)) & (btt < at(14) - at(2)); bass *= sc * (~brk)
gw[b0:b1, 0] += bass; gw[b0:b1, 1] += bass
# 드롭 코드: 어둡고 어긋난 슈퍼톱니(C#m + 반음 위 D) 엇박 찌르기
c0, c1 = S(T["AURA"]), S(T["FINAL"]); cn = c1 - c0; ct = np.arange(cn) / SR; chord = np.zeros(cn)
for m in (49, 52, 56, 62, 61):
    for d in (-.18, -.09, 0, .09, .18): chord += saw(mid(m) * 2 ** (d / 12), ct + rs.rand())
cph = (ct % BT) / BT; stab = ((cph > .5) & (cph < .85)) * np.exp(-(cph - .5) * 7) + ((ct % (BT * 8)) > BT * 7.5) * .7
chord = lp(2600, chord) * stab * .05 * sc[c0 - b0:c1 - b0]
gw[c0:c1, 0] += chord; gw[c0:c1, 1] += np.roll(chord, 250)
# 기묘한 종소리 선율(온음음계) — 18.0 부터 16분, 쉼표가 섞이고 옥타브가 튄다 · 드롭에서는 깎인 네모파 아르페지오가 겹친다
WT = [73, 75, 77, 79, 81, 83]; PAT = [0, -1, 3, -1, 5, 4, -1, 1, 0, -1, 3, -1, 2, -1, 5, -1]
for s16 in range(4, int(SEC_C[1] * 4)):
    k = s16 / 4; t16 = at(k); ix = PAT[s16 % 16]
    if ix < 0 or at(12) <= t16 < at(14): continue
    if k < 14 and rs.rand() < .25: continue
    f = mid(WT[ix] + (12 if rs.rand() < .18 else 0) - (12 if k < 6 else 0)); add(gw, bell(f, .5, .09 if k < 14 else .07, -rs.choice([0, 0, 3, 7])), t16, .55 * np.sin(s16 * 1.7))
PHR = [61, 62, 65, 66, 68, 69, 71]; q = int(BT / 4 * SR); arp = np.zeros(cn)
for i16 in range(cn // q):
    tt2 = np.arange(q) / SR; f = mid(PHR[(i16 * 3 + (i16 // 8)) % 7] + 12 * ((i16 // 4) % 2)); arp[i16 * q:(i16 + 1) * q] = np.sign(np.sin(2 * np.pi * f * tt2)) * np.exp(-tt2 * 16) * .06
arp = crush(arp, 3, 4); gw[c0:c1, 0] += arp * .8; gw[c0:c1, 1] += np.roll(arp, 600)
# 목소리 조각: 20.0 부터 엇박에 기묘하게
for s16 in range(6 * 4, int(SEC_C[1] * 4)):
    k = s16 / 4; t16 = at(k)
    if at(12) <= t16 < at(14): continue
    if s16 % 4 in (1, 3) and rs.rand() < (.35 if k < 14 else .55):
        f = mid(rs.choice([49, 52, 56, 61, 55])) * (2 if rs.rand() < .3 else 1); x = vox(f, BT / 4 * rs.choice([1, 1, 2]), rs.randint(5), .16)
        if rs.rand() < .3: x = x[::-1]
        add(gw, x, t16, rs.uniform(-.7, .7))
# 거대한 파동 · 에너지 모임 · 브레이크 · 폭발
wn = int(1.6 * SR); wt = np.arange(wn) / SR; wh = rs.randn(wn); fc = 200 + 3800 * np.sin(np.pi * wt / 1.6) ** 2; whoosh = np.zeros(wn)
for i0 in range(0, wn, 2048): f = fc[i0]; whoosh[i0:i0 + 2048] = bp(max(80, f * .6), min(15000, f * 1.6), wh[i0:i0 + 2048], 2)
add(gw, whoosh * np.sin(np.pi * wt / 1.6) ** 1.5 * .7, T["WAVE"] - .5)
bq = np.arange(int(1.8 * SR)) / SR; add(gw, np.sin(2 * np.pi * np.cumsum(55 * np.exp(-bq * .8) + 22) / SR) * np.exp(-bq * 1.8) * .6, T["WAVE"])
rn = S(T["AURA"] - .12) - S(T["GATHER"]); rt = np.arange(rn) / SR; R = rt[-1]
rise = np.sin(2 * np.pi * np.cumsum(180 * 2 ** (3.2 * (rt / R) ** 1.6)) / SR) * .05 + hp(2500, rs.randn(rn)) * .05 * (rt / R) ** 2
rise *= (np.sin(2 * np.pi * np.cumsum(4 + 28 * (rt / R) ** 2) / SR) > -.2) * (rt / R) ** .7
add(gw, rise * 2.4, T["GATHER"]); add(gw, crackle(.25, 1, 99) * 1.1, at(12)); rv = hp(3000, rs.randn(int(.7 * SR))) * np.linspace(0, 1, int(.7 * SR)) ** 3 * .35; add(gw, rv, at(13) - .25)
gw[S(at(14) - .1):S(at(14))] *= np.linspace(1, 0, S(at(14)) - S(at(14) - .1))[:, None]                 # 드롭 직전 한 호흡 정적
add(gw, np.sin(2 * np.pi * np.cumsum(60 * np.exp(-bq * 1.5) + 30) / SR) * np.exp(-bq * 2.2) * .8, T["AURA"])   # 드롭 충격
for tb2 in (T["B1"], T["B2"]):
    n3 = int(1.2 * SR); t3 = np.arange(n3) / SR; imp = lp(3000, rs.randn(n3)) * np.exp(-t3 * 5) * .35 + np.sin(2 * np.pi * np.cumsum(60 * np.exp(-t3 * 2) + 28) / SR) * np.exp(-t3 * 2.5) * .6
    add(gw, imp, tb2); add(gw, crackle(.3, 1.1, int(tb2 * 7)) * .8, tb2 + .05)
for tw in (17.6, 18.5, 19.1, 20.9, 21.3): add(gw, crackle(.07, .9, int(tw * 10)) * .6, tw, rs.uniform(-.8, .8))
# 마디 끝 글리치 편집: 짧은 조각을 되풀이
for k0, g, r in ((5.5, BT / 8, 4), (7.5, BT / 16, 8), (9.25, BT / 8, 6), (11.5, BT / 16, 8), (17.5, BT / 8, 4), (19.5, BT / 16, 8), (21.25, BT / 32, 8)):
    stutter_bus(gw, at(k0), g, r)
# 26.6 ~ 28.9 모든 것이 빨려 들어간다: 비트가 테이프처럼 느려지고, 빨아들이는 소리와 낮은 울림이 커진다
d0, d1 = S(T["DEVOUR"]), S(T["FINAL"]); segd = gw[d0:d1].copy(); m = d1 - d0; u = np.arange(m) / m; pos = np.cumsum(1 - .72 * u ** 1.4); pos = np.clip(pos.astype(int), 0, m - 1)
gw[d0:d1] = segd[pos] * (1 - .3 * u)[:, None]
suck = lp(9000, hp(1500, rs.randn(m)) * (u ** 2.2) * .5); rum = np.sin(2 * np.pi * np.cumsum(28 + 30 * u ** 2) / SR) * (u ** 1.3) * .8
gw[d0:d1, 0] += suck + rum; gw[d0:d1, 1] += suck[::-1] + rum
for k in range(9): add(gw, crackle(.05 + .04 * k / 9, 1, 300 + k) * (.3 + .6 * k / 9), T["DEVOUR"] + .25 + k * .22, rs.uniform(-.7, .7))
gw[S(T["BLACK"]):] = 0
gw[S(G0):S(T["GATHER"])] *= .62; gw[S(T["GATHER"]):S(T["AURA"])] *= .8
gw = gw / (np.max(np.abs(gw)) + 1e-9); gw = np.tanh(gw * 2.2) / np.tanh(2.2)                              # 글리치 세계는 크게: 버스 리미터
fin = np.zeros((N, 2)); add(fin, crackle(T["BLACK"] - T["FINAL"], 1.4, 1234, 200, 12000) * 2.2, T["FINAL"])   # 치지지직 — 화면이 먹히며 닫힌다
bt2 = np.arange(int(.8 * SR)) / SR; add(fin, np.sin(2 * np.pi * np.cumsum(50 * np.exp(-bt2 * 2) + 24) / SR) * np.exp(-bt2 * 3) * .7, T["FINAL"])

mix = piano * .12 + birds * .2 + fx * .35 + gw + fin * .34
mix[S(T["BLACK"]):] = 0
mix[:int(.3 * SR)] *= np.linspace(0, 1, int(.3 * SR))[:, None]
pk = np.max(np.abs(mix)); mix = (np.tanh(mix / pk * 1.25) * .76).astype(np.float32)
p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "224k", PUB + "glitch_cut.mp3"], input=mix.tobytes())
print("mp3", p.returncode, round(len(mix) / SR, 2), "peak", round(float(pk), 3))
