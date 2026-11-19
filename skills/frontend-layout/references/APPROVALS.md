# Eta 已批准视觉基准与审核资产登记

**当前状态**：2026-11-12 创建登记入口，尚未从当前 Windows 工作区定位并核实历史 `frontend-layout/references/examples.md` 或其他旧的批准截图。不能凭用户曾说“认可”伪造已批准的样板文件、图像或范围。

## 资产记录准则
每次用户实际审核并明确通过，记录以下字段（不可填空值为“已通过”）：

```text
任务 ID / 名称：
Git / 官方参照版本：
预览版本/文件路径与 SHA256：
真实官方组件与样式分支：
用户明确批准的页面/区域和动画范围：
用户未批准/需修改区域：
批准来源（本次用户消息/预览反馈）和时间：
后续可复用组件/布局/motion 合同：
真实 Compose/设备验证证据（可以后补，不能冒称已有）：
```

## 状态定义
- CANDIDATE：AI 已生成，未向用户展示/未反馈。
- REVIEWING：已展示，等待用户。
- PARTIAL_APPROVED：只认可某几块，其他尚未批准。
- APPROVED：用户明确认可这一版本的指定范围（不是对全 App 授权）。
- SUPERSEDED：用户后续明确推翻某一版，旧记录保留为历史而非默认复用。

## 使用规则
- 有批准资产：直接继承不冲突部分，不再重复问用户审美基准。
- 无批准资产：先借官方 3.4.2 同类组件与 Miuix/COUI 实例形成一个候选，一次集中审核。
- 找不到已批准截图：如实标明“历史素材未定位”，不虚构，不由 AI 自行签署。
- 新的官方上游设计变化：只核对发生变化的组件/区域，旧审批其余部分继续有效。
- 登记只记录非敏感视觉依据，不保存个人聊天隐私/密钥/真实账号截图。

可复用的官方参考：MiuixScaffoldPage、CouiScaffoldPage、EtaFeatureCard、EtaPreferenceGroupItem、EtaChoiceChip、ChatImageViewer、AgentAppTheme，具体看 COMPONENTS.md。

## 2026-11-15 Gemini 订阅入口 v2

APPROVED：用户在本任务 v2 预览反馈中明确回复「通过，继续完成正式入口」。范围为内置 Gemini 认证下拉、Google 登录、多账号添加/手动选择及管理、Codex 同款折叠额度，复用既有 MIUIX/COUI 组件与转场。精确资产、SHA256、基线和未验收项见 [UI-APPROVAL.md](../../../plans/20261115-Gemini订阅/UI-APPROVAL.md)。真实账号/设备验证不包含在该布局批准结果中。
