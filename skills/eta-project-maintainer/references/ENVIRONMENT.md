# 按环境定位工程

先确认执行宿主和物理路径；同名 /workspace 不代表同一设备或工程。

| 环境 | 工程/知识入口 | 当前用途 |
|---|---|---|
| Windows | F:/eta/01-核心开发源码；F:/eta/02-工程知识库/knowledge | 核心源码编辑、知识主源；原签名双包 |
| WSL2 Eta-Test-20261112 | /opt/eta/trees/<name>；/mnt/f/eta/02-工程知识库/knowledge | ext4编译/单测/Lint优先；Windows WIP需同步 |
| 旧手机开发环境 | /workspace/projects/eta；/workspace/projects/eta-local/knowledge | 仅实际存在且用户选中时；不机械迁移旧scratch路径 |
| 当前手机共享工程 | Android /data/local/tmp/eta；逻辑Linux /workspace | 相机、请求排障、环境与工作区维护；是否同一bind须查当前namespace |
| 手机安装Skill | /data/user/0/io.github.mangi.eta/files/skills | 与电脑版本化维护Skill不是自动同步副本 |

本机完整环境命令及安全目录路由由根 AGENTS 拥有；本表不复制命令：

```text
F:/eta/AGENTS.md
F:/eta/02-工程知识库/knowledge/WINDOWS.md
F:/eta/02-工程知识库/skills/frontend-layout/SKILL.md
```

WSL2优先是当前用户决策。固定run-env脚本只测已有t00/integration快照，不会自动同步电脑最新修改。旧 eta-local-dev.py / ARM64 overlay 不在 Windows 或 WSL x86环境执行。Windows签名入口不得输出keystore口令。文档维护不构建APK。

旧手机分级入口说明见[LOCAL_DEV路由](LOCAL_DEV.md)，电脑环境细则见[WINDOWS路由](WINDOWS.md)。

外部历史路径未找到就标记不可达，禁止新建隐蔽链接或占位文件假装已恢复。此资源是路径路由，具体部署和版本不在这里维护。

## 手机快速对接

当前工程资料对接入口为 F:/eta/eta-phone.ps1。日常先doctor、pull，再search/locate/status；离线也能搜索镜像。完整命令由电脑知识主库PHONE-WORKSPACE及核心scripts/phone-workspace/README维护。

镜像位于F:/eta/07-构建与运行日志/phone-eta/mirror；它是手机文件副本，不是电脑源码或知识主源。修改后指定路径push，默认计划、--apply才落手机；有冲突先比较并resolve，不传播删除。工具不读取会话数据库，不启动服务、不重启Eta。写入Skill文件后仍须分别验证App可读与原生发现，不把同步成功当缓存刷新。
