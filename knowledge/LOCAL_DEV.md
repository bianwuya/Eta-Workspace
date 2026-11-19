# 本地分级验证与交付入口

本页是Eta本地日常开发的操作入口，不改变当次授权。App稳定源码local/main、远端推送和APK安装独立决定；开发工具接入维护资产主路径不等于合入App功能。

## 日常使用

先定位目标源码worktree，保留已有修改；将本次源码变更保存到独立功能提交，再在该源码目录运行：

```sh
python3 /workspace/projects/eta-local/scripts/eta-local-dev.py check
```

默认读取当前源码Git仓/完整HEAD，基线使用本地local分支并要求是HEAD祖先。验证目录按同一仓库+分支固定在`/workspace/projects/eta-local/.local-dev/`，不随每个SHA新建，沿用已有SDK/JDK/Gradle home与构建缓存。源码脏树不自动提交或清理；缺local、基线非祖先、detached HEAD无明确任务根时停止，使用显式参数消除歧义，不猜远端。

```sh
# UI/局部反馈：给出真实对应的完整测试类名，无法确定则保守跑全量单测
python3 /workspace/projects/eta-local/scripts/eta-local-dev.py check --tests 完整包名.真实Test类
# 最终APK交付：强制完整Lint/单测/标准双包，原签名校验
python3 /workspace/projects/eta-local/scripts/eta-local-dev.py check --delivery --signed
```

上述测试类是说明占位符，执行时必须替换。显式`--repo/--sha/--base/--task-root`仍可用；sha/base要求完整真实SHA。同一分支的稳定树由锁串行使用，独立任务可显式分配任务根。不会自动修改开发树、切换local/main、push或install。

## 分级与恢复

- L0：文档/说明，只做差异和仓库检查，不启动Gradle。
- L1/L2：已知局部逻辑或UI+明确对应测试；编译和定向测试，UI另标待视觉验收。
- L3：共享状态/API/持久化/构建输入/未知范围，编译和完整单测；缺或模糊测试选择时升级。
- L4：手动提高或交付，完整Lint、全量单测、标准Debug/Release、原证书和产物元数据/哈希核验。不能降级交付。

每次回执记录真实SHA/默认值/命令/每次尝试/日志摘要/报告与产物证明。复制或审计失败可重做对应步骤，不重新冷构建。恢复使用`resume --receipt <真实回执> --repo <源码> --task-root <回执任务根>`；成功检查可直接核验复用，失败只处理明确可恢复路径，最多两次恢复。中断/超时只终止本次创建的子进程组，旧日志封存不覆盖；SIGKILL/断电等不能执行清理处理，仍需现场检查，不等同已覆盖。

`deliver --receipt <已通过L4回执> --destination <本次Downloads专属目录>`重新核实证据、原证书与双包哈希后发布；不同已有文件不覆盖。`cleanup`只操作记录归属的验证树，拒绝用户WIP和未知ignored文件；通常保留稳定树，减少反复构建。

## 配置缓存与仍未启用的项目

配置缓存已修复为默认严格开启：ARM64测试classpath在AGP配置完成后组装，不再在执行阶段调用Project；原overlay/compat装载顺序、运行库与JNI保持。`--no-configuration-cache`仅为显式诊断开关，失败不自动降级或改warning。回执区分store/reuse，实际测试执行和SDK34/36/37原生SQLite/Canvas缓存双轮另有证据；不能只靠UP-TO-DATE存储宣称兼容。

host源码位于维护资产`toolchains/host/`，实际工具链为`/workspace/toolchains/eta/`，来源与落地文件摘要需一致；host输入变更会使旧回执的恢复/交付失效，保留旧证据，不重写为新通过。修复证据见`/workspace/scratch/20261108-eta-configuration-cache/RESULT.md`。

完整依赖锁定仍未建立：沿用离线版本目录和输入摘要，不冒称完整依赖锁定；未强制LEGACY或删测试。工具测试、构建通过、安装与本人OEM体验分别报告。

底层手动Gradle入口仍为`/workspace/toolchains/eta/bin/eta-gradle`，仅用于具体诊断或工具链维护；日常反馈和交付优先走本页入口。完整参数/本地完整性边界见`/workspace/projects/eta-local/scripts/local_dev/README.md`。

本轮接入证据：`/workspace/scratch/20261108-eta-fastdev-rollout/RESULT.md`、`VALIDATION.md`和`RUN_STATE.json`。历史P0–P4证据保留在原任务，不能把旧包冒充新产品功能。
