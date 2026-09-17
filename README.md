# ScreenLite

Windows 10/11 x64 便携截图、区域录屏与图片/视频压缩工具。

开发规格见 [HTML 开发文档](docs/development.html)，阶段记录见 [progress.md](docs/progress.md)。

## 便携版

解压 `ScreenLite-0.1.0-windows-x64.zip`，运行其中的 `ScreenLite.exe`。保持 `_internal/` 和 `bin/` 在旁边。
详细操作和恢复方法见 [使用说明](docs/USAGE.md)。首版为本地测试版。

## 开发运行
```powershell
uv venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
.venv\Scripts\python.exe -m screenlite
```

默认截图 `Ctrl+Alt+A`，录屏开始/停止 `Ctrl+Alt+R`。关闭主窗口后驻留托盘，托盘菜单可退出。
本地设置、录制临时文件和日志位于程序目录 `data/`，不上传网络。
首版不录音、不跨屏录制；每块屏幕分别选区，适配各自缩放倍率。

当前实现和验收状态以阶段记录为准。

## 测试与打包

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src tests scripts
.venv\Scripts\python.exe scripts/build_portable.py
```

可重复构建需先安装 `requirements-lock.txt` 中的固定版本。构建脚本拒绝覆盖旧产物，使用 `--output-dir` 指定新的输出目录。
FFmpeg/Qt 版本、许可和分发边界见 [第三方组件说明](docs/THIRD_PARTY.md)。
