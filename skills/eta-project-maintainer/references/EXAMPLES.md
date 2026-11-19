# 按需示例：不是固定剧本

例子展示高自由度判断与低自由度执行如何衔接，不授予任何后续push/merge/install权限。所有编号/SHA/版本参数必须从当次任务实读，不复制历史值。

## A. 用户说“设置页太卡，优化我的Eta”

- 高自由度：根据具体页面、日志/已知经验判断是主线程IO、探测、重组或资源问题；优先复用既有状态/组件，不先造通用性能框架。
- 低自由度：核实实际已装版本与源码基线，明确最小改动，按风险做本地相关回归/必要完整验证；云检查仅在本次路线需要时；界面必须用真实Miuix。没有需求不顺手同步官方main。
- 输出：具体修了哪里、精确验证范围；若已授权交付再给原签名标准双包，不拿源码完成冒充用户手感通过。

## B. 用户说“把隔壁补丁和断流分支合进来”

1. 只读取得两个真实SHA、本地local与独立worktree/补丁报告；仅涉及远端时核实真实远端，不以tracking ref冒充实时API。
2. `git merge-base --is-ancestor <补丁SHA> <localSHA>`；已合入则核对关键文件没回退，不重复cherry-pick。
3. 从local建集成worktree，按实际差异合入未包含的补丁。高自由度解决语义冲突，低自由度保留签名/手动官方workflow/已交付功能；本地合版按本次批准做精确集成验证，涉及远端再走正常保护PR。
4. 示例中的“断流已存在”是一次历史事实，后续必须实际核实；不能预判所有分支都已有防护。

## C. 云端交付命令（仅当本次已获授权）

先读BUILD取得本次base版本与证书事实，核对验签工具路径。以下环境变量来自当前工程/API实读，不要填猜测值：

```sh
SKILL=/workspace/projects/eta-local/skills/eta-project-maintainer
/usr/bin/python3 "$SKILL/scripts/cloud_delivery.py" --help
# 已在正确功能worktree内，PR_NUMBER/VERSION/TASK_DIR/LABEL由本任务确定：
HEAD_SHA=$(git rev-parse HEAD)
/usr/bin/python3 -u "$SKILL/scripts/cloud_delivery.py" \
  --pr "$PR_NUMBER" --head "$HEAD_SHA" --version "$VERSION" \
  --label "$LABEL" --receipt-dir "$TASK_DIR" --merge-approved
```

长任务将这一个命令交给`terminal_job`，任务描述写清“<本批>双包下载验签”，记录job并等待其完成通知；不为每个步骤再开监视器。**没有本次合入授权，删除`--merge-approved`**，脚本仅等待PR已被正常合并；不改变未来授权口径。

已有工具默认路径：`/workspace/toolchains/eta/android-sdk/build-tools/37.0.0/lib/apksigner.jar`与`/workspace/toolchains/eta/bin/aapt2`；缺失时显式传`--apksigner-jar`/`--aapt`真实路径，不从scratch旧任务推断工具可用，不生成新签名。

脚本退出0后读`<TASK_DIR>/delivery.json`，再核实本地路径与通知。它不dispatch、不安装，也不会因为这条示例自动执行。

## D. “CI怎么又红了”

- 编译未过：读具体错误行，不猜网络。
- 11个测试同一HTTP429下载失败：先XML核实，修依赖解析/下载，不称11个功能坏了。
- 代码按用户要求从异步恢复同步，但测试还要求异步文字：对照需求更新过期断言，补“旧control/report提示不得出现”的反向测试，不删除整套测试。
- 只有等待脚本EOF、对应CI实际success：继续已成功阶段，不再改源码/重构建。
- 无关自动官方合并冲突：检查是否意外恢复了旧triggers。只按用户决定手动处理官方更新，不让它阻塞个人版。

## E. “没有包/没人通知”

先查job、准确run和Downloads回执。仍构建就准确告知等待阶段；文件已存在则给实际APK引用，不重新构建。检查最新测试包.txt是否过时、GitHub下载是否看错Releases（普通构建在Artifacts）。

通知问题按权限→真实通知→频道/应用开关→声音/勿扰有界排查，设置仅在用户要求下更改。本机ColorOS曾在应用层关闭横幅/振动；这是线索不是永恒根因。不要用“通知许可=true”声称用户收到了，不默认替用户开启全局铃声或锁屏内容。

完成答复示意（值必须来自真实回执）：

> 两包已下载且原证书/摘要校验通过，源码`<sha>`。Release：[实际本地APK路径]；Debug：[实际本地APK路径]。目录：`<Downloads目录>`。未自动安装，功能待你亲测。

## F. 只要求“把流程写成Skill”

改Skill/知识/脚本→相关离线测试→按选定来源同步/校验发布副本；仅当本次包括Skill安装更新时再发布Android并核对hash/权限/缓存边界→反馈实际可用入口。**不触发应用CI、不merge源码PR、不安装APK**；不要为证明流程可复用而再跑一次真实构建。
