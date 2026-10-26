"""Render ra file stereo mot kenh guide / mot kenh beat (Phuong an A).

    L = beat + vocal * guide_gain   -> tai nghe
    R = beat                        -> loa ngoai

Hai kenh nam trong CUNG mot buffer, cung mot clock, nen lech bang 0 tuyet doi -
khong phai canh sync o runtime. Doi lai: moi ben la mono.

Dung file nay khi can mot artifact mang di dau cung duoc (cam jack chia doi vao
may nao cung chay). Khi phat tu trong app thi player mix truc tiep tu stems
(xem msa.player.dual) de nguoi hat van keo duoc slider guide gain luc dang hat -
bake gain vao file thi mat kha nang do.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from msa.engine.separate import Stems

# 24-bit cho file cuoi: du dong cho moi muc dich thuc te, va tranh WAV float
# ma mot so may phat/loa di dong khong doc duoc.
_RENDER_SUBTYPE = "PCM_24"


@dataclass
class RenderResult:
    path: Path
    sample_rate: int
    duration_sec: float
    peak_guide: float
    peak_beat: float
    # He so phai nhan vao CA HAI kenh de khong clip. 1.0 = khong phai ha gi.
    applied_gain: float


def to_mono(audio: np.ndarray) -> np.ndarray:
    """(frames, channels) hoac (frames,) -> (frames,) float32."""
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 1:
        return audio
    return audio.mean(axis=1, dtype=np.float32)


def build_dual_mono(
    beat: np.ndarray, vocal: np.ndarray, guide_gain: float = 1.0
) -> tuple[np.ndarray, float]:
    """beat/vocal mono cung do dai -> (stereo (frames, 2), applied_gain).

    Kenh 0 = guide, kenh 1 = beat. Neu dinh vuot 1.0 thi ha CA HAI kenh cung
    mot he so: ha rieng tung kenh se lam can bang beat ma nguoi hat nghe trong
    tai khac voi can bang khan gia nghe tu loa.
    """
    if beat.shape != vocal.shape:
        raise ValueError(f"beat {beat.shape} va vocal {vocal.shape} khong cung do dai")

    guide = beat + vocal * np.float32(guide_gain)

    peak = float(max(np.abs(guide).max(initial=0.0), np.abs(beat).max(initial=0.0)))
    applied_gain = 1.0
    if peak > 1.0:
        applied_gain = 1.0 / peak
        guide = guide * np.float32(applied_gain)
        beat = beat * np.float32(applied_gain)

    out = np.empty((beat.shape[0], 2), dtype=np.float32)
    out[:, 0] = guide
    out[:, 1] = beat
    return out, applied_gain


def render(
    stems: Stems,
    out_path: Path,
    *,
    guide_gain: float = 1.0,
) -> RenderResult:
    """Doc stems tu dia, render file stereo guide/beat."""
    vocal_raw, sr_v = sf.read(stems.vocals, dtype="float32", always_2d=True)
    beat_raw, sr_b = sf.read(stems.no_vocals, dtype="float32", always_2d=True)

    if sr_v != sr_b:
        raise ValueError(f"sample rate lech nhau: vocals {sr_v} vs no_vocals {sr_b}")

    vocal = to_mono(vocal_raw)
    beat = to_mono(beat_raw)

    # Hai stem tu cung mot lan tach nen phai bang nhau. Lech o day la dau hieu
    # cache bi hong, khong phai chuyen de im lang cat bot cho bang.
    if vocal.shape != beat.shape:
        raise ValueError(
            f"stems lech do dai ({vocal.shape[0]} vs {beat.shape[0]} frames) - "
            f"cache co the da hong, thu tach lai voi force=True"
        )

    stereo, applied_gain = build_dual_mono(beat, vocal, guide_gain)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out_path, stereo, sr_v, subtype=_RENDER_SUBTYPE)

    return RenderResult(
        path=out_path,
        sample_rate=sr_v,
        duration_sec=stereo.shape[0] / sr_v,
        peak_guide=float(np.abs(stereo[:, 0]).max(initial=0.0)),
        peak_beat=float(np.abs(stereo[:, 1]).max(initial=0.0)),
        applied_gain=applied_gain,
    )
