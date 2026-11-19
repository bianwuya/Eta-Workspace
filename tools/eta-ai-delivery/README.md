# Eta AI 任务级自动交付

用途：AI 在隔离开发工作树中完成明确文件修改后，自动执行 **仅显式文件提交 → 精确提交 Linux 完整验证/组装 → Windows 原签名验签 → 非强制推送开发分支 → 远端 SHA 读回**。

运行时使用 PowerShell 7：

```powershell
pwsh -NoProfile -File F:/eta/06-环境运维工具/eta-ai-delivery/eta-ai-delivery.ps1 `
  -RepoPath F:/eta/projects/<task>/worktree `
  -RemoteName github `
  -Files @(
    'app/src/main/kotlin/example/Changed.kt',
    'app/src/test/kotlin/example/ChangedTest.kt'
  ) `
  -Message 'fix(scope): describe the change'
```

仅检查门禁而不提交、构建或推送：追加 `-CheckOnly`。

## 强制边界

- 仅接受 `F:/eta/projects/` 下的隔离工作树和 `fix/`、`feat/`、`feature/`、`ai/`、`night/`、`chore/`、`docs/` 开发分支；拒绝 `main`、`local`、`master`。
- 远端必须是无内嵌凭据的 `bianwuya/Eta`。本地 bundle 可保留为 `origin`，GitHub 使用独立 `github` remote。
- 只暂存 `-Files` 明确列出的现有文本文件；不使用 `git add -A`，不接受预暂存内容，不上传密钥、数据库、APK、手机备份或凭据特征内容。
- 其他未暂存 WIP 保留在原地，不进入提交，也不进入基于该提交生成的归档和 APK。
- 提交后通过 `eta-cloud-flow.ps1` 从精确 SHA 构建，Linux 执行编译、完整单测、Lint、Debug/Release 组装，Windows 仅原签名。
- 任一测试、Lint、组装、签名、来源 SHA 或文件集校验失败均不推送，本地提交和日志保留。没有跳过测试或强制推送参数。
- 推送目标只有同名开发分支；随后用 `ls-remote` 核对完整 SHA。代码推送不创建 PR、Release、标签，也不安装 APK。

## 回执

运行目录：`F:/eta/07-构建与运行日志/eta-ai-delivery/`。

- `receipt-<timestamp>.txt`：显式文件、提交 SHA、APK 哈希、推送或失败原因。
- `ai-delivery-<commit12>/`：精确提交归档、Linux 构建日志、APK、签名结果和 `flow-result.txt`。

2026-11-20 实测：STGPT 修复最终提交 `b65d83794119a4c4cd06f42928106c1f98931984` 完成精确提交交付，2143 项单测 0 失败、0 错误、1 跳过，Lint、双包、原签名和验签均通过；`fix/stgpt-prompt-cache-20261118` 已推送并读回同一 SHA。原签名 APK 已作为 `preview-stgpt-cache-fix-20261120` Pre-release 发布，云端下载读回 SHA-256 一致。

过程中发现旧测试把 Room 持久 `eta.db.lck` 误算为备份残留，已仅修改测试断言范围；生产备份逻辑未改。交付器还曾把键值文本 `flow-result.txt` 误读为 JSON，现改为读取 Linux `source-commit` 并校验 `STATUS passed`，来源和成功门禁没有放宽。
