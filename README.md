# ETA Windows 工作区开发全景指南

欢迎使用 ETA Windows 统一开发工作区。本工作区已完成目录扁平化与中文语义重构，兼顾人类日常操作直达与 AI Agent 自动化维护。

---

## 一、 核心工作目录全景表

| 序号与中文目录 | 兼容映射路径 | 角色与定位 | 开发者操作建议 |
|---|---|---|---|
| **`01-核心开发源码`** | `projects/eta-dev` | **当前活跃 Android 开发工程**（Kotlin/Compose，分支 `local`） | ⭐️ **日常代码编辑与开发全部在此目录进行** |
| **`02-工程知识库`** | `projects/eta-local` | **AI 知识主库、签名密钥与工程规则**（含 keystore、rules、skills） | 查看架构决策、经验法则或修改配置规约 |
| **`03-上游基线仓库`** | `projects/eta` | **上游镜像与多分支历史参考**（含全量分支与历史提交） | 仅作参考对照或追溯历史，**日常切勿在此直接修改** |
| **`04-手机备份数据`** | `phone-data` | **手机原始数据归档**（7.65GB，含 SQLite 对话数据库、JSONL 快照） | 仅供离线排查或数据还原，免管免动，严禁提交 |
| **`05-本地构建工具链`** | `toolchains` | **Windows 离线构建套件**（4.33GB，含 JDK 25、Android SDK 37、Gradle 9.7） | 环境脚本自动调用，无需手动操作，严禁提交 |
| **`06-环境运维工具`** | `tools` | **环境初始化、数据提取与 Git 钩子脚本** | 包含 Windows 依赖分发与构建辅助工具 |
| **`07-构建与运行日志`** | `logs` | **历史编译、下载与测试日志归档** | 追溯以往构建验证记录与测试摘要 |
| **`08-历史归档与交接`** | `archive` | **历史电脑 F2 交接包与专项调查目录** | 存档资料，日常开发无需关注 |

> **提示**：工作区同时通过 NTFS 目录联接（Junction）保留了原英文路径映射（`projects/eta-dev`、`toolchains` 等），磁盘空间零额外占用，保证老脚本、旧工具与外部调用 100% 兼容。

---

## 二、 人类开发者极简上手

### 1. 启动开发终端
- **方式一（推荐）**：双击根目录的 **`开发终端.cmd`**，自动设置好 JDK 25 和 Android SDK 环境变量，并直接进入 `01-核心开发源码`。
- **方式二（VS Code）**：用 VS Code 打开根目录的 **`eta.code-workspace`**，所有工程已按中文语义分栏展示，内置终端自动加载环境变量。

### 2. 多端云端源码与隔离构建（推荐统一入口）

云端拉取、审查材料、Linux 编译/测试/Lint/组装、Windows 仅原签名统一使用：

```powershell
$flow = 'F:\eta\06-环境运维工具\eta-cloud-flow\eta-cloud-flow.ps1'
# 查看本地提交的执行计划，不构建、不签名
pwsh -NoProfile -File $flow `
  -SourceRepo 'F:\eta\projects\eta-night-20261118\worktree' -Ref HEAD -Mode compile -CheckOnly
# 拉取云端分支并在 Linux 编译
pwsh -NoProfile -File $flow `
  -Branch 'night/v344-to-main-20261118' -Mode compile
```

完整模式、缓存策略和输出说明见 `06-环境运维工具/eta-cloud-flow/README.md`。该入口不自动提交、推送或安装。

AI 在隔离开发工作树完成明确文件修改后，使用 `06-环境运维工具/eta-ai-delivery/eta-ai-delivery.ps1` 执行任务级“显式文件提交 → 完整验证/组装 → 非强推开发分支 → 远端 SHA 读回”；失败保留本地提交但不推送，详见该目录 `README.md`。

工作区约束、项目 Skill 和流程工具通过 `06-环境运维工具/eta-workspace-sync/eta-workspace-sync.ps1` 净化同步到 `https://github.com/bianwuya/Eta-Workspace` 的 `sync` 分支。其他设备执行 `git clone --branch sync --single-branch https://github.com/bianwuya/Eta-Workspace.git` 即可一并拉取；不包含密钥、私有备份或 APK。

### 3. 本机核心树的 Windows 补充构建命令

专用 WSL2 Linux 环境仍是常规编译、单测与 Lint 的优先入口；以下命令保留给本机核心树补充检查或既有签名流程：

```powershell
# 1. 编译 Debug Kotlin 源码（快速语法与编译检查）
F:/eta/eta-gradle.ps1 :app:compileDebugKotlin --console=plain

# 2. 运行单测
F:/eta/eta-gradle.ps1 :app:testDebugUnitTest --console=plain

# 3. 运行代码检查 (Lint)
F:/eta/eta-gradle.ps1 :app:lintDebug --console=plain

# 4. 全量装配 Debug 与 Release APK（自动加载 02-工程知识库 中的正式签名）
F:/eta/eta-gradle.ps1 :app:assembleDebug :app:assembleRelease --console=plain
```

---

## 三、 重要安全与边界约定

1. **代码修改唯一入口**：日常所有 Bug 修复、特性开发必须在 **`01-核心开发源码`** 中进行。
2. **两座重资产大山（免管免提交）**：
   - `04-手机备份数据`（7.65GB）和 `05-本地构建工具链`（4.33GB）属于本地环境和备份，绝不要纳入任何 Git 仓库提交或上传。
3. **签名保护**：`eta-signing.ps1` 会自动在进程内存中安全读取 keystore 凭据，不会在控制台或日志中回显口令。
4. **可视化全景导航**：双击打开根目录的 **`工作区全景导航.html`**，可以在浏览器中以可视化拓扑树与卡片的形式查看所有目录与路由关系。