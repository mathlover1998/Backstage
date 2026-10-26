"""Smoke test moi truong: import duoc het? thay output device nao?

Chay: uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import sys


def check(label: str, fn) -> bool:
    try:
        print(f"  {label:22} {fn()}")
        return True
    except Exception as e:
        print(f"  {label:22} FAIL -> {type(e).__name__}: {e}")
        return False


def main() -> int:
    print(f"python  {sys.version.split()[0]}  ({sys.executable})")
    ok = []

    print("\n-- core --")

    def _torch():
        import torch

        return f"{torch.__version__}  threads={torch.get_num_threads()}  cuda={torch.cuda.is_available()}"

    def _sphn():
        # demucs 4.1.0 dung sphn (khong phai torchaudio) de doc/ghi audio
        import sphn

        return getattr(sphn, "__version__", "ok")

    def _demucs():
        import demucs
        import demucs.pretrained

        return f"{demucs.__version__} (model chua tai)"

    def _librosa():
        import librosa

        return librosa.__version__

    def _numpy():
        import numpy

        return numpy.__version__

    def _soundfile():
        import soundfile

        return f"{soundfile.__version__} libsndfile={soundfile.__libsndfile_version__}"

    def _sounddevice():
        import sounddevice

        return sounddevice.__version__

    def _ffmpeg():
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_version()

    def _pyside():
        import PySide6

        return PySide6.__version__

    for label, fn in [
        ("torch", _torch),
        ("sphn", _sphn),
        ("demucs", _demucs),
        ("librosa", _librosa),
        ("numpy", _numpy),
        ("soundfile", _soundfile),
        ("sounddevice", _sounddevice),
        ("ffmpeg", _ffmpeg),
        ("PySide6", _pyside),
    ]:
        ok.append(check(label, fn))

    # Phan quan trong nhat cho Phuong an A: co chon duoc output device khong,
    # va co device nao >= 2 kenh de chia L/R khong.
    print("\n-- output devices --")
    try:
        import sounddevice as sd

        default_out = sd.default.device[1]
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] < 1:
                continue
            mark = " <- default" if i == default_out else ""
            api = sd.query_hostapis(d["hostapi"])["name"]
            print(f"  [{i:2}] {d['max_output_channels']}ch  {d['name']}  ({api}){mark}")
    except Exception as e:
        print(f"  FAIL -> {type(e).__name__}: {e}")
        ok.append(False)

    print(f"\n{sum(ok)}/{len(ok)} ok")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
