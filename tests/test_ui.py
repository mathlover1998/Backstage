"""Test cua so dung duoc va trang thai nut dung, khong can man hinh.

Chay voi QT_QPA_PLATFORM=offscreen (set trong conftest.py) nen chay duoc ca
tren CI runner khong co display. Khong test phat am thanh - viec do can thiet
bi that.
"""

from PySide6.QtWidgets import QApplication

from backstage.ui.app import MainWindow, SeparateWorker


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_window_builds():
    _app()
    w = MainWindow()
    assert w.windowTitle() == "Backstage"


def test_buttons_start_disabled_until_a_song_is_picked():
    _app()
    w = MainWindow()

    # Chua chon bai -> khong tach, khong phat duoc
    assert not w._separate_btn.isEnabled()
    assert not w._play_btn.isEnabled()
    assert not w._stop_btn.isEnabled()
    # ...nhung van chon duoc file
    assert w._pick_btn.isEnabled()


def test_device_box_always_has_a_default_entry():
    _app()
    w = MainWindow()
    assert w._device_box.count() >= 1
    assert w._device_box.itemData(0) is None  # "(mac dinh he thong)"


def test_guide_slider_starts_at_full_and_updates_its_label():
    _app()
    w = MainWindow()
    assert w._guide_slider.value() == 100
    assert "100%" in w._guide_label.text()

    w._guide_slider.setValue(40)
    assert "40%" in w._guide_label.text()

    # Khong dang phat thi keo slider khong duoc no ra loi
    w._guide_slider.setValue(0)
    assert "0%" in w._guide_label.text()


def test_demucs_progress_mapping():
    """Callback cua Demucs -> phan tram. Guard phai chan duoc dict thieu field."""
    worker = SeparateWorker(song=None)  # khong chay, chi goi ham mapping
    seen: list[float] = []
    worker.progress.connect(seen.append)

    worker._on_demucs_progress({})  # thieu het -> bo qua
    worker._on_demucs_progress({"audio_length": 0})  # chia 0 -> bo qua
    assert seen == []

    worker._on_demucs_progress(
        {"audio_length": 100, "models": 1, "model_idx_in_bag": 0, "segment_offset": 50}
    )
    assert seen == [0.5]

    # 2 model trong bag, dang o model thu 2, nua duong -> 0.75
    worker._on_demucs_progress(
        {"audio_length": 100, "models": 2, "model_idx_in_bag": 1, "segment_offset": 50}
    )
    assert seen[-1] == 0.75

    # Khong bao gio vuot 1.0
    worker._on_demucs_progress(
        {"audio_length": 100, "models": 1, "model_idx_in_bag": 0, "segment_offset": 999}
    )
    assert seen[-1] == 1.0
