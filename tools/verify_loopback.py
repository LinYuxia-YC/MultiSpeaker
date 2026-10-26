"""Verify true stereo separation on each endpoint via WASAPI loopback capture."""
import sys
from pathlib import Path
import time
import wave

import numpy as np
import pyaudiowpatch as pyaudio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.devices import list_output_devices
from app.engine import MultiSpeakerEngine
from app.testtone import make_stereo_test

RATE = 48000
devs = list_output_devices()[:3]
print("playing on:", [d.name for d in devs])

pa = pyaudio.PyAudio()
looops = {}
for i in range(pa.get_device_count()):
    d = pa.get_device_info_by_index(i)
    if d.get("isLoopbackDevice"):
        for dev in devs:
            base = dev.name.replace("扬声器", "").strip(" ()")
            if base and base.lower() in str(d["name"]).lower():
                looops[dev.key] = (i, str(d["name"]))
for k, v in looops.items():
    print("loopback for", k, "->", v)

eng = MultiSpeakerEngine()
eng.set_track(make_stereo_test(RATE))
errs = eng.start(devs)
print("start:", errs)
time.sleep(0.05)

records = {}
streams = {}
for key, (idx, name) in looops.items():
    s = pa.open(format=pyaudio.paInt16, channels=2, rate=RATE, input=True,
                input_device_index=idx, frames_per_buffer=1024)
    streams[key] = s

t_end = time.time() + 5.2
chunks = {k: [] for k in streams}
while time.time() < t_end:
    for k, s in streams.items():
        try:
            chunks[k].append(s.read(1024, exception_on_overflow=False))
        except Exception as e:
            print("read err", k, e)
for k, s in streams.items():
    s.stop_stream(); s.close()
pa.terminate()
eng.stop()

print("\n--- analysis ---")
for key, parts in chunks.items():
    if not parts:
        print(key, "no data"); continue
    raw = b"".join(parts)
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    a = a.reshape(-1, 2)
    rms = np.sqrt((a ** 2).mean(axis=1))
    thr = max(1e-4, rms.max() * 0.15)
    idx = np.flatnonzero(rms > thr)
    if idx.size == 0:
        print(key, "silent"); continue
    cap_start = idx[0] - int(0.10 * RATE)  # tone starts at 0.10 s

    def band(sig, f, t, dur=0.15):
        i0 = cap_start + int(t * RATE)
        seg = sig[i0:i0 + int(dur * RATE)]
        if seg.size < 512:
            return -120.0
        w = np.hanning(seg.size)
        spec = np.abs(np.fft.rfft(seg * w))
        freqs = np.fft.rfftfreq(seg.size, 1 / RATE)
        j = int(np.argmin(np.abs(freqs - f)))
        v = spec[max(0, j - 2):j + 3].max()
        return 20 * np.log10(max(v, 1e-9) / (seg.size / 2))

    print(f"\n{key}  (capture len {len(a)/RATE:.2f}s, first sound at {idx[0]/RATE:.2f}s)")
    for t, label in [(0.8, "L-only seg"), (2.4, "R-only seg"), (4.5, "stereo chord")]:
        print(f"  t={t:.1f}s {label:12s} "
              f"L440={band(a[:,0],440,t):6.1f}dB L659={band(a[:,0],659.25,t):6.1f}dB | "
              f"R440={band(a[:,1],440,t):6.1f}dB R659={band(a[:,1],659.25,t):6.1f}dB | "
              f"L523={band(a[:,0],523.25,t):6.1f}dB R784={band(a[:,1],783.99,t):6.1f}dB")
