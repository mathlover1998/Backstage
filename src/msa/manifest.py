"""Artifact contract.

Day la hop dong trung tam cua ca du an. Engine chi sinh ra manifest; player chi
doc manifest. Nho vay khi len mobile, app chi can phan player va engine day len
server ma khong phai viet lai gi.

Moi cap (bai goc, beat) -> mot manifest.json trong cache/.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

SCHEMA_VERSION = 1


class BeatSource(str, Enum):
    """Beat den tu dau. Quyet dinh alignment co can lam gi khong."""

    AI_SEPARATED = "ai_separated"  # Option 1: tach tu chinh ban goc -> align mien phi
    LIBRARY = "library"  # Option 2a: beat co san trong thu vien
    UGC = "ugc"  # Option 2b: beat do nguoi dung cung cap


class AlignMethod(str, Enum):
    IDENTITY = "identity"  # cung nguon file -> sample-aligned san
    DTW = "dtw"  # chroma DTW, dung cho beat khac ban thu


@dataclass
class SongInfo:
    fingerprint: str
    path: str
    duration_sec: float
    sample_rate: int
    title: str | None = None
    artist: str | None = None


@dataclass
class BeatInfo:
    fingerprint: str
    path: str
    source: BeatSource
    duration_sec: float
    uploader: str | None = None


@dataclass
class Alignment:
    """Cach dua vocal cua ban goc len timeline cua beat."""

    method: AlignMethod
    offset_ms: float = 0.0
    semitones: int = 0
    # warp_path: cac cap (t_song_sec, t_beat_sec) tu DTW. None khi method=IDENTITY.
    warp_path: list[tuple[float, float]] | None = None


@dataclass
class Quality:
    """Diem chat luong do tu dong luc import - khong cho rating cua nguoi dung.

    auto_score tong hop tu cac chi so duoi, thang 0..100.
    """

    auto_score: float = 0.0
    dtw_cost: float | None = None  # beat sai bai / sai ban phoi
    warp_slope_var: float | None = None  # tempo troi, choi tay khong deu
    structural_coverage: float | None = None  # thieu verse, lap chorus
    vocal_bleed_db: float | None = None  # file karaoke gia (chi giam vocal)
    spectral_cutoff_hz: float | None = None  # transcode bitrate thap
    clipping_pct: float | None = None
    lufs: float | None = None


@dataclass
class Render:
    """File stereo cuoi cung. Phuong an A: chia kenh L/R.

    L = beat + vocal (guide trong tai nghe)
    R = beat        (ra loa ngoai)

    Hai kenh nam trong cung mot buffer, cung mot clock -> sync chinh xac
    tung sample, khong co gi de lech.
    """

    path: str
    sample_rate: int
    layout: str = "L=guide,R=beat"
    guide_gain: float = 1.0  # slider "muc giong guide" 100% -> 0%


@dataclass
class Manifest:
    song: SongInfo
    beat: BeatInfo
    alignment: Alignment
    quality: Quality = field(default_factory=Quality)
    render: Render | None = None
    schema_version: int = SCHEMA_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> Manifest:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                f"manifest schema {raw.get('schema_version')} != {SCHEMA_VERSION}: {path}"
            )
        align = raw["alignment"]
        warp = align.get("warp_path")
        return cls(
            song=SongInfo(**raw["song"]),
            beat=BeatInfo(**{**raw["beat"], "source": BeatSource(raw["beat"]["source"])}),
            alignment=Alignment(
                method=AlignMethod(align["method"]),
                offset_ms=align["offset_ms"],
                semitones=align["semitones"],
                warp_path=[tuple(p) for p in warp] if warp else None,
            ),
            quality=Quality(**raw.get("quality", {})),
            render=Render(**raw["render"]) if raw.get("render") else None,
            schema_version=raw["schema_version"],
            created_at=raw["created_at"],
        )
