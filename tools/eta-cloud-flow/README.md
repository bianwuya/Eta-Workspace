# Eta 多端源码审查与本地构建主流程

统一入口：`F:/eta/06-环境运维工具/eta-cloud-flow/eta-cloud-flow.ps1`

## 优化后的主链

```text
云端分支或本地提交
  -> 固定完整 commit SHA（不直接改动 main/local/其他工作树）
  -> 可选生成 review-files.txt / review.diff
  -> Windows 仅归档一次精确提交，WSL2 ext4 按 SHA 建立不可变快照
  -> 共享 Gradle 依赖缓存 + 构建缓存，默认离线
  -> Linux 连续执行编译 / 测试 / Lint / Debug 与未签名 Release 组装
  -> Windows 只执行 apksigner 原签名、证书与包信息核验
  -> 输出 APK、哈希、来源与耗时回执
  -> 推送仍由原有独立安全门禁决定；本流程不推送、不安装
```

关键变化：不再让 Windows 使用第二套 Gradle 缓存重新下载依赖并重复执行全部组装任务。配置缓存仍按现有兼容边界关闭，只增加 Gradle `--build-cache`，不盲目改变项目配置。

## 模式

| 模式 | Linux 任务 | Windows 动作 |
|---|---|---|
| `compile` | `compileDebugKotlin` | 无 |
| `test` | 编译、完整单测、Lint | 无 |
| `assemble` | 编译、Debug、未签名 Release | 原签名 Release、验签（可用 `-SkipSign` 跳过） |
| `delivery` | 编译、完整单测、Lint、双包组装 | 原签名 Release、验签 |

默认离线解析构建依赖。首次新版源码缺依赖时显式加 `-Online`；依赖预热后继续使用默认离线模式。任何测试、Lint、构建或签名失败都会阻断后续步骤并保留证据。

## 云端审查或构建

```powershell
$flow = 'F:\eta\06-环境运维工具\eta-cloud-flow\eta-cloud-flow.ps1'

# 拉取云端分支，生成与基线提交的审查材料，并做 Linux 编译
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $flow `
  -RepoUrl 'https://github.com/bianwuya/Eta.git' `
  -Branch 'night/v344-to-main-20261118' `
  -CompareRef 'bd557bbb9ccb51d52b75b297a0e921d3f8afe0f2' `
  -Mode compile

# 首次缺依赖时允许在线解析，完整验证并组装、原签名
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $flow `
  -Branch 'night/v344-to-main-20261118' -Mode delivery -Online

# 多端断连或已确认缓存足够时，复用最近拉取的同一云端分支
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $flow `
  -Branch 'night/v344-to-main-20261118' -Mode assemble -UseCached
```

云端 URL 按内容散列映射到 `F:/eta/projects/eta-cloud-flow-cache/<key>.git` 裸镜像。拉取只更新镜像中的对应分支，不切换或覆盖任何现有工作树。`-UseCached` 只复用镜像，不访问网络；输出始终记录最终完整 SHA，不能把缓存分支冒称为云端最新。

`CompareRef` 必须是源镜像或源仓已有的提交，推荐使用完整基线 SHA。审查材料位于本次运行目录的 `review-files.txt` 和 `review.diff`。

## 本地提交审查

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $flow `
  -SourceRepo 'F:\eta\projects\eta-stgpt-cache-fix-20261118\worktree' `
  -Ref '924f6c146b9766c6b2af32c3b7f36b57b9bd33bf' `
  -Mode assemble
```

本地模式只读取 Git 已提交对象；未提交、暂存或未跟踪 WIP 不会被悄悄打入产物。需要验证 WIP 时，仍应先在获批准的隔离分支形成明确提交，或继续使用可审计的脏树快照流程，不能借本工具绕过现有提交门禁。

`-CheckOnly` 只解析来源并输出执行计划，不构建、不签名；云端模式除非指定 `-UseCached`，仍会先拉取引用以确认真实 SHA。

## 缓存、并发与冲突保护

- Windows 用 `git archive` 只导出精确提交，不把整仓历史复制到 Linux；归档 SHA-256 同时记录并校验，避免 WSL 直接对 `/mnt/f` 仓库执行 Git I/O。
- Linux 快照按完整提交 SHA 复用；文件清单和逐文件哈希不符时拒绝覆盖。全局构建通过 `flock` 串行执行，锁随进程释放，不依赖手工删除锁文件。
- 共享 `/opt/eta/cache` 依赖缓存，并启用 Gradle 本地构建缓存；同提交复用构建输出，新提交使用独立目录并复用共享构建缓存。
- 每次运行目录必须全新，APK、日志、哈希和回执不覆盖旧结果。
- Release 签名先写入 `.unverified`，证书或包信息不符时不交付为正式文件；不自动删除失败证据。

## 本次实测

- 云端引用拉取和 `CheckOnly` 计划通过，原自动推送 `CheckOnly` 门禁通过，没有构建或推送。
- 首轮 Linux 双包组装耗时 5 分 52 秒；修正新版 `apksigner` 默认启用 v3 的参数后，同提交热缓存完整流程耗时 **20 秒**（Gradle 16 秒，89 项任务 `UP-TO-DATE`），Release v2 原证书验签通过。
- 成功回执：`F:/eta/07-构建与运行日志/eta-cloud-flow/selftest-cloud-assemble-bd557-20261118-03/flow-result.txt`。旧失败运行目录保留用于排障，没有覆盖或删除。

## 下一阶段规划：把源码镜像也迁入 Linux（尚未执行）

截图中的 WSL 性能提示针对 `/mnt/f` 上的 Git I/O。当前阶段已经移走构建和 WSL 侧 Git 操作，但 Windows 云端镜像与每次 `source.tar` 仍是剩余拷贝成本。下一步按以下顺序推进：

1. 在 `/opt/eta/sources/<repo-key>.git` 建立 Linux 原生裸镜像；公开仓库直接由 WSL 增量 fetch，审查和快照均在 ext4 内完成，去掉每次提交归档。
2. 对需要 Windows 凭据的私有源保留兼容通道：Windows 只生成单次 bundle/archive，Linux 不直接读取 `/mnt/f` Git 仓库。凭据不写入 WSL 配置或日志。
3. 保留现有 `/opt/eta/cache`、`/opt/eta/trees` 和 Windows 原签名，不整体搬迁 `F:/eta`，更不迁移手机备份或 Windows 工具链；只把云端源镜像和 Git 审查热路径迁入 Linux。
4. 用同一提交比较冷/热 fetch、审查、构建和签名耗时，核验远端 SHA、脏快照阻断及离线行为后，再把自动交付切到 Linux 源镜像。推送白名单与非强推门禁不变。

## 输出

默认：`F:/eta/07-构建与运行日志/eta-cloud-flow/<run-name>/`

- `source.json`：来源类型、请求引用、完整 SHA、模式和是否签名。
- `command.txt`、`gradle.log`、`exit-code`、`duration-seconds`：真实 Linux 命令与耗时。
- `debug.apk`、`release-unsigned.apk`：仅在组装模式生成。
- `release-original-signed.apk`：仅在 Windows 原签名和验签通过后生成。
- `flow-result.txt`：最终状态、来源、耗时、签名路径以及明确的 `PUSH false` / `INSTALL false`。

## 与原有自动推送的关系

`eta-auto-delivery/eta-auto-push.ps1` 仍只允许原来的夜间隔离树、指定开发分支、干净工作树和 `bianwuya/Eta` 远端。它现在复用本流程完成 Linux 验证与组装、Windows 仅签名；原有非强推和远端 SHA 读回逻辑不变。

本工具自身不会提交、推送、开 PR、合并 `main/local`、安装 APK 或修改云端保护规则。多端“拉取构建”不等于获得“写回云端”的授权。
