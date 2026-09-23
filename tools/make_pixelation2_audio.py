# -*- coding: utf-8 -*-
"""pixelation2_cut.mp3 + pixelation2_data.js 생성 (음원은 로컬 전용 — 저장소에 올리지 않음)
원곡(Censored) 앞 28.34초(마디 23 첫 박) → 테이프 스톱 0.55초 → 29.5 끝. 195 BPM, 박 0.30769s, 첫 박 0.034s
분석값: 킥 펄스 · 고역 펄스 · 음량 · 24대역 스펙트럼(36진수 한 글자씩, 오디오 비주얼라이저용)"""
import subprocess, json, os, sys
import numpy as np
from scipy.signal import stft

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src_media", "Censored.mp3.mpeg")
PUB = os.path.join(os.path.dirname(HERE), "public") + os.sep
SR, CUT, TAIL, END = 44100, .034 + 23 * 1.23077, .55, 29.5
if not os.path.exists(SRC):
    sys.exit("원본 음원이 없습니다: " + SRC)
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-t", "31", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
x = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)
assert len(x) > SR * 30, "원본에서 소리를 읽지 못했습니다"
N = int(END * SR); y = np.zeros((N, 2)); n0 = int(CUT * SR)
y[:n0] = x[:n0]; y[:int(.05 * SR)] *= np.linspace(0, 1, int(.05 * SR))[:, None]
m = int(TAIL * SR); u = np.arange(m) / m; pos = n0 + np.cumsum((1 - u) ** 1.7); i0 = np.floor(pos).astype(int); fr = (pos - i0)[:, None]
y[n0:n0 + m] = (x[i0] * (1 - fr) + x[i0 + 1] * fr) * ((1 - u) ** .7)[:, None]                 # 테이프 스톱
y = np.clip(y, -1, 1).astype(np.float32)
p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "192k", PUB + "pixelation2_cut.mp3"], input=y.tobytes())
print("mp3", p.returncode, round(len(y) / SR, 3))

mono = y.mean(1).astype(np.float64)[::2]; S2 = SR // 2; hop = S2 // 60
f, tt, Z = stft(mono, S2, nperseg=1024, noverlap=1024 - hop); M = np.abs(Z)
def env(a, dec):
    out = np.zeros_like(a); v = 0
    for i, q in enumerate(a):
        v = max(v * dec, q); out[i] = v
    return out
Q = n0 // 2 // hop
def envl(mask):
    e = M[mask].mean(0); fl = np.maximum(np.diff(e, prepend=e[0]), 0); out = env(fl, .86); return np.clip(out / np.percentile(out[:Q], 99.5), 0, 1)
low, high = envl(f < 150), envl(f > 5000); lvl = M.mean(0); lvl = np.clip(lvl / np.percentile(lvl[:Q], 99), 0, 1)
edges = np.geomspace(50, 11000, 25); spec = []
for a, b in zip(edges[:-1], edges[1:]):
    mk = (f >= a) & (f < b); e = M[mk].mean(0) if mk.any() else np.zeros(M.shape[1]); e = env(e, .78); spec.append(np.clip(e / max(1e-9, np.percentile(e[:Q], 98)), 0, 1))
spec = np.array(spec)
n = int(END * 60); pad = lambda a: [round(float(v), 2) for v in np.concatenate([a, np.zeros(max(0, n - len(a)))])[:n]]
D36 = "0123456789abcdefghijklmnopqrstuvwxyz"
rows = ["".join(D36[int(round(float(v) * 35))] for v in (spec[:, i] if i < spec.shape[1] else np.zeros(24))) for i in range(n)]
open(PUB + "pixelation2_data.js", "w", encoding="utf-8").write("// PIXELATION V2 컷씬 음원 분석값 (60fps: 킥 펄스 · 고역 펄스 · 음량 · 24대역 스펙트럼[36진수]). 195 BPM, 박 0.30769s, 첫 박 0.034s, 28.34 테이프 스톱\nwindow.PX2_DATA = "
    + json.dumps({"fps": 60, "kick": pad(low), "hat": pad(high), "lvl": pad(lvl), "spec": "".join(rows)}, separators=(",", ":")) + ";\n")
print("frames", n)
