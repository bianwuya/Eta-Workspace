# ETA Windows 开发工作区

源码：`F:/eta/projects/eta-dev`。打开 `F:/eta/eta.code-workspace` 使用现有 VS Code；Codex 可直接在源码目录工作。双击 `开发终端.cmd` 进入已配置终端。没有安装 Android Studio，没有修改系统 JAVA_HOME/PATH。

## 常用命令

```powershell
# 从任意 PowerShell 运行，默认加载原签名
F:/eta/eta-gradle.ps1 :app:compileDebugKotlin --console=plain
F:/eta/eta-gradle.ps1 :app:testDebugUnitTest --console=plain
F:/eta/eta-gradle.ps1 :app:lintDebug --console=plain
# 构建需要独立验证签名/产物，默认不会安装
F:/eta/eta-gradle.ps1 :app:assembleDebug :app:assembleRelease --console=plain
```

环境为 JDK 25.0.5.0.3、Gradle 9.7.1、SDK Platform 37.0，官方 Windows build-tools 36.0.0/37.0.0。Gradle 依赖及配置缓存保存在 `toolchains/gradle-home`；后续增量构建复用。现有手机 ARM64 分级构建器没有冒称已移植，Windows 使用直接 Gradle 入口。终端原生库重编脚本仍只支持 Linux/macOS；现有 jniLibs 可参与常规构建。

## 数据和源码迁移证据

用户数据在 `phone-data/eta-latest-20261108-2220`，保留原始 tar、数据库/WAL、记忆、Skill、WebView、配置、日志、通信文件及本轮 App 文件。未重复复制 Debian rootfs，先前完整 6.62 GB 私有目录归档仍保留。复制期间用 SIGSTOP/SIGCONT 短暂停住 ETA 主进程及 voice 进程，结束后已确认进程恢复。手机原件未删除。

- SQLite quick_check：三个数据库均为 `ok`。
- 89 个会话、27,065 条消息、89 个上下文检查点、10,040 个文本分块、4,954 条子 Agent 请求统计。
- 前次快照 26,434 条消息，本次增加 631 条；保留所有会话，不仅增量片段。
- 五个对话相关表完整 JSONL 在 `conversation-records/`，原始数据库仍在 `app-state/databases`；未将私密内容输出到聊天。
- 原始源码/Git/资产归档 `development.tar` 已保留。开发树基于手机 `local` 的 `8f0228ca728981cd5d4ad7abbaa741c17c143b95`，保留未提交压缩逻辑/测试改动。1,297 个源码文件逐字节核对一致；仅 AGENTS 添加 Windows 路径说明。
- 归档 SHA256、数据库核验和源码比对在快照目录的 `manifest.json`、`database-verification.json`、`source-verification.json`。

原签名密钥保留在 `projects/eta-local/keystore`，加载入口不会回显口令。证书 SHA256 已实读，与原记录一致：`A7:A9:2C:CA:03:F7:D7:39:0A:B7:40:01:C9:7E:FB:FE:4F:F4:28:9B:0D:C4:FF:A2:1D:6E:BC:3C:EE:1C:81:A8`。本地 Git 钩子已用 Git Bash 实跑；未提交或推送。

## 验证状态

- Java、Gradle、aapt2 实际运行通过；JDK/Gradle/SDK 下载归档按官方摘要核验。
- Gradle `help`：`BUILD SUCCESSFUL`，配置缓存已保存，日志 `windows-gradle-help.log`。
- 当前源码主 Kotlin/Java 与测试源码编译通过；三组压缩/恢复单测实际运行 21 项，0 失败/错误/跳过。成功日志 `windows-build-validation-local-2.log`，汇总 `windows-test-summary.json`。首次在线构建在 Maven HEAD 返回 429 时失败，离线解析也因 Gradle 元数据未登记失败，均保留日志。
- 为解决这一项已证实的限流，`tools/windows-dependencies.init.gradle` 只把 `org.robolectric:nativeruntime-dist-compat:1.0.19` 路由到本地 Maven 缓存；其官方 JAR 按 Maven 公布 SHA1 校验，原始 POM 一并复制，未修改内容/版本。日常 `eta-gradle.ps1` 已接入；其他依赖继续按项目官方仓库解析。没有关闭配置缓存或测试。
- 本轮只验证环境、编译和对应 21 项测试；未运行完整单测/Lint、未交付双包、未安装 APK，不代表手机上的具体问题已修复。
- 手机在迁移结束后 ADB 断开；尚未迁入其 Gradle modules 缓存，Windows 当前从官方仓库建立自己的缓存。环境构建不依赖手机在线；以后设备调试需要重新连接。

本地数据与密钥不要提交或上传。Android Keystore 的硬件密钥不会因复制 App 数据而变成 Windows 可用凭据。没有安装/卸载手机 App，也没有清理其工作区。
