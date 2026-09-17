# 开发记录

## 2026-09-17 · 准备
- 当前目录为空；Python 3.12 可用；已验证 GitHub 账号 amateurish-programmer。
- 完整 ChatGPT 对话读取遇到 Cloudflare，浏览器连接失败；已提供预览作为需求依据。
- 用户要求自动推进和阶段提交，执行时不重复请求确认。
- GitKraken 工具未提供，使用 Git CLI。现有 GPG 配置不可用；使用仅本仓库的 SSH 签名，不修改全局设置、不上传认证密钥。
- 采用 PySide6-Essentials 降低 Qt 模块数量；便携包使用 PyInstaller onedir，以便直接验证可运行产物。

## 阶段 1 完成
- HTML 规格、计划、Python 3.12 环境、私有远程仓库已建立。
- 配置恢复、尺寸换算与负坐标基础测试：6 passed。
- 使用仓库专用 SSH 提交签名；GitHub 未登记此签名公钥，因此不宣称 Verified。
