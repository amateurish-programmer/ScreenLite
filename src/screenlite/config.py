"""Portable, validated JSON settings, never writes to the registry."""
import json
import os
from pathlib import Path

DEFAULTS = {'screenshot_hotkey': 'Ctrl+Alt+A', 'record_hotkey': 'Ctrl+Alt+R',
            'fps': 30, 'preset': 'balanced', 'output_dir': '', 'copy_after_capture': True,
            'record_cursor': True, 'countdown': 3}


class SettingsStore:
    def __init__(self, root: Path):
        self.path = Path(root) / 'data' / 'settings.json'
        self.warning = ''

    def load(self) -> dict:
        result = DEFAULTS.copy()
        if not self.path.exists():
            return result
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError('settings must be an object')
        except (ValueError, UnicodeError):
            backup = self.path.with_suffix('.broken.json')
            backup.write_bytes(self.path.read_bytes())
            self.warning = '配置损坏，已保留备份并恢复默认设置。'
            return result
        for key, value in data.items():
            if key not in result:
                continue
            if key == 'fps' and type(value) is int and value in (15, 30, 60):
                result[key] = value
            elif key == 'preset' and value in ('ultra', 'clear', 'balanced', 'small', 'lossless'):
                result[key] = value
            elif key in ('copy_after_capture', 'record_cursor') and type(value) is bool:
                result[key] = value
            elif key == 'countdown' and type(value) is int and value in (0, 3):
                result[key] = value
            elif key in ('screenshot_hotkey', 'record_hotkey', 'output_dir') and isinstance(value, str):
                result[key] = value
        return result

    def save(self, values: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps({**DEFAULTS, **values}, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, self.path)
