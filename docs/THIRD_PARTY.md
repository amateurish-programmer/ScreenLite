# Third-party components and provenance

This record applies to the locked Windows x64 evaluation build of ScreenLite 0.1.0.
ScreenLite calls a separate `bin/ffmpeg.exe` process and dynamically loads external
Qt/PySide DLLs from the PyInstaller onedir package. The package is not a single
statically linked executable. Do not remove its `LICENSES/` or `_internal/` folders.

## Included notices

`scripts/build_portable.py` copies license/notice files from the installed distributions
using `importlib.metadata`, records all locked distribution versions and upstream URLs
in `LICENSES/DEPENDENCIES.json`, and includes the Python runtime license. This inventory
also covers build-time tools; listing a tool does not imply its complete Python package
is shipped in the executable. Pillow's wheel license file includes its bundled-library notices.

| Component | Locked version | License / source |
| --- | --- | --- |
| Python | Build interpreter recorded in BUILD-INFO.json | PSF license; [CPython source](https://github.com/python/cpython) |
| PySide6 Essentials / Shiboken6 | 6.11.2 | LGPL-3.0 option; [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html), [matching source archive directory](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/) |
| Qt runtime | 6.11.2 | Applicable Qt module licenses; [Qt sources](https://download.qt.io/official_releases/qt/6.11/6.11.2/single/), [Qt licensing](https://doc.qt.io/qt-6/licensing.html) |
| Pillow | 12.3.0 | HPND and bundled-library notices; [source](https://github.com/python-pillow/Pillow/tree/12.3.0) |
| mss | 10.2.0 | MIT; [source](https://github.com/BoboTiG/python-mss/tree/v10.2.0) |
| imageio-ffmpeg | 0.6.0 | BSD-2-Clause wrapper; [source](https://github.com/imageio/imageio-ffmpeg/tree/v0.6.0); binary has its own GPL license |
| PyInstaller bootloader/build tool | 6.22.3 | GPL with bootloader exception; copied COPYING.txt and [source](https://github.com/pyinstaller/pyinstaller/tree/v6.22.3) |

The installed Qt-for-Python wheels contain a commercial-license notice but do not include
the complete LGPL text. The build therefore retrieves the full
[LGPL-3.0 text from Qt 6.11.2](https://raw.githubusercontent.com/qt/qtbase/v6.11.2/LICENSES/LGPL-3.0-only.txt)
and GPL-3.0 text separately and records their hashes. Qt DLLs remain replaceable outside
the executable. ScreenLite imposes no additional restriction on replacing these libraries
or debugging such replacements. Matching ABI and architecture are required to run them.

## FFmpeg binary chain

The binary is copied directly from the locked imageio-ffmpeg wheel; environment overrides
and PATH are deliberately ignored during packaging. Its known identity is:

- Wheel: `imageio-ffmpeg==0.6.0`, Windows x64.
- Wheel member: `imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe`.
- Executable version: `7.1-essentials_build-www.gyan.dev`, GCC 14.2.0 / MSYS2.
- SHA256: `2ce797a0f88d7f067180338fb227f7b1928ea727bd9a4d7a1d022f7c52af71a3`.
- Configuration includes `--enable-gpl --enable-version3 --enable-static --enable-libx264`.
- License: GPL version 3 or later, as also reported by this binary's `-L` output.

The upstream [platform mapping](https://github.com/imageio/imageio-ffmpeg/blob/v0.6.0/imageio_ffmpeg/_definitions.py)
selects this filename. Its [packaging script](https://github.com/imageio/imageio-ffmpeg/blob/v0.6.0/tasks.py)
copies it from imageio-binaries or downloads it from
[the imageio binary repository](https://github.com/imageio/imageio-binaries/raw/master/ffmpeg/ffmpeg-win-x86_64-v7.1.exe).
That repository URL uses a mutable branch; the hardcoded binary hash identifies the exact
file used here. [Gyan's FFmpeg 7.1 release](https://github.com/GyanD/codexffmpeg/releases/tag/7.1)
identifies the vendor build; it is not an FFmpeg-project-produced Windows executable.

FFmpeg's base source is [ffmpeg-7.1.tar.xz](https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz),
also available at [tag n7.1](https://github.com/FFmpeg/FFmpeg/tree/n7.1). The full
[GPL-3.0 text](https://raw.githubusercontent.com/FFmpeg/FFmpeg/n7.1/COPYING.GPLv3)
is included in `LICENSES/GPL-3.0.txt`. The actual `-version`, `-L`, and `-buildconf`
outputs are captured in `LICENSES/FFMPEG-BUILD.txt`; source links and hashes are in
`LICENSES/FFMPEG-PROVENANCE.json`.

## Redistribution status

These build artifacts are prepared for internal evaluation. The build does **not** yet
collect or verify complete corresponding source and build scripts for every statically
linked FFmpeg dependency, or all Qt bundled third-party components. The FFmpeg 7.1 source
tarball alone does not establish that complete source chain. The current notice inventory
and upstream links are provenance evidence, not a completed redistribution clearance.

Before conveying binary packages to recipients, the distributor must provide the applicable
corresponding source, build information and notices through a license-compliant mechanism,
and verify that the source matches the binaries and their bundled dependencies. See
[FFmpeg's legal guidance](https://ffmpeg.org/legal.html) and
[Qt's open-source obligations](https://www.qt.io/licensing/open-source-lgpl-obligations).
The generated manifest records `redistribution_source_bundle_verified: false` until that
work is actually completed. Building this package does not publish it or create a release.
