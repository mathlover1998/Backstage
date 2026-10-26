import numpy as np
import pytest
import soundfile as sf

from backstage.engine.render import build_dual_mono, render, to_mono
from backstage.engine.separate import Stems


def _tone(freq: float, n: int, sr: int = 44100, amp: float = 0.3) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


# --- to_mono ---


def test_to_mono_averages_channels():
    stereo = np.array([[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]], dtype=np.float32)
    assert to_mono(stereo) == pytest.approx([0.5, 0.5, 0.5])


def test_to_mono_passes_through_mono():
    mono = np.array([0.1, -0.2, 0.3], dtype=np.float32)
    assert to_mono(mono) == pytest.approx(mono)


# --- build_dual_mono ---


def test_channel_layout_is_guide_then_beat():
    beat = _tone(220, 1000)
    vocal = _tone(440, 1000)
    out, _ = build_dual_mono(beat, vocal, guide_gain=1.0)

    assert out.shape == (1000, 2)
    assert out[:, 1] == pytest.approx(beat)  # kenh 1 = beat nguyen ban
    assert out[:, 0] == pytest.approx(beat + vocal)  # kenh 0 = guide


def test_beat_cancels_exactly_between_channels():
    """Loi hua cot loi cua san pham, duoi dang mot phep tru.

    Neu L - R dung bang guide_gain * vocal thi beat o hai kenh la MOT tin hieu
    giong nhau tung mau - khong the lech nhau du mot sample.
    """
    beat = _tone(220, 4096)
    vocal = _tone(440, 4096)

    for gain in (0.0, 0.25, 1.0):
        out, applied = build_dual_mono(beat, vocal, guide_gain=gain)
        assert applied == 1.0
        assert out[:, 0] - out[:, 1] == pytest.approx(vocal * gain, abs=1e-6)


def test_guide_gain_zero_makes_both_channels_identical():
    """guide_gain = 0 la luc nguoi hat da tu tin: tai nghe chi con beat."""
    beat = _tone(220, 512)
    vocal = _tone(440, 512)
    out, _ = build_dual_mono(beat, vocal, guide_gain=0.0)
    assert out[:, 0] == pytest.approx(out[:, 1])


def test_clipping_is_scaled_on_both_channels_equally():
    """Ha rieng tung kenh se lam can bang beat trong tai khac voi ngoai loa."""
    beat = np.full(256, 0.8, dtype=np.float32)
    vocal = np.full(256, 0.8, dtype=np.float32)

    out, applied = build_dual_mono(beat, vocal, guide_gain=1.0)

    assert applied == pytest.approx(1.0 / 1.6)
    assert np.abs(out).max() == pytest.approx(1.0)
    # ty le guide/beat giu nguyen sau khi ha
    assert out[:, 0] / out[:, 1] == pytest.approx(1.6 / 0.8)


def test_length_mismatch_is_rejected():
    with pytest.raises(ValueError, match="khong cung do dai"):
        build_dual_mono(np.zeros(10, dtype=np.float32), np.zeros(11, dtype=np.float32))


# --- render (doc/ghi dia) ---


def _write_stems(tmp_path, beat: np.ndarray, vocal: np.ndarray, sr: int = 44100) -> Stems:
    v, nv = tmp_path / "vocals.wav", tmp_path / "no_vocals.wav"
    sf.write(v, vocal, sr, subtype="FLOAT")
    sf.write(nv, beat, sr, subtype="FLOAT")
    return Stems(
        vocals=v,
        no_vocals=nv,
        sample_rate=sr,
        duration_sec=len(beat) / sr,
        model="test",
        song_fingerprint="fp",
    )


def test_render_round_trip_preserves_cancellation(tmp_path):
    sr = 44100
    beat = _tone(220, sr, sr)
    vocal = _tone(440, sr, sr)
    stems = _write_stems(tmp_path, beat, vocal, sr)

    result = render(stems, tmp_path / "render.wav", guide_gain=0.5)

    assert result.sample_rate == sr
    assert result.duration_sec == pytest.approx(1.0)
    assert result.applied_gain == 1.0

    data, read_sr = sf.read(result.path, dtype="float32", always_2d=True)
    assert read_sr == sr
    assert data.shape == (sr, 2)
    # File ghi PCM_24 nen co sai so luong tu hoa ~1/2^23
    assert data[:, 0] - data[:, 1] == pytest.approx(vocal * 0.5, abs=1e-6)


def test_render_rejects_mismatched_stem_lengths(tmp_path):
    stems = _write_stems(
        tmp_path, np.zeros(1000, dtype=np.float32), np.zeros(999, dtype=np.float32)
    )
    with pytest.raises(ValueError, match="lech do dai"):
        render(stems, tmp_path / "render.wav")


def test_render_rejects_mismatched_sample_rates(tmp_path):
    v, nv = tmp_path / "vocals.wav", tmp_path / "no_vocals.wav"
    sf.write(v, np.zeros(1000, dtype=np.float32), 44100, subtype="FLOAT")
    sf.write(nv, np.zeros(1000, dtype=np.float32), 48000, subtype="FLOAT")
    stems = Stems(
        vocals=v, no_vocals=nv, sample_rate=44100, duration_sec=1.0, model="t", song_fingerprint="f"
    )
    with pytest.raises(ValueError, match="sample rate lech"):
        render(stems, tmp_path / "render.wav")
