# -*- coding: utf-8 -*-
"""equinox2_cut.mp3 + equinox2_data.js 생성 (음원은 로컬 전용 — 저장소에 올리지 않음)
참고 영상(EquinoxReworkedCutscene)의 사운드를 0.264초부터 사용: 180 BPM(박 0.3333s), 첫 박 0.10, 8박마다 대사(陰 陽 衡 無), 32번째 박(10.77)에 큰 타격.
끝: 잔향이 줄어드는 자리에 빨려드는 소리를 얹고, 두 구체가 부딪혀 터지는 14.6초에 '펑'(서브 붐 + 잡음 파열 + 짧은 꼬리) → 15.6 끝"""
import subprocess, json, os, sys
import numpy as np
from scipy.signal import stft, butter, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src_media", "EquinoxReworkedCutscene.mp4.mp4")
PUB = os.path.join(os.path.dirname(HERE), "public") + os.sep
SR, OFF, END, ZERO = 44100, .264, 15.6, 14.6            # ZERO = 터지는 순간

if not os.path.exists(SRC):
    sys.exit("원본 영상이 없습니다: " + SRC)
raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(OFF), "-i", SRC, "-vn", "-t", str(END), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
x = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)
assert len(x) > SR * 12, "원본에서 소리를 읽지 못했습니다"
N = int(END * SR); y = np.zeros((N, 2)); y[:min(N, len(x))] = x[:N]
t = np.arange(N) / SR; rng = np.random.default_rng(7)
y *= 1.12                                                                   # 원본이 조금 작음 (최대 -2.6dB)
# 빨려드는 소리: 점점 밝아지는 잡음 + 올라가는 사인, ZERO 에서 뚝
k = np.clip((t - (ZERO - 1.5)) / 1.5, 0, 1); rise = k ** 3 * (t < ZERO)
nz = rng.standard_normal((N, 2)); lo = sosfilt(butter(2, [250, 1800], "bandpass", fs=SR, output="sos"), nz, axis=0); hi = sosfilt(butter(2, [2500, 11000], "bandpass", fs=SR, output="sos"), nz, axis=0)
y += (lo * (1 - k)[:, None] + hi * k[:, None]) * (rise * .2)[:, None]
ph = 2 * np.pi * np.cumsum(60 + 380 * k ** 2) / SR; y += (np.sin(ph) * rise * .1)[:, None]
cut = int(ZERO * SR); f = int(.012 * SR); y[cut - f:cut] *= np.linspace(1, 0, f)[:, None]; y[cut:] = 0
n = N - cut; tt = np.arange(n) / SR                                          # 펑: 내려가는 서브 붐 + 잡음 파열 + 어두운 꼬리
boom = np.sin(2 * np.pi * np.cumsum(38 + 70 * np.exp(-tt / .07)) / SR) * np.exp(-tt / .28) * .68
burst = sosfilt(butter(2, [180, 7000], "bandpass", fs=SR, output="sos"), rng.standard_normal((n, 2)), axis=0) * (np.exp(-tt / .09) * .42)[:, None]
tail = sosfilt(butter(2, 900, "lowpass", fs=SR, output="sos"), rng.standard_normal((n, 2)), axis=0) * (np.exp(-tt / .3) * .22)[:, None]
y[cut:] += boom[:, None] + burst + tail; y[cut:] = np.tanh(y[cut:] * 1.1) * .86; k2 = int(.2 * SR); y[-k2:] *= np.linspace(1, 0, k2)[:, None]
y[:int(.03 * SR)] *= np.linspace(0, 1, int(.03 * SR))[:, None]
y = np.clip(y, -1, 1).astype(np.float32)
p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "192k", PUB + "equinox2_cut.mp3"], input=y.tobytes())
print("mp3", p.returncode, round(len(y) / SR, 2))

mono = y.mean(1).astype(np.float64)[::2]; S2 = SR // 2; hop = S2 // 60
f, tt, Z = stft(mono, S2, nperseg=1024, noverlap=1024 - hop); M = np.abs(Z)
def env(a, dec):
    out = np.zeros_like(a); v = 0
    for i, q in enumerate(a):
        v = max(v * dec, q); out[i] = v
    return out
fl = np.maximum(np.diff(np.log1p(M * 40), axis=1, prepend=0), 0)
Q = int(14.4 * 60)                                                           # 정규화는 '펑' 이전 구간 기준
hit = env(fl.sum(0), .86); hit = np.clip(hit / np.percentile(hit[:Q], 99.5), 0, 1)
lowf = env(fl[f < 160].sum(0), .84); lowf = np.clip(lowf / np.percentile(lowf[:Q], 99.5), 0, 1)
lvl = M.mean(0); lvl = np.clip(lvl / np.percentile(lvl[:Q], 99), 0, 1)
# 음악 막대용 스펙트럼: 로그 간격 24대역, 대역별 정규화, 빠르게 오르고 천천히 내림
edges = np.geomspace(55, 9500, 25); spec = []
for a, b in zip(edges[:-1], edges[1:]):
    m = (f >= a) & (f < b); e = M[m].mean(0) if m.any() else np.zeros(M.shape[1]); e = env(e, .8); spec.append(np.clip(e / max(1e-9, np.percentile(e[:Q], 98)), 0, 1))
spec = np.array(spec)
n = int(END * 60); pad = lambda a: [round(float(q), 2) for q in np.concatenate([a, np.zeros(max(0, n - len(a)))])[:n]]
D36 = "0123456789abcdefghijklmnopqrstuvwxyz"
rows = ["".join(D36[int(round(float(v) * 35))] for v in np.concatenate([spec[:, i] if i < spec.shape[1] else np.zeros(24)])) for i in range(n)]
open(PUB + "equinox2_data.js", "w", encoding="utf-8").write("// EQUINOX V2 컷씬 음원 분석값 (60fps: 타격 · 저음 타격 · 음량 · 24대역 스펙트럼[36진수 한 글자씩])\nwindow.EQ2_DATA = "
    + json.dumps({"fps": 60, "hit": pad(hit), "low": pad(lowf), "lvl": pad(lvl), "spec": "".join(rows)}, separators=(",", ":")) + ";\n")
print("frames", n)
# 박 위상 확인: 정박(0.10 + n/3)과 엇박에서의 타격 세기
B = 1 / 3
for name, arr in (("hit", hit), ("low", lowf)):
    on = np.mean([arr[int((.1 + i * B) * 60) + 1] for i in range(32)]); off = np.mean([arr[int((.1 + (i + .5) * B) * 60) + 1] for i in range(32)]); print(name, "on-beat", round(on, 2), "off-beat", round(off, 2))
