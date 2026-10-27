# MultiSpeaker — 多扬声器同步播放器
# Copyright (C) 2026 YuXiaYC, Deepseek Harness
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Multi-endpoint synchronised playback engine.

One decoded stereo source is timestamped against a single wall clock.  Every
output endpoint gets its own WASAPI stream and reads the source slightly ahead
(by its own output latency) so that all speakers emit the same sample at the
same instant.  A gentle drifting-corrector keeps each device locked to the
master clock, and stereo channels are mapped explicitly - never averaged down
to mono.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import sounddevice as sd

from .chmap import build_matrix, downmix_to_mono, downmix_to_stereo, source_names
from .decode import DecodedTrack
from .devices import AudioDevice
from .resample import resample_stereo


def _channel_map(block: np.ndarray, channels: int, mode: str = "all") -> np.ndarray:
    """Expand a (n, 2) stereo block to the device's channel layout.

    Channel order follows the Windows/WAVE default: FL, FR, FC, LFE, BL, BR,
    SL, SR.  Left and right always stay separate - the rear pairs get their own
    left/right copy instead of a mono sum.
    """
    n = block.shape[0]
    if channels <= 1:
        mono = block.mean(axis=1, keepdims=True, dtype=np.float32)
        return mono
    if channels == 2:
        return block

    out = np.zeros((n, channels), np.float32)
    left = block[:, 0]
    right = block[:, 1]
    out[:, 0] = left
    out[:, 1] = right
    if mode == "front":
        return out

    if channels >= 3:
        out[:, 2] = (left + right) * 0.25  # centre, -12 dB
    if channels >= 4:
        # 4.0 -> FL FR BL BR
        if channels == 4:
            out[:, 2] = left * 0.7071
            out[:, 3] = right * 0.7071
        else:
            out[:, 3] = 0.0  # LFE stays silent
    if channels >= 6:
        out[:, 4] = left * 0.7071
        out[:, 5] = right * 0.7071
    if channels >= 8:
        out[:, 6] = left * 0.7071
        out[:, 7] = right * 0.7071
    return out


class _DeviceWorker:
    """Owns one OutputStream and its read cursor inside the shared PCM."""

    def __init__(self, engine: "MultiSpeakerEngine", dev: AudioDevice,
                 data: np.ndarray, rate: int):
        """初始化单个设备的工作状态：源数据、声道布局、延迟与电平。"""
        self.engine = engine
        self.dev = dev
        self.data = data
        self.rate = int(rate)
        self.n = int(data.shape[0])
        self.channels = max(1, min(int(dev.channels), 8))
        self.src_ch = int(data.shape[1]) if data.ndim == 2 and data.size else 2
        self.src_names = source_names(getattr(engine, "source_layout", "stereo"), self.src_ch)
        self._matrix = None
        self._matrix_mode = None
        self.stream: Optional[sd.OutputStream] = None
        self.error = ""
        self.latency = max(0.0, float(dev.latency)) + 0.012
        self.base_latency = self.latency
        self.user_delay = 0.0

        self.pos = 0.0
        self.err = 0.0
        self.gain = 1.0
        self.muted = False
        self.peak_l = 0.0
        self.peak_r = 0.0
        self.xruns = 0
        self.blocks = 0
        self._gain_t0 = time.perf_counter()

        # live (virtual cable) mode
        self.live = None
        self.src_rate = int(rate)
        self.step_base = 1.0
        self.buf_src = 0
        self.delay_src = 0.0

    # ------------------------------------------------------------------ setup
    @property
    def blocksize(self) -> int:
        """按设备采样率计算约 12 ms 的块大小（64 帧对齐）。"""
        bs = int(self.rate * 0.012 / 64.0) * 64
        return max(128, min(2048, bs))

    def open(self) -> None:
        """打开 WASAPI 输出流并读取实际延迟，用于同步补偿。"""
        self.stream = sd.OutputStream(
            device=self.dev.index,
            samplerate=self.rate,
            channels=self.channels,
            dtype="float32",
            blocksize=self.blocksize,
            latency="low",
            callback=self.callback,
            clip_off=True,
            dither_off=True,
            prime_output_buffers_using_stream_callback=False,
        )
        self.stream.start()
        self.blocksize_actual = int(self.stream.blocksize)
        try:
            lat = float(self.stream.latency)
        except Exception:
            lat = 0.0
        if not (0.0 < lat < 2.0):
            lat = float(self.dev.latency) + self.blocksize_actual / self.rate
        self.latency = lat + self.user_delay
        self.base_latency = lat

    def close(self) -> None:
        """停止并关闭输出流。"""
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        self.stream = None

    def retime(self, now: float, t0: float) -> None:
        """按当前墙钟与主时间轴重新对齐读取位置。"""
        self.pos = (now + self.latency - t0) * self.rate
        self.err = 0.0

    def set_delay(self, ms: float) -> None:
        """设置本设备的延迟补偿；实时模式换算为源采样帧。"""
        self.user_delay = float(ms) / 1000.0
        self.latency = self.base_latency + self.user_delay
        if self.live is not None:
            self.delay_src = self.user_delay * self.src_rate
            return
        if self.engine.running and not self.engine.paused:
            self.retime(time.perf_counter(), self.engine.t0)
            self._gain_t0 = time.perf_counter()

    # --------------------------------------------------------------- callback
    def callback(self, outdata, frames, time_info, status) -> None:
        """
        PortAudio 回调（每个设备一个线程）。
        
        流程：计算目标源位置 → 误差平滑 → 微调读取速率 → 读取/插值 →
        增益与淡入淡出 → 单声道/立体声/多声道映射 → 写入输出缓冲。
        """
        eng = self.engine
        try:
            if status and getattr(status, "output_underflow", False):
                self.xruns += 1
            if not eng.running or not eng.armed or eng.paused:
                outdata.fill(0.0)
                self.peak_l = self.peak_r = 0.0
                return

            t = time.perf_counter()
            if self.live is not None:
                live = self.live
                target = float(live.write) - self.buf_src - self.delay_src
                if target < 0.0:
                    outdata.fill(0.0)
                    self.peak_l = self.peak_r = 0.0
                    return
                err = target - self.pos
                if abs(err) > self.src_rate * 0.35:
                    self.pos = target
                    self.err = 0.0
                else:
                    self.err = 0.75 * self.err + 0.25 * err
                ratio = 1.0
                if abs(self.err) > self.src_rate * 0.002:
                    ratio = 1.0 + max(-0.004, min(0.004, 1.6 * self.err / self.src_rate))
                step = self.step_base * ratio
                start = self.pos
                block = live.read(start, frames, step)
                self.pos = start + step * frames
                avail = float(live.write) - start
                need = frames * step
                if avail < need:
                    valid = int(max(0.0, avail) / max(step, 1e-9))
                    if valid < frames:
                        block = block.copy()
                        block[valid:] = 0.0
                self.blocks += 1
            else:
                target = (t + self.latency - eng.t0) * self.rate
                if target < 0.0:
                    outdata.fill(0.0)
                    self.pos = 0.0
                    self.peak_l = self.peak_r = 0.0
                    return

                err = target - self.pos
                if abs(err) > self.rate * 0.35:
                    self.pos = target
                    self.err = 0.0
                else:
                    self.err = 0.75 * self.err + 0.25 * err

                ratio = 1.0
                if abs(self.err) > self.rate * 0.0015:
                    ratio = 1.0 + max(-0.004, min(0.004, 1.6 * self.err / self.rate))

                start = self.pos
                if ratio == 1.0 and start == float(int(start)):
                    i = int(start)
                    seg = self.data[i:i + frames]
                    m = seg.shape[0]
                    if m == frames:
                        block = seg
                    else:
                        block = np.zeros((frames, 2), np.float32)
                        if m:
                            block[:m] = seg
                else:
                    idx = start + ratio * np.arange(frames, dtype=np.float64)
                    block = self._interp(idx)
                self.pos = start + ratio * frames
                self.blocks += 1

            env = min(1.0, max(0.0, (t - self._gain_t0) / 0.04))
            gain = self.gain * eng.master_gain * env * eng.fade_gain(t)
            if self.muted:
                gain = 0.0
            if eng.solo_key is not None and eng.solo_key != self.dev.key:
                gain = 0.0

            if gain != 1.0:
                block = block * gain

            if block.shape[1] >= 2:
                pk_l = float(np.max(np.abs(block[:, 0]))) if frames else 0.0
                pk_r = float(np.max(np.abs(block[:, 1]))) if frames else 0.0
            else:
                pk_l = pk_r = float(np.max(np.abs(block[:, 0]))) if frames else 0.0
            self.peak_l = max(pk_l, self.peak_l * 0.80)
            self.peak_r = max(pk_r, self.peak_r * 0.80)

            if eng.effective_mono():
                mono = downmix_to_mono(block, self.src_names)
                stereo = np.concatenate((mono, mono), axis=1)
                out = _channel_map(stereo, self.channels, eng.channel_mode)
            elif block.shape[1] <= 2:
                out = _channel_map(block[:, :2], self.channels, eng.channel_mode)
            elif eng.mono_mode == "stereo":
                stereo = downmix_to_stereo(block, self.src_names)
                out = _channel_map(stereo, self.channels, eng.channel_mode)
            else:
                if self._matrix is None or self._matrix_mode != eng.channel_mode:
                    self._matrix = build_matrix(self.src_names, self.channels, eng.channel_mode)
                    self._matrix_mode = eng.channel_mode
                out = (block @ self._matrix).astype(np.float32, copy=False)
            outdata[...] = out
        except Exception as exc:  # never let an exception escape into PortAudio
            self.error = f"{type(exc).__name__}: {exc}"
            try:
                outdata.fill(0.0)
            except Exception:
                pass

    def _interp(self, idx: np.ndarray) -> np.ndarray:
        """Catmull-Rom fractional read - transparent at ratio ~ 1.0."""
        n = self.n
        i = np.floor(idx).astype(np.int64)
        f = (idx - i).astype(np.float32)[:, None]
        valid = (i >= 0) & (i < n)
        ic = np.clip(i, 0, n - 1)
        i0 = np.clip(ic - 1, 0, n - 1)
        i2 = np.clip(ic + 1, 0, n - 1)
        i3 = np.clip(ic + 2, 0, n - 1)
        d = self.data
        y0 = d[i0]
        y1 = d[ic]
        y2 = d[i2]
        y3 = d[i3]
        a = -0.5 * y0 + 1.5 * y1 - 1.5 * y2 + 0.5 * y3
        b = y0 - 2.5 * y1 + 2.0 * y2 - 0.5 * y3
        c = -0.5 * y0 + 0.5 * y2
        out = ((a * f + b) * f + c) * f + y1
        if not valid.all():
            out[~valid] = 0.0
        return out.astype(np.float32, copy=False)


class MultiSpeakerEngine:
    def __init__(self) -> None:
        """初始化引擎：工作线程表、主时钟、声道模式与淡入淡出状态。"""
        self._lock = threading.RLock()
        self.track: Optional[DecodedTrack] = None
        self._cache: Dict[int, np.ndarray] = {}
        self.workers: Dict[str, _DeviceWorker] = {}
        self.t0 = 0.0
        self.running = False
        self.armed = False
        self.paused = False
        self._pause_at = 0.0
        self._stop_pos = 0.0
        self.master_gain = 0.9
        self.channel_mode = "all"
        self.source_layout = "stereo"
        self.mono_mode = "auto"
        self.mono_mix = True
        self.source_channels = 2
        self.solo_key: Optional[str] = None
        self._fade_t0 = 0.0
        self._fade_from = 1.0
        self._fade_to = 1.0
        self._fade_dur = 0.0
        self._stop_timer: Optional[threading.Timer] = None
        self.dropped_frames = 0
        self.live_source = None
        self.live_buffer_ms = 80.0

    # ------------------------------------------------------------------ state
    def is_playing(self) -> bool:
        """是否正在播放（运行中且未暂停）。"""
        return self.running and not self.paused

    def duration(self) -> float:
        """当前音轨时长（秒）。"""
        return self.track.duration if self.track else 0.0

    def position(self) -> float:
        """当前可听位置（秒）；暂停/停止时返回冻结位置。"""
        if not self.track:
            return 0.0
        now = time.perf_counter()
        if self.paused:
            pos = self._pause_at - self.t0
        elif self.running:
            pos = now - self.t0
        else:
            pos = self._stop_pos
        return max(0.0, min(pos, self.track.duration))

    def fade_gain(self, t: float) -> float:
        """计算 t 时刻的淡入淡出增益（0..1）。"""
        if self._fade_dur <= 0.0:
            return self._fade_to
        x = (t - self._fade_t0) / self._fade_dur
        if x <= 0.0:
            return self._fade_from
        if x >= 1.0:
            return self._fade_to
        return self._fade_from + (self._fade_to - self._fade_from) * x

    def _set_fade(self, to: float, duration: float) -> None:
        """从当前增益平滑过渡到目标值（用于启停/暂停）。"""
        now = time.perf_counter()
        self._fade_from = self.fade_gain(now)
        self._fade_to = to
        self._fade_t0 = now
        self._fade_dur = duration

    # ------------------------------------------------------------------ track
    def set_track(self, track: Optional[DecodedTrack]) -> None:
        """载入解码后的音轨：重置缓存并按源声道刷新声道模式。"""
        with self._lock:
            self._hard_stop()
            self.track = track
            self.source_channels = int(track.source_channels) if track else 2
            self.source_layout = track.source_layout if track else "stereo"
            self._refresh_mono()
            self._cache.clear()
            self._stop_pos = 0.0
            self.t0 = 0.0

    def _data_for(self, rate: int) -> np.ndarray:
        """取得指定采样率的音轨数据（按需重采样并缓存）。"""
        arr = self._cache.get(rate)
        if arr is None:
            assert self.track is not None
            arr = np.ascontiguousarray(
                resample_stereo(self.track.data, self.track.rate, rate), np.float32
            )
            self._cache[rate] = arr
        return arr

    # --------------------------------------------------------------- playback
    def start(self, devices: List[AudioDevice]) -> List[str]:
        """(Re)start playback on the given endpoints. Returns error strings."""
        errors: List[str] = []
        with self._lock:
            self._hard_stop()
            if not self.track or not self.track.frames:
                return ["没有可播放的音频"]
            self.running = True
            self.armed = False
            self.paused = False
            self.solo_key = None
            self.dropped_frames = 0
            self.t0 = 0.0
            self._fade_from = 0.0
            self._fade_to = 1.0
            self._fade_t0 = time.perf_counter()
            self._fade_dur = 0.10

            for dev in devices:
                err = self._open_worker(dev)
                if err:
                    errors.append(f"{dev.short}: {err}")

            if not self.workers:
                self.running = False
                return errors or ["没有可用的输出设备"]

            pos0 = max(0.0, min(self._stop_pos, self.track.duration - 0.01))
            self.t0 = time.perf_counter() + 0.30 - pos0
            for w in self.workers.values():
                w.pos = max(0.0, (time.perf_counter() + w.latency - self.t0) * w.rate)
                w.err = 0.0
            self.armed = True
            return errors

    def _open_worker(self, dev: AudioDevice) -> Optional[str]:
        """为设备创建工作线程，并按文件/实时模式初始化。"""
        try:
            if self.live_source is not None:
                src = self.live_source
                worker = _DeviceWorker(self, dev, np.zeros((0, 2), np.float32), dev.rate)
                worker.live = src
                worker.src_rate = src.rate
                worker.step_base = src.rate / float(dev.rate)
                worker.buf_src = int(self.live_buffer_ms / 1000.0 * src.rate)
                worker.delay_src = 0.0
                worker.pos = max(0.0, float(src.write) - worker.buf_src)
                worker.open()
            else:
                data = self._data_for(dev.rate)
                worker = _DeviceWorker(self, dev, data, dev.rate)
                worker.open()
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"
        self.workers[dev.key] = worker
        return None

    def start_live(self, devices: List[AudioDevice], source, buffer_ms: float = 80.0) -> List[str]:
        """Relay a live capture source (virtual cable) to the given devices."""
        errors: List[str] = []
        with self._lock:
            self._hard_stop()
            self.track = None
            self.source_channels = 2
            self.source_layout = "stereo"
            self._refresh_mono()
            self._cache.clear()
            self.running = True
            self.armed = False
            self.paused = False
            self.solo_key = None
            self.live_buffer_ms = float(buffer_ms)
            self.live_source = source
            self.t0 = 0.0
            self._fade_from = 0.0
            self._fade_to = 1.0
            self._fade_t0 = time.perf_counter()
            self._fade_dur = 0.10
            try:
                if not source.running:
                    source.start()
                source.wait_ready(1.5)
            except Exception as exc:
                self.running = False
                self.live_source = None
                return [f"无法采集虚拟声卡: {exc}"]
            for dev in devices:
                err = self._open_worker(dev)
                if err:
                    errors.append(f"{dev.short}: {err}")
            if not self.workers:
                self.running = False
                self.live_source = None
                try:
                    source.stop()
                except Exception:
                    pass
                return errors or ["没有可用的输出设备"]
            self.armed = True
            return errors

    def add_device(self, dev: AudioDevice) -> Optional[str]:
        """播放中新增一个输出设备（立即加入同步）。"""
        with self._lock:
            if dev.key in self.workers:
                return None
            if not self.running:
                return "未在播放"
            err = self._open_worker(dev)
            if err:
                return err
            worker = self.workers[dev.key]
            if self.live_source is not None:
                worker.pos = max(0.0, float(self.live_source.write) - worker.buf_src)
            else:
                now = time.perf_counter()
                worker.pos = (now + worker.latency - self.t0) * worker.rate
            return None

    def remove_device(self, key: str) -> None:
        """移除并关闭一个输出设备。"""
        with self._lock:
            worker = self.workers.pop(key, None)
        if worker:
            worker.close()

    def _hard_stop(self) -> None:
        """立即停止所有输出流与实时采集源。"""
        with self._lock:
            if self._stop_timer:
                try:
                    self._stop_timer.cancel()
                except Exception:
                    pass
                self._stop_timer = None
            self.running = False
            self.armed = False
            self.paused = False
            self.t0 = 0.0
            workers = list(self.workers.values())
            self.workers.clear()
            source = self.live_source
            self.live_source = None
        for w in workers:
            w.close()
        if source is not None:
            try:
                source.stop()
            except Exception:
                pass

    def stop(self, fade: bool = True) -> None:
        """停止播放（默认 70 ms 淡出，避免爆音）。"""
        with self._lock:
            if not self.running:
                self._hard_stop()
                self._stop_pos = 0.0
                return
            self._stop_pos = 0.0
            if fade and not self.paused:
                self._set_fade(0.0, 0.07)
                timer = threading.Timer(0.09, self._hard_stop)
                timer.daemon = True
                self._stop_timer = timer
                timer.start()
            else:
                self._hard_stop()

    def pause(self) -> None:
        """暂停：淡出后冻结主时钟，输出流保持连接以便快速恢复。"""
        with self._lock:
            if self.live_source is not None:
                return
            if not self.running or self.paused:
                return
            self._set_fade(0.0, 0.05)
            timer = threading.Timer(0.06, self._do_pause)
            timer.daemon = True
            timer.start()

    def _do_pause(self) -> None:
        """淡出结束后真正进入暂停状态。"""
        with self._lock:
            if not self.running:
                return
            self.paused = True
            self._pause_at = time.perf_counter()
            self._set_fade(1.0, 0.0)

    def resume(self) -> None:
        """恢复播放：平移主时钟并重新对齐所有设备。"""
        with self._lock:
            if not self.running or not self.paused:
                return
            now = time.perf_counter()
            self.t0 += now - self._pause_at
            self.paused = False
            for w in self.workers.values():
                w.pos = (now + w.latency - self.t0) * w.rate
                w.err = 0.0
            self._set_fade(1.0, 0.06)

    def seek(self, seconds: float) -> None:
        """跳转到指定秒数（仅文件模式）。"""
        with self._lock:
            if not self.track or self.live_source is not None:
                return
            seconds = max(0.0, min(float(seconds), max(0.0, self.track.duration - 0.05)))
            now = time.perf_counter()
            if self.paused:
                self._pause_at = now
                self.t0 = now - seconds
                anchor = now
            else:
                self.t0 = now - seconds
                anchor = now
            self._stop_pos = seconds
            for w in self.workers.values():
                w.pos = (anchor + w.latency - self.t0) * w.rate
                w.err = 0.0

    # --------------------------------------------------------------- controls
    def set_master_gain(self, value: float) -> None:
        """设置全局主音量（0..1）。"""
        self.master_gain = max(0.0, min(1.0, float(value)))

    def set_gain(self, key: str, value: float) -> None:
        """设置单设备软件增益（系统音量不可用时的回退路径）。"""
        w = self.workers.get(key)
        if w:
            w.gain = max(0.0, min(1.5, float(value)))

    def set_muted(self, key: str, muted: bool) -> None:
        """设置单设备软件静音（端点静音不可用时的回退）。"""
        w = self.workers.get(key)
        if w:
            w.muted = bool(muted)

    def set_solo(self, key: Optional[str]) -> None:
        """独奏：仅保留指定设备发声（None 取消）。"""
        self.solo_key = key

    def set_delay(self, key: str, ms: float) -> None:
        """设置单设备延迟补偿（毫秒）。"""
        w = self.workers.get(key)
        if w:
            w.set_delay(ms)

    def set_channel_mode(self, mode: str) -> None:
        """多声道设备的立体声分配方式：all（铺开）/ front（仅前置）。"""
        self.channel_mode = "front" if mode == "front" else "all"

    def effective_mono(self) -> bool:
        """计算当前是否合并单声道；自动模式按源声道判断（仅 1ch 合并）。"""
        if self.mono_mode == "mono":
            return True
        if self.mono_mode == "stereo":
            return False
        # auto: 仅单声道源合并；双声道及以上按源的实际声道还原
        return self.source_channels <= 1

    def set_mono_mode(self, mode: str) -> None:
        """设置声道模式：auto / mono / stereo。"""
        self.mono_mode = mode if mode in ("auto", "mono", "stereo") else "auto"
        self._refresh_mono()

    def _refresh_mono(self) -> None:
        """根据模式与源声道刷新 mono_mix 标志。"""
        if self.mono_mode == "mono":
            self.mono_mix = True
        elif self.mono_mode == "stereo":
            self.mono_mix = False
        else:  # auto: 单声道源合并，双声道及以上保持对应声道
            self.mono_mix = self.effective_mono()

    def set_devices(self, devices: List[AudioDevice]) -> List[str]:
        """Live add/remove of endpoints while playing."""
        errors: List[str] = []
        with self._lock:
            wanted = {d.key: d for d in devices}
            for key in list(self.workers.keys()):
                if key not in wanted:
                    worker = self.workers.pop(key)
                    worker.close()
            for key, dev in wanted.items():
                if key in self.workers:
                    continue
                if not self.running:
                    continue
                err = self._open_worker(dev)
                if err:
                    errors.append(f"{dev.short}: {err}")
                elif self.live_source is not None:
                    worker = self.workers[key]
                    worker.pos = max(0.0, float(self.live_source.write) - worker.buf_src)
                else:
                    now = time.perf_counter()
                    self.workers[key].pos = (
                        (now + self.workers[key].latency - self.t0) * self.workers[key].rate
                    )
        return errors

    def peaks(self) -> Dict[str, tuple]:
        """各设备当前 L/R 峰值（供电平表）。"""
        return {
            key: (w.peak_l, w.peak_r, w.channels)
            for key, w in self.workers.items()
        }

    def device_stats(self) -> Dict[str, dict]:
        """各设备运行状态（延迟、欠载、错误、声道数）。"""
        return {
            key: {
                "latency": w.latency,
                "xruns": w.xruns,
                "error": w.error,
                "channels": w.channels,
                "blocksize": getattr(w, "blocksize_actual", w.blocksize),
                "rate": w.rate,
            }
            for key, w in self.workers.items()
        }

    def shutdown(self) -> None:
        """关闭引擎（窗口退出时调用）。"""
        self._hard_stop()
