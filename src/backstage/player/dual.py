"""Phat 2 kenh: guide ra tai nghe, beat ra loa - tu cung mot clock.

    L = beat + vocal * guide_gain
    R = beat

Mix ngay trong audio callback thay vi phat file da render san, vi `guide_gain`
la linh hon cua san pham: nguoi hat ha dan giong guide xuong khi tu tin hon, va
phai ha duoc NGAY LUC DANG HAT. Bake gain vao file thi mat kha nang do.

Sync van tuyet doi: hai kenh duoc ghi trong cung mot buffer, cung mot lan goi
callback, tu cung mot chi so mau. Khong co duong nao de chung lech nhau.
"""

from __future__ import annotations

import threading
from typing import Self

import numpy as np
import soundfile as sf

from backstage.engine.render import to_mono
from backstage.engine.separate import Stems


def mix_block(
    beat: np.ndarray,
    vocal: np.ndarray,
    gain_start: float,
    gain_end: float,
) -> np.ndarray:
    """Mot block -> stereo (frames, 2): kenh 0 = guide, kenh 1 = beat.

    Khi gain doi, ramp tuyen tinh trong long block thay vi nhay bac - nhay bac
    tao tieng "click" nghe rat ro trong tai nghe.
    """
    n = beat.shape[0]
    if gain_start == gain_end:
        gain: float | np.ndarray = np.float32(gain_start)
    else:
        gain = np.linspace(gain_start, gain_end, n, dtype=np.float32)

    out = np.empty((n, 2), dtype=np.float32)
    out[:, 0] = beat + vocal * gain
    out[:, 1] = beat
    return out


def load_stems_mono(stems: Stems) -> tuple[np.ndarray, np.ndarray, int]:
    """Doc stems tu dia thanh 2 mang mono trong RAM.

    Nap het vao RAM co y: doc dia trong audio callback la cach chac chan nhat de
    tao dropout. Mot bai 4 phut mono float32 chi khoang 42MB moi stem.
    """
    vocal_raw, sr_v = sf.read(stems.vocals, dtype="float32", always_2d=True)
    beat_raw, sr_b = sf.read(stems.no_vocals, dtype="float32", always_2d=True)
    if sr_v != sr_b:
        raise ValueError(f"sample rate lech nhau: vocals {sr_v} vs no_vocals {sr_b}")

    vocal = to_mono(vocal_raw)
    beat = to_mono(beat_raw)
    if vocal.shape != beat.shape:
        raise ValueError(
            f"stems lech do dai ({vocal.shape[0]} vs {beat.shape[0]} frames) - "
            f"cache co the da hong, thu tach lai voi force=True"
        )
    return beat, vocal, sr_v


class DualPlayer:
    """Mot OutputStream 2 kenh, mix guide/beat theo tung block."""

    def __init__(
        self,
        beat: np.ndarray,
        vocal: np.ndarray,
        sample_rate: int,
        *,
        device: int | None = None,
        blocksize: int = 1024,
        guide_gain: float = 1.0,
    ) -> None:
        if beat.shape != vocal.shape:
            raise ValueError(f"beat {beat.shape} va vocal {vocal.shape} khong cung do dai")

        self._beat = np.ascontiguousarray(beat, dtype=np.float32)
        self._vocal = np.ascontiguousarray(vocal, dtype=np.float32)
        self.sample_rate = sample_rate
        self._pos = 0
        # _target doc/ghi tu thread khac (UI, CLI); gan float la atomic trong
        # CPython nen khong can lock cho rieng no. _cur chi callback dung.
        self._target_gain = float(guide_gain)
        self._cur_gain = float(guide_gain)
        self._finished = threading.Event()

        import sounddevice as sd

        self._sd = sd
        self._stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=2,
            dtype="float32",
            device=device,
            blocksize=blocksize,
            callback=self._callback,
            finished_callback=self._finished.set,
        )

    @classmethod
    def from_stems(cls, stems: Stems, **kwargs) -> DualPlayer:
        beat, vocal, sr = load_stems_mono(stems)
        return cls(beat, vocal, sr, **kwargs)

    # --- guide gain ---

    @property
    def guide_gain(self) -> float:
        return self._target_gain

    def set_guide_gain(self, gain: float) -> None:
        """Doi duoc luc dang phat. 1.0 = nghe ro giong goc, 0.0 = hat moc."""
        self._target_gain = float(np.clip(gain, 0.0, 1.0))

    # --- trang thai ---

    @property
    def position_sec(self) -> float:
        return self._pos / self.sample_rate

    @property
    def duration_sec(self) -> float:
        return self._beat.shape[0] / self.sample_rate

    @property
    def finished(self) -> bool:
        return self._finished.is_set()

    # --- dieu khien ---

    def start(self) -> None:
        self._stream.start()

    def stop(self) -> None:
        self._stream.stop()

    def close(self) -> None:
        self._stream.close()

    def wait(self, timeout: float | None = None) -> bool:
        """Cho den khi phat xong. True neu da xong, False neu het timeout."""
        return self._finished.wait(timeout)

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
        self.close()

    # --- audio callback: khong cap phat lon, khong I/O, khong log ---

    def _callback(self, outdata, frames, _time, status) -> None:
        if status:
            # Chi ghi nhan, khong print: print trong callback co the gay dropout.
            self.last_status = status

        start = self._pos
        end = min(start + frames, self._beat.shape[0])
        n = end - start

        if n <= 0:
            outdata[:] = 0
            raise self._sd.CallbackStop

        target = self._target_gain
        outdata[:n] = mix_block(
            self._beat[start:end], self._vocal[start:end], self._cur_gain, target
        )
        self._cur_gain = target
        self._pos = end

        if n < frames:
            outdata[n:] = 0
            raise self._sd.CallbackStop


def play_stems(
    stems: Stems,
    *,
    device: int | None = None,
    blocksize: int = 1024,
    guide_gain: float = 1.0,
) -> DualPlayer:
    """Tien ich: nap stems va bat dau phat. Nguoi goi tu dong `wait()`/`close()`."""
    player = DualPlayer.from_stems(stems, device=device, blocksize=blocksize, guide_gain=guide_gain)
    player.start()
    return player
