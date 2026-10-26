import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pycaw.utils import AudioUtilities
from app.devices import list_output_devices

devs = list_output_devices()
print("PortAudio WASAPI outputs:")
for d in devs:
    print(f"  {d.key!r}")
print("\npycaw render endpoints:")
for d in AudioUtilities.GetAllDevices():
    try:
        vol = d.EndpointVolume
        scalar = vol.GetMasterVolumeLevelScalar() if vol else None
        mute = vol.GetMute() if vol else None
        print(f"  {d.FriendlyName!r} | vol={scalar} mute={mute}")
    except Exception as e:
        print("  err", d.FriendlyName, e)
