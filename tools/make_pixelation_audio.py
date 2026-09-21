# -*- coding: utf-8 -*-
"""pixelation_cut.mp3 + pixelation_data.js 생성 (음원은 로컬 전용 — 저장소에 올리지 않음)
원곡 앞 33.26초(마디 27 첫 박) → 그 지점에서 테이프 스톱, 그 위로 '치지직' TV 잡음이 0.4초 전부터 끼어들어 0.6초간 꽉 찼다가 뚝 끊김"""
import subprocess, json
import numpy as np
from scipy.signal import stft, butter, sosfilt

SRC = r"C:\Users\rnjsg\Downloads\Censored.mp3.mpeg"
PUB = r"C:\Users\rnjsg\dev\recover\public" + "\\"
SR, CUT, TAIL, NOISE_IN, NOISE_END, END = 44100, 33.264, .5, 32.85, 33.86, 34.1

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-t", "36", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
x = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)
N = int(END * SR); y = np.zeros((N, 2)); n0 = int(CUT * SR)
y[:n0] = x[:n0]; y[:int(.05 * SR)] *= np.linspace(0, 1, int(.05 * SR))[:, None]
m = int(TAIL * SR); u = np.arange(m) / m; pos = n0 + np.cumsum((1 - u) ** 1.6); i0 = np.floor(pos).astype(int); fr = (pos - i0)[:, None]
y[n0:n0 + m] = (x[i0] * (1 - fr) + x[i0 + 1] * fr) * ((1 - u) ** .8)[:, None]                 # 테이프 스톱

rng = np.random.default_rng(11); t = np.arange(N) / SR
nz = rng.standard_normal((N, 2)); nz = sosfilt(butter(2, [700, 9000], "bandpass", fs=SR, output="sos"), nz, axis=0)
gate = np.repeat(rng.uniform(.35, 1, N // 735 + 1), 735)[:N]                                   # 60Hz 로 출렁이는 세기 = 치지직
crack = (rng.uniform(0, 1, N) > .9985).astype(float); crack = np.convolve(crack, np.exp(-np.arange(200) / 30.), "same")   # 탁탁 튀는 소리
env = np.where(t < NOISE_IN, 0, np.where(t < CUT, ((t - NOISE_IN) / (CUT - NOISE_IN)) ** 2 * .22, np.where(t < NOISE_END, .5, 0)))
y += (nz * gate[:, None] * .55 + (crack * rng.choice([-1, 1], N))[:, None] * .5) * env[:, None]
k = int(NOISE_END * SR); pop = np.exp(-np.arange(int(.05 * SR)) / (SR * .008)); y[k:k + len(pop)] += (pop * .6)[:, None]   # 전원 '툭'
y = np.clip(np.tanh(y * 1.05) / np.tanh(1.05), -1, 1).astype(np.float32)
p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "192k", PUB + "pixelation_cut.mp3"], input=y.tobytes())
print("mp3", p.returncode, round(len(y) / SR, 3))

mono = y[:n0 + m].mean(1).astype(np.float64)[::2]; S2 = SR // 2; hop = S2 // 60
f, tt, Z = stft(mono, S2, nperseg=1024, noverlap=1024 - hop); M = np.abs(Z)
def envl(mask):
    e = M[mask].mean(0); fl = np.maximum(np.diff(e, prepend=e[0]), 0); out = np.zeros_like(fl); v = 0
    for i, a in enumerate(fl):
        v = max(v * .86, a); out[i] = v
    return np.clip(out / np.percentile(out, 99.5), 0, 1)
low, high = envl(f < 150), envl(f > 5000); lvl = M.mean(0); lvl = np.clip(lvl / np.percentile(lvl, 99), 0, 1)
n = int(END * 60); pad = lambda a: [round(float(v), 2) for v in np.concatenate([a, np.zeros(max(0, n - len(a)))])[:n]]
open(PUB + "pixelation_data.js", "w", encoding="utf-8").write("// PIXELATION 컷씬 음원 분석값 (60fps: 킥 펄스 · 고역 펄스 · 전체 음량). 195 BPM, 박 0.30769s, 첫 박 0.034s. 33.26초 테이프 스톱 + 잡음 엔딩\nwindow.PX_DATA = "
    + json.dumps({"fps": 60, "kick": pad(low), "hat": pad(high), "lvl": pad(lvl)}, separators=(",", ":")) + ";\n")
print("frames", n)
