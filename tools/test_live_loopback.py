"""Verify stereo separation of the system-audio relay via WASAPI loopback."""
import sys
from pathlib import Path
import threading
import time

import numpy as np
import pyaudiowpatch as pyaudio
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.devices import list_output_devices
from app.engine import MultiSpeakerEngine
from app.live import LiveSource, find_cable_capture

RATE = 48000
DUR = 6.0
t = np.arange(int(RATE * DUR)) / RATE
left = 0.28 * np.sin(2 * np.pi * 440 * t)
right = 0.28 * np.sin(2 * np.pi * 880 * t)
tone = np.stack([left, right], axis=1).astype(np.float32)

devices = list(sd.query_devices())
cable_render = next(i for i, d in enumerate(devices)
                    if "MultiSpeaker" in d["name"] and int(d.get("max_output_channels", 0)) >= 2)

outs = [d for d in list_output_devices() if "MultiSpeaker" not in d.key and "CABLE" not in d.key][:2]
print("outputs:", [d.name for d in outs])

cap = find_cable_capture()
print("capture:", cap)


def play():
    with sd.OutputStream(device=cable_render, samplerate=RATE, channels=2, dtype="float32") as s:
        s.write(tone)


threading.Thread(target=play, daemon=True).start()
time.sleep(0.2)

eng = MultiSpeakerEngine()
src = LiveSource(cap[0], cap[2])
errs = eng.start_live(outs, src, buffer_ms=80.0)
print("start:", errs, "running:", eng.running)
time.sleep(0.6)

pa = pyaudio.PyAudio()
loop = None
for i in range(pa.get_device_count()):
    d = pa.get_device_info_by_index(i)
    if d.get("isLoopbackDevice") and outs[0].name.replace("扬声器", "").strip(" ()").lower() in str(d["name"]).lower():
        loop = i
        break
print("loopback device:", loop)

chunks = []
if loop is not None:
    st = pa.open(format=pyaudio.paInt16, channels=2, rate=RATE, input=True,
                 input_device_index=loop, frames_per_buffer=1024)
    end = time.time() + 3.5
    while time.time() < end:
        chunks.append(st.read(1024, exception_on_overflow=False))
    st.stop_stream(); st.close()
pa.terminate()

print("peaks over time:")
for _ in range(3):
    time.sleep(1.0)
    print("  ", {k: (round(v[0], 3), round(v[1], 3)) for k, v in eng.peaks().items()},
          "xruns:", {k: v["xruns"] for k, v in eng.device_stats().items()})
eng.stop()
time.sleep(0.2)

if chunks:
    a = np.frombuffer(b"".join(chunks), dtype=np.int16).astype(np.float32) / 32768.0
    a = a.reshape(-1, 2)
    seg = a[2000:2000 + int(0.4 * RATE)]

    def band(sig, f):
        w = np.hanning(seg.shape[0])
        spec = np.abs(np.fft.rfft(sig * w))
        freqs = np.fft.rfftfreq(seg.shape[0], 1 / RATE)
        j = int(np.argmin(np.abs(freqs - f)))
        v = spec[max(0, j - 2):j + 3].max()
        return 20 * np.log10(max(v, 1e-9) / (seg.shape[0] / 2))

    print(f"loopback: L440={band(seg[:,0],440):6.1f}dB R440={band(seg[:,1],440):6.1f}dB | "
          f"L880={band(seg[:,0],880):6.1f}dB R880={band(seg[:,1],880):6.1f}dB")
