"""MultiSpeaker launcher."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication, QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import __version__  # noqa: E402
from app.ui import theme  # noqa: E402
from app.ui.main_window import MainWindow, resource_path  # noqa: E402


def run_selftest(log_path: str = "") -> int:
    import time
    import traceback

    from app.devices import list_output_devices
    from app.engine import MultiSpeakerEngine
    from app.testtone import make_stereo_test

    lines = []

    def out(msg: str) -> None:
        print(msg)
        lines.append(msg)

    ok = False
    try:
        out(f"MultiSpeaker {__version__}")
        devs = list_output_devices()
        out(f"endpoints: {len(devs)}")
        for d in devs:
            out(f"  {d.key} | ch={d.channels} | {d.rate} Hz | default={d.is_default}")

        # --- decoder + resampler check (PyAV / soxr bundle) ---
        import tempfile
        import wave

        import numpy as np

        from app.decode import decode_track
        from app.resample import backend_name, resample_stereo

        tmp = os.path.join(tempfile.gettempdir(), "multispeaker_selftest.wav")
        rate = 44100
        t = np.arange(rate) / rate
        pcm = np.stack(
            [
                0.25 * np.sin(2 * np.pi * 440 * t),
                0.25 * np.sin(2 * np.pi * 880 * t),
            ],
            axis=1,
        )
        with wave.open(tmp, "wb") as fh:
            fh.setnchannels(2)
            fh.setsampwidth(2)
            fh.setframerate(rate)
            fh.writeframes((pcm * 32767).astype(np.int16).tobytes())
        track = decode_track(tmp)
        corr = float(np.corrcoef(track.data[:, 0], track.data[:, 1])[0, 1])
        out(f"decode: {track.rate} Hz {track.duration:.2f}s ch={track.data.shape[1]} "
            f"source_ch={track.source_channels} L/R corr={corr:+.3f}")
        res = resample_stereo(track.data, track.rate, 48000)
        out(f"resample: {backend_name()} {track.data.shape[0]} -> {res.shape[0]} frames")
        decode_ok = (track.duration > 0.9 and track.data.shape[1] == 2 and abs(corr) < 0.2
                     and abs(res.shape[0] - int(rate * 48000 / 44100)) < 32)
        try:
            os.remove(tmp)
        except OSError:
            pass

        from app.live import find_cable_capture
        from app.sysvol import SystemVolume

        vol = SystemVolume()
        out(f"virtual cable: {find_cable_capture()}")
        out(f"system volume: available={vol.available}, endpoints={len(vol._map)}")

        if not devs:
            out("SELFTEST: no output device")
        else:
            eng = MultiSpeakerEngine()
            eng.set_track(make_stereo_test(48000))
            errs = eng.start(devs[:1])
            out(f"stream errors: {errs}")
            time.sleep(0.8)
            playing = eng.running
            stats = eng.device_stats()
            eng.stop()
            time.sleep(0.2)
            out(f"stats: {stats}")
            ok = decode_ok and playing and all(not s["error"] for s in stats.values())
        out("SELFTEST: " + ("OK" if ok else "FAIL"))
    except Exception:
        out("SELFTEST EXCEPTION:\n" + traceback.format_exc())

    if log_path:
        try:
            Path(log_path).write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="MultiSpeaker")
    parser.add_argument("--selftest", action="store_true", help="check audio devices and exit")
    parser.add_argument("--smoke", action="store_true", help="open the window briefly and exit")
    parser.add_argument("--screenshot", default="", help="save a window screenshot and exit")
    parser.add_argument("--log", default="", help="write selftest output to this file")
    parser.add_argument("--tray", action="store_true", help="start hidden in the notification area")
    args, _unknown = parser.parse_known_args()

    if args.selftest:
        return run_selftest(args.log)

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv[:1])
    app.setApplicationName("MultiSpeaker")
    app.setOrganizationName("MultiSpeaker")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setFont(theme.base_font(9.5))
    app.setStyleSheet(theme.build_qss())

    icon = QIcon(resource_path("app.ico"))
    app.setWindowIcon(icon)
    app.setQuitOnLastWindowClosed(False)

    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    server_name = "MultiSpeaker_IPC_v1"
    interactive = not (args.screenshot or args.smoke)
    if interactive:
        probe = QLocalSocket()
        probe.connectToServer(server_name)
        if probe.waitForConnected(300):
            probe.write(b"show")
            probe.waitForBytesWritten(300)
            probe.disconnectFromServer()
            return 0

    window = MainWindow(icon)

    server = QLocalServer()
    if interactive:
        QLocalServer.removeServer(server_name)
        if server.listen(server_name):
            server.newConnection.connect(window.show_from_tray)
        app._server = server

    if args.tray and window.tray is not None:
        window.start_hidden()
    else:
        window.show()

    if args.screenshot:
        target = args.screenshot

        def grab():
            pix = window.grab()
            pix.save(target)
            print("screenshot saved:", target, pix.size().width(), "x", pix.size().height())
            app.quit()

        QTimer.singleShot(900, grab)

    if args.smoke:
        QTimer.singleShot(2200, app.quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
