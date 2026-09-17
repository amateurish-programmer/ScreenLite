import pytest

from screenlite.platform_win import parse_hotkey


def test_hotkey_parser_supports_standard_qt_strings():
    assert parse_hotkey('Ctrl+Alt+A') == (0x4003, 65)
    assert parse_hotkey('Ctrl+Shift+F12') == (0x4006, 123)


@pytest.mark.parametrize('value', ['A', 'Ctrl+', 'Ctrl+Alt+?', 'Ctrl+Alt+F25', 'Ctrl+Alt+A+B'])
def test_hotkeys_reject_unsupported_or_unmodified_keys(value):
    with pytest.raises(ValueError):
        parse_hotkey(value)
