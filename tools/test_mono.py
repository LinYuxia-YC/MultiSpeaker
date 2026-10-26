"""Verify the mono-mix option: loopback stereo vs merged output."""
import sys
import time as _t
from pathlib import Path

import numpy as np
import pyaudiowpatch as pyaudio
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.devices import list_output_devices
from app.engine import MultiSpeakerEngine
from app.testtone import make_stereo_test

RATE = 48000
dev = list_output_devices()[0]
print("device:", dev.name)


def loopback_index(name):
    pa = pyaudio.PyAudio()
    base = name.replace("扬声器", "").strip(" ()").lower()
    for i in range(pa.get_device_count()):
        d = pa.get_device_info_by_index(i)
        if d.get("isLoopbackDevice") and base and base in str(d["name"]).lower():
            return pa, i
    pa.terminate()
    return None, None


def record(seconds, engine):
    pa, idx = loopback_index(dev.name)
    if idx is None:
        print("no loopback")
        return None
    st = pa.open(format=pyaudio.paInt16, channels=2, rate=RATE, input=True,
                 input_device_index=idx, frames_per_buffer=1024)
    engine.start([dev])
    chunks = []
    end = _t.time() + seconds
    while _t.time() < end:
        chunks.append(st.read(1024, exception_on_overflow=False))
    st.stop_stream(); st.close(); pa.terminate()
    engine.stop(fade=False)
    a = np.frombuffer(b"".join(chunks), dtype=np.int16).astype(np.float32) / 32768.0
    return a.reshape(-1, 2)


def band(sig, f, sr=RATE, dur=0.15):
    seg = sig[: int(dur * sr)]
    if seg.size < 512:
        return -120.0
    w = np.hanning(seg.size)
    spec = np.abs(np.fft.rfft(seg * w))
    freqs = np.fft.rfftfreq(seg.size, 1 / sr)
    j = int(np.argmin(np.abs(freqs - f)))
    return 20 * np.log10(max(spec[max(0, j - 2):j + 3].max(), 1e-9) / (seg.size / 2))


def align(a):
    rms = np.sqrt((a ** 2).mean(axis=1))
    idx = np.flatnonzero(rms > max(1e-4, rms.max() * 0.15))
    return idx[0] - int(0.10 * RATE) if idx.size else 0


eng = MultiSpeakerEngine()
eng.set_track(make_stereo_test(RATE))

print("\n--- stereo (mono off) ---")
a = record(2.2, eng)
if a is not None:
    s = align(a)
    seg = a[s + int(0.6 * RATE): s + int(0.9 * RATE)]
    print(f"L-only seg: L440={band(seg[:,0],440):6.1f}dB  R440={band(seg[:,1],440):6.1f}dB")

eng.set_mono(True)
print("\n--- mono (merged) ---")
a = record(2.2, eng)
if a is not None:
    s = align(a)
    seg = a[s + int(0.6 * RATE): s + int(0.9 * RATE)]
    print(f"L-only seg: L440={band(seg[:,0],440):6.1f}dB  R440={band(seg[:,1],440):6.1f}dB")
    seg2 = a[s + int(1.9 * RATE): s + int(2.1 * RATE)]
    print(f"R-only seg: L659={band(seg2[:,0],659.25):6.1f}dB  R659={band(seg2[:,1],659.25):6.1f}dB")
eng.set_mono(False)
print("\ndone")
