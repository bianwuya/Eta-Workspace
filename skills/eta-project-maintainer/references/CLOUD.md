# 云QA、保护合入与云交付（按需）

日常本地迭代见[ITERATION](ITERATION.md)，身份/工具链见[BUILD](BUILD.md)。此页承接旧ITERATION中云专属内容，不为普通文档/本地修复启动云。


既有云QA/稳定两线（上线证据见TASKS中的parallel-delivery）。本页仅在当次任务选中云路线时使用，不是手机本地构建的前置，也不授予push/合入/安装权限。远端是否仍部署以相关任务实时读取为准：

- **QA线**：独立worktree/分支 → PR目标local且正文链接需求/前置及相关PR → 原完整PR Check一次生成标准Debug/Release → 默认local可信签名工作流复用同次制品、不重编译 → 原签名双包/上下文/回执下载，业务PR不因此合入。
- **稳定线**：本人决定后正常保护规则合并 → local的Eta Build（全检查+标准Debug/Release）。main仍只作上游镜像。

feature head、base SHA、实际checkout source（PR merge候选）必须分开记录；包绑定真实source SHA、check run和sign run。云审查的需求/关联入口应在PR正文或GitHub版本化文件，不能只给本机scratch路径；AI收到链接/skipped不等于已阅读或通过。分支A/B包分别覆盖安装不等于集成，组合功能须明确集成源码及检查。

- 保留严格必需检查、来源约束、原签名；main 只按需镜像官方。不得为了“快”直接推 local、绕规则、换签或关闭测试。
- 启动前按 workflow+HEAD 查已有 run；正常 push/PR 已触发就不 dispatch。旧 SHA success 不能验证新改动。官方 sync/prepare 仅 workflow_dispatch；准备 PR 也不自动 merge/close。
- 合入前同时读 `isDraft/draft`，不能把 CLEAN/MERGEABLE 与检查全绿当作非草稿；本人已明确授权该PR合入时可转 ready，再读回 draft=false 才合。写后未确认先 GET 真实 merged/head/base；不要为网络 EOF 连续启动同一等待器或盲重放 merge。
- 长等待用单个有界 `terminal_job`，默认60秒级查询，不多开监视器或密集轮询。若任务失败，先读日志/真实 PR 状态；已合并或已成功的阶段不重做。
- 复用 `skills/eta-project-maintainer/scripts/cloud_delivery.py`：稳定线沿原参数；QA用 `--qa-run <精确签名run>`，复用同一验签/下载器并验证证明bundle、关联PR/head/base/source/check/sign/双包摘要，绝不merge或dispatch。QA模式与`--merge-approved`互斥。依赖 `gh` 已登录、Python3.11+、Java/openssl/apksigner/aapt2；缺依赖提供真实路径，不下载一套手机编译SDK。验签不等于手机编译。
- 仅有本次合入授权才传 `--merge-approved`。否则脚本不发起合并；PR已合并时仍校验原功能HEAD、base/local、仓库与合入SHA。脚本不负责push、dispatch、官方同步、安装或更改通知。
- GitHub GET 的 EOF/超时/429/5xx有限重试；认证/权限失败停止。merge只发一次精确HEAD的REST请求，响应丢失先读回；不把写入当GET自动重放。


## 云交付额外检查

稳定线接收合入SHA对应run；QA接收可信签名run及proof绑定的精确PR/head/base/source与完整check。两者都要检查全部必需job、双包与有效artifact，不能只看APK job绿。基础设施执行入口变更先单独审查，不自动自批签名；CI/签名不证明任意测试代码绝对安全。

下载按artifact类型处理，archive:false字节就是APK；跨站redirect移除Authorization。用同一验签下载器核对证书/元数据/摘要，QA按PR维护最新入口，不能并发覆盖稳定入口。通用回执和告知标准在ITERATION；不在此复制所有历史run。
