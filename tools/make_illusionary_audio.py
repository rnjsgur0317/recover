# -*- coding: utf-8 -*-
"""illusionary_cut.mp3 + illusionary_data.js 생성 (음원은 로컬 전용 — 저장소에 올리지 않음)
참고 영상의 사운드(2.3초~29.0초)를 쓰되, 원본의 긴 정적 구간에는 아우라 설명대로 '희미한 잡음 + 간헐적인 딩·삐 소리'를 아주 작게 깔아 불안감을 유지한다"""
import subprocess, json
import numpy as np
from scipy.signal import stft, butter, sosfilt

import os
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src_media", "IllusionaryCutscene.mp4.mp4")          # 받은 원본의 사본(gitignore)
if not os.path.exists(SRC): SRC = r"C:\Users\rnjsg\Downloads\IllusionaryCutscene.mp4.mp4"
PUB = r"C:\Users\rnjsg\dev\recover\public" + "\\"
SR, OFF, END = 44100, 2.3, 26.7

import os, sys
if not os.path.exists(SRC):
    sys.exit("원본 영상이 없습니다: " + SRC + "  (Downloads 에 다시 넣고 실행하세요)")
raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(OFF), "-i", SRC, "-vn", "-t", str(END), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
x = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)
assert len(x) > SR * 20, "원본에서 소리를 읽지 못했습니다"
N = int(END * SR); y = np.zeros((N, 2)); y[:min(N, len(x))] = x[:N]
t = np.arange(N) / SR; rng = np.random.default_rng(23)
# 잡음 바닥: 음악이 없는 곳에서만 들리게 (음악 구간 0.2~9.0, 12.2~18.1)
quiet = np.clip(np.minimum.reduce([np.abs(t - 4.6) - 4.5, np.abs(t - 15.15) - 3.05]) / .4, 0, 1)
nz = sosfilt(butter(2, [300, 6000], "bandpass", fs=SR, output="sos"), rng.standard_normal((N, 2)), axis=0)
wob = .6 + .4 * np.sin(2 * np.pi * .23 * t) * np.sin(2 * np.pi * 1.7 * t)
y += nz * (quiet * wob * .02)[:, None]
hum = np.sin(2 * np.pi * 50 * t) * .012 + np.sin(2 * np.pi * 100.3 * t) * .006
y += (hum * quiet)[:, None]
def ding(t0, f, g, dec=.5):
    n = int(1.6 * SR); i = int(t0 * SR); tt = np.arange(n) / SR
    s = (np.sin(2 * np.pi * f * tt) + .4 * np.sin(2 * np.pi * f * 2.76 * tt)) * np.exp(-tt / dec) * g
    y[i:i + n] += s[:max(0, min(n, N - i)), None]
for t0, f, g in [(9.6, 1318, .05), (10.9, 988, .04), (11.55, 1568, .035), (18.9, 880, .04), (19.5, 1175, .03), (22.6, 659, .045), (25.3, 1760, .03)]:
    ding(t0, f, g)
for t0 in [10.2, 19.2, 22.2]:                                              # 삐 소리
    n = int(.12 * SR); i = int(t0 * SR); y[i:i + n] += (np.sign(np.sin(2 * np.pi * 2000 * np.arange(n) / SR)) * .018)[:, None]
for t0 in [7.05, 15.95, 17.15]:                                                     # 치지직: 꼭두각시가 앉은 모습 → 무너진 모습으로 끊겨 넘어가는 순간의 잡음 (화면 ZAP 과 같은 시각)
    n = int(.24 * SR); i = int(t0 * SR); gate = np.repeat(rng.random(n // 220 + 1) ** 2, 220)[:n]; cr = sosfilt(butter(2, [900, 9500], "bandpass", fs=SR, output="sos"), rng.standard_normal((n, 2)), axis=0)
    y[i:i + n] = y[i:i + n] * .35 + cr * (gate * .34)[:, None]
y[:int(.05 * SR)] *= np.linspace(0, 1, int(.05 * SR))[:, None]; k = int(.35 * SR); y[-k:] *= np.linspace(1, 0, k)[:, None]
y = np.clip(y, -1, 1).astype(np.float32)
p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "192k", PUB + "illusionary_cut.mp3"], input=y.tobytes())
print("mp3", p.returncode, round(len(y) / SR, 2))

mono = y.mean(1).astype(np.float64)[::2]; S2 = SR // 2; hop = S2 // 60
f, tt, Z = stft(mono, S2, nperseg=1024, noverlap=1024 - hop); M = np.abs(Z)
fl = np.maximum(np.diff(np.log1p(M * 40), axis=1, prepend=0), 0).sum(0); out = np.zeros_like(fl); v = 0
for i, a in enumerate(fl):
    v = max(v * .88, a); out[i] = v
out = np.clip(out / np.percentile(out, 99.5), 0, 1); lvl = M.mean(0); lvl = np.clip(lvl / np.percentile(lvl, 99), 0, 1)
n = int(END * 60); pad = lambda a: [round(float(q), 2) for q in np.concatenate([a, np.zeros(max(0, n - len(a)))])[:n]]
open(PUB + "illusionary_data.js", "w", encoding="utf-8").write("// ILLUSIONARY 컷씬 음원 분석값 (60fps: 타격 펄스 · 음량)\nwindow.IL_DATA = " + json.dumps({"fps": 60, "hit": pad(out), "lvl": pad(lvl)}, separators=(",", ":")) + ";\n")
print("frames", n)
