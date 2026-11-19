# ETA 工作区顶层 Agent 协作契约

本文件是 `F:/eta` 工作区的根级规范。所有在此工作区执行任务的 AI Agent 必须遵守本契约。

---

## 1. 核心目录路由与职责划分

| 物理中文目录 | 兼容别名路径 | 权限级别 | 唯一职责说明 |
|---|---|---|---|
| **`01-核心开发源码/`** | `projects/eta-dev/` | **读写（核心开发）** | **代码变更唯一合法位置**。Eta Android App 主工程（Kotlin/Compose，分支 `local`）。所有代码修改、Bug 修复和测试只能在此目录进行。 |
| **`02-工程知识库/`** | `projects/eta-local/` | **读写（受控）** | **知识主库与签名资产**。包含 `knowledge/`（规则、经验库 LESSONS）、`keystore/`（原包签名密钥）、维护技能 `skills/`。按任务只读命中项，修改仅限文档沉淀与规则更新。 |
| **`03-上游基线仓库/`** | `projects/eta/` | **只读（参考）** | **上游代码与历史镜像**。用于追溯官方提交历史与多分支对照，**严禁在此直接修改代码**。 |
| **`04-手机备份数据/`** | `phone-data/` | **只读（隔离）** | 7.65GB 手机全量数据归档（SQLite 数据库、JSONL 对话记录、私有备份）。含隐私数据，**严禁扫描、修改、提交或上传**。 |
| **`05-本地构建工具链/`** | `toolchains/` | **只读（底层）** | 4.33GB Windows 离线构建链（JDK 25, Android SDK 37, Gradle 9.7）。由脚本内部调用，**严禁修改或提交**。 |
| **`06-环境运维工具/`** | `tools/` | **只读/可扩展** | 包含 Windows 初始化与依赖分发脚本（如 `windows-dependencies.init.gradle`）。 |
| **`07-构建与运行日志/`** | `logs/` | **读写（追加）** | Windows 环境构建验证与测试输出日志归档。 |
| **`08-历史归档与交接/`** | `archive/` | **只读（归档）** | 历史交接归档与专项排查记录。 |

---

## 2. 手机旧环境路径自动映射字典

旧知识文档（源自手机 Debian PRoot）中记录了大量 `/workspace/...` 路径，AI 在 Windows 下必须按以下规则自动转译：

| 手机 Linux 旧路径（文档中出现） | Windows 当前实际物理路径 | 说明 |
|---|---|---|
| `/workspace/projects/eta` | `F:/eta/01-核心开发源码` | 核心 App 源码 |
| `/workspace/projects/eta-local` | `F:/eta/02-工程知识库` | 规则与知识库主源 |
| `/workspace/projects/eta-local/knowledge/` | `F:/eta/02-工程知识库/knowledge/` | 知识条目主源（按 INDEX 命中按需读取） |
| `/workspace/toolchains/...` | `F:/eta/05-本地构建工具链/...` | Windows 对应工具链 |
| `/workspace/scratch/...` | **已废弃** | 手机端历史临时 worktree，不可寻址 |

---

## 3. 构建与验证命令契约（Linux 测试环境最优先）

1. **最优先使用 Linux 测试环境（WSL2 `Eta-Test-20261112`，2026-11-15 用户明确要求）**：
   - 单元测试（`:app:testDebugUnitTest`）、Lint（`:app:lintDebug`）与常规 Kotlin 编译检查，**最优先在专用 WSL2 Linux ext4 环境（发行版 `Eta-Test-20261112`，用户 `eta-test`）运行**，避免 Windows NTFS 下 POSIX 权限、symlink、打开 FD unlink、`/bin/sh`、原生 SQLite 路径和 JDK 25 JCE/Conscrypt 差异导致的假失败。
   - 不得修改 Windows 源码树的 `local.properties` 或污染其 `build/`。验证受控工作树时，将源码（含未提交与未跟踪源码，排除 `.gradle/`、`build/`、`app/build/`、`.kotlin/`、`local.properties`）同步到 Linux ext4 目录 `/opt/eta/trees/<name>`，写入 `sdk.dir=/opt/eta/sdk` 的 `local.properties`，并以 `eta-test` 调用：

```bash
env \
JAVA_HOME=/opt/eta/runtimes/jdk-25.0.2 \
GRADLE_USER_HOME=/opt/eta/cache \
ANDROID_HOME=/opt/eta/sdk \
ANDROID_SDK_ROOT=/opt/eta/sdk \
ANDROID_USER_HOME=/opt/eta/home/android \
TMPDIR=/opt/eta/tmp \
/opt/eta/runtimes/gradle-9.7.1/bin/gradle \
  -I /mnt/f/eta/02-工程知识库/plans/20261112-测试环境与Git权限修复/linux.init.gradle \
  --no-configuration-cache --build-cache --no-daemon --max-workers=1 --console=plain \
  -Pkotlin.compiler.execution.strategy=in-process \
  -Dorg.gradle.java.installations.auto-download=false \
  -Dorg.gradle.java.installations.paths=/opt/eta/runtimes/jdk-25.0.2 \
  "-Dorg.gradle.jvmargs=-Xmx4g -XX:MaxMetaspaceSize=1g -Dfile.encoding=UTF-8" \
  :app:compileDebugKotlin :app:testDebugUnitTest :app:lintDebug --offline
```

   - 固定 `t00` / `integration` 快照可直接运行 `F:/eta/02-工程知识库/plans/20261112-测试环境与Git权限修复/run-env.ps1`。

2. **Windows 构建与签名打包入口（补充/签名交付）**：
   - 在 Windows 环境下，不得调用手机专用的 `eta-local-dev.py` 或 ARM64 host init 脚本；签名打包或仅需 Windows 侧快速编译时使用根目录 PowerShell 入口（不作为优先单元测试环境）：

```powershell
# 编译验证（Windows 补充）
F:/eta/eta-gradle.ps1 :app:compileDebugKotlin --console=plain

# 打包构建（自动安全加载签名）
F:/eta/eta-gradle.ps1 :app:assembleDebug :app:assembleRelease --console=plain
```

---

## 3A. 多端云端源码审查与构建统一主链（2026-11-18）

- 统一入口为 `F:/eta/06-环境运维工具/eta-cloud-flow/eta-cloud-flow.ps1`，详细参数与输出见其 `README.md`。云端分支或本地已提交源码先固定完整 SHA，可生成审查 diff；Linux 在 ext4 隔离快照中依次完成编译、测试、Lint 和双包组装，Windows 只负责 Release 原签名与验签，不再重复运行 Windows Gradle。
- 公开云端源优先使用 Linux 原生裸镜像 `/opt/eta/sources/<repo-key>.git`，分支引用只读绑定到固定提交；Linux 快照复用依赖缓存与 Gradle `--build-cache`，同源以 `flock` 串行，脏快照拒绝覆盖。WSL 不对 `/mnt/f` 仓库执行 Git 热路径 I/O；本地提交或需要 Windows 凭据的私有源使用单次 `git archive` 传输。
- 本地 `SourceRepo` 模式只读取已提交对象，未提交 WIP 不得被悄悄打入产物。该入口不自动提交、推送、开 PR 或安装；自动推送仍只能走现有独立白名单门禁。

---

## 4. 安全与版本控制红线

1. **禁止在根目录执行全量 Git 提交**：各子工程（`01-核心开发源码`、`02-工程知识库`、`03-上游基线仓库`）拥有各自独立的 Git 仓库，Git 操作必须限定在具体子工程内执行。
2. **严禁泄露密钥与私密数据**：`02-工程知识库/keystore` 中的密钥口令由 `eta-signing.ps1` 在内存中加载，严禁输出到聊天记录、文档或日志中；`04-手机备份数据` 严禁读取未脱敏正文输出到聊天。

## 5. 官方优先与重复功能清理（2026-11-12 用户最新决策）

- **唯一设计原则：官方已有的功能直接复用，个人只补充官方不足的边界与体验。** 与官方等价的自制实现必须连同无用接线、旧状态机与失效测试一起精简，不保留第二套重叠机制；能用官方组件/接口就不改写官方核心。
- 官方是否覆盖必须先依据实际上游 SHA、调用链和测试证明，不能因文件名相似就直接删除；审查未完成的项目标记 REVIEW，不盲删。删除在新隔离开发分支实施，不动原 `local` 的未提交修改和上游 `main`。
- 明确保留：中转兼容、主代理及子代理缓存稳定和安全自动接续、子代理实际模型/Token/缓存统计与设置页汇总、可配置压缩模型/提示词、手动优先级和安全降级、独立生图。自制计划模式与多余子代理调度机制依此前用户指令退出，相关修改要做引用与数据兼容清理。
- **唯一细则来源**：`F:/eta/02-工程知识库/knowledge/RULES.md` 的“个人版与代码边界”（最新决策）；Runtime 具体边界见 `F:/eta/02-工程知识库/plans/20261112-Runtime官方优先与中转接续最小增量审查计划.md`。遇到早期“个人魔改优先”的旧条款，以本节最新用户决策为准。

## 5A. 本地直接修复优先与 Codex 派发（2026-11-13）

- **用户最新授权：能由 ChatGPT 通过 Remote Desktop Commander 直接、安全地完成的代码修改，优先在本地受控隔离 worktree 编写，并最优先在 Linux 测试环境（WSL2 `Eta-Test-20261112`）完成本地编译/单测/Lint（签名打包使用 `F:/eta/eta-gradle.ps1`），不必为了简单问题消耗 Codex 的付费额度。** 此许可不扩大删除、安装、推送、合并、付费 API 调用、覆盖原有 WIP 的范围；构建结果必须真实验证。只有明确需要 Codex 原生代理执行、用户特别指定 Codex、或本地直接修改不适合时才派发；此时仍严格遵守以下桌面新会话、前端验收和草稿保护规则。

## 5B. Codex 原生派发链路唯一事实来源（2026-11-12）

- **先读已核实链路，不重复探查**：`F:/eta/02-工程知识库/knowledge/CODEX-DISPATCH-CHAIN.md`；云端长期副本 `https://docs.google.com/document/d/15Q4ya7FnvFYAg_1JbnwS9TMqEHctl45lOoEutC7L20c/edit`。已知 Codex UIA `ValuePattern.SetValue` 对 ProseMirror 无效，外部 app-server thread 不能证明桌面侧栏可见；两条失败派发法禁止重复。现有线程 `queue` 仅同任务继续；新任务必须独立且原生前端可见、不抢用户焦点。无法端到端验证报告 `NOT_DISPATCHED`，不得虚构会话/后台 CLI 冒充。
- **2026-11-13 新增派发前草稿分流**：在任何新任务派发前，通过只读 UIA 读取原生输入框并与历史线程查重，将草稿判为 EMPTY / SAME_TASK / DUPLICATE / VALUABLE_OTHER / AMBIGUOUS；有价值的其他任务草稿不得清空、覆盖或发送。若新聊天仍带着其他草稿，先尝试可验证的不抢焦点独立编辑器；确需暂存并腾挪原草稿，先征得用户对临时备份、编辑器更改及可能焦点操作的明确许可，并在结束后逐字哈希核验恢复。完整规程以 CODEX-DISPATCH-CHAIN.md 最新章节为准，不准只报“有草稿所以无法派发”而不归类、不提出可操作方案。

## 6. 长期前端审美、官方组件与预览审批（2026-11-12）

- **所有 Eta UI 任务首先阅读** `F:/eta/02-工程知识库/skills/frontend-layout/SKILL.md`，按 `references/COMPONENTS.md` 查官方真实 Miuix/COUI 源码，不新造重复组件、不凭 GPT 自由审美重绘。
- 新页面、明显布局或动画变动：先自动设计/自审，再给用户一次集中可视预览；**只有用户明确认可的范围才可实施正式业务 UI**。不改视觉的纯逻辑任务不受此审批阻塞；已认可的官方同类样式按记录复用，不重复询问。
- 动画必须连同 UI 预览（初/中/终帧或真实 Compose Animation Preview）审核；正式版本需有真实截图与过渡/手势验证，不能用 HTML 示意或“编译成功”冒充真机 UI。样板批准记录见 `references/APPROVALS.md`；旧批准截图尚未实际定位不能伪称已保存。
- 本条是 Agent 操作契约，不是运行时访问控制。需要强制技术拦截时另建设计审核状态检查，不擅自改业务源码或安装工具。

## 7. 手机 Eta 工程资料快速对接（2026-11-16）

- 当任务需要查找手机工程、Skill、知识或诊断资料时，使用 `F:/eta/eta-phone.ps1`：先 doctor/pull，再 search/locate/status；手机断开可搜索既有镜像。流程见 `F:/eta/02-工程知识库/knowledge/PHONE-WORKSPACE.md`。
- 镜像与回执位于 `F:/eta/07-构建与运行日志/phone-eta`。它不属于电脑源码/知识主源，不自动合并手机业务修改，也不覆盖04历史私有备份。用户本次范围不含会话、账号或数据库。
- 电脑修改镜像后按明确文件push，默认出计划，--apply才写手机；先比共同基线，冲突另存并显式resolve，删除仅报告。写回保留原文件备份并读回hash；文件同步不等于Eta原生Skill发现/加载已刷新。不启动常驻服务或重启Eta来完成普通对接。

## 8. 跨 AI 的统一工程规则入口与本地交付（2026-11-18）

- **唯一总规范**：本文件 `F:/eta/AGENTS.md` 是 Eta 工作区各 AI（Codex、Claude Code、Gemini CLI、OpenCode，以及通过 Remote Desktop Commander 操作的 ChatGPT）的共同工程约束；实际开始任务时再读**目标仓库/目录最近的 `AGENTS.md`**、`F:/eta/02-工程知识库/knowledge/RULES.md` 中命中的规则及本任务计划。目录 AGENTS 补充具体约束，不可以解除本文件安全要求；若历史计划与用户最新明确要求冲突，以最新明确要求、实时 Git/源码与安全边界为准。若工具没有自动加载本文件，执行者须显式读取，**不得声称已自动生效**。
- **轻量入口而非多套复制**：工作区根 `CLAUDE.md` 与 `GEMINI.md` 仅引用总规范；各实际源码根按需配置独立的 `CLAUDE.md`/`GEMINI.md` 和 OpenCode `opencode.json` 指向此总规范及本仓 `AGENTS.md`。Claude/Gemini 的跨仓导入可能受信任目录或用户许可限制；OpenCode 在 Git 项目根之外不一定自动读取父级 AGENTS，故使用项目配置显式引用。其他 AI 需读取，不以创建入口文件冒充工具已加载。
- **Git 分支职责始终不变**：`main` 仅存官方镜像，`local` 是个人稳定版本；新业务修改、未验证代码、自动同步只能进入明确批准且独立的开发分支/隔离工作树。原 `local` 的已暂存、未暂存及未跟踪 WIP、其他会话工作树均不得擅自提交、清理、覆盖、切换或推送。Git 根目录不执行递归 add/commit/push。
- **AI 修改后自动 GitHub 同步的定义：任务级、而非保存级**。用户已要求每次 AI 修改并构建后自动执行“仅显式文件提交 → 精确提交验证/组装 → 非强推开发分支 → 远端 SHA 读回”，统一调用 `F:/eta/06-环境运维工具/eta-ai-delivery/eta-ai-delivery.ps1`。不得使用文件监视守护进程，不得自动 `git add -A` 或无边界制造提交；上传密钥、账号数据、手机备份、源码外私有资产、APK 或无关 WIP 始终禁止。推送仅指 Git 源码提交，**不等于 GitHub Actions 云端编译、PR 或自动发布**。
- **构建与 Push 门槛**：业务代码提交必须绑定当前实际 SHA，在 WSL2 `Eta-Test-20261112` ext4 隔离快照执行编译、完整单测、`lintDebug` 与双包组装；Windows 只负责 Release 原签名和验签，密钥不上传。任一测试/Lint/组装/签名失败、验证源与提交 SHA 不一致、显式文件集变化、敏感文件风险、远端不是 `bianwuya/Eta`、目标为 `main`/`local` 或非快进时，阻止自动 Push，保留本地提交并明确报告。无关未暂存 WIP 可以保留，但不得进入提交或产物；预暂存内容必须先分开审查。文档/Skill 等非业务变更按风险采用静态/定向检查，不机械构建 APK；最终交付包仍必须有对应源码的完整验证。
- **已生效的实际范围（不要泛化）**：任务级入口 `F:/eta/06-环境运维工具/eta-ai-delivery/eta-ai-delivery.ps1` 适用于 `F:/eta/projects/` 下通过门禁的隔离开发工作树，由 AI 在每次任务交付时显式调用，不安装文件监视器。原夜间仓库 `F:/eta/projects/eta-night-20261118/worktree` 的既有 Hook 仍按其独立白名单运行；其他仓库没有因此自动安装 Hook。入口和 Hook 都不是安全沙箱，远端分支规则与独立验收同样必须遵守。
- **云端状态必须准确**：现有 GitHub `local`/PR Actions 工作流仍可能执行 Android 云构建；远端 `local` 保护规则要求 PR 和 `Lint / Test / Debug Build`，不能绕过或声称已关闭。用户选择仅本地构建时，默认只推未关联 PR 的开发分支；需修改云端触发器和保护规则时另行审查，不能因为自动 Push 许可就放宽保护、自动开 PR 或触发收费检查。
- **可审计结果**：分别记录提交 SHA、本地测试/Lint/签名包回执、GitHub 远端读取 SHA，以及未测真机项；不得把“已写规范”“提交成功”“Hook 触发”“构建通过”混同为“已推送/已安装/已验收”。禁止自动安装 APK、推送/合并 `local`、发布 Release、强制推送或干扰现有 Codex 会话。

## 8A. 工作区约束、Skill 与浏览器协作同步（2026-11-19）

- 工作区约束、精选知识、项目 Skill 和流程工具通过 `F:/eta/06-环境运维工具/eta-workspace-sync/eta-workspace-sync.ps1` 同步到独立仓 `https://github.com/bianwuya/Eta-Workspace.git` 的 `sync` 分支。必须使用 PowerShell 7：先 `-CheckOnly`，确认白名单和敏感内容扫描后再 `-Publish`；不得上传整个知识库、密钥、账号、私有日志、备份、APK 或未审查 WIP。该仓推送不代替 APP 源码仓提交与构建。
- 网页登录和需要真实登录态的网页自动化优先使用已接入的 `BrowserOS-1` MCP（本机 `http://127.0.0.1:9015/mcp`）。不得读取、输出或写入真实密码、Cookie、令牌；遇到验证码、二次验证或必须人工处理的登录挑战时交给用户接管。GitHub CLI 凭据与浏览器登录态是两回事，分别核验。
