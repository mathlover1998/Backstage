"""CLI chay end-to-end Option 1.

backstage ui                           mo cua so (chon file, slider guide gain)
backstage devices                      liet ke output device
backstage prepare <bai.mp3>            tach + render + ghi manifest
backstage play <bai.mp3> --guide 0.7   phat: L = guide, R = beat
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from backstage import paths
from backstage.manifest import (
    Alignment,
    AlignMethod,
    BeatInfo,
    BeatSource,
    Manifest,
    Render,
    SongInfo,
)

RENDER_NAME = "render.wav"


def _fmt_time(sec: float) -> str:
    return f"{int(sec) // 60}:{int(sec) % 60:02d}"


def _prepare(args: argparse.Namespace) -> int:
    from backstage.engine import render as render_mod
    from backstage.engine import separate as separate_mod

    song = Path(args.song)
    print(f"bai   : {song.name}")
    print(f"model : {args.model}  (CPU - mot bai 4 phut mat khoang 2-4 phut)")

    t0 = time.monotonic()
    stems = separate_mod.separate(
        song, model=args.model, jobs=args.jobs, force=args.force, progress=True
    )
    took = time.monotonic() - t0
    cached = took < 1.0 and not args.force
    print(f"stems : {stems.cached_dir}{'  (dung cache)' if cached else f'  ({took:.0f}s)'}")

    # Option 1: beat la chinh no_vocals vua tach ra -> align la identity.
    beat_fp = paths.file_fingerprint(stems.no_vocals)
    pair = paths.pair_dir(stems.song_fingerprint, beat_fp)
    result = render_mod.render(stems, pair / RENDER_NAME, guide_gain=args.guide)

    print(f"render: {result.path}")
    print(
        f"        peak guide {result.peak_guide:.3f} / beat {result.peak_beat:.3f}"
        + (
            f"  (da ha {result.applied_gain:.3f} de khong clip)"
            if result.applied_gain < 1.0
            else ""
        )
    )

    manifest = Manifest(
        song=SongInfo(
            fingerprint=stems.song_fingerprint,
            path=str(song),
            duration_sec=stems.duration_sec,
            sample_rate=stems.sample_rate,
            title=song.stem,
        ),
        beat=BeatInfo(
            fingerprint=beat_fp,
            path=str(stems.no_vocals),
            source=BeatSource.AI_SEPARATED,
            duration_sec=stems.duration_sec,
        ),
        # Tach tu cung mot file nguon -> sample-aligned san, khong co gi de warp.
        alignment=Alignment(method=AlignMethod.IDENTITY),
        render=Render(
            path=str(result.path),
            sample_rate=result.sample_rate,
            guide_gain=args.guide,
        ),
    )
    manifest_path = paths.manifest_path(stems.song_fingerprint, beat_fp)
    manifest.save(manifest_path)
    print(f"manifest: {manifest_path}")
    return 0


def _play(args: argparse.Namespace) -> int:
    from backstage.engine import separate as separate_mod
    from backstage.player.device import resolve_device
    from backstage.player.dual import DualPlayer

    song = Path(args.song)
    stems = separate_mod.separate(song, model=args.model, progress=True)

    try:
        device = resolve_device(args.device)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2

    player = DualPlayer.from_stems(
        stems, device=device, blocksize=args.blocksize, guide_gain=args.guide
    )
    print(f"L = beat + vocal x {args.guide:.2f}   -> tai nghe")
    print("R = beat                      -> loa ngoai")
    print(f"{_fmt_time(player.duration_sec)} | Ctrl+C de dung\n")

    try:
        with player:
            while not player.finished:
                print(
                    f"\r  {_fmt_time(player.position_sec)} / {_fmt_time(player.duration_sec)}",
                    end="",
                    flush=True,
                )
                player.wait(0.25)
    except KeyboardInterrupt:
        print("\ndung.")
        return 130
    print("\nxong.")
    return 0


def _devices(_args: argparse.Namespace) -> int:
    from backstage.player.device import list_output_devices

    for d in list_output_devices():
        print(d)
    return 0


def _ui(_args: argparse.Namespace) -> int:
    from backstage.ui.app import run

    return run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="backstage",
        description=__doc__,
        # Khong co dong nay thi argparse bop newline cua docstring thanh mot cuc.
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ui = sub.add_parser("ui", help="mo cua so")
    p_ui.set_defaults(func=_ui)

    p_dev = sub.add_parser("devices", help="liet ke output device")
    p_dev.set_defaults(func=_devices)

    for name, help_text, func in [
        ("prepare", "tach + render + ghi manifest", _prepare),
        ("play", "phat truc tiep tu stems", _play),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("song", help="file nhac goc (mp3/wav/flac/m4a)")
        p.add_argument("--model", default="htdemucs", help="model Demucs (default: htdemucs)")
        p.add_argument(
            "--guide",
            type=float,
            default=1.0,
            help="muc giong guide trong tai nghe, 0.0-1.0 (default: 1.0)",
        )
        p.set_defaults(func=func)

    p_prep = sub.choices["prepare"]
    p_prep.add_argument("--jobs", type=int, default=0, help="so worker cho Demucs")
    p_prep.add_argument("--force", action="store_true", help="tach lai du da co cache")

    p_play = sub.choices["play"]
    p_play.add_argument("--device", default=None, help="index hoac mot phan ten output device")
    p_play.add_argument("--blocksize", type=int, default=1024)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
