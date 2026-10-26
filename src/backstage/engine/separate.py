"""Option 1: tach ban goc thanh vocals + no_vocals bang Demucs.

Day la duong mac dinh cua san pham. Diem quan trong: hai stem sinh ra tu CUNG
mot file nguon nen chung sample-aligned san - khong co offset, khong can warp,
khong co gi de lech. Toan bo bai toan alignment chi xuat hien o Option 2.

Tach mot lan roi cache. Tren CPU (may dev khong co CUDA) mot bai 4 phut mat
khoang 2-4 phut, nen day la viec offline, khong bao gio goi tu audio callback
hay UI thread.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from backstage import paths

VOCALS_NAME = "vocals.wav"
NO_VOCALS_NAME = "no_vocals.wav"

DEFAULT_MODEL = "htdemucs"

# Stems luu dang float32 WAV, khong phai PCM 16/24: day la file trung gian,
# va no_vocals la tong cua 3 stem nen co the vuot [-1, 1]. Float thi khong
# clip, khong quantize - de dan sai so cho buoc render quyet dinh.
_STEM_SUBTYPE = "FLOAT"


@dataclass
class Stems:
    """Ket qua tach, da nam tren dia."""

    vocals: Path
    no_vocals: Path
    sample_rate: int
    duration_sec: float
    model: str
    song_fingerprint: str

    @property
    def cached_dir(self) -> Path:
        return self.vocals.parent


def _save(array: np.ndarray, path: Path, sample_rate: int) -> None:
    """array: (channels, samples) kieu Demucs -> soundfile can (frames, channels)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, array.T, sample_rate, subtype=_STEM_SUBTYPE)


def separate(
    song: Path,
    *,
    model: str = DEFAULT_MODEL,
    jobs: int = 0,
    force: bool = False,
    progress: bool = True,
    callback: Callable[[dict], None] | None = None,
) -> Stems:
    """Tach `song` thanh vocals + no_vocals, cache theo (fingerprint, model).

    `force=True` de tach lai du da co cache.

    `callback` duoc Demucs goi trong luc tach, nhan dict co 'segment_offset',
    'audio_length', 'model_idx_in_bag', 'models'. UI dung no de ve progress
    that thay vi mot thanh chay vo nghia (xem backstage.ui.app). Callback chay
    tren thread dang tach, khong phai UI thread.
    """
    song = Path(song)
    if not song.is_file():
        raise FileNotFoundError(song)

    song_fp = paths.file_fingerprint(song)
    out_dir = paths.stems_dir(song_fp, model)
    vocals_path = out_dir / VOCALS_NAME
    no_vocals_path = out_dir / NO_VOCALS_NAME

    if not force and vocals_path.is_file() and no_vocals_path.is_file():
        info = sf.info(vocals_path)
        return Stems(
            vocals=vocals_path,
            no_vocals=no_vocals_path,
            sample_rate=info.samplerate,
            duration_sec=info.duration,
            model=model,
            song_fingerprint=song_fp,
        )

    # Import trong ham: demucs keo theo torch, mat vai giay. Cac lenh khong tach
    # (vi du `backstage devices`) khong nen phai tra gia do.
    from demucs.api import Separator

    separator = Separator(
        model=model, device="cpu", jobs=jobs, progress=progress, callback=callback
    )
    _origin, stems = separator.separate_audio_file(song)

    if "vocals" not in stems:
        raise RuntimeError(f"model {model!r} khong co stem 'vocals': {sorted(stems)}")

    vocals = stems["vocals"].numpy()
    # no_vocals = tong moi stem con lai. Tuong duong `--two-stems=vocals` cua
    # Demucs CLI, nhung giu luon ca 4 stem trong bo nho de khong tach lai neu
    # sau nay can tung nhac cu rieng.
    others = [t.numpy() for name, t in stems.items() if name != "vocals"]
    no_vocals = np.sum(others, axis=0)

    sample_rate = separator.samplerate
    _save(vocals, vocals_path, sample_rate)
    _save(no_vocals, no_vocals_path, sample_rate)

    return Stems(
        vocals=vocals_path,
        no_vocals=no_vocals_path,
        sample_rate=sample_rate,
        duration_sec=vocals.shape[-1] / sample_rate,
        model=model,
        song_fingerprint=song_fp,
    )
