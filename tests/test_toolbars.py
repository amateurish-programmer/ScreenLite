from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog


def test_screenshot_toolbar_copies_and_requests_details(qtbot, tmp_path):
    from screenlite.ui.toolbars import ScreenshotToolbar
    bar = ScreenshotToolbar(Image.new('RGB', (160, 90), 'teal'), tmp_path)
    qtbot.addWidget(bar)
    bar.show()
    bar.auto_copy()
    assert QApplication.clipboard().image().size().width() == 160
    with qtbot.waitSignal(bar.edit_requested):
        qtbot.mouseClick(bar.details_button, Qt.MouseButton.LeftButton)
    assert bar.result() == QDialog.DialogCode.Accepted
    bar.show()
    with qtbot.waitSignal(bar.closed):
        bar.close()


def test_recording_toolbar_stop_and_timer(qtbot):
    from screenlite.ui.toolbars import RecordingToolbar
    bar = RecordingToolbar()
    qtbot.addWidget(bar)
    bar.set_seconds(3661)
    assert '01:01:01' in bar.timer_label.text()
    with qtbot.waitSignal(bar.stop_requested):
        qtbot.mouseClick(bar.stop_button, Qt.MouseButton.LeftButton)


def test_toolbar_close_waits_for_save(qtbot, tmp_path):
    from screenlite.ui.toolbars import ScreenshotToolbar
    bar = ScreenshotToolbar(Image.new('RGB', (400, 240), 'navy'), tmp_path)
    qtbot.addWidget(bar)
    bar.show()
    target = tmp_path / 'saved.png'
    bar.start_export(target)
    bar.reject()
    assert bar.isVisible()
    qtbot.waitUntil(lambda: bar._worker is None, timeout=10000)
    assert not bar.isVisible()
    with Image.open(target) as saved:
        assert saved.size == (400, 240)


def test_failed_save_cancels_pending_close_and_retains_image(qtbot, tmp_path):
    from screenlite.ui.toolbars import ScreenshotToolbar
    bar = ScreenshotToolbar(Image.new('RGB', (120, 80), 'navy'), tmp_path)
    qtbot.addWidget(bar)
    bar.show()
    target = tmp_path / 'existing.png'
    target.write_bytes(b'existing file')
    bar.start_export(target)
    bar.reject()
    qtbot.waitUntil(lambda: bar._worker is None, timeout=10000)
    assert bar.isVisible()
    assert '失败' in bar.status_label.text()
    assert target.read_bytes() == b'existing file'
    assert bar.image.size == (120, 80)
    assert bar.save_button.isEnabled()
