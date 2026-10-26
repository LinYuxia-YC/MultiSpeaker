"""Headless engine test: play the built-in stereo test tone on 3 endpoints."""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.devices import list_output_devices
from app.engine import MultiSpeakerEngine
from app.testtone import make_stereo_test

devs = list_output_devices()
print("devices:")
for d in devs:
    print(f"  [{d.index}] {d.key} ch={d.channels} rate={d.rate} default={d.is_default}")

picked = devs[:3]
print("\nplaying on:", [d.name for d in picked])

eng = MultiSpeakerEngine()
eng.set_track(make_stereo_test(48000))
errs = eng.start(picked)
print("start errors:", errs)
print("t0 in", round(eng.t0 - time.perf_counter(), 3), "s")

t0 = time.perf_counter()
while time.perf_counter() - t0 < 4.0:
    time.sleep(0.5)
    peaks = eng.peaks()
    st = eng.device_stats()
    pos = eng.position()
    line = f"pos={pos:5.2f} "
    for k, (l, r, ch) in peaks.items():
        s = st[k]
        line += f"| {k[:18]:18s} L={l:.3f} R={r:.3f} lat={s['latency']*1000:.0f}ms xr={s['xruns']} "
    print(line)

print("\nfinal stats:", eng.device_stats())
eng.stop()
time.sleep(0.3)
print("stopped, running=", eng.running)
