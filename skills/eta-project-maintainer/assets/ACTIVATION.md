# 维护Skill来源、接入与刷新

## 主源与发布副本

- `eta-local/knowledge/`是唯一知识正文主源；Skill主体、scripts/tests与EXAMPLES在版本化Skill目录维护。
- 资产仓 scripts/eta-skill-sync.sh 只处理指定引用：ITERATION/BUILD/MIGRATION/CLOUD是按需稳定手册副本；INDEX/RULES/LESSONS/STATE生成短路由，不打包动态全文。EXAMPLES等手写资产不由该脚本覆盖。
- 源码目标AGENTS与资产AGENTS是就近入口，独立worktree通过`/workspace/projects/eta-local/`定位资产，不猜`../eta-local`；遵守是约定，不是保证自动加载。
- Android发布位置`/data/user/0/io.github.mangi.eta/files/skills/eta-project-maintainer/`；由Android作用域工具操作，不把Linux目录假称App私有路径。发布仅针对获准Skill，恢复实际App UID/权限，不复制__pycache__/日志/凭据。

## 按需接入（新机器/克隆）

1. 核实真实仓库/工具路径与既有hook；按相关风险跑资产/Skill离线测试和shell语法。文档/Skill任务不安装APK或编Gradle。
2. 只有接入任务明确要求时执行`/workspace/projects/eta-local/scripts/eta-setup-hooks.sh`；它设置本机local core.hooksPath，不覆盖旧hook，不改全局Git配置。配置/文件存在不等于hook运行过，用隔离fixture核验。
3. 主库定稿后先`sh /workspace/projects/eta-local/scripts/eta-skill-sync.sh --check`，核对来源/目标hash与WIP；明确更新时再不带参数同步，复检八项current。逐文件替换，不是多文件整体事务；失败先检查，不盲覆盖并发修改。
4. 安装Skill是独立受控发布步骤，仅在本次范围包括时做。先保留原文件与hash，只更新本Skill，核对实际App UID、文件模式、正文/资源hash及实际skills_read。

## 日常使用与状态

相关任务触发短Skill入口→目标AGENTS→命中知识，不默认读整本索引/STATE/LESSONS。只沉淀受影响主条目；工程收尾不向核心复制流水。临时任务许可不升级为所有未来操作权限。

- 卫生检查：`python3 /workspace/projects/eta-local/scripts/eta-check.py --repo <目标树>`默认staged；`--base REF`只查REF...HEAD，不含工作区。
- 离线脚本自测：`python3 -m unittest discover -s /workspace/projects/eta-local/skills/eta-project-maintainer/tests -v`；不联网/CI/安装。云脚本--help仅显示参数。
- hooks只作用于相应本机git commit，可被标准Git方式跳过，不是沙箱。外部/网页提交按适用流程显式检查，不擅自新增CI。
- 文件发布、运行时metadata缓存、当次可见ID、skills_read正文是不同层。外部复制不会自动刷新索引；正常Skills管理页forceRefresh或新加载边界后核实，不重启承载会话Eta、不改registry。旧run可见旧description而读取新正文，必须如实标明。
- 当前版本/CI/安装/验收只从知识主库STATE与实时对象读取，离线副本不冒称当前状态。
