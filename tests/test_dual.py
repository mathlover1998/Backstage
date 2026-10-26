"""Test phan mix cua player ma khong can thiet bi audio.

`mix_block` co y la ham thuan tuy va `sounddevice` chi duoc import ben trong
DualPlayer.__init__ - nho vay logic mix test duoc tren CI runner (khong co
thiet bi audio nao).
"""

import numpy as np
import pytest
import soundfile as sf

from msa.engine.separate import Stems
from msa.player.dual import load_stems_mono, mix_block


def _ramp(n: int) -> np.ndarray:
    return np.linspace(-0.5, 0.5, n, dtype=np.float32)


def test_layout_and_cancellation_at_constant_gain():
    beat = _ramp(256)
    vocal = np.full(256, 0.25, dtype=np.float32)

    out = mix_block(beat, vocal, 0.4, 0.4)

    assert out.shape == (256, 2)
    assert out.dtype == np.float32
    assert out[:, 1] == pytest.approx(beat)
    assert out[:, 0] - out[:, 1] == pytest.approx(vocal * 0.4, abs=1e-6)


def test_gain_ramp_is_linear_across_the_block():
    """Doi gain phai ramp trong long block, khong nhay bac - nhay bac tao click."""
    n = 101
    beat = np.zeros(n, dtype=np.float32)
    vocal = np.ones(n, dtype=np.float32)

    out = mix_block(beat, vocal, 0.0, 1.0)

    guide = out[:, 0]
    assert guide[0] == pytest.approx(0.0)
    assert guide[-1] == pytest.approx(1.0)
    assert guide[n // 2] == pytest.approx(0.5, abs=1e-3)
    # tuyen tinh => sai phan deu nhau
    assert np.diff(guide) == pytest.approx(np.full(n - 1, 1.0 / (n - 1)), abs=1e-6)


def test_beat_channel_is_untouched_by_gain_ramp():
    """Keo slider guide khong duoc lam loa ngoai thay doi."""
    beat = _ramp(64)
    vocal = np.ones(64, dtype=np.float32)

    flat = mix_block(beat, vocal, 0.3, 0.3)
    ramped = mix_block(beat, vocal, 0.0, 1.0)

    assert flat[:, 1] == pytest.approx(beat)
    assert ramped[:, 1] == pytest.approx(beat)


def test_load_stems_mono_downmixes_and_returns_rate(tmp_path):
    sr = 8000
    vocal_stereo = np.stack([np.full(100, 0.2), np.full(100, 0.4)], axis=1).astype(np.float32)
    beat_stereo = np.stack([np.full(100, -0.1), np.full(100, 0.3)], axis=1).astype(np.float32)

    v, nv = tmp_path / "vocals.wav", tmp_path / "no_vocals.wav"
    sf.write(v, vocal_stereo, sr, subtype="FLOAT")
    sf.write(nv, beat_stereo, sr, subtype="FLOAT")
    stems = Stems(
        vocals=v,
        no_vocals=nv,
        sample_rate=sr,
        duration_sec=100 / sr,
        model="t",
        song_fingerprint="f",
    )

    beat, vocal, read_sr = load_stems_mono(stems)

    assert read_sr == sr
    assert beat == pytest.approx(np.full(100, 0.1), abs=1e-6)
    assert vocal == pytest.approx(np.full(100, 0.3), abs=1e-6)
