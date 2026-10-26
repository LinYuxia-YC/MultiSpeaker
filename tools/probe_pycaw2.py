import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pycaw.utils import AudioUtilities
from app.devices import list_output_devices

working = {}
for d in AudioUtilities.GetAllDevices():
    try:
        vol = d.EndpointVolume
        if vol is None:
            continue
        working[d.FriendlyName] = (vol.GetMasterVolumeLevelScalar(), bool(vol.GetMute()))
    except Exception:
        pass

print("PortAudio outputs vs pycaw:")
for dev in list_output_devices():
    hit = working.get(dev.name)
    print(f"  {dev.name!r:55s} -> {hit}")
print("\nall working endpoints:")
for k, v in working.items():
    print(f"  {k!r} vol={v[0]:.3f} mute={v[1]}")
