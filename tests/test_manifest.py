from backstage.manifest import (
    Alignment,
    AlignMethod,
    BeatInfo,
    BeatSource,
    Manifest,
    Quality,
    Render,
    SongInfo,
)


def _sample() -> Manifest:
    return Manifest(
        song=SongInfo(
            fingerprint="aaa", path="x.mp3", duration_sec=241.3, sample_rate=44100, title="Thu"
        ),
        beat=BeatInfo(fingerprint="bbb", path="b.wav", source=BeatSource.UGC, duration_sec=239.8),
        alignment=Alignment(
            method=AlignMethod.DTW,
            offset_ms=-120.5,
            semitones=-2,
            warp_path=[(0.0, 0.1), (1.0, 1.08)],
        ),
        quality=Quality(auto_score=81.5, dtw_cost=0.31, vocal_bleed_db=-28.4),
        render=Render(path="r.wav", sample_rate=48000),
    )


def test_round_trip(tmp_path):
    p = tmp_path / "manifest.json"
    _sample().save(p)
    r = Manifest.load(p)

    assert r.beat.source is BeatSource.UGC
    assert r.alignment.method is AlignMethod.DTW
    assert r.alignment.offset_ms == -120.5
    assert r.alignment.semitones == -2
    # warp_path phai ve lai dung tuple, khong phai list (json khong phan biet)
    assert r.alignment.warp_path == [(0.0, 0.1), (1.0, 1.08)]
    assert r.quality.auto_score == 81.5
    assert r.render is not None
    assert r.render.layout == "L=guide,R=beat"


def test_identity_alignment_has_no_warp_path(tmp_path):
    """Option 1: tach tu chinh ban goc -> khong can warp."""
    m = _sample()
    m.alignment = Alignment(method=AlignMethod.IDENTITY)
    m.beat.source = BeatSource.AI_SEPARATED
    p = tmp_path / "manifest.json"
    m.save(p)

    r = Manifest.load(p)
    assert r.alignment.warp_path is None
    assert r.alignment.offset_ms == 0.0
    assert r.beat.source is BeatSource.AI_SEPARATED


def test_schema_version_mismatch_is_rejected(tmp_path):
    import json

    import pytest

    p = tmp_path / "manifest.json"
    _sample().save(p)
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw["schema_version"] = 999
    p.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="schema"):
        Manifest.load(p)
