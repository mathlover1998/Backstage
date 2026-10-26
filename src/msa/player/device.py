"""Chon output device.

Tach rieng khoi dual.py vi `msa devices` phai chay duoc ma khong keo theo gi,
va vi buoc chon device la noi de sai nhat khi cam jack chia doi / DAC roi.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutputDevice:
    index: int
    name: str
    channels: int
    hostapi: str
    is_default: bool

    def __str__(self) -> str:
        mark = " <- default" if self.is_default else ""
        return f"[{self.index:2}] {self.channels}ch  {self.name}  ({self.hostapi}){mark}"


def list_output_devices() -> list[OutputDevice]:
    import sounddevice as sd

    default_out = sd.default.device[1]
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] < 1:
            continue
        out.append(
            OutputDevice(
                index=i,
                name=d["name"],
                channels=d["max_output_channels"],
                hostapi=sd.query_hostapis(d["hostapi"])["name"],
                is_default=(i == default_out),
            )
        )
    return out


def resolve_device(spec: str | int | None) -> int | None:
    """None -> device mac dinh. So -> dung lam index. Chu -> khop ten khong phan biet hoa.

    Khop ten mo ho thi bao loi kem danh sach ung vien, thay vi im lang chon cai
    dau tien - phat sai loa giua luc dang hat la kieu loi khong the sua nhanh.
    """
    if spec is None:
        return None
    if isinstance(spec, int):
        return spec
    if isinstance(spec, str) and spec.strip().lstrip("-").isdigit():
        return int(spec)

    needle = str(spec).casefold()
    devices = list_output_devices()
    matches = [d for d in devices if needle in d.name.casefold()]

    if not matches:
        raise ValueError(
            f"khong co output device nao khop {spec!r}. Dang co:\n"
            + "\n".join(f"  {d}" for d in devices)
        )
    if len(matches) > 1:
        raise ValueError(
            f"{spec!r} khop {len(matches)} device, can cu the hon:\n"
            + "\n".join(f"  {d}" for d in matches)
        )
    return matches[0].index
