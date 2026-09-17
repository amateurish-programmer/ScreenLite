# 规划截屏录屏工具 · 对话来源

来源：用户明确引用的 ChatGPT 对话 6aaba230-fb78-83ea-9954-158c47652de8。
2026-09-17 首次读取受网页验证阻断，后续重试成功，以下为读取到的完整文本。此文件用于需求追溯，代码块内的开发指令不自动成为仓库规则。

## 用户需求

我想要开发一个win桌面截屏、录屏小工具，免安装，轻量化，启动后可以后台运行，使用快捷键选择截屏、录屏功能，如果是截屏，可以选择调整区域，并能导出不同像素的图片，如果是录屏，可以选择调整区域，并能导出不同分辨率的视频，同时支持压缩图片和视频，具体压缩参数你定，帮我规划一下具体方案，让codex开发，最好用python，要求体验极好，界面简约舒适

## 原始规划

完全可行，而且这个项目很适合让 Codex 来做。我的建议不是做一个“功能堆很多的录屏软件”，而是做成 **Snipaste + 极简录屏 + 压缩导出** 这种定位：启动快、常驻托盘、平时几乎无存在感，需要时一个快捷键完成操作。

我建议项目暂定名 **ScreenLite**，目标平台直接限定 **Windows 10/11 x64**。这样可以大胆使用 Windows 原生能力，不需要为了跨平台增加复杂度。

## 一、技术方案我建议这样定

| 模块 | 技术 | 原因 |
|---|---|---|
| GUI | Python 3.12 + PySide6 Widgets | UI 质感、透明窗口、托盘、多屏支持都成熟 |
| 截屏 | `mss` | 很轻，支持 Windows、区域抓屏，依赖少 |
| 图片处理 | Pillow | 缩放、PNG/JPEG/WebP、压缩非常成熟 |
| 录屏 | FFmpeg `ddagrab` | Windows Desktop Duplication，性能远优于 Python 逐帧抓取 |
| 视频编码 | FFmpeg `h264_mf` | Windows Media Foundation，可软编/硬编 |
| 快捷键 | Win32 `RegisterHotKey` + ctypes | 真正系统级快捷键，不依赖 keyboard/pynput |
| DPI | Per-Monitor DPI Awareness V2 | 125%、150%、双显示器坐标不会乱 |
| 配置 | JSON | 便携版不写注册表 |
| 打包 | `pyside6-deploy` / Nuitka standalone | 官方 PySide6 部署路线，适合免安装便携包 |
| FFmpeg | `bin/ffmpeg.exe` | 独立封装，不要求电脑安装 FFmpeg |

PySide6 是 Qt 官方 Python Binding，自带系统托盘、透明窗口等桌面能力。:chatgpt-content-reference{index="0"}

截屏我反而**不建议第一版上 OpenCV + DXCam**。DXCam 很强，适合高 FPS 游戏捕获，但会引入 NumPy 等额外依赖。普通桌面截屏用 MSS 已经足够，而且 MSS 当前 Windows 后端直接支持区域捕获和鼠标捕获。:chatgpt-content-reference{index="1"}

---

# 二、核心产品体验

启动 `ScreenLite.exe` 后：

**没有大窗口一直挂着。**

右下角托盘出现一个小图标，程序后台等待快捷键。

我建议默认：

| 快捷键 | 功能 |
|---|---|
| `Ctrl + Alt + A` | 截图 |
| `Ctrl + Alt + R` | 开始区域录屏 |
| 再按 `Ctrl + Alt + R` | 停止录屏 |
| `Esc` | 取消当前操作 |

快捷键可以在设置里修改。

这里不要使用 Qt 的普通 `QShortcut` 做全局快捷键，而是直接调用 Windows `RegisterHotKey()`，它就是系统范围快捷键 API，并支持 `MOD_NOREPEAT` 避免按住键连续触发。:chatgpt-content-reference{index="2"}

---

# 三、截图交互设计

按：

**Ctrl + Alt + A**

整个桌面轻微变暗。

鼠标拖动：

```text
┌───────────────────────────┐
│                           │
│       选中区域             │
│                           │
│                1280×720   │
└───────────────────────────┘
           ↓
  复制  保存  尺寸  格式  压缩
```

选区设计一定不要只做“鼠标拉个框就保存”。

要支持八个拖动控制点：

```text
●────────●────────●
│                 │
●                 ●
│                 │
●────────●────────●
```

并支持鼠标拖动整个区域。

鼠标靠近边缘时改变 Cursor。

键盘支持：

```text
方向键       移动 1 px
Shift+方向键 移动 10 px
Enter        确认
Esc          取消
```

右下角实时显示：

```text
X: 426
Y: 215
1280 × 720
```

这个小细节非常影响工具的专业感。

---

# 四、截图完成后不要弹大窗口

截图后选区旁出现一个轻量浮动工具条：

```text
┌────────────────────────────────────┐
│ 📋复制  💾保存 │ 原始 ▼ │ PNG ▼ │ ●•• │
└────────────────────────────────────┘
```

默认行为我建议：

**截完立即复制到剪贴板。**

这样聊天、微信、Word、钉钉、QQ 里面可以直接：

`Ctrl + V`

同时右下角弹一个非常小的 Toast：

```text
截图已复制

1280 × 720
保存
```

不要弹 QMessageBox。

---

# 五、“不同像素导出”这样设计最好

不要给普通用户显示复杂参数。

尺寸菜单：

| 模式 | 行为 |
|---|---|
| 原始尺寸 | 100% |
| 75% | 宽高 ×0.75 |
| 50% | 宽高 ×0.5 |
| 25% | 宽高 ×0.25 |
| 长边 1920 | 等比缩放 |
| 长边 1280 | 等比缩放 |
| 长边 720 | 等比缩放 |
| 自定义 | 输入宽高 |

比如截图：

```text
2536 × 1440
```

选：

```text
长边 1280
```

自动得到：

```text
1280 × 727
```

绝不拉伸变形。

缩放使用 Pillow 的高质量 LANCZOS。

Pillow 当前本身就支持高质量 resize 和 WebP/JPEG 等格式。:chatgpt-content-reference{index="3"}

---

# 六、图片压缩我帮你直接定参数

用户不要面对“JPEG subsampling、WebP method”这种参数。

界面只显示：

```text
无损
高清
均衡       ← 默认
极致压缩
```

后台对应：

| 模式 | 格式 | 参数 |
|---|---|---|
| 无损 | PNG | optimize=True |
| 高清 | WebP | quality=92, method=4 |
| 均衡 | WebP | quality=82, method=4 |
| 极致压缩 | WebP | quality=68, method=6 |

另外保存格式可以手动选：

```text
PNG
JPG
WebP
```

如果选择 JPG：

```text
高清：quality 95
均衡：quality 88
压缩：quality 75
```

Pillow 的 WebP `quality` 为 0–100，并支持 `method=0~6` 控制速度/压缩率，非常适合这种工具。:chatgpt-content-reference{index="4"}

---

# 七、录屏不要让 Python 自己逐帧处理

这是整个项目最重要的架构选择。

不要这样：

```text
Python
 ↓
抓屏
 ↓
numpy frame
 ↓
Python循环
 ↓
ffmpeg stdin
```

1080P RGB：

```text
1920 × 1080 × 3 × 60
≈ 373 MB/s
```

光 Python 和进程之间搬数据就已经很浪费。

正确路线：

```text
PySide6
   │
   │ 选择录屏区域
   ↓
RecorderService
   │
   │ 启动
   ↓
FFmpeg
   │
Desktop Duplication API
   ↓
GPU / Windows
   ↓
H.264
   ↓
MP4
```

FFmpeg 当前原生的 `ddagrab` 就是使用 Windows Desktop Duplication API，可以直接指定：

```text
monitor
x
y
width
height
framerate
cursor
```

官方文档明确支持：

```text
video_size
offset_x
offset_y
framerate
draw_mouse
```

甚至直接给出了 NVENC 捕获示例。:chatgpt-content-reference{index="5"}

这非常适合你的工具。

---

# 八、录屏体验

按：

```text
Ctrl + Alt + R
```

同样出现截图选区。

选完之后出现：

```text
┌────────────────────────────────────────┐
│ 1280×720 │ 30 FPS │ 原始 ▼ │ 均衡 ▼ │ ● REC │
└────────────────────────────────────────┘
```

点击：

```text
● REC
```

可以选择：

```text
立即录制
3秒倒计时
```

我建议默认 3 秒。

录制开始：

```text
3
2
1
```

然后浮动面板变成：

```text
● 00:01:28     ■ 停止
```

这里第一版**暂时不要做暂停**。

暂停比看起来麻烦，因为需要处理时间戳或者多片段合并。先把录制和停止做到绝对稳定，再加暂停。

---

# 九、一个很漂亮的 Windows 技巧

录屏时用户需要看到：

```text
● REC  00:32
```

但是这个控制条不能被录进去。

Windows 本身提供：

```text
SetWindowDisplayAffinity(
    hwnd,
    WDA_EXCLUDEFROMCAPTURE
)
```

微软甚至明确把“视频录制控制窗口不出现在捕获中”作为这个 API 的使用场景之一。Windows 10 2004 起支持 `WDA_EXCLUDEFROMCAPTURE`。:chatgpt-content-reference{index="6"}

所以浮动控制条可以：

**用户看得见，录出来的视频看不见。**

这个细节会让软件一下子有成品感。

---

# 十、视频分辨率

不要写死：

```text
1080P
720P
480P
```

因为用户可能选的是：

```text
1337 × 624
```

所以定义成：

```text
原始
最大 1080P
最大 720P
最大 480P
75%
50%
自定义
```

例如区域：

```text
2560 × 1440
```

选择：

```text
最大 1080P
```

输出：

```text
1920 × 1080
```

如果区域：

```text
1000 × 600
```

选 1080P：

默认：

```text
1000 × 600
```

**不要主动放大。**

否则浪费体积且画质不会提高。

FFmpeg 的 `scale` 本身支持保持纵横比并按倍数约束尺寸。:chatgpt-content-reference{index="7"}

---

# 十一、视频压缩参数

界面仍然只给四个档位：

| 档位 | H.264质量 | 用途 |
|---|---:|---|
| 超清 | 90 | UI演示 / 教程 |
| 高清 | 82 | 高质量录屏 |
| 均衡 | 72 | 默认 |
| 小体积 | 58 | 分享 |

推荐默认：

```text
MP4
H.264
30 FPS
均衡
```

录教程、软件操作：

**30FPS 已经够。**

只有游戏、动画或快速拖动才需要：

```text
60FPS
```

FFmpeg 当前提供 Windows Media Foundation 的：

```text
h264_mf
hevc_mf
av1_mf
```

其中 `h264_mf` 支持软件和硬件编码，并有 `quality 0~100`、`rate_control`、`hw_encoding` 参数，非常适合我们的四档 UI。:chatgpt-content-reference{index="8"}

所以 RecorderBackend 可以自动探测：

```text
h264_mf hardware
        ↓失败
h264_mf software
        ↓失败
备用编码器
```

用户完全不需要知道这些。

---

# 十二、第一版不建议做系统音频

第一版目标应该是：

> 把截图 + 区域录屏做到非常顺滑。

先不加入：

```text
系统声音
麦克风
摄像头
GIF
OCR
标注画笔
滚动截图
```

这些非常容易让项目膨胀。

我建议 V1 完成以后再加入：

```text
麦克风录音
系统音频
箭头/矩形/文字标注
GIF录制
窗口智能识别
OCR
```

尤其“系统音频”不要一开始就加，会明显增加兼容性测试工作量。

---

# 十三、多显示器和 125%/150% 缩放一定要一开始解决

这是截图程序最常见的大坑。

比如：

```text
显示器1
1920×1080
100%

显示器2
2560×1440
150%
```

如果 DPI 没处理好：

鼠标框出来的位置和真正截图位置会错几十甚至几百像素。

程序启动、创建 QApplication 之前就设置：

```text
Per Monitor DPI Awareness V2
```

Windows 官方推荐 `SetProcessDpiAwarenessContext`，Per-Monitor V2 会让每个顶层窗口正确响应不同显示器 DPI。:chatgpt-content-reference{index="9"}

这个要求我会直接写进 Codex 的架构约束里。

---

# 十四、UI 我建议走这种风格

不要模仿 OBS。

主窗口控制在大约：

```text
560 × 420
```

视觉类似：

```text
┌──────────────────────────────────────┐
│ ScreenLite                       ─ × │
│                                      │
│  快速操作                            │
│                                      │
│  ┌──────────┐     ┌──────────┐      │
│  │   截图   │     │   录屏   │      │
│  │CtrlAlt A │     │CtrlAlt R │      │
│  └──────────┘     └──────────┘      │
│                                      │
│  保存                                │
│  C:\Users\...\Pictures\ScreenLite   │
│                                      │
│  图片质量     ● 均衡                 │
│  视频质量     ● 均衡                 │
│  视频帧率       30 FPS               │
│                                      │
│  □ 开机启动                          │
│  ☑ 截图自动复制                      │
│                                      │
│                       设置    关于   │
└──────────────────────────────────────┘
```

配色：

```text
背景：#F7F8FA
卡片：#FFFFFF
主文字：#202124
次文字：#70757A
强调色：#4F7CFF
圆角：10~12px
```

按钮不使用大面积渐变。

阴影也尽量轻。

可以支持跟随系统：

```text
Light
Dark
System
```

---

# 十五、程序架构不要让 Codex 写成一个 main.py

我建议目录直接这么定：

```text
ScreenLite/
│
├─ main.py
│
├─ app/
│  ├─ application.py
│  └─ controller.py
│
├─ core/
│  ├─ hotkey_manager.py
│  ├─ monitor_manager.py
│  ├─ dpi_manager.py
│  ├─ single_instance.py
│  ├─ settings_manager.py
│  └─ paths.py
│
├─ capture/
│  ├─ screenshot_service.py
│  ├─ recorder_service.py
│  ├─ ffmpeg_backend.py
│  └─ capture_types.py
│
├─ media/
│  ├─ image_exporter.py
│  ├─ image_compressor.py
│  ├─ video_profiles.py
│  └─ ffmpeg_probe.py
│
├─ ui/
│  ├─ main_window.py
│  ├─ region_overlay.py
│  ├─ screenshot_toolbar.py
│  ├─ recording_toolbar.py
│  ├─ toast.py
│  ├─ settings_dialog.py
│  └─ tray_icon.py
│
├─ native/
│  ├─ win_hotkey.py
│  ├─ win_dpi.py
│  └─ win_capture_exclusion.py
│
├─ resources/
│  ├─ icons/
│  └─ style.qss
│
├─ bin/
│  └─ ffmpeg.exe
│
├─ data/
│  └─ settings.json
│
├─ tests/
│
├─ requirements.txt
└─ README.md
```

这样以后加 OCR、GIF、标注不会把程序结构搞烂。

---

# 十六、程序状态机必须提前定义

这是避免后期大量 Bug 的关键。

截图：

```text
IDLE
 ↓
SELECTING_SCREENSHOT
 ↓
SCREENSHOT_READY
 ↓
EXPORTING
 ↓
IDLE
```

录屏：

```text
IDLE
 ↓
SELECTING_RECORD_AREA
 ↓
COUNTDOWN
 ↓
RECORDING
 ↓
STOPPING
 ↓
FINALIZING
 ↓
IDLE
```

任何时候：

```text
ESC
```

都应该能够安全回：

```text
IDLE
```

绝对不要靠一堆：

```python
is_recording
is_selecting
is_screenshot
is_waiting
```

互相组合判断。

---

# 十七、设置保存

因为这是免安装软件，所以不要默认写：

```text
Windows Registry
```

直接：

```text
ScreenLite/
    ScreenLite.exe
    data/
        settings.json
```

例如：

```json
{
    "screenshot_hotkey": "Ctrl+Alt+A",
    "record_hotkey": "Ctrl+Alt+R",
    "image_format": "webp",
    "image_quality": "balanced",
    "video_quality": "balanced",
    "video_fps": 30,
    "copy_after_capture": true,
    "record_cursor": true,
    "countdown": 3
}
```

非常方便便携。

---

# 十八、免安装打包方案

这里有一个重要区别：

**免安装 ≠ 必须单 EXE。**

我更推荐最终发布：

```text
ScreenLite_Portable.zip
```

解压：

```text
ScreenLite/
 ├ ScreenLite.exe
 ├ ffmpeg.exe
 ├ Qt...
 └ data/
```

然后双击运行。

Qt 官方现在提供的 `pyside6-deploy` 本身就是基于 Nuitka，可以输出 `standalone` 或 `onefile`；官方也将它作为 PySide6 推荐部署方式之一。:chatgpt-content-reference{index="10"}

我建议正式版先：

```text
Nuitka standalone
       ↓
ZIP
       ↓
便携版
```

以后再额外提供：

```text
ScreenLite.exe
```

单文件版本。

这样启动速度、稳定性和调试都更好。

---

# 十九、Codex 不要一次性让它“把软件写完”

这是最关键的一点。

这个项目我建议让 Codex 按下面 7 个阶段开发：

1. **骨架**：创建 PySide6 项目、主窗口、托盘、单实例运行、关闭窗口转入托盘、JSON 设置和日志系统；此阶段完全不做截屏。
2. **系统能力**：加入 DPI Per-Monitor V2、显示器枚举、Win32 全局快捷键，并做一个调试窗口实时显示鼠标物理坐标和所在显示器。
3. **截图系统**：实现多显示器透明遮罩、鼠标拖选、八个调整点、移动选区、尺寸标签、Enter/Esc，再接 MSS 真正抓图和剪贴板。
4. **图片导出**：加入 PNG/JPEG/WebP、尺寸缩放、四档压缩、自动文件名、Toast 和打开文件夹。
5. **录屏系统**：只实现“区域 → 倒计时 → FFmpeg ddagrab → MP4 → 停止”，先不做暂停、声音和复杂编码器。
6. **体验打磨**：加入录制 HUD、`WDA_EXCLUDEFROMCAPTURE`、异常恢复、FFmpeg 崩溃处理、硬件编码探测、快捷键冲突提示。
7. **发布测试**：多显示器、100/125/150/200% DPI、1080P/2K/4K、30/60FPS、锁屏、休眠、显示器插拔，并用 Nuitka standalone 生成 Portable ZIP。

Codex 每完成一个阶段：

**你自己使用 10 分钟，再进入下一阶段。**

不要连续让它写 30 个文件然后最后才运行。

---

# 二十、给 Codex 的项目总指令

你可以先把下面这段放进项目根目录的 `AGENTS.md`，以后 Codex 每次工作都按照它来：

```text
# ScreenLite Development Guidelines

You are developing ScreenLite, a lightweight portable Windows screenshot
and screen-recording utility.

Target:
- Windows 10/11 x64
- Python 3.12
- PySide6 Widgets
- Portable / no installer
- Simple, fast and polished UX

Primary goals:
1. Very low idle CPU usage.
2. Fast screenshot activation.
3. Correct behavior on multi-monitor systems.
4. Correct behavior at 100%, 125%, 150%, 175% and 200% DPI.
5. Minimal and comfortable UI.
6. Stable screen recording.
7. Clear modular architecture.

Technology:

UI:
- PySide6 Widgets
- QSS styling
- QSystemTrayIcon

Screenshot:
- MSS
- Pillow

Video recording:
- FFmpeg subprocess
- Windows Desktop Duplication / ddagrab
- MP4 / H.264

Windows native integration:
- ctypes
- RegisterHotKey
- SetProcessDpiAwarenessContext
- SetWindowDisplayAffinity

Configuration:
- JSON
- Do not use Windows Registry for normal settings.

Architecture rules:

Do NOT put application logic into UI widgets.

Use separate services:
- HotkeyManager
- MonitorManager
- ScreenshotService
- RecorderService
- ImageExporter
- SettingsManager
- FFmpegBackend

UI communicates with services through Qt signals/slots.

Never block the Qt main thread.

All FFmpeg operations must use QProcess or a worker mechanism.

Recording must not pass every captured frame through Python.

Use FFmpeg native desktop capture.

The application must have an explicit application state:
IDLE
SELECTING_SCREENSHOT
SCREENSHOT_READY
SELECTING_RECORD_AREA
COUNTDOWN
RECORDING
STOPPING
FINALIZING

Do not represent these states using multiple boolean variables.

Region selection requirements:
- translucent fullscreen overlay
- multi-monitor support
- draggable region
- 8 resize handles
- size indicator
- keyboard fine adjustment
- Enter confirms
- Escape cancels

Screenshot export:
- PNG
- JPEG
- WebP

Image resize:
- original
- 75%
- 50%
- 25%
- long edge 1920
- long edge 1280
- long edge 720
- custom

Recording:
- original resolution
- max 1080p
- max 720p
- max 480p
- 75%
- 50%
- custom

FPS:
- 30 default
- 60 optional

Video quality:
- Ultra
- High
- Balanced
- Small

Default:
- H.264
- MP4
- 30 FPS
- Balanced

Do not implement microphone, system audio, OCR, GIF,
scroll capture or annotation in the first version.

Every feature must:
1. handle errors
2. log failures
3. clean up native resources
4. restore application state to IDLE after failure

Code requirements:
- type hints
- dataclasses where appropriate
- small classes
- clear naming
- no giant main.py
- no giant QWidget classes
- no unnecessary third-party dependencies

Before changing architecture, explain why.

When implementing a feature:
first inspect existing code,
then provide a short plan,
then modify the smallest reasonable number of files,
then run relevant tests.
```

这个 `AGENTS.md` 对 Codex 很重要，因为它可以避免项目做到后面变成“哪里需要功能就往哪里塞代码”。

---

## 二十一、第一版功能边界

我建议 **V1.0 就做到这里为止**：

```text
托盘后台运行

Ctrl+Alt+A
区域截图
选区二次调整
剪贴板
PNG/JPEG/WebP
尺寸转换
图片压缩

Ctrl+Alt+R
区域录屏
30/60FPS
尺寸转换
H264 MP4
四档压缩
录制时间显示
停止录制

多屏
高DPI
配置保存

Portable免安装
```

只要这些功能打磨好，已经是一个非常实用的软件。

最重要的是：

> **功能可以少，但每次按快捷键都必须顺滑。**

不要第一版就做成“小 OBS”。

Python + PySide6 的包体不会小到几 MB，特别是再带 FFmpeg；但它可以做到**运行轻量、后台几乎零 CPU、开发维护成本低、UI 体验明显好于 Tkinter 类方案**。如果未来这个工具真的长期使用或准备商业发布，再考虑把捕获核心换成 C++/Rust 都来得及。

我下一步可以直接做两件事之一：**我可以给你整理“Codex 第一阶段到第七阶段的完整逐步 Prompt”，让你一条条复制给 Codex 开发；或者我可以直接按上面的架构开始生成 ScreenLite 的第一版项目骨架和核心代码。**
