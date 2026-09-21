# -*- coding: utf-8 -*-
"""equinox_cut.mp3 재편집: 끝을 서서히 줄이는 대신 21.02초(마디 첫 박)에 '펑' — 빨려드는 라이저 + 서브 붐 + 노이즈 버스트, 음악은 그 순간 끊김"""
import subprocess, shutil, os
import numpy as np
from scipy.signal import butter, sosfilt

SRC = r"C:\Users\rnjsg\Downloads\KoraiiLayersCut.mp3.mpeg"
OUT = r"C:\Users\rnjsg\dev\recover\public\equinox_cut.mp3"
BAK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "equinox_cut_before_pop.mp3")
SR, POP, END = 44100, 21.02, 21.9

if not os.path.exists(BAK):
    shutil.copy(OUT, BAK)


def decode(path, dur):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-t", str(dur), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


old = decode(BAK, END)
src = decode(SRC, END + .5)
# 기존 컷이 원본의 0초부터인지 확인 (앞 5초 상관)
n = SR * 5
a, b = old[:n, 0], src[:n, 0]
lag = int(np.argmax(np.correlate(a[::20], b[::20], "full")) - (len(b[::20]) - 1)) * 20
gain = float(np.sqrt((old[SR:SR * 15] ** 2).mean()) / max(1e-9, np.sqrt((src[SR:SR * 15] ** 2).mean())))
print("lag samples", lag, "gain old/src", round(gain, 3))
assert abs(lag) < 400, "기존 컷과 원본의 시작점이 다름"

N = int(END * SR)
x = np.zeros((N, 2)); m = min(N, len(src)); x[:m] = src[:m] * gain
t = np.arange(N) / SR
rel = t - POP
# 음악: 펑 직전까지 그대로, 그 순간 날아가듯 빠르게 감쇠 (+ 첫 0.25초 페이드인은 기존과 같게)
env = np.where(rel < -.02, 1., np.exp(-np.maximum(rel + .02, 0) / .07))
x *= env[:, None]
rng = np.random.default_rng(7)
# 라이저: 빨려드는 바람 (고역 노이즈가 커지다가 펑 직전에 끊김)
ris = rng.standard_normal(N)
ris = sosfilt(butter(2, [1800, 9000], "bandpass", fs=SR, output="sos"), ris)
k = np.clip((rel + .5) / .5, 0, 1); ris *= np.where(rel < 0, k ** 3, 0) * .16
# 붐: 서브 스윕 + 미드 펀치 + 노이즈 버스트 + 짧은 잔향
p = np.maximum(rel, 0); onm = (rel >= 0).astype(float)
f_sub = 38 + 70 * np.exp(-p / .06); sub = np.sin(2 * np.pi * np.cumsum(f_sub * onm) / SR) * np.exp(-p / .26) * .95 * onm
f_mid = 70 + 190 * np.exp(-p / .03); mid = np.sin(2 * np.pi * np.cumsum(f_mid * onm) / SR) * np.exp(-p / .07) * .6 * onm
nz = rng.standard_normal(N); crack = sosfilt(butter(2, 6000, "lowpass", fs=SR, output="sos"), nz) * np.exp(-p / .045) * .55 * onm
tail = sosfilt(butter(2, 1400, "lowpass", fs=SR, output="sos"), rng.standard_normal(N)) * np.exp(-p / .3) * .22 * onm
fx = ris + sub + mid + crack + tail
y = x + fx[:, None]
y[:, 1] += (np.roll(tail, 331) - tail) * .5                      # 잔향만 살짝 좌우 다르게
y = np.tanh(y * 1.05) / np.tanh(1.05)
fade = np.clip((END - t) / .3, 0, 1); y *= fade[:, None]
y = np.clip(y, -1, 1)

p2 = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "192k", OUT], input=y.astype(np.float32).tobytes())
print("written", OUT, p2.returncode)
for tt in np.arange(19.8, END, .1):
    s = y[int(tt * SR):int((tt + .1) * SR)]
    print(round(tt, 2), round(float(np.sqrt((s ** 2).mean())), 3))
