# 构建身份、工具链与验证入口

本页只保存身份和执行环境事实。流程/交付关卡见[ITERATION](ITERATION.md)；仅当需要云QA/保护合入/云下载时再读[CLOUD](CLOUD.md)。历史提交/run不是默认参数。

## 当前电脑验证路线

2026-11-15 用户指定：编译/单测/Lint 优先 WSL2 `Eta-Test-20261112`，源码同步到 Linux ext4；完整环境变量与命令唯一维护在 F:/eta/AGENTS.md。Windows `F:/eta/eta-gradle.ps1` 负责原签名标准 Debug/Release 打包及补充检查。见[WINDOWS](WINDOWS.md)。本节优先于下方历史手机 ARM64 默认入口；不修改 Windows 源码的 local.properties，不把 Windows 权限/SQLite 差异直接当产品回归。

## 真实基线与身份

- 源码共享仓`/workspace/projects/eta`，资产`/workspace/projects/eta-local`。从`git worktree list`、`rev-parse local`及目标树status选择基线；当前对象见STATE，不能把主树旧HEAD、tracking ref、实时GitHub和已装版本混用。
- 上游`Mangi-11/Eta`，自有fork`bianwuya/Eta`；main为上游镜像、local为个人线。Git镜像可能影响push URL，按任务核实，不向remote/config/日志写凭据；绕既有只读镜像的本机经验见LESSONS L01。
- 应用包名`io.github.mangi.eta`。保留versionCode/versionName策略，用`-Peta.buildMetadata=<实际源码标识>`；标准Debug/Release同源码，Debug保留通用诊断，不裁专项包或删除调试点。
- 原证书SHA256：`a7a92cca03f7d7390ab74001c97efbfe4ff4289b0dc4ffa21d6ebc3cee1c81a8`，仍须实际apksigner verify及X.509读回。原keystore位于eta-local本机私有目录，不入Git/不外发/不更换；缺失停止，不自动生成临时签名。

## 历史手机Linux工具链（仅工程仍存在时）

日常验证优先入口：从目标源码工作树执行`python3 /workspace/projects/eta-local/scripts/eta-local-dev.py check`，最终双包加`--delivery --signed`。默认参数/缓存/恢复见[LOCAL_DEV](LOCAL_DEV.md)；下列`eta-gradle`为保留的底层手动诊断入口，不是每次重新全量编包的要求。

配置缓存兼容修复已接入：ARM64 Test classpath在配置完成后组装，不再在doFirst访问Project；默认严格CC，显式`--no-configuration-cache`仅用于诊断，不自动降级。真实store/reuse、native SDK34/36/37和原始源码完整L4证据见/workspace/scratch/20261108-eta-configuration-cache/RESULT.md；历史IPC超时具体诱因仍未确证。版本化host源在`toolchains/host/`，实际安装摘要需一致。

用户已撤销仅云端/省算力限制。本机入口`/workspace/toolchains/eta/bin/eta-gradle`，在**目标worktree**中执行，复用已装JDK/SDK/Gradle及缓存，不重搭工具链。

`sh
/workspace/toolchains/eta/bin/eta-gradle :app:lintDebug :app:testDebugUnitTest :app:assembleDebug :app:assembleRelease -Peta.buildMetadata=<实际源码标识>
`

`<…>`为说明占位符，不可直接当shell命令或伪造SHA。签名参数沿既有受保护环境和项目配置，不在命令摘要记录口令。文档/Skill任务不执行此构建。

ARM64补齐记录：/workspace/scratch/20261107-eta-arm64-toolchain/RESULT.md。host-only Robolectric loader+官方ARM64运行库已验证SDK34/36/37真实SQLite/Canvas，sqlite4java JNI有真实SQL证据；SDK35未验证，入口明确拒绝，不强制LEGACY或跳测试假绿。aapt2仍是既有QEMU官方x86包装，不能称全链原生。对构建子树去DAC绕过以恢复权限测试，不改变系统Root授权。

具体JDK/SDK/Gradle实时版本用入口/任务核实，不把文档数字当永久事实。已有精确合版完整验证/包回执可复用；修改代码的最终源码仍需对应验证，文档HEAD不能借旧包声称新代码通过。

## 按风险检查

- 文档：引用/绝对路径/状态冲突/覆盖来源；脚本：语法和相关隔离fixture；不触发APK/整机备份。
- 代码：对应编译/测试；交付前现有必要完整检查和标准双包。失败XML与初始化/HTTP429分开，不吞失败、不削弱断言；测试/安装/本人OEM体验独立报告。
- 提交检查：`python3 /workspace/projects/eta-local/scripts/eta-check.py --repo <目标树>`，默认只看staged；`--base REF`只看REF...HEAD，非工作区。main/版本/高置信secret/产物规则是有限启发式，不是完整DLP或沙箱。
- 既有hook配置可用`git -C <目标树> config --get core.hooksPath`查看；存在不等于本次已运行，不覆盖已有hook。跨工程检查器能力/默认漏检见project-maintainer。

## 云端与发布身份

- GitHub local受保护，PR/必需检查按实时规则，不因本地通过直接推protected local、改保护或合上游。官方sync/prepare为手动入口，不自动merge/close；用户选中云路线才查询远端并执行适用步骤。
- 现有QA双包线可在业务未合时用完整check制品签名，稳定线沿正常合入SHA；上线证据见TASKS，不将部署历史当远端实时保证。feature head/base/source/check/sign互链，不能把PR原始开发签名Debug直接当可覆盖包。
- 早期云Debug开发签名问题已有修正证据；后续每次仍验原证书，不能继续固定声称云Debug不可覆盖。不同变体大小与选测数量不能证明功能被裁剪，APK本身不含JUnit。
- 同包名原签名正常覆盖；不同签名先读MIGRATION，不反复尝试安装。Downloads交付副本是用户可见产物，环境bind mount文件不重复搬运。真实安装需适用授权，承载会话Eta默认本人手动。
