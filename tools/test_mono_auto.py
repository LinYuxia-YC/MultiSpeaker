import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from app.engine import MultiSpeakerEngine
from app.decode import DecodedTrack

def make_track(ch):
    t = np.arange(48000) / 48000.0
    data = np.stack([0.2*np.sin(2*np.pi*440*t), 0.2*np.sin(2*np.pi*880*t)], axis=1).astype(np.float32)
    return DecodedTrack(path="", data=data, rate=48000, duration=1.0, title="t", source_channels=ch)

eng = MultiSpeakerEngine()
for ch in (1, 2, 6, 8):
    eng.set_track(make_track(ch))
    print(f"auto  src={ch}ch -> mono_mix={eng.mono_mix}")
eng.set_mono_mode("stereo"); eng.set_track(make_track(1)); print("stereo mode, 1ch ->", eng.mono_mix)
eng.set_mono_mode("mono");   eng.set_track(make_track(6)); print("mono mode,   6ch ->", eng.mono_mix)
eng.set_mono_mode("auto");   eng.set_track(make_track(6)); print("auto mode,   6ch ->", eng.mono_mix)
