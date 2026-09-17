# ScreenLite 分阶段开发计划

日期：2026-09-17。规格：development.html。用户已授权自动执行全部阶段、创建 GitHub 仓库并逐阶段提交推送。

## 全局约束

Windows 10/11 x64；Python 3.12；PySide6 Widgets；后台托盘；便携目录配置；中文界面；所有重型导出使用工作线程或进程。
完整引用对话已在后续重试中读取成功，见 conversation-source.md；追加自动复制、浮动工具条、HUD 排除捕获、完整尺寸和四档质量、录制前硬件探测。
仅本项目源码、合成测试样本、文档进入仓库；桌面截图、录屏和用户导出不提交。

## 阶段 1：文档与基础
- [x] HTML 开发规格与进度记录；Git 仓库和私有 GitHub 远程。
- [x] 数据模型、尺寸换算、配置原子写入；先测负坐标、缩放、偶数尺寸、损坏配置。
- [x] 接口：Rect(x,y,width,height)，fit_size(width,height,max_width,max_height,even=False)；SettingsStore(root).load()/save(dict)。
- [x] 验证 pytest 基础用例、HTML 解析、git diff --check；提交。

## 阶段 2：截图与交互
- [x] 多屏独立遮罩，冻结桌面，拖动/8 点调整/方向键/Enter/Esc。
- [x] 图片导出：原尺寸、50%、1080p、720p、自定义宽度；PNG/JPEG/WebP，三档压缩，复制剪贴板。
- [x] 托盘、系统热键 Ctrl+Alt+A / Ctrl+Alt+R，冲突可见，可配置。
- [x] 测试图片尺寸与格式、选区边界、UI 事件；提交。

## 阶段 3：录屏与压缩
- [x] FFmpeg 独立进程，优先 ddagrab + h264_mf，兼容 gdigrab + libx264；单屏区域，负坐标支持。
- [x] 3 秒倒计时、录制计时、停止/异常恢复；临时 MKV 保留，成功导出 MP4 后再清理。
- [x] 已有图片/视频压缩，异步进度与取消，不覆盖源文件。
- [x] Media 接口：find_ffmpeg(root)->Path；export_image(image,path,width,height,preset)->Path；VideoJob(QObject) start_record(Rect,path,fps,backend), stop_record(), transcode(source,target,max_width,max_height,preset), cancel()；signals progress(int), finished(str), failed(str), started()。
- [x] subprocess 参数列表、无 shell；测试命令、真实合成视频转码/取消；提交。

## 阶段 4：便携交付与验收
- [x] PyInstaller onedir 便携包（本机可重复验证），保留 Nuitka 作为替代路线。
- [x] 包含 FFmpeg、依赖许可和来源说明；生成 SHA256、运行说明。
- [x] 测试与 lint、真实录制冒烟、exe 启停、GitHub CI；最终审查后提交推送。
- [x] 报告实测结果、包体积及限制，混合 DPI/多硬件验收不冒称通过。

## 模块所有权
foundation: geometry.py, config.py, platform_win.py, app.py；UI: ui/selection.py, ui/dialogs.py, ui/theme.py；media: media.py, video.py；delivery: scripts/, .github/, docs/。
UI 契约：SelectionOverlay(screen, pixmap, mode='capture')，selected(QRect) 发出屏幕局部逻辑坐标，cancelled()；ImageDialog(PIL.Image, root, parent=None)；SettingsDialog(dict,parent=None).values()；MainWindow signals capture_requested, record_requested, compress_requested, settings_requested，set_recording(bool,seconds=0)，set_status(str)。

## 补全阶段：对齐完整对话
- [x] 截图自动复制、紧凑浮动工具条；设置可关闭自动复制。
- [x] 图片75%/25%/长边与锁比宽高；视频75%/50%/自定义；四档质量原始参数。
- [x] 录制HUD、Windows捕获排除，失败隐藏；0/3秒倒计时、鼠标录制设置。
- [x] 单屏录制前异步硬件/软件探测与兼容回退。
- [x] HTML 纳入完整来源和原七阶段映射；阶段签名提交与推送。

完成证据及未实机验收项见 ACCEPTANCE.md；勾选表示该工程任务完成，不代表所有硬件矩阵通过。

## v0.2 体验修订（用户 2026-09-17 追加要求）
- [x] 阶段 A：每次启动显示主界面；关闭退出、最小化保留快捷键；修复截图、设置和导出窗口的资源生命周期。
- [x] 阶段 B：选区外侧右下方标注工具条（矩形、椭圆、箭头、画笔、马赛克、文字、取消、确认），颜色/粗细、撤销/重做；截图和录屏的操作提示随选区移动。
- [x] 阶段 C：合成图像像素验证、重复操作内存测量、完整回归、独立审查与新版本 EXE 实际启停；同步 HTML 和使用说明。

约定：屏幕边缘放不下时工具条移到选区上方，极限满屏时约束在屏幕内；导出只含冻结图像和标注。
标注以选区所在屏幕的逻辑坐标存储，裁切时按物理像素渲染；录屏共用跟随布局和确认/取消。
内存策略：冻结画面只持有一份 Qt 像素缓冲；裁切后立即清除整屏缓冲；导出窗口共享只读选区图像，结束释放引用。
不使用强制缩减工作集制造内存下降；测量重复操作后的进程专用内存，并验证关闭后的窗口/线程清理。
