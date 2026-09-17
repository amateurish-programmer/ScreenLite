"""Ownership checks for large image buffers and transient Qt windows."""

import weakref

import pytest
from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent

from screenlite.app import Controller
from screenlite.ui.dialogs import ImageDialog, SettingsDialog
from screenlite.ui.toolbars import ScreenshotToolbar


def flush_deletes():
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_main_close_requests_exit_but_minimize_keeps_shortcuts(qtbot, qapp, tmp_path):
    from PySide6.QtTest import QSignalSpy
    controller = Controller(qapp, tmp_path, enable_hotkeys=False)
    qtbot.addWidget(controller.window)
    requested = QSignalSpy(controller.window.quit_requested)
    controller.window.showMinimized()
    assert requested.count() == 0
    assert controller.tray.isVisible()
    controller.show_window()
    controller.window.close()
    assert requested.count() == 1
    assert not controller.tray.isVisible()
    assert not controller.window.isVisible()
    assert controller.state == 'idle'


def test_closed_settings_dialogs_do_not_accumulate(qtbot, qapp, tmp_path, monkeypatch):
    controller = Controller(qapp, tmp_path, enable_hotkeys=False)
    qtbot.addWidget(controller.window)
    monkeypatch.setattr(SettingsDialog, 'exec', lambda self: self.DialogCode.Rejected)
    for _ in range(8):
        controller.configure()
        flush_deletes()
    assert controller.window.findChildren(SettingsDialog) == []
    controller.shutdown()


@pytest.mark.parametrize('dialog_class', [ImageDialog, ScreenshotToolbar])
def test_image_dialogs_share_read_only_image_and_release_it(qtbot, tmp_path, dialog_class):
    image = Image.new('RGB', (2048, 1024), 'teal')
    reference = weakref.ref(image)
    dialog = dialog_class(image, tmp_path)
    qtbot.addWidget(dialog)
    assert dialog.image is image
    del image
    dialog.release_resources()
    assert reference() is None


def test_image_dialog_cleanup_runs_even_if_modal_fails(qtbot, qapp, tmp_path, monkeypatch):
    controller = Controller(qapp, tmp_path, enable_hotkeys=False)
    qtbot.addWidget(controller.window)

    def fail(dialog):
        raise RuntimeError('modal failure')

    monkeypatch.setattr(ImageDialog, 'exec', fail)
    with pytest.raises(RuntimeError, match='modal failure'):
        controller._show_image(Image.new('RGB', (64, 48)))
    flush_deletes()
    assert controller.window.findChildren(ImageDialog) == []
    assert controller.state == 'idle'
    controller.shutdown()


def test_worker_releases_source_after_success(qtbot, tmp_path):
    dialog = ImageDialog(Image.new('RGB', (900, 600), 'navy'), tmp_path)
    qtbot.addWidget(dialog)
    dialog.start_export(tmp_path / 'export.png')
    worker = dialog._worker
    qtbot.waitUntil(lambda: dialog._worker is None, timeout=10000)
    assert worker.image is None
    assert (tmp_path / 'export.png').exists()
