import json

import pytest

from screenlite.config import SettingsStore
from screenlite.geometry import Rect, fit_size, logical_to_physical


def test_negative_monitor_coordinate_and_fractional_scale():
    assert logical_to_physical(Rect(10, 20, 100, 80), Rect(-1920, 0, 1920, 1080), 1.5) == Rect(-1905, 30, 150, 120)


def test_fit_does_not_upscale_and_keeps_aspect():
    assert fit_size(3840, 2160, 1280, 720) == (1280, 720)
    assert fit_size(640, 480, 1920, 1080) == (640, 480)
    assert fit_size(1080, 1920, 1280, 720, even=True) == (404, 720)


def test_invalid_sizes_rejected():
    with pytest.raises(ValueError):
        fit_size(0, 1, 20, 20)
    with pytest.raises(ValueError):
        Rect(0, 0, -1, 20)


def test_config_roundtrip_and_defaults(tmp_path):
    store = SettingsStore(tmp_path)
    assert store.load()['fps'] == 30
    store.save({'fps': 60, 'screenshot_hotkey': 'Ctrl+Alt+S'})
    assert store.load()['fps'] == 60
    assert store.load()['screenshot_hotkey'] == 'Ctrl+Alt+S'


def test_corrupt_config_is_preserved_and_recovers(tmp_path):
    store = SettingsStore(tmp_path)
    store.path.parent.mkdir(parents=True)
    store.path.write_text('{bad', encoding='utf-8')
    assert store.load()['fps'] == 30
    assert store.path.with_suffix('.broken.json').read_text() == '{bad'


def test_invalid_config_values_revert(tmp_path):
    store = SettingsStore(tmp_path)
    store.path.parent.mkdir(parents=True)
    store.path.write_text(json.dumps({'fps': 0, 'preset': 'x', 'record_hotkey': 12}), encoding='utf-8')
    settings = store.load()
    assert settings['fps'] == 30
    assert settings['preset'] == 'balanced'
    assert settings['record_hotkey'] == 'Ctrl+Alt+R'
