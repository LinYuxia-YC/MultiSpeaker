"""Probe WASAPI endpoints and multi-stream behaviour."""
import sys
import time
from pathlib import Path
import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.devices import list_output_devices

print("sounddevice", sd.__version__, "| PortAudio", sd.get_portaudio_version()[1])
print("hostapis:")
for i, h in enumerate(sd.query_hostapis()):
    print(f"  {i}: {h['name']} devices={len(h['devices'])} default_out={h['default_output_device']}")

devs = list_output_devices()
print("\nWASAPI render endpoints:")
for d in devs:
    print(f"  [{d.index:3d}] {d.key!r:55s} ch={d.channels} rate={d.rate} lat={d.latency:.4f} default={d.is_default}")

if len(sys.argv) > 1 and sys.argv[1] == "stream":
    print("\n--- opening streams ---")
    streams = []
    for d in devs:
        try:
            s = sd.OutputStream(
                device=d.index, samplerate=d.rate, channels=min(d.channels, 2),
                dtype="float32", blocksize=int(d.rate * 0.012 / 64) * 64,
                latency="low", callback=lambda *a: None,
            )
            print(f"  open ok  [{d.index}] ch={min(d.channels,2)} rate={d.rate} "
                  f"latency(before start)={s.latency:.4f} blocksize={s.blocksize}")
            streams.append((d, s))
        except Exception as e:
            print(f"  open FAIL [{d.index}] {d.name}: {type(e).__name__}: {e}")

    calls = {d.key: 0 for d, _ in streams}

    def make_cb(key, ch):
        def cb(outdata, frames, t, status):
            calls[key] += 1
            outdata.fill(0.0)
        return cb

    for d, s in streams:
        s.callback = make_cb(d.key, s.channels)
        s.start()
        print(f"  started [{d.index}] latency(after)={s.latency:.4f} bs={s.blocksize}")

    t_end = time.time() + 2.0
    while time.time() < t_end:
        time.sleep(0.2)
    for d, s in streams:
        print(f"  [{d.index}] {d.name}: cb={calls[d.key]} latency={s.latency:.4f}")
        s.stop(); s.close()
    print("done")
