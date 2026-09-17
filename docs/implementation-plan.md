# ScreenLite 分阶段开发计划

日期：2026-09-17。规格：development.html。用户已授权自动执行全部阶段、创建 GitHub 仓库并逐阶段提交推送。

## 全局约束

Windows 10/11 x64；Python 3.12；PySide6 Widgets；后台托盘；便携目录配置；中文界面；所有重型导出使用工作线程或进程。
完整引用对话读取失败（Cloudflare 验证），仅已提供的预览可确认；后续补充设计必须注明，不伪称完整原文。
仅本项目源码、合成测试样本、文档进入仓库；桌面截图、录屏和用户导出不提交。

## 阶段 1：文档与基础
- [ ] HTML 开发规格与进度记录；Git 仓库和私有 GitHub 远程。
- [ ] 数据模型、尺寸换算、配置原子写入；先测负坐标、缩放、偶数尺寸、损坏配置。
- [ ] 接口：Rect(x,y,width,height)，fit_size(width,height,max_width,max_height,even=False)；SettingsStore(root).load()/save(dict)。
- [ ] 验证 pytest 基础用例、HTML 解析、git diff --check；提交。

## 阶段 2：截图与交互
- [ ] 多屏独立遮罩，冻结桌面，拖动/8 点调整/方向键/Enter/Esc。
- [ ] 图片导出：原尺寸、50%、1080p、720p、自定义宽度；PNG/JPEG/WebP，三档压缩，复制剪贴板。
- [ ] 托盘、系统热键 Ctrl+Alt+A / Ctrl+Alt+R，冲突可见，可配置。
- [ ] 测试图片尺寸与格式、选区边界、UI 事件；提交。

## 阶段 3：录屏与压缩
- [ ] FFmpeg 独立进程，优先 ddagrab + h264_mf，兼容 gdigrab + libx264；单屏区域，负坐标支持。
- [ ] 3 秒倒计时、录制计时、停止/异常恢复；临时 MKV 保留，成功导出 MP4 后再清理。
- [ ] 已有图片/视频压缩，异步进度与取消，不覆盖源文件。
- [ ] Media 接口：find_ffmpeg(root)->Path；export_image(image,path,width,height,preset)->Path；VideoJob(QObject) start_record(Rect,path,fps,backend), stop_record(), transcode(source,target,max_width,max_height,preset), cancel()；signals progress(int), finished(str), failed(str), started()。
- [ ] subprocess 参数列表、无 shell；测试命令、真实合成视频转码/取消；提交。

## 阶段 4：便携交付与验收
- [ ] PyInstaller onedir 便携包（本机可重复验证），保留 Nuitka 作为替代路线。
- [ ] 包含 FFmpeg、依赖许可和来源说明；生成 SHA256、运行说明。
- [ ] 测试与 lint、真实录制冒烟、exe 启停、GitHub CI；最终审查后提交推送。
- [ ] 报告实测结果、包体积及限制，混合 DPI/多硬件验收不冒称通过。

## 模块所有权
foundation: geometry.py, config.py, platform_win.py, app.py；UI: ui/selection.py, ui/dialogs.py, ui/theme.py；media: media.py, video.py；delivery: scripts/, .github/, docs/。
UI 契约：SelectionOverlay(screen, pixmap, mode='capture')，selected(QRect) 发出屏幕局部逻辑坐标，cancelled()；ImageDialog(PIL.Image, root, parent=None)；SettingsDialog(dict,parent=None).values()；MainWindow signals capture_requested, record_requested, compress_requested, settings_requested，set_recording(bool,seconds=0)，set_status(str)。
