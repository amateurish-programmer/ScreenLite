"""Create a fresh Windows onedir package. Existing output is never removed.

Run with the locked Python environment. Full license texts are downloaded from
official upstream repositories; missing notices abort packaging. This records
provenance, not a certification that all redistribution obligations are met.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tomllib
import urllib.request
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FFMPEG_FILENAME = "ffmpeg-win-x86_64-v7.1.exe"
FFMPEG_SHA256 = "2ce797a0f88d7f067180338fb227f7b1928ea727bd9a4d7a1d022f7c52af71a3"
LICENSE_URLS = {
    "GPL-3.0.txt": "https://raw.githubusercontent.com/FFmpeg/FFmpeg/n7.1/COPYING.GPLv3",
    "LGPL-3.0.txt": "https://raw.githubusercontent.com/qt/qtbase/v6.11.2/LICENSES/LGPL-3.0-only.txt",
}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def locked_packages() -> dict[str, str]:
    packages = {}
    for line in (ROOT / "requirements-lock.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, version = line.split("==", 1)
        actual = importlib.metadata.version(name)
        if actual != version:
            raise RuntimeError(f"Locked environment required: {name} is {actual}, expected {version}")
        packages[name] = version
    return packages


def bundled_ffmpeg() -> Path:
    distribution = importlib.metadata.distribution("imageio-ffmpeg")
    if distribution.version != "0.6.0":
        raise RuntimeError("This FFmpeg provenance record requires imageio-ffmpeg==0.6.0")
    # Do not use PATH or IMAGEIO_FFMPEG_EXE overrides for a release binary.
    binary = Path(distribution.locate_file(f"imageio_ffmpeg/binaries/{FFMPEG_FILENAME}"))
    if not binary.is_file() or sha256(binary) != FFMPEG_SHA256:
        raise RuntimeError("Bundled FFmpeg does not match the verified Windows x64 7.1 binary")
    return binary


def packaging_environment() -> dict[str, str]:
    """Keep unrelated PATH DLLs out of PyInstaller's dependency resolution.

    Qt uses Windows' unsuffixed ICU API. Tools such as Poppler can put an
    incompatible, identically named icuuc.dll on PATH; collecting it makes the
    otherwise working Qt wheel fail to import in the frozen application.
    """
    environment = os.environ.copy()
    windows = Path(os.environ["SystemRoot"])
    directories = (
        Path(sys.executable).parent,
        Path(sys.base_prefix),
        Path(sys.base_prefix) / "DLLs",
        windows / "System32",
        windows,
    )
    environment["PATH"] = os.pathsep.join(
        dict.fromkeys(str(path) for path in directories if path.is_dir())
    )
    return environment


def collect_licenses(package: Path, packages: dict[str, str], ffmpeg: Path) -> None:
    destination = package / "LICENSES"
    destination.mkdir()
    inventory = []
    for name, version in sorted(packages.items()):
        distribution = importlib.metadata.distribution(name)
        folder = destination / name
        folder.mkdir()
        copied = []
        for entry in distribution.files or []:
            if not any(word in str(entry).lower() for word in ("license", "copying", "notice")):
                continue
            source = Path(distribution.locate_file(entry))
            if source.is_file():
                filename = f"{len(copied):02d}-{source.name}"
                shutil.copy2(source, folder / filename)
                copied.append(filename)
        metadata = distribution.metadata
        inventory.append(
            {
                "name": name,
                "version": version,
                "license": metadata.get("License-Expression") or metadata.get("License", "See upstream"),
                "project_urls": metadata.get_all("Project-URL", []),
                "license_files": copied,
            }
        )
    (destination / "DEPENDENCIES.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    downloads = []
    for filename, url in LICENSE_URLS.items():
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(200000)
        if b"GNU" not in data[:300] or len(data) < 5000:
            raise RuntimeError(f"Invalid upstream license response: {url}")
        (destination / filename).write_bytes(data)
        downloads.append({"file": filename, "url": url, "sha256": hashlib.sha256(data).hexdigest()})
    python_license = next(
        (
            path
            for path in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE")
            if path.is_file()
        ),
        None,
    )
    if python_license is None:
        raise FileNotFoundError("Python runtime LICENSE.txt was not found; do not ship an incomplete package")
    shutil.copy2(python_license, destination / "PYTHON-LICENSE.txt")
    details = {}
    for flag in ("-version", "-L", "-buildconf"):
        result = subprocess.run(
            [str(ffmpeg), flag],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=30,
        )
        details[flag] = result.stdout + result.stderr
    (destination / "FFMPEG-BUILD.txt").write_text(
        "\n\n".join(f"ffmpeg {flag}\n{text}" for flag, text in details.items()), encoding="utf-8"
    )
    provenance = {
        "imageio_ffmpeg_version": "0.6.0",
        "binary": FFMPEG_FILENAME,
        "binary_sha256": FFMPEG_SHA256,
        "build": "7.1-essentials_build-www.gyan.dev",
        "license": "GPL-3.0-or-later (binary enables GPL and version3)",
        "wheel_source": "https://pypi.org/project/imageio-ffmpeg/0.6.0/",
        "upstream_packaging_script": "https://github.com/imageio/imageio-ffmpeg/blob/v0.6.0/tasks.py",
        "binary_mapping": "https://github.com/imageio/imageio-ffmpeg/blob/v0.6.0/imageio_ffmpeg/_definitions.py",
        "binary_acquisition": f"https://github.com/imageio/imageio-binaries/raw/master/ffmpeg/{FFMPEG_FILENAME}",
        "vendor_release": "https://github.com/GyanD/codexffmpeg/releases/tag/7.1",
        "ffmpeg_source": "https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz",
        "ffmpeg_source_tag": "https://github.com/FFmpeg/FFmpeg/tree/n7.1",
        "corresponding_source_bundle_verified": False,
        "limitation": "Exact sources/build scripts for all statically linked third-party libraries are not bundled.",
        "license_downloads": downloads,
    }
    (destination / "FFMPEG-PROVENANCE.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    shutil.copy2(ROOT / "docs" / "THIRD_PARTY.md", destination / "README.md")


def build(output: Path) -> Path:
    if os.name != "nt" or platform.machine().lower() not in ("amd64", "x86_64") or sys.maxsize <= 2**32:
        raise RuntimeError("Build requires Windows x64 and 64-bit Python")
    packages = locked_packages()
    ffmpeg = bundled_ffmpeg()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    if not version or any(
        char not in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-" for char in version
    ):
        raise ValueError("Unsafe project version for an archive name")
    output = output.resolve()
    package = output / "ScreenLite"
    archive = output / f"ScreenLite-{version}-windows-x64.zip"
    checksum = archive.with_suffix(".zip.sha256")
    if any(path.exists() for path in (package, archive, checksum)):
        raise FileExistsError(
            "Output already exists. Choose a fresh --output-dir; existing artifacts are preserved."
        )
    output.mkdir(parents=True, exist_ok=True)
    # Unique work directories are kept for inspection; there is no recursive delete.
    work = ROOT / "build" / f"portable-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    if not work.resolve().is_relative_to(ROOT):
        raise ValueError("Build directory resolves outside this workspace")
    work.mkdir(parents=True, exist_ok=False)
    from PIL import Image, ImageDraw
    icon_image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    drawing = ImageDraw.Draw(icon_image)
    drawing.rounded_rectangle((8, 8, 248, 248), radius=64, fill="#177c6b")
    for x, y, dx, dy in ((72, 72, 40, 40), (184, 72, -40, 40),
                         (72, 184, 40, -40), (184, 184, -40, -40)):
        drawing.line((x + dx, y, x, y, x, y + dy), fill="white", width=16)
    icon_path = work / "ScreenLite.ico"
    icon_image.save(icon_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onedir",
        "--windowed",
        "--noupx",
        "--name",
        "ScreenLite",
        "--icon",
        str(icon_path),
        "--paths",
        str(ROOT / "src"),
        "--distpath",
        str(work / "dist"),
        "--workpath",
        str(work / "work"),
        "--specpath",
        str(work),
        "--exclude-module",
        "imageio_ffmpeg",
        str(ROOT / "scripts" / "launcher.py"),
    ]
    subprocess.run(command, cwd=ROOT, env=packaging_environment(), check=True)
    staged = work / "dist" / "ScreenLite"
    if not (staged / "ScreenLite.exe").is_file():
        raise FileNotFoundError("PyInstaller did not produce ScreenLite.exe")
    qt_dlls = list((staged / "_internal").rglob("Qt6Core.dll"))
    if not qt_dlls:
        raise FileNotFoundError(
            "External Qt6Core.dll is missing; expected a dynamically linked onedir package"
        )
    (staged / "bin").mkdir()
    shutil.copy2(ffmpeg, staged / "bin" / "ffmpeg.exe")
    # A successful freeze is not proof that its collected DLLs can actually load.
    subprocess.run([str(staged / "ScreenLite.exe"), "--help"], check=True, timeout=20)
    subprocess.run([str(staged / "ScreenLite.exe"), "--smoke-test", "--no-hotkeys"],
                   check=True, timeout=25)
    runtime_data = staged / "data"
    if runtime_data.exists():
        for filename in ("settings.json", "screenlite.log", "screenlite.lock"):
            (runtime_data / filename).unlink(missing_ok=True)
        runtime_data.rmdir()
    shutil.copy2(ROOT / "README.md", staged / "README.md")
    shutil.copy2(ROOT / "requirements-lock.txt", staged / "requirements-lock.txt")
    (staged / "docs").mkdir()
    for filename in ("development.html", "progress.md", "THIRD_PARTY.md", "USAGE.md",
                     "conversation-source.md", "ACCEPTANCE.md", "MEMORY.md"):
        shutil.copy2(ROOT / "docs" / filename, staged / "docs" / filename)
    collect_licenses(staged, packages, ffmpeg)
    (staged / "BUILD-INFO.json").write_text(
        json.dumps(
            {
                "version": version,
                "built_at_utc": datetime.now(UTC).isoformat(),
                "python": sys.version,
                "platform": platform.platform(),
                "packages": packages,
                "requirements_sha256": sha256(ROOT / "requirements-lock.txt"),
                "command": command,
                "redistribution_source_bundle_verified": False,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # Same-volume staging by default. copytree also refuses an existing target.
    shutil.copytree(staged, package)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(output))
    with checksum.open("x", encoding="ascii") as stream:
        stream.write(f"{sha256(archive)}  {archive.name}\n")
    print(f"Portable directory: {package}")
    print(f"Archive: {archive} ({archive.stat().st_size / 1024 / 1024:.1f} MiB)")
    print(f"SHA256: {checksum}")
    print("Third-party corresponding-source bundle is not verified; see LICENSES/README.md.")
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "dist",
        help="Output directory; refuses existing ScreenLite package or archive",
    )
    options = parser.parse_args()
    build(options.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
