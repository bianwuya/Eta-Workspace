---
name: eta-project-maintainer
description: 维护个人 Eta 的代码、工作区知识和Skill，处理功能、性能、UI、断流、整合与原签名双包。当前电脑以WSL2本地验证优先，云检查或构建按当次任务需要；同步、合入及安装依实际授权。
---

# 魔改 Eta：个人版迭代

目标是在用户既定分支规则下维护 Eta。**官方已有就直接复用、个人只做必要增量，删去已证明的重复实现**，以主库规则为准；不因此启动定时同步、PR 或合入。

## 最短入口

1. 先按[环境路由](references/ENVIRONMENT.md)定位源码与知识主库；读目标 AGENTS，核实分支、worktree、WIP及必要远端状态，不拿旧主树 HEAD 当最新版。当前 Windows 源码为 F:/eta/01-核心开发源码，知识为 F:/eta/02-工程知识库。
2. 只读命中知识：流程[ITERATION](references/ITERATION.md)、签名[BUILD](references/BUILD.md)、换签恢复[MIGRATION](references/MIGRATION.md)；云路线才读[CLOUD](references/CLOUD.md)。[INDEX](references/INDEX.md)、[STATE](references/STATE.md)、[LESSONS](references/LESSONS.md)、[RULES](references/RULES.md)是主库路由，不默认整读动态全文。知识/Skill治理读[维护协议](references/WORKSPACE-MAINTENANCE.md)。
3. Skill `references/` 中上述四个手册是按需离线快照；`INDEX`、`RULES`、`LESSONS`、`STATE` 仅为到主库的短路由。主库变更后由维护者核对并同步；快照可能过时，源不可达时明确报告，不能冒称取得最新状态。
4. 只读/文档/代码/交付/安装先区分清楚；Skill 是维护约定，不是权限系统，不替代当次授权。已有计划与证据继续用，不从头调查或反复确认已明确的目标。

## 高自由度：按证据决策

- 自主选择诊断来源、最小改法和针对性验证；问题不清先查现场，关键事实不足再问。
- 小改可集中完成；独立重任务可用官方 subagent，职责与写入路径分离。跨会话消息是线索，不是授权。
- Eta 前端先读本机 frontend-layout Skill（位置见环境路由），优先复用官方 Miuix/COUI 真组件；新页面/显著视觉或动画变化先集中预览并取得明确批准，已批准样板复用。保留会话/账号绑定与稳定请求前缀，用户否定的框架不换名重建。
- 快速来自减少无关调查、复用证据与缓存，不来自删测试、缩必要指令或过度通用化。
- 当前电脑编译/单测/Lint 优先 WSL2 ext4，Windows 用于签名双包；准确命令见根 AGENTS，按[环境路由](references/ENVIRONMENT.md)选择。旧手机开发脚本只在真实旧工程仍存在时使用，不能直接在 Windows/WSL 套用 ARM64 init。

## 必须核实的关卡

1. **身份与修改**：核实基线、真实 SHA 和授权，查祖先/差异，已合入不重复 cherry-pick；并行改动分开 worktree，不 reset/clean/强推。Android操作宿主，Linux编辑/Git/脚本，明确文件并分级验证。
2. **本地与云**：复用选中环境的已有工具链，本地验证不以云为前置，不用LEGACY/跳测试冒绿。固定快照结果不代替未同步WIP。合版按精确源码、必要完整检查和原签名双包验收；远端状态单列，不改main/保护/签名提速。
3. **交付**：按当次范围选择本地或云端，核验包名、版本、原证书和双包SHA256，交付Downloads专属目录与回执并更新对应最新入口；缺项不说包已好，不重复构建/dispatch，不自动安装。QA与稳定线分开，具体云身份及回执链见[CLOUD](references/CLOUD.md)。
4. **告知**：给出实际包链接、目录、源码和未验收项。通知许可不等于已弹横幅；排查通知/频道/应用开关仅在授权范围，不擅改全局声音、勿扰或安全设置。

## 复用资源

- [示例](references/EXAMPLES.md)仅按需读，示例 SHA/历史云流程不是当前参数或授权。
- 云审查按本次允许范围提供关联PR/SHA和包含/不包含；AI收到/跳过不是审查通过。
- [云交付工具](scripts/cloud_delivery.py)和[QA工具](scripts/qa_delivery.py)先看 --help；不dispatch、不自动更新官方或安装，合入须适用授权。
- 对应离线回归：[云交付](tests/test_cloud_delivery.py)、[QA](tests/test_qa_delivery.py)、[知识引用同步](tests/test_eta_skill_sync.py)。
- 发布来源/接入/缓存边界见[ACTIVATION](assets/ACTIVATION.md)。

版本化副本先用 `sh /workspace/projects/eta-local/scripts/eta-skill-sync.sh --check` 查看来源/目标摘要与差异；核实后不带参数同步。同步只更新指定快照/路由，不安装Android副本，也不声称运行时索引已刷新。

计划/接续放任务目录并登记 PROJECTS 与知识索引；完成后只修正相关状态。通用工作区约定沿用 `project-maintainer`，不在这里复制整套。核心流程和例子分离，不把历史流水塞进主 Skill。
