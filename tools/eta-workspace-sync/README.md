# Eta Workspace 净化同步

目标仓：`https://github.com/bianwuya/Eta-Workspace.git`，分支：`sync`。

同步内容仅限 `workspace-manifest.json` 白名单中的工作区约束、精选知识、项目 Skill 和云端构建/交付工具。不会导出整个知识库、APP 源码仓、密钥、账号数据、私有日志、手机备份、APK 或未审查 WIP。

## 本机发布

必须使用 PowerShell 7；脚本同时统一 Git 原生输入输出为 UTF-8，避免中文文件名被系统代码页误解码。

```powershell
$sync = 'F:\eta\06-环境运维工具\eta-workspace-sync\eta-workspace-sync.ps1'

# 只扫描白名单、文件大小、敏感文件名和凭据特征，不导出或提交
pwsh -NoProfile -File $sync -CheckOnly

# 导出到独立仓，复核暂存文件集，提交并非强推 sync，再读回远端 SHA
pwsh -NoProfile -File $sync -Publish
```

独立导出仓：`F:/eta/projects/eta-workspace-sync/repository`。已有提交后的再次导出要求该仓干净；异常文件、陈旧跟踪文件、白名单外文件或推送后 SHA 不符都会阻止完成回执。远端使用系统 Git Credential Manager，不在脚本或 WSL 中保存凭据。

## 另一台设备拉取

```bash
git clone --branch sync --single-branch https://github.com/bianwuya/Eta-Workspace.git
cd Eta-Workspace
```

后续更新：

```bash
git -C Eta-Workspace pull --ff-only origin sync
```

- `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`：工作区协作约束入口。
- `source/`：APP 源码仓级约束，不是 APP 源码。
- `skills/`：经白名单导出的项目 Skill。
- `knowledge/`、`plans/`：精选知识和流程规范。
- `tools/`：云端构建、AI 任务级交付、夜间推送及本同步器。
- `SYNC-MANIFEST.json`：每个导出文件的来源、大小和 SHA-256。

拉到其他设备后仍需按该设备的目录结构配置路径、JDK/Android SDK、WSL 和签名资产；本仓不包含这些私有或大型依赖，也不会自动执行构建、推送、Release 或安装。

回执目录：`F:/eta/07-构建与运行日志/eta-workspace-sync/`。
