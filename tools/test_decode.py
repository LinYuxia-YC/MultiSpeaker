"""Encode/decode round-trip test for the formats users actually play."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import av

from app.decode import decode_track

OUT = Path(r"I:\DSHwork\MultiSpeaker\build\media")
OUT.mkdir(parents=True, exist_ok=True)

RATE = 44100
DUR = 12.0
n = int(RATE * DUR)
t = np.arange(n) / RATE
# left: 220 Hz + 330 Hz, right: 440 Hz + 660 Hz  (clearly different spectra)
left = 0.22 * np.sin(2 * np.pi * 220 * t) + 0.12 * np.sin(2 * np.pi * 330 * t)
right = 0.22 * np.sin(2 * np.pi * 440 * t) + 0.12 * np.sin(2 * np.pi * 660 * t)
env = np.minimum(1.0, np.minimum(t / 0.05, (DUR - t) / 0.05))
data = np.stack([left * env, right * env], axis=1).astype(np.float32)

CASES = [("wav", "pcm_s16le", ".wav"), ("flac", "flac", ".flac"), ("mp3", "libmp3lame", ".mp3"),
         ("ogg", "libvorbis", ".ogg"), ("m4a", "aac", ".m4a")]

for fmt, codec, ext in CASES:
    path = OUT / f"tone{ext}"
    try:
        container = av.open(str(path), "w")
        stream = container.add_stream(codec, rate=RATE)
        stream.layout = "stereo"
        frame = av.AudioFrame.from_ndarray(data.T.copy(), format="fltp", layout="stereo")
        frame.sample_rate = RATE
        frame.pts = 0
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
        container.close()
    except Exception as exc:
        print(f"{fmt:5s} ENCODE FAIL: {type(exc).__name__}: {exc}")
        continue

    try:
        tr = decode_track(str(path))
        l = tr.data[:, 0]
        r = tr.data[:, 1]
        # correlation between channels: must stay low (they are different signals)
        corr = float(np.corrcoef(l[1000:-1000], r[1000:-1000])[0, 1])
        print(f"{fmt:5s} ok  {tr.rate} Hz  {tr.duration:.2f}s  ch={tr.source_channels}  "
              f"peakL={np.abs(l).max():.3f} peakR={np.abs(r).max():.3f}  L/R corr={corr:+.3f}  "
              f"size={path.stat().st_size/1024:.0f} kB")
    except Exception as exc:
        print(f"{fmt:5s} DECODE FAIL: {type(exc).__name__}: {exc}")
