# Windows 与 WSL2 开发入口

当前源码 `F:/eta/01-核心开发源码`，知识与维护 Skill 在 `F:/eta/02-工程知识库`。兼容别名 projects/eta-dev、projects/eta-local 仍可用。2026-11-15 用户指定：编译、单测、Lint 优先专用 WSL2 `Eta-Test-20261112`；Windows 用于签名双包及补充检查。

## 按任务选环境

| 工作 | 入口 | 约束 |
|---|---|---|
| Kotlin 编译、单测、Lint | WSL2 Eta-Test-20261112，eta-test 用户，ext4 受控树 | 根 F:/eta/AGENTS.md 第3节维护完整命令；含 WIP 同步，排除缓存/build/local.properties |
| 固定 t00 / integration 单测快照 | 测试环境计划目录的 run-env.ps1 | 它只测试既定 Linux 快照，不会自动同步当前 Windows WIP；结果不得冒称当前源树通过 |
| 原签名标准 Debug/Release | F:/eta/eta-gradle.ps1 | 不输出签名口令；构建不自动安装 |
| 文档、索引、Skill 维护 | 文件差异、链接/JSON、对应离线脚本测试 | 不编 APK、不重启 Eta，不为整理重跑业务测试 |

完整 WSL2 命令只在根 AGENTS 维护，避免复制后漂移。同步当前受控树到 /opt/eta/trees/<name>，不改 Windows 树 local.properties 或污染其 build。Linux 的 sdk.dir=/opt/eta/sdk；运行时 JDK25.0.2、Gradle9.7.1 与缓存由现有环境提供，不另搭工具链。

Windows 打包示例：

```powershell
F:/eta/eta-gradle.ps1 :app:assembleDebug :app:assembleRelease --console=plain
```

Windows 入口加载 eta-signing.ps1，在进程环境安全读取本机原 keystore；不能输出环境或口令。实际签名仍须 apksigner 验证。手机 eta-local-dev.py 与 ARM64 init 脚本不能在 Windows/WSL x86 环境直接套用。

## 当前手机与旧路径

手机新的共享工程根是 Android `/data/local/tmp/eta`；其逻辑 Linux 路径通常为 `/workspace`，必须核实本次终端 namespace 的挂载，不能只凭历史 bind 声明。2026-11-16 在 ADB Root namespace 中旧 /workspace/projects/eta-local 未找到；当前手机根主要是相机、环境与工作区维护工程，不是电脑 Eta 源码仓副本。

安装的手机 Skill 在 `/data/user/0/io.github.mangi.eta/files/skills`。文件、App身份可读、原生列表发现、正文/资源加载分开核实；没有原生工具时明确未验，不强停应用刷新。手机方法的本机适用版本见维护 Skill 的 WORKSPACE-MAINTENANCE 参考。

## 本次迁移现场（2026-11-08 历史）

- 新增用户数据：`F:/eta/phone-data/eta-latest-20261108-2220/app-state.tar`；已展开为 `app-state/`，数据库完整性与数量见 `database-verification.json`。
- 对话表 JSONL：同目录 `conversation-records/`，含消息、文本分块、压缩检查点和会话状态；原数据库/WAL 保留。
- 源码/Git/工程资产原始归档：同目录 `development.tar`。当前开发树来自手机 local worktree，基线 `8f0228ca728981cd5d4ad7abbaa741c17c143b95`，未提交压缩逻辑与测试修改已保留，未提交/推送。
- 上一轮完整应用私有目录含 Debian 环境的归档仍在 `F:/eta/phone-data/eta-io.github.mangi.eta-2026-11-08/app-private-full.tar`。本轮用户数据快照仅排除未变更用途的 `files/terminal` Linux rootfs，其他 files/数据库/偏好/缓存/WebView 均复制。
- 数据和密钥保留在本机，不能提交、上传或当作公开测试 fixture。Android Keystore 中的硬件密钥不能靠复制应用文件迁到电脑。

实际配置/编译/测试结果见工作区 `F:/eta/WINDOWS-SETUP.md` 与对应日志：本轮 Kotlin/Java及测试源码编译通过，定向21项测试0失败。官方原生测试库遭遇Maven HEAD 429后，按官方摘要校验的原始JAR/POM在本机Maven目录复用；工作区Gradle入口只为这一模块接入本地仓库，不改项目依赖版本。完整单测/Lint/双包/安装未运行；环境可启动、代码可编译、测试通过、APK安装、用户实机验收是不同结论。
