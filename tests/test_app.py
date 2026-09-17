from screenlite.app import Controller


def test_controller_starts_idle_and_hides_to_tray(qtbot, qapp, tmp_path):
    controller = Controller(qapp, tmp_path, enable_hotkeys=False)
    qtbot.addWidget(controller.window)
    assert controller.state == 'idle'
    controller.show_window()
    assert controller.window.isVisible()
    controller.window.close()
    assert not controller.window.isVisible()
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
