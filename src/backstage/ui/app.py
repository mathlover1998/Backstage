"""Cua so Backstage - cac tinh nang co ban.

Ly do ton tai cua UI nay la SLIDER GUIDE GAIN: nguoi hat ha dan giong guide
trong tai nghe xuong khi tu tin hon, va phai ha duoc ngay luc dang hat. CLI
chi nhan mot gia tri co dinh luc khoi dong nen khong lam duoc viec do.

Tach nhac mat 2-4 phut tren CPU nen BAT BUOC chay o QThread rieng. Moi thu
cham trong file nay deu nam trong SeparateWorker; UI thread khong duoc phep
block du mot giay.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from backstage.engine.separate import DEFAULT_MODEL, Stems, separate
from backstage.player.device import list_output_devices
from backstage.player.dual import DualPlayer, load_stems_mono

AUDIO_FILTER = "Nhac (*.mp3 *.wav *.flac *.m4a *.ogg *.aac);;Tat ca (*.*)"


def _fmt_time(sec: float) -> str:
    return f"{int(sec) // 60}:{int(sec) % 60:02d}"


class SeparateWorker(QThread):
    """Tach nhac + nap stems vao RAM, tat ca o thread rieng.

    Nap stems o day luon (chu khong de luc bam Phat) de bam Phat la phat ngay:
    doc ~170MB tu dia tren UI thread se lam cua so dong bang vai giay.
    """

    progress = Signal(float)  # 0.0 .. 1.0
    finished_ok = Signal(object, object, object, int)  # stems, beat, vocal, sample_rate
    failed = Signal(str)

    def __init__(self, song: Path, model: str = DEFAULT_MODEL) -> None:
        super().__init__()
        self._song = song
        self._model = model

    def _on_demucs_progress(self, data: dict) -> None:
        # Demucs goi callback nay tren thread dang tach. Chi emit signal - Qt tu
        # dua ve UI thread, khong duoc cham widget truc tiep tu day.
        #
        # Guard tung gia tri thay vi boc try/except: callback nay chay trong
        # long vong lap tach, mot exception o day se lam vo ca viec tach.
        length = data.get("audio_length") or 0
        models = data.get("models") or 1
        if not length or not models:
            return
        idx = data.get("model_idx_in_bag") or 0
        offset = data.get("segment_offset") or 0
        self.progress.emit(min(1.0, (idx + offset / length) / models))

    def run(self) -> None:
        try:
            stems = separate(
                self._song,
                model=self._model,
                progress=False,
                callback=self._on_demucs_progress,
            )
            beat, vocal, sr = load_stems_mono(stems)
        except Exception:  # noqa: BLE001 - bien gioi thread: khong bat thi loi bi mat hut
            self.failed.emit(traceback.format_exc())
            return
        self.progress.emit(1.0)
        self.finished_ok.emit(stems, beat, vocal, sr)


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Backstage")
        self.setMinimumWidth(560)

        self._song: Path | None = None
        self._stems: Stems | None = None
        self._beat: np.ndarray | None = None
        self._vocal: np.ndarray | None = None
        self._sample_rate = 0
        self._player: DualPlayer | None = None
        self._worker: SeparateWorker | None = None

        self._build()
        self._refresh_devices()
        self._sync_enabled()

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # --- dung giao dien ---

    def _build(self) -> None:
        root = QVBoxLayout(self)

        wiring = QLabel(
            "Tai nghe = kenh L  ·  Loa ngoai = kenh R\n"
            "Cam jack chia doi: mot nhanh vao tai nghe, nhanh kia vao loa."
        )
        wiring.setStyleSheet("color: palette(mid);")
        root.addWidget(wiring)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(line)

        form = QFormLayout()

        pick_row = QHBoxLayout()
        self._song_label = QLabel("chua chon bai nao")
        self._song_label.setWordWrap(True)
        self._pick_btn = QPushButton("Chon file...")
        self._pick_btn.clicked.connect(self._pick_song)
        pick_row.addWidget(self._song_label, 1)
        pick_row.addWidget(self._pick_btn)
        form.addRow("Bai hat", pick_row)

        dev_row = QHBoxLayout()
        self._device_box = QComboBox()
        refresh = QPushButton("Lam moi")
        refresh.clicked.connect(self._refresh_devices)
        dev_row.addWidget(self._device_box, 1)
        dev_row.addWidget(refresh)
        form.addRow("Output", dev_row)

        root.addLayout(form)

        self._separate_btn = QPushButton("Tach nhac")
        self._separate_btn.clicked.connect(self._start_separate)
        root.addWidget(self._separate_btn)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        play_row = QHBoxLayout()
        self._play_btn = QPushButton("Phat")
        self._play_btn.clicked.connect(self._start_play)
        self._stop_btn = QPushButton("Dung")
        self._stop_btn.clicked.connect(self._stop_play)
        play_row.addWidget(self._play_btn)
        play_row.addWidget(self._stop_btn)
        root.addLayout(play_row)

        self._pos_label = QLabel("0:00 / 0:00")
        self._pos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._pos_label)

        # --- slider guide gain: ly do ton tai cua cua so nay ---
        guide_box = QVBoxLayout()
        self._guide_label = QLabel("Giong guide trong tai nghe: 100%")
        self._guide_slider = QSlider(Qt.Orientation.Horizontal)
        self._guide_slider.setRange(0, 100)
        self._guide_slider.setValue(100)
        self._guide_slider.valueChanged.connect(self._on_guide_changed)
        hint = QLabel("Keo xuong 0% khi da tu tin - luc dang hat cung keo duoc.")
        hint.setStyleSheet("color: palette(mid);")
        guide_box.addWidget(self._guide_label)
        guide_box.addWidget(self._guide_slider)
        guide_box.addWidget(hint)
        root.addLayout(guide_box)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

    # --- trang thai ---

    def _sync_enabled(self) -> None:
        busy = self._worker is not None and self._worker.isRunning()
        playing = self._player is not None and not self._player.finished

        self._pick_btn.setEnabled(not busy and not playing)
        self._separate_btn.setEnabled(self._song is not None and not busy and not playing)
        self._play_btn.setEnabled(self._beat is not None and not busy and not playing)
        self._stop_btn.setEnabled(playing)
        self._device_box.setEnabled(not playing)

    def _set_status(self, text: str) -> None:
        self._status.setText(text)

    # --- chon file / device ---

    def _pick_song(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chon bai hat", "", AUDIO_FILTER)
        if not path:
            return
        self._song = Path(path)
        self._song_label.setText(self._song.name)
        # Doi bai thi stems cu khong con dung nua.
        self._stems = self._beat = self._vocal = None
        self._progress.setVisible(False)
        self._set_status("Bam 'Tach nhac'. Lan dau mot bai 4 phut mat 2-4 phut tren CPU.")
        self._sync_enabled()

    def _refresh_devices(self) -> None:
        current = self._device_box.currentData()
        self._device_box.clear()
        self._device_box.addItem("(mac dinh he thong)", None)
        try:
            for d in list_output_devices():
                self._device_box.addItem(f"{d.name} - {d.channels}ch ({d.hostapi})", d.index)
        except Exception as e:  # noqa: BLE001 - khong co thiet bi van phai mo duoc cua so
            self._set_status(f"Khong doc duoc danh sach thiet bi: {e}")
            return
        if current is not None:
            i = self._device_box.findData(current)
            if i >= 0:
                self._device_box.setCurrentIndex(i)

    # --- tach nhac ---

    def _start_separate(self) -> None:
        if self._song is None:
            return
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._set_status(f"Dang tach {self._song.name}...")

        self._worker = SeparateWorker(self._song)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_separated)
        self._worker.failed.connect(self._on_separate_failed)
        self._worker.finished.connect(self._sync_enabled)
        self._worker.start()
        self._sync_enabled()

    def _on_progress(self, fraction: float) -> None:
        self._progress.setValue(int(fraction * 100))

    def _on_separated(self, stems, beat, vocal, sample_rate: int) -> None:
        self._stems = stems
        self._beat = beat
        self._vocal = vocal
        self._sample_rate = sample_rate
        self._set_status(
            f"Xong - {_fmt_time(len(beat) / sample_rate)} @ {sample_rate} Hz. Bam 'Phat'."
        )
        self._sync_enabled()

    def _on_separate_failed(self, tb: str) -> None:
        self._progress.setVisible(False)
        self._set_status(f"Tach that bai:\n{tb.strip().splitlines()[-1]}")
        print(tb, file=sys.stderr)
        self._sync_enabled()

    # --- phat ---

    def _start_play(self) -> None:
        if self._beat is None or self._vocal is None:
            return
        gain = self._guide_slider.value() / 100.0
        try:
            self._player = DualPlayer(
                self._beat,
                self._vocal,
                self._sample_rate,
                device=self._device_box.currentData(),
                guide_gain=gain,
            )
            self._player.start()
        except Exception as e:  # noqa: BLE001 - thiet bi co the dang bi chiem
            self._player = None
            self._set_status(f"Khong mo duoc output: {e}")
            self._sync_enabled()
            return
        self._set_status("Dang phat. L = tai nghe (co giong), R = loa ngoai (chi beat).")
        self._sync_enabled()

    def _stop_play(self) -> None:
        if self._player is None:
            return
        self._player.stop()
        self._player.close()
        self._player = None
        self._set_status("Da dung.")
        self._sync_enabled()

    # --- slider ---

    def _on_guide_changed(self, value: int) -> None:
        self._guide_label.setText(f"Giong guide trong tai nghe: {value}%")
        if self._player is not None:
            # Doi duoc giua luc dang phat; dual.py ramp trong long block nen
            # khong co tieng click.
            self._player.set_guide_gain(value / 100.0)

    # --- nhip 100ms ---

    def _tick(self) -> None:
        if self._player is None:
            return
        pos, dur = self._player.position_sec, self._player.duration_sec
        self._pos_label.setText(f"{_fmt_time(pos)} / {_fmt_time(dur)}")
        if self._player.finished:
            self._player.close()
            self._player = None
            self._set_status("Het bai.")
            self._sync_enabled()

    # --- dong cua so ---

    def closeEvent(self, event) -> None:  # ten do Qt quy dinh, khong doi duoc
        if self._player is not None:
            self._player.stop()
            self._player.close()
            self._player = None
        if self._worker is not None and self._worker.isRunning():
            # Demucs khong co diem huy giua chung; cho no xong de khong bo lai
            # file stems viet do dang trong cache.
            self._set_status("Dang doi buoc tach ket thuc...")
            self._worker.wait()
        event.accept()


def run() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
