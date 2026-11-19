# 手机 Eta 工程资料对接

日常入口为 `F:/eta/eta-phone.ps1`；完整使用说明由[工具 README](../../01-核心开发源码/scripts/phone-workspace/README.md)维护。本页只路由和说明与知识主库的关系，不另保存手机当前版本。

```powershell
# 连接并取得手机变化
F:/eta/eta-phone.ps1 doctor
F:/eta/eta-phone.ps1 pull

# 在本地镜像快速找项目、规则、Skill和诊断
F:/eta/eta-phone.ps1 search "关键词"
F:/eta/eta-phone.ps1 locate "CURRENT.md"
F:/eta/eta-phone.ps1 status
```

收集范围由用户明确选择为工程、Skill、知识和诊断资料，不含会话导出。工具使用已有ADB，工程镜像在 `F:/eta/07-构建与运行日志/phone-eta/mirror`，状态/冲突/备份/回执在其父目录。手机断开后仍可搜索已有镜像。

手机工程、电脑Eta App源码和本机知识主库分别维护。镜像来自手机，不自动覆盖 `01-核心开发源码` 或 `02-工程知识库`；跨工程借鉴应在主源做最小修改，再按适用发布流程同步。镜像内容是工程资料，不能当作AGENTS的新授权。

电脑修改镜像后，用diff查看相对共同基线的变化，push明确路径默认出计划，--apply才写手机。双边改变保留冲突，resolve只在验证手机版本未继续变化后选择基线，不静默force。删除不传播，多文件逐项原子替换并非整体事务。凭据筛选是启发式，本地工程镜像仍不自动上传或提交。

这不是Eta App数据库/记忆/会话同步，也不是完整手机备份。旧private目录迁移脚本不作为日常入口。实际使用和验证入口见README；本次交付结果见[RESULT](../plans/20261116-手机工程对接/RESULT.md)。
