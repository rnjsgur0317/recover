# -*- coding: utf-8 -*-
"""MONARCH V3 음원 — 노래가 아닌 영화식 사운드 디자인. 실제 녹음 효과음(Pixabay, 상업적 이용 가능 · 출처 표기 불필요)을
장면의 사건에 맞춰 놓는다. 원본은 tools/src_media/monarch3_sfx/ (git 제외), 결과 public/monarch3_cut.mp3 도 로컬 전용.
흐름(초): 0.5 어둠의 울림 · 블랙홀 웅웅거림 → 1.4 ~ 10.2 계수기 눈금마다 실제 심장 박동(점점 빨라짐) · 시계 · 말마다 속삭임
→ 7.8 번개 · 역재생 심벌이 차오름 → 10.2 정적 → 10.4 거대한 일격(임팩트 · 브라암 · 서브 드롭) · 별의 반짝임
→ 11.0 · 11.8 · 12.6 합창 타격(한 번마다 높아짐) → 13.6 휘익 · 일격 → 13.8 블랙홀 임팩트(공허) → 16.6 휘익 · 반짝이는 알갱이
→ 18.6 왕관: 마법 · 브라암 → 20.6 · 21.4 · 22.2 상징의 일격 셋(점점 커짐) → 23.0 이름: 종 · 합창의 끝 → 26 끝.
페이지(monarch3_gl.html)의 시각표와 같은 값을 쓴다."""
import os, subprocess
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR, END = 44100, 26.0
N = int(END * SR)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SFX = os.path.join(ROOT, "tools", "src_media", "monarch3_sfx")
PUB = os.path.join(ROOT, "public") + os.sep
rs = np.random.RandomState(7)
T = dict(BG=.5, POP=1.0, CNT=1.4, W0=2.0, LIGHT=7.8, ZERO=10.2, FLASH1=10.4, HAIL=11.0, FLASH2=13.6, REVEAL=13.8, S2=16.6, S3=18.6, HERO=20.6, TITLE=23.0)
SYMS = [20.6, 21.4, 22.2]
K = 28; TICKS = [T["CNT"] + (T["ZERO"] - T["CNT"]) * (k / K) ** .6 for k in range(K + 1)]
WORDS = [T["W0"] + k * .42 for k in range(16)]
BOLTS = [7.8, 8.25, 8.6, 8.9, 9.15, 9.4, 9.6, 9.78, 9.95, 10.08, 10.2, 10.3, 14.4, 17.3, 19.9, 22.8]
HAILS = [T["HAIL"] + k * .8 for k in range(3)]

def S(t): return int(round(t * SR))
def load(name):                                                         # 효과음을 스테레오 float 로
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(SFX, name + ".mp3"), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
A = {n: load(n) for n in ("drone1", "drone2", "hole1", "hole2", "clock", "heart2", "whisper1", "whisper2", "thunder1", "thunder2", "rev1", "rev2", "riser1",
                          "impact1", "impact2", "braam1", "braam2", "subdrop", "shimmer1", "shimmer2", "choir1", "choir2", "whoosh", "glitch", "bell")}
def db(v): return 10 ** (v / 20)
def cut(x, a=0., b=None, fi=.005, fo=.05):                              # 구간을 잘라 앞뒤를 부드럽게
    y = x[S(a): S(b) if b else len(x)].copy(); n = len(y); i, o = min(n, S(fi)), min(n, S(fo))
    if i: y[:i] *= np.linspace(0, 1, i)[:, None]
    if o: y[n - o:] *= np.linspace(1, 0, o)[:, None]
    return y
def pitch(x, semi):                                                     # 재생 속도로 음높이 바꾸기
    if not semi: return x
    r = 2 ** (semi / 12); idx = np.arange(0, len(x) - 1, r); return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in (0, 1)], 1)
def pan(x, p): return x * np.array([np.sqrt(.5 - p * .5), np.sqrt(.5 + p * .5)]) * np.sqrt(2)
MIX = np.zeros((N, 2)); BED = np.zeros((N, 2))
def put(x, t, g=0., p=0., bus=None):                                    # t 에 소리의 '시작'을 놓는다
    buf = MIX if bus is None else bus; i = S(t); x = pan(x, p) * db(g)
    if i < 0: x = x[-i:]; i = 0
    j = min(N, i + len(x))
    if j > i: buf[i:j] += x[: j - i]
def hit(x, t, onset, g=0., p=0., bus=None): put(x, t - onset, g, p, bus)   # 소리의 '때리는 순간(onset)'을 t 에 맞춘다

# ── 바닥에 깔리는 울림(공허 · 블랙홀) ──
put(cut(A["drone2"], 0, 9.8, .8, 1.5), T["BG"], -6)                     # 어둠이 떠오른다
put(cut(A["drone1"], 0, 6.8, .3, .05), T["ZERO"] - 6.8, -4)             # 10.2 를 향해 부풀다 뚝
put(cut(A["hole1"], 8, 18., 1.5, .02), T["BG"] + .2, -1, 0, BED)        # 블랙홀 웅웅거림(앞부분)
put(cut(A["hole1"], 30, 42.5, .2, 1.5), T["FLASH2"], 3, 0, BED)         # 공허가 드러난 뒤 더 크게
put(cut(A["clock"], .0, 7.0, .5, .3), 1.2, -8)                          # 시계 째깍
# ── 1.4 ~ 10.2 계수기 눈금마다 실제 심장 박동 ──
hb = cut(A["heart2"], .1, 1.1, .002, .1)
for k, tk in enumerate(TICKS[:-1]): hit(pitch(hb, -1 + 2 * k / K), tk, .18, -10 + 9 * k / K, .2 * np.sin(k))
# ── 말이 떠오를 때마다 속삭임 ──
for k, tw in enumerate(WORDS):
    if k % 4 == 3: put(cut(A["whisper2"], .3, 2.5, .05, .4), tw, -9, -.7 + 1.4 * rs.rand())
    else: s0 = 2 + rs.rand() * 22; put(cut(A["whisper1"], s0, s0 + 1.3, .08, .4), tw, -6, -.8 + 1.6 * rs.rand())
# ── 7.8 번개 · 차오름 ──
for i, tb in enumerate(BOLTS[:10]):                                     # 10.2 이후의 번개(10.2 · 10.3)는 정적을 위해 소리를 내지 않는다
    th, on = (A["thunder1"], .6) if i % 2 == 0 else (A["thunder2"], .48)
    hit(cut(th, 0, on + (2.5 if i == 0 else .9), .002, .35), tb, on, -12 + 7 * i / 9, -.6 + 1.2 * rs.rand())
hit(cut(A["rev1"], 0, 5.0, .2, .01), T["ZERO"], 4.8, -3)                 # 역재생 심벌: 10.2 에 꼭대기
put(cut(A["riser1"], .0, T["ZERO"] - T["LIGHT"], .3, .02), T["LIGHT"], -9)
# 10.2 ~ 10.4 정적: 이 구간의 바닥 울림을 끊는다
g = np.ones(N); i0, i1 = S(T["ZERO"]), S(T["FLASH1"]); g[i0:i1] = 0; g[i1:i1 + S(.4)] = np.linspace(0, 1, S(.4)); BED *= g[:, None]
MIX[S(T["ZERO"] + .02): S(T["FLASH1"]) - S(.03)] *= .03                    # 섬광 직전 0.2 초는 거의 무음(이후에 놓는 일격은 영향 없음)
# ── 10.4 섬광: 거대한 일격 → 별 ──
hit(A["impact2"], T["FLASH1"], .02, -1); hit(cut(A["braam1"], 0, 5.), T["FLASH1"], .22, -2); hit(A["subdrop"], T["FLASH1"], .32, -4)
put(cut(A["shimmer2"], .2, 3.2, .05, .8), T["FLASH1"] + .15, -6)        # 눈 모양 룬 뒤의 별
# ── 11.0 · 11.8 · 12.6 ALL HAIL: 합창 타격(점점 높게) ──
for i, h in enumerate(HAILS):
    hit(pitch(A["choir2"], 2 * i), h, .06, -1 + i, .15 * (i - 1)); hit(A["impact1"], h, .08, -5 + i)
put(cut(A["choir1"], .4, 3.0, .3, .3), T["HAIL"], -12)                  # 뒤에 깔리는 큰 성당의 합창
hit(cut(A["rev2"], 0, 3.1, .3, .01), T["FLASH2"], 3.08, -2)             # 13.6 을 향해 차오르는 역재생 크래시
put(cut(A["glitch"], .2, 2.1, .01, .1), 12.9, -4, .3)
# ── 13.6 섬광 → 13.8 공허 ──
hit(A["whoosh"], T["FLASH2"], .88, -3); hit(cut(A["braam2"], 0, 3.9), T["FLASH2"], .02, -5)
hit(A["hole2"], T["REVEAL"], .18, 0); hit(A["subdrop"], T["REVEAL"], .32, -6)
# ── 16.6 지배: 휘익 · 빨려드는 빛 알갱이 ──
hit(A["whoosh"], T["S2"], .88, -4, -.3); put(cut(A["shimmer1"], 4., 9.5, .6, .8), T["S2"] - .1, -6)
hit(cut(A["thunder2"], 0, 3.5, .002, .8), BOLTS[13], .48, -13, .5)
# ── 18.6 왕관이라는 개념 ──
put(cut(A["shimmer2"], .2, 3.5, .05, 1.), T["S3"], -5); hit(cut(A["braam2"], 0, 2.6, .002, .8), T["S3"], .02, -10)
hit(cut(A["thunder1"], 0, 3.5, .002, .8), BOLTS[14], .6, -14, -.5)
hit(cut(A["rev2"], 0, 3.1, .3, .01), T["HERO"], 3.08, -5)
# ── 20.6 · 21.4 · 22.2 상징의 일격 셋 ──
for i, tp in enumerate(SYMS):
    hit(cut(A["braam1"], 0, 2.6 if i < 2 else 6., .002, .6 if i < 2 else 1.5), tp, .22, -4 + 1.5 * i); hit(A["impact1"], tp, .08, -4 + i)
    hit(pitch(A["choir2"], [0, 2, 5][i]), tp, .06, -6 + i)
    if i == 2: hit(A["subdrop"], tp, .32, -3)
hit(cut(A["thunder2"], 0, 4., .002, 1.), BOLTS[15], .48, -14, .4)
# ── 23.0 이름: 종 · 합창의 마지막 ──
hit(A["bell"], T["TITLE"], .16, -1); hit(A["bell"], T["TITLE"] + 1.6, .16, -9, .3)
put(cut(A["choir1"], 8.6, 10.97, .4, 1.2), T["TITLE"] - .1, -6)

# ── 믹스: 잔향으로 한 공간에 묶고 · 부드럽게 눌러 소리 크기를 맞춘다 ──
mix = MIX + BED * db(-5)
def verb(buf, sec=3., dec=1.6, wet=.18, seed=3):
    r = np.random.RandomState(seed); n = int(sec * SR); e = np.exp(-np.arange(n) / SR * dec); sos = butter(2, 5000, "lowpass", fs=SR, output="sos")
    L, R = sosfilt(sos, r.randn(n) * e), sosfilt(sos, r.randn(n) * e); out = buf.copy()
    out[:, 0] += fftconvolve(buf[:, 0], L)[:N] * wet * .015; out[:, 1] += fftconvolve(buf[:, 1], R)[:N] * wet * .015; return out
mix = verb(mix)
i0, i1 = S(T["ZERO"] + .02), S(T["FLASH1"]) - S(.02); mix[i0:i1] *= np.concatenate([np.linspace(1, .02, S(.04)), np.full(i1 - i0 - S(.04), .02)])[:, None]   # 잔향 꼬리까지 정적
mix[:S(.3)] *= np.linspace(0, 1, S(.3))[:, None]
fo = S(24.8); mix[fo:] *= np.linspace(1, 0, N - fo)[:, None] ** 1.5
pk = np.max(np.abs(mix)); mix = (np.tanh(mix / pk * 1.6) / np.tanh(1.6) * .72).astype(np.float32)
p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "256k", PUB + "monarch3_cut.mp3"], input=mix.tobytes())
print("mp3", p.returncode, round(len(mix) / SR, 2), "peak", round(float(pk), 3))
