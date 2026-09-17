from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from screenlite.ui.dialogs import ImageDialog, MainWindow, SettingsDialog
from screenlite.ui.selection import SelectionOverlay


def overlay(qtbot):
    screen = QApplication.primaryScreen()
    pixmap = QPixmap(screen.size())
    pixmap.fill(Qt.GlobalColor.white)
    widget = SelectionOverlay(screen, pixmap)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def drag(qtbot, widget, start, end):
    qtbot.mousePress(widget, Qt.MouseButton.LeftButton, pos=QPoint(*start))
    qtbot.mouseMove(widget, QPoint(*end))
    qtbot.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=QPoint(*end))


def test_selection_reverse_drag_keyboard_and_confirm(qtbot):
    widget = overlay(qtbot)
    drag(qtbot, widget, (110, 90), (10, 20))
    assert widget.selection == QRect(10, 20, 100, 70)
    qtbot.keyClick(widget, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    qtbot.keyClick(widget, Qt.Key.Key_Up)
    with qtbot.waitSignal(widget.selected) as signal:
        qtbot.keyClick(widget, Qt.Key.Key_Return)
    assert signal.args == [QRect(20, 19, 100, 70)]


def test_selection_drag_clamps_without_changing_size_and_resizes(qtbot):
    widget = overlay(qtbot)
    drag(qtbot, widget, (30, 30), (150, 130))
    drag(qtbot, widget, (70, 70), (1, 1))
    assert widget.selection == QRect(0, 0, 120, 100)
    drag(qtbot, widget, (120, 100), (160, 150))
    assert widget.selection == QRect(0, 0, 160, 150)


def test_empty_selection_cannot_confirm_and_escape_cancels(qtbot):
    widget = overlay(qtbot)
    emitted = []
    widget.selected.connect(emitted.append)
    qtbot.keyClick(widget, Qt.Key.Key_Return)
    assert emitted == []
    with qtbot.waitSignal(widget.cancelled):
        qtbot.keyClick(widget, Qt.Key.Key_Escape)


def test_native_selection_close_cancels(qtbot):
    widget = overlay(qtbot)
    with qtbot.waitSignal(widget.cancelled):
        widget.close()


def test_image_export_dimensions_preserve_aspect_and_do_not_upscale(qtbot, tmp_path):
    dialog = ImageDialog(Image.new('RGB', (2560, 1600)), tmp_path)
    qtbot.addWidget(dialog)
    dialog.size_combo.setCurrentIndex(1)
    assert dialog.output_size() == (1280, 800)
    dialog.size_combo.setCurrentIndex(2)
    assert dialog.output_size() == (1728, 1080)
    dialog.size_combo.setCurrentIndex(4)
    dialog.width_spin.setValue(500)
    assert dialog.output_size() == (500, 312)


def test_image_copy_uses_selected_size(qtbot, tmp_path):
    dialog = ImageDialog(Image.new('RGB', (200, 100), 'red'), tmp_path)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.size_combo.setCurrentIndex(1)
    dialog.copy_image()
    assert dialog._worker is not None
    qtbot.waitUntil(lambda: dialog._worker is None, timeout=10000)
    image = QApplication.clipboard().image()
    assert (image.width(), image.height()) == (100, 50)


def test_settings_round_trip_keeps_other_values(qtbot):
    settings = {'screenshot_hotkey': 'Ctrl+Alt+A', 'record_hotkey': 'Ctrl+Alt+R',
                'fps': 60, 'preset': 'small', 'output_dir': 'D:/Shots', 'extra': 'keep',
                'copy_after_capture': True, 'countdown': 3, 'record_cursor': True}
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    assert dialog.values() == settings


def test_recording_dashboard_disables_screenshot_and_has_stop_action(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.set_recording(True, 65)
    assert not window.capture_button.isEnabled()
    assert '01:05' in window.record_button.text()
    assert '停止' in window.record_button.text()
    window.set_recording(False)
    assert window.capture_button.isEnabled()


def test_image_background_export_refuses_close_until_finished(qtbot, tmp_path):
    dialog = ImageDialog(Image.new('RGB', (600, 400), 'navy'), tmp_path)
    qtbot.addWidget(dialog)
    dialog.show()
    path = tmp_path / 'saved.jpg'
    dialog.start_export(path)
    dialog.close()
    assert dialog.isVisible()
    qtbot.waitUntil(lambda: dialog._worker is None, timeout=10000)
    assert dialog.output_path == path
    with Image.open(path) as result:
        assert result.size == (600, 400)
        assert result.format == 'JPEG'
    dialog.close()
    assert not dialog.isVisible()


def test_video_export_rejects_input_overwrite_and_handles_missing_input(qtbot, tmp_path):
    from screenlite.ui.dialogs import VideoExportDialog
    source = tmp_path / 'missing.mp4'
    dialog = VideoExportDialog(source, tmp_path)
    qtbot.addWidget(dialog)
    dialog.start_export(source)
    assert dialog.output_path is None
    assert '原文件' in dialog.status_label.text()
    dialog.start_export(tmp_path / 'output.mp4')
    qtbot.waitUntil(lambda: not dialog.is_busy, timeout=10000)
    assert dialog.output_path is None
    assert '失败' in dialog.status_label.text()


def test_settings_rejects_identical_hotkeys(qtbot):
    dialog = SettingsDialog({'screenshot_hotkey': 'Ctrl+Alt+A', 'record_hotkey': 'Ctrl+Alt+A'})
    qtbot.addWidget(dialog)
    dialog.accept()
    assert dialog.result() == 0


def test_custom_width_export_matches_preview(qtbot, tmp_path):
    dialog = ImageDialog(Image.new('RGB', (2560, 1600), 'navy'), tmp_path)
    qtbot.addWidget(dialog)
    dialog.size_combo.setCurrentIndex(4)
    dialog.width_spin.setValue(500)
    path = tmp_path / 'custom.png'
    dialog.start_export(path)
    qtbot.waitUntil(lambda: dialog._worker is None, timeout=10000)
    with Image.open(path) as result:
        assert result.size == (500, 312)
    assert 'B' in dialog.status_label.text()


def test_video_chooser_uses_configured_output_directory(qtbot, tmp_path, monkeypatch):
    from screenlite.ui.dialogs import VideoExportDialog
    dialog = VideoExportDialog(tmp_path / 'input.mp4', tmp_path)
    qtbot.addWidget(dialog)
    output = tmp_path / 'exports'
    dialog.output_directory = output
    defaults = []

    def choose(parent, title, default, filters):
        defaults.append(default)
        return '', ''

    monkeypatch.setattr('screenlite.ui.dialogs.QFileDialog.getSaveFileName', choose)
    dialog.choose_export()
    assert output.is_dir()
    assert defaults == [str(output / 'input_分享.mp4')]


def test_video_result_reports_growth_instead_of_claiming_savings(qtbot, tmp_path):
    from screenlite.ui.dialogs import VideoExportDialog
    source, target = tmp_path / 'input.mp4', tmp_path / 'output.mp4'
    source.write_bytes(b'a' * 100)
    target.write_bytes(b'b' * 200)
    dialog = VideoExportDialog(source, tmp_path)
    qtbot.addWidget(dialog)
    dialog._done(str(target))
    assert '100 B' in dialog.status_label.text()
    assert '200 B' in dialog.status_label.text()
    assert '增大' in dialog.status_label.text()


def test_video_chooser_reports_unusable_directory(qtbot, tmp_path):
    from screenlite.ui.dialogs import VideoExportDialog
    invalid_directory = tmp_path / 'file.txt'
    invalid_directory.write_text('occupied', encoding='utf-8')
    dialog = VideoExportDialog(tmp_path / 'input.mp4', tmp_path)
    qtbot.addWidget(dialog)
    dialog.output_directory = invalid_directory
    dialog.choose_export()
    assert '无法创建' in dialog.status_label.text()


def test_image_extra_sizes_and_locked_height(qtbot, tmp_path):
    dialog = ImageDialog(Image.new('RGB', (2400, 1600)), tmp_path)
    qtbot.addWidget(dialog)
    dialog.size_combo.setCurrentIndex(5)
    assert dialog.output_size() == (1800, 1200)
    dialog.size_combo.setCurrentIndex(6)
    assert dialog.output_size() == (600, 400)
    dialog.size_combo.setCurrentIndex(7)
    assert dialog.output_size() == (1920, 1280)
    dialog.size_combo.setCurrentIndex(4)
    dialog.height_spin.setValue(600)
    assert dialog.output_size() == (900, 600)
    dialog.width_spin.setValue(300)
    assert dialog.output_size() == (300, 200)
    dialog.quality_combo.setCurrentIndex(dialog.quality_combo.findData('lossless'))
    assert dialog.format_combo.currentIndex() == 0


def test_new_settings_controls_round_trip(qtbot):
    settings = {'copy_after_capture': False, 'countdown': 0, 'record_cursor': False}
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    values = dialog.values()
    assert values['copy_after_capture'] is False
    assert values['countdown'] == 0
    assert values['record_cursor'] is False
