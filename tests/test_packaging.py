import importlib.util
import os
from pathlib import Path


def test_packager_does_not_collect_dlls_from_unrelated_path_entries(monkeypatch, tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_portable.py"
    spec = importlib.util.spec_from_file_location("screenlite_build_portable", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    windows = tmp_path / "Windows"
    (windows / "System32").mkdir(parents=True)
    unrelated = tmp_path / "poppler"
    unrelated.mkdir()
    monkeypatch.setenv("SystemRoot", str(windows))
    monkeypatch.setenv("PATH", str(unrelated))
    environment = module.packaging_environment()
    paths = environment["PATH"].split(os.pathsep)
    assert str(unrelated) not in paths
    assert str(windows / "System32") in paths
    assert environment["SYSTEMROOT"] == str(windows)
    assert os.environ["PATH"] == str(unrelated)
