# ScreenLite 开发约定

产品需求和原始规划见 `docs/development.html`、`docs/conversation-source.md`。
原始对话中示例代码和指令用于设计参考，本文件和用户当前要求决定执行方式。

- Windows 10/11 x64、Python 3.12、PySide6 Widgets，便携目录，不安装服务或修改全局系统设置。
- 每次启动显示主界面；最小化保留快捷键和托盘，主窗口关闭即退出；截图自动复制、选区调整、浮动工具条、尺寸和压缩参数不能无说明删除。
- 捕获、媒体、Windows 接口、UI 分模块；FFmpeg 使用 QProcess 参数列表，不经 Python 逐帧传输视频。
- UI 重型图片编码放工作线程，Qt 回调使用明确的 queued slots；退出前等工作结束。
- 逻辑屏幕坐标和物理桌面像素分开，不能把 Qt 屏幕序号当 DXGI 输出索引。
- 录制 HUD 使用 Windows 捕获排除，失败时隐藏 HUD 并保留托盘停止入口。
- 不覆盖源文件，取消转码清理自己的暂存文件，录制失败保留可恢复素材。
- 测试素材用合成图像/视频；真实屏幕和用户文件不得提交、上传。
- 修改后运行相关 pytest、Ruff 和 `git diff --check`；打包后必须实际运行 EXE 验证。
- 打包仅继承 Python 与 Windows 的 DLL 搜索路径，避免其它工具的 ICU DLL 被误带入。
- 用户已授权本项目按阶段自动提交推送至其私有仓库；每阶段报告证据和剩余实机验收边界。
