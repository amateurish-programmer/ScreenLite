# ScreenLite

Windows 10/11 x64 便携截图、区域录屏与图片/视频压缩工具。

开发规格见 [HTML 开发文档](docs/development.html)，阶段记录见 [progress.md](docs/progress.md)。

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
