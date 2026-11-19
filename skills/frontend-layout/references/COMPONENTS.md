# Eta 官方 UI 组件映射与复用优先级（2026-11-12 本地源码实查）

## 读取原则
首次执行先确认目标工作树、官方参考 SHA、用户当前所选 UI 主题。以下路径已用 `git cat-file -e db0004ca:<path>` 实际核对：除 `EtaImageViewer.kt` 为个人新增薄桥接外，所列基础入口在官方 3.4.2 中存在。**但当前 local 的 AgentAppTheme.kt、MiuixScaffoldPage.kt、ChatImageViewer.kt 已有个人修改**；复用时必须逐段与官方 3.4.2 对照，不能把个人改动冒充官方原样。具体 API/导入/主题 token 以目标树和官方快照为准。

| 场景 | 首选 Eta 现有入口（相对 app/src/main/kotlin/io/github/mangi/eta） | 对应设计要求 |
|---|---|---|
| 全局主题、Miuix/COUI、浅深色、界面缩放 | ui/app/AgentAppTheme.kt、ui/app/AppearanceThemeLocals.kt | 使用 LocalUiStyle、MiuixTheme/CouiTheme，不覆写新调色系统；运行期切换保留状态 |
| Miuix 二级页面/滚动大标题 | ui/components/MiuixScaffoldPage.kt、AdaptiveTopAppBar.kt | 原生 Scaffold、导航、顶部滚动/毛玻璃、安全区、回弹 |
| COUI 二级页面 | ui/components/coui/CouiScaffoldPage.kt | 必须在 COUI 样式分支使用现有 COUI token 和 Scaffold |
| 分组设置项 | ui/components/EtaPreferenceGroupItem.kt、ui/components/coui/CouiPreferenceRows.kt | 保留分组首尾圆角、原生行高/内容布局、图标与说明层级 |
| 功能卡片 | ui/components/EtaFeatureCard.kt | 自适应选 COUI 或 Miuix Card；内边距/点击反馈直接复用 |
| 选项胶囊/筛选 | ui/components/EtaChoiceChip.kt | 现有样式和 160ms 颜色切换是同类控件参照，未证实必要不另造 |
| Miuix 返回按钮和弹窗按钮 | ui/components/MiuixBackButton.kt、MiuixDialogActions.kt | 不自绘返回及通用弹窗确认 |
| COUI 输入、弹窗、搜索 | ui/components/coui/CouiControls.kt | CouiTextField、CouiConfirmDialog、CouiNoticeDialog、CouiInputDialog 等 |
| 聊天主舞台/输入栏 | ui/components/AgentChatBody.kt、AgentChatInputBar.kt、ui/app/AgentAppShell.kt | 不无意改变官方 3.4.2 的消息排版、浮动输入胶囊和工具时间线 |
| 图片预览及动画 | ui/components/ChatImageViewer.kt、EtaImageViewer.kt | 官方 HeroZoomableImageCanvas 为主；`EtaImageViewer.kt` **不是官方文件**，仅作为本地附件/HTML 预览复用官方 Canvas 的薄桥接保留；严禁再做独立手势引擎 |
| 响应式宽屏 | ui/layout/AdaptivePageLayout.kt、MiuixScaffoldPage.kt | 复用 WidePageContent / horizontalCutoutPadding |
| 页面/对话转场 | ui/components/ConversationPaneMotion.kt、ConversationPanePanel.kt | 基于已有面板比例/位移/手势基础，复用导航转场 |

**工程审查动作**：为每个视觉改动写出“官方入口文件 / 复用 API / 是否必须增量 / 无法直接复用的原因”，缺其中一项则设计审核不通过。允许用户明确要求的设计创新，但应局部、可回退。

### 禁止事项
- 不能在 MIUIX 风格的设置页直接塞 COUI 样式组件，反之同理。
- 不能只凭“看起来像 Miuix”使用自绘圆角/高光/调色板冒充真实组件。
- 不能为一个新页面又建一套通用 Card、Dialog、Navigation、Theme、ImageViewer。
- 未对照官方同类页的截图/源码，不能凭 AI 风格喜好批量替换字体和布局。
- 用户在对话页明确要求小面积变动时，不能顺便大改输入栏或现有高级设置页。

### 外部参考（设计时查原文，避免版本假设）
- 官方 Eta 3.4.2：https://github.com/Mangi-11/Eta/releases/tag/v3.4.2
- Miuix Card：https://compose-miuix-ui.github.io/miuix/components/card
- Android Compose Preview：https://developer.android.com/develop/ui/compose/tooling/previews
- Android 自适应：https://developer.android.com/develop/ui/compose/build-adaptive-apps
