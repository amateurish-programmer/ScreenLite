from screenlite.app import Controller
from screenlite.geometry import Rect


def test_controller_starts_idle_and_hides_to_tray(qtbot, qapp, tmp_path):
    controller = Controller(qapp, tmp_path, enable_hotkeys=False)
    qtbot.addWidget(controller.window)
    assert controller.state == 'idle'
    controller.show_window()
    assert controller.window.isVisible()
    controller.window.close()
    assert not controller.window.isVisible()
    controller.shutdown()


def test_countdown_can_be_cancelled_without_creating_recording(qtbot, qapp, tmp_path):
    controller = Controller(qapp, tmp_path, enable_hotkeys=False)
    qtbot.addWidget(controller.window)
    controller.arm_recording(Rect(0, 0, 320, 240))
    assert controller.state == 'countdown'
    controller.toggle_record()
    assert controller.state == 'idle'
    assert controller.record_job is None
    assert not list(tmp_path.rglob('*.mkv'))
    controller.shutdown()


def test_record_stop_updates_state_and_preserves_source_until_export(qtbot, qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QTimer
    from screenlite import video

    def synthetic_capture(rect, path, fps, backend):
        return ['-hide_banner', '-n', '-re', '-f', 'lavfi', '-i', 'testsrc2=size=64x48:rate=10',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '2', '-f', 'matroska', str(path)]

    monkeypatch.setattr(video, 'build_record_command', synthetic_capture)
    controller = Controller(qapp, tmp_path, enable_hotkeys=False)
    qtbot.addWidget(controller.window)
    outputs = []
    monkeypatch.setattr(controller, '_show_video', lambda source, recorded=False: outputs.append(source))
    controller.arm_recording(Rect(0, 0, 64, 48))
    controller._countdown_timer.stop()
    controller._start_recording()
    QTimer.singleShot(700, controller.toggle_record)
    qtbot.waitUntil(lambda: bool(outputs), timeout=10000)
    assert outputs[0].exists()
    assert controller.state == 'idle'
    assert controller.record_job is None
    controller.shutdown()


def test_unwritable_output_preference_does_not_discard_preview(qtbot, qapp, tmp_path, monkeypatch):
    from PIL import Image
    from screenlite.ui.dialogs import ImageDialog

    controller = Controller(qapp, tmp_path, enable_hotkeys=False)
    qtbot.addWidget(controller.window)
    invalid = tmp_path / 'not-a-directory'
    invalid.write_text('existing file')
    controller.settings['output_dir'] = str(invalid)
    viewed = []
    monkeypatch.setattr(ImageDialog, 'exec', lambda dialog: viewed.append(dialog.image.size))
    controller._show_image(Image.new('RGB', (120, 80)))
    assert viewed == [(120, 80)]
    assert controller.state == 'idle'
    assert invalid.read_text() == 'existing file'
    controller.shutdown()


def test_repeated_capture_request_during_busy_state_is_ignored(qtbot, qapp, tmp_path):
    controller = Controller(qapp, tmp_path, enable_hotkeys=False)
    qtbot.addWidget(controller.window)
    controller.state = 'exporting'
    controller.begin_selection('capture')
    assert controller.state == 'exporting'
    assert controller.overlays == []
    controller.state = 'idle'
    controller.shutdown()
