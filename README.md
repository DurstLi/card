# Card iOS 启动诊断

更新：2026-10-21。诊断工作流显示名为 **Card iOS - startup diagnostic build 2**，ID 为 `unity-ios-diagnostic`，产物为 `Card-diagnostic.ipa`，应用构建号为 **2**。

## 已处理的配置

- 通过 Unity API 设置自动旋转，仅允许左右横屏；导出后明确写入 iPhone、iPad 的两个横屏方向。
- iOS 图标沿用安卓的 `Assets/UI素材/icon.png`，补齐所有 Unity iOS 图标槽位，并导出包含 iPhone、iPad、App Store 的 18 项图标目录。
- 导出图标去掉透明通道，透明处铺深灰底。原图是 128×128，大尺寸清晰度受限；本次没有重绘图案。
- `Assets/Editor/IosBuildConfiguration.cs` 在后续 iOS 构建后自动处理导出；现有导出也可用菜单 `Build → iOS → Apply settings and icons to existing export` 更新。
- `tools/Prepare-IosUpload.ps1` 打 ZIP 前检查方向声明与图标，避免把旧的空配置再次上传。

## 1. 准备上传内容

本地上传仓库目录：`D:\wb\wsrc\Card\build\ios-upload`。

如果已经使用本次准备好的导出及 ZIP，可直接进入第 2 步。以后修改游戏内容时，用 **Unity 2022.3.14f1c1** 打开项目：

1. `File → Build Settings → iOS → Switch Platform`。
2. `Build → iOS → Export Xcode for Codemagic`，等待导出成功。
3. 在 PowerShell 执行：

```powershell
Set-Location D:\wb\wsrc\Card
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Prepare-IosUpload.ps1
```

上传目录至少应包含 `ios-export.zip.part001` 等分片、`ios-export.parts.json`、`IosExportArchive.py`、`codemagic.yaml`、`codemagic-diagnostic.yaml`、`Prepare-IosDiagnostic.py`。本地仍保留完整 ZIP。ZIP 根目录应直接包含 `Unity-iPhone.xcodeproj`、`Data`、`Libraries` 等内容。

## 2. 提交并推送构建仓库

在 PowerShell 执行，把**本次配置和更新后的诊断脚本**一并上传。只推旧 ZIP 或只更新 YAML 都不够。

```powershell
Set-Location D:\wb\wsrc\Card\build\ios-upload
git status --short
git add .gitignore ios-export.zip.part* ios-export.parts.json IosExportArchive.py codemagic.yaml codemagic-diagnostic.yaml codemagic-unsigned.yaml Prepare-IosDiagnostic.py README.md
git commit -m "Fix iOS orientation and icons; prepare startup diagnostic build 2"
git push origin main
```

GitHub LFS 额度已满，本次改为普通 Git 分片，每片最多 90 MiB。Codemagic 先核对各片及整包 SHA256，再还原 ZIP；不再请求 LFS。完整 ZIP 仅留本地，不提交。需要 Git 推送成功；本地修改完成不表示云端已经更新。

## 3. 在 Codemagic 选择诊断工作流

1. 打开现有 Card 构建应用，开始新构建。
2. 选择刚推送的 `main` 最新提交。
3. 选择 **Card iOS - startup diagnostic build 2**（ID：`unity-ios-diagnostic`）。默认配置第一个工作流是普通 `unity-ios-development`，不会采集此次诊断日志。
4. 沿用已有开发签名材料：证书引用 `card_client_development`、描述文件引用 `card_client_profile`。Bundle ID 保持 `com.sakasaka.wstools`。
5. 成功后从 Artifacts 下载 **Card-diagnostic.ipa**。不要再次安装原来的 `Card-development.ipa`。
6. 若构建失败，下载 `xcode-signed.log` / `xcode-export.log`，保留第一条编译或签名错误。

这个过程在 Mac 云端编译并签名。Windows 本地成功导出、脚本检查通过，都不能代替 Xcode 编译和真机启动验证。

## 4. 安装并复现

1. 使用爱思或现有安装工具，把新下载的 `Card-diagnostic.ipa` **覆盖安装**到原测试手机，不要先卸载。
2. 保持现有开发签名，不用另一个免费 Apple ID 重签。手机应是现有描述文件授权的测试设备。
3. 打开 Card 一次。如果仍然退出，保留应用，不要卸载、清理数据或反复启动。
4. 记录是否还闪退、是否看到 Unity 启动画面或开始界面。

## 5. 导出日志

诊断版会把原生启动日志写到应用 Documents，最多 4MB；每次启动保留上次日志：

- `Card-startup.log`
- `Card-startup.log.previous`（如果存在）

可尝试在 iPhone“文件 → 浏览 → 我的 iPhone → Card”找到日志；或通过爱思的应用文件共享、支持 iOS 文件共享的电脑工具导出。普通 development 旧包没有这项文件日志能力，必须先安装本次诊断版。

把日志文件原文提供给后续排查。即使应用不再闪退，也保留这次成功日志，以便对比。

## 日志会提供什么

开头应出现 `Card diagnostic build 2: native startup begins`。随后记录应用版本、iOS 版本、关键 Data 文件是否存在及大小、Unity 原生日志和下列阶段：

| 标记 | 含义 |
| --- | --- |
| `native-runtime: begin/complete` | Unity 原生运行时初始化 |
| `register-features: begin/complete` | 注册原生功能模块 |
| `engine-no-graphics: begin/complete` | IL2CPP 和无图形引擎初始化 |
| `graphics: begin/complete` | 图形设备初始化 |
| `first-scene: begin/complete` | 加载应用和首场景 |

例如有 `engine-no-graphics: begin` 而没有对应 `complete`，就能把退出位置缩小到该调用内；仍应结合真实错误正文判断具体原因，不能把阶段标记当作完整调用栈。

若没有任何日志文件，先确认下载的是此次最新提交的诊断包，以及云端执行过 `Prepare native startup diagnostics`。若文件存在但仍没有足够错误信息，下一步连接 macOS/Xcode 抓控制台并对 `exit` 设置断点。

日志仅写到本机，不自动上传网络。方向和图标补齐后，仍需实机确认启动退出是否解决；附近商店的 iOS 城市解析需要另外实现。
