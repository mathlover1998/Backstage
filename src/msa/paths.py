"""Cache layout. Moi thu key theo fingerprint, khong theo ten file.

cache/
  songs/<song_fp>/           vocals.wav, no_vocals.wav   (ket qua Demucs, tach 1 lan)
  pairs/<song_fp>__<beat_fp>/ manifest.json, render.wav
"""

from __future__ import annotations

import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / "cache"


def song_dir(song_fp: str) -> Path:
    return CACHE_DIR / "songs" / song_fp


def pair_dir(song_fp: str, beat_fp: str) -> Path:
    return CACHE_DIR / "pairs" / f"{song_fp}__{beat_fp}"


def manifest_path(song_fp: str, beat_fp: str) -> Path:
    return pair_dir(song_fp, beat_fp) / "manifest.json"


def file_fingerprint(path: Path, chunk: int = 1 << 20) -> str:
    """Fingerprint theo noi dung file (blake2b, 16 byte hex).

    Du de de-dupe cache. KHONG dung de nhan dang bai hat - viec do can
    acoustic fingerprint tren chroma (xem engine/align.py), vi hai file cung
    mot bai nhung khac bitrate se cho hash khac nhau.
    """
    h = hashlib.blake2b(digest_size=16)
    with path.open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()
