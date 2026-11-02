# Agent Operations（智能体运营轴）

> 正本：strata-kit `core/docs/zh/methodology/agent-operations.md`（2026-10-29 从 strata `docs/04-agents/agent-operations.md` 迁移，DEC-2026-10-29-11）。

> Strata 的**第三条正交轴**。Execution Mode（如何做事）→ Verification Tier（由谁验证）→ **Agent Operations（何时、多少、如何消化）**。
> Verification Tier 的定义以 `core/docs/zh/methodology/verification-tier.md` 为 source of truth。
> 涵盖：运行时间段（夜间批处理）、预算（budget envelope）、多会话结构，以及人如何消化激增的产出（Decision Inbox + 自报验证门禁）。
> 状态：`draft`（设计已达成一致。§1 packet 与 §5 ledger CLI（`kb ledger`）已实现。§2–4 的产出校验与 Decision Inbox gate 没有自动化工具——旧 strata 的 agent-ops.py 自 2026-06 起不再使用（DEC-2026-10-29-12）。实际的 agent runner 尚未实现）

## 0. 为什么需要

Execution Mode 与 Verification Tier 处理的是“如何把一项工作做好”。
Agent Operations 处理的是它之上的问题——**同时、长时间运行多个智能体时，让人既不成为瓶颈也不被淹没的运营纪律**。

核心前提（贯穿整条轴）：

> 目的不是多跑智能体。目的是**严格限制交付单元、角色、产出物以及人要看的表面积**。
> 一切增加产出量的装置（多会话、夜间批处理），如果没有消化产出的装置（Decision Inbox、验证门禁），就会淹没人。

原则概要：

1. 中继（relay）发送的是**结构化 packet**，而不是整段对话。
2. 多会话以 **Coordinator 为中心（hub-and-spoke）** 运行，而不是 N:N 对话。
3. 夜间工作限定为 **budgeted batch**，而不是自治。
4. 人只看 **Decision Inbox**，不看 raw output。
5. 人看到的标签不是自报的，而是**经交叉验证重新判定的**。

本文档是 runtime 系列方法论 primitive——**Relay Packet、Decision Inbox、review_gate、Shared Session Ledger**——的 source of truth。
Quilt 中枢这类 adapter/runtime 不得重新定义这些 primitive，而是把它们当作 routing、projection、execution surface 来消费。

---

## 1. Relay Packet 分层（节省 token + 减少错误）

禁止发送整段对话。目标不是减少 token 数量，而是**提高每个 token 的信息密度**。
（交叉评审流程：`skills/strata.review/SKILL.md`，传递使用 Quilt 枢纽的 `hub_send`）

```text
Level 0: 仅问题
Level 1: 问题 + 当前结论 + 争议点            ← 默认
Level 2: Level 1 + 依据文件/行 + diff 摘要  ← 默认
Level 3: 所需摘录的全文
Level 4: 完整 transcript（仅限例外）
```

默认为 Level 1~2。把散文式对话原样扔过去，对方该判断什么就会变得模糊。
推荐的 packet 形式：

```yaml
intent: "review"
decision_so_far: "Verification Tier 的正本已拆分到 verification-tier.md"
open_questions:
  - "Promotion Gate 流程与 backlog schema 的边界是否吻合?"
evidence:
  - file: "core/docs/zh/methodology/verification-tier.md"
  - file: "core/docs/zh/methodology/task-spec-schema.md"
constraints:
  - "Core 文档中不写入工具名称"
request:
  - "只指出 1~2 处缺口"
```

- **附带锚点**：多轮往返时，为避免对方忘记已达成的共识而漂移，每次都附带 `decision_so_far`（固定摘要）。
- **拦截单薄的 packet**：`evidence`/`request` 为空时，发送前警告——若发送了空 packet，会出现并未执行验证却看起来像 Cross-Verified 的风险。（真实案例：收到空 packet 的 Reviewer 准确返回了“无法审查”）

## 2. 多会话（Model-A n · Model-B n）

可以做，但如果让会话之间 N:N 地互相对话，就会走向 token 爆炸、重复审查、责任不清。
默认是 **hub-and-spoke**。

```text
Coordinator
  ├─ ModelA-Review-1
  ├─ ModelA-Research-1
  ├─ ModelB-CodeReview-1
  ├─ ModelB-Impl-1
  └─ ModelB-Contrarian-1
```

不允许会话之间直接对话。所有会话都把产出放进 relay queue，由 **Coordinator 汇总**。

禁止的结构：
```text
Model A1 ↔ Model B1 ↔ Model A2 ↔ Model B2 ...   (扇出容易，扇入困难)
```

角色分离：

| 角色 | 职责 | 权限边界 |
|------|------|----------|
| Primary | 主导工作 | — |
| Reviewer | 找缺陷 | 不下判定，只指出 |
| Contrarian | 找反对的论据 | 与 adversarial verify 衔接 |
| Summarizer | 压缩产出物 | 禁止改动内容 |
| Archivist | 整理 decision/backlog | **只到 `open→triaged`。`accepted/rejected` 由人决定** |

> **关键**：扇出（多会话）容易，扇入（综合）困难。没有收敛点（Coordinator 或人），就会自己加剧 §4 的问题。

工作树（git worktree）规则（DEC-2026-09-17-01）：即使是并行 Worker、并行会话，工作树也**只有在用户接受了该提议时**才创建。自动模式同样如此。默认是在用户所看的检出（checkout）的单一分支上顺序执行；如果确实需要工作树，就把必要性、分支名称、清理计划作为一项提出，并等待答复。结束后保留分支、清理工作树并汇报。正本规则是 `core/docs/zh/methodology/execution-modes.md` § 绝对规则 7。

### 2.1 执行产出物 schema

目前还没有执行多会话本身的 runner。Coordinator 将收到的 plan 产出物遵循下面的 schema，评审时确认 **N:N 链接禁令**、角色 enum、Archivist 权限边界（目前没有自动检查工具）。

```yaml
multi_session:
  coordinator: "human"        # human | agent
  sessions:
    - id: "review-1"
      role: "reviewer"        # primary | reviewer | contrarian | summarizer | archivist
      tool: "codex"           # adapter label，不是 Core enum
      packet_ref: "$STRATA_VAULT/projects/{n}/relays/..."
      allowed_transitions: [] # archivist 仅允许 ["open->triaged"]
```

禁止：
- `direct_peer_links`：会话之间直接对话的链接。发现时予以驳回。
- Archivist 一直判定到 `accepted/rejected/applied` 的转换。

## 3. 夜间批处理协议（22:00–08:00）

不是自治工作，而是 **budgeted batch**。为了不破坏“决定由人做”的原则，把**夜间=生成，白天=判定**分开。

### 22 点之前 — 人来准备
```text
1. 选定今晚要处理的 work packet 3~5 个
2. 在每个 packet 中写明范围/禁止事项/预算/完成条件
3. 限制写入许可范围 (write_scope)
4. 定义中止条件
```

### 夜间智能体规则
```text
- 禁止新的架构决定
- 禁止影响生产的工作
- 禁止提交/部署/删除（或另行批准）
- 含糊时中止并以问题的形式留下
- 每个 agent 只提交最终的一页摘要
- 产出物一律等待 needs_decision（cross_verified 之前禁止采纳）
```

### budget envelope + 硬性上限
```yaml
agent_budget:
  max_turns: 8
  max_files_read: 12
  max_output_lines: 80
  write_scope: ["assigned/paths/only"]
  stop_if:
    - "architecture decision required"
    - "test cannot run"
    - "scope expands beyond assigned files"
```

> **安全装置的优先级**：硬性上限（`max_turns`/`max_files`/`write_scope`）是**第一道**。自行判断的中止（`stop_if: 含糊时`）是**第二道**——因为智能体若意识不到含糊，就不会停。第一道必须始终生效。

### 08 点 — 人要看的内容
```text
- 需要决定的项目 / 实际改动的文件 / 测试结果 / 风险 / 要丢弃的产出物 / 下一步指示候选
```

token/时间的管理不看精确数字，而看**每个会话的 budget envelope + 按小时的节奏控制**（避免额度在凌晨耗尽而出现空档）。

### 3.1 批处理产出物 schema

夜间批处理先用 **batch spec** 固定，而不是 runner。启动前确认 packet 是否存在以及
hard budget 字段（目前没有自动检查工具）。无论执行工具是什么，没有这份 spec 就不启动夜间批处理。

```yaml
night_batch:
  window: "22:00-08:00"
  packets:
    - id: "nb-001"
      packet_ref: "$STRATA_VAULT/projects/{n}/relays/..."
      owner: "primary"
  budget:
    max_turns: 8
    max_files_read: 12
    max_output_lines: 80
    write_scope:
      - "assigned/paths/only"
    stop_if:
      - "architecture decision required"
      - "test cannot run"
```

所有夜间产出物，在 §4 的 gate 中都按 `review_gate.required: true` 处理。

## 4. Decision Inbox + 自报验证门禁（本轴的核心）

人的瓶颈不是“阅读”，而是“**判定**”。把智能体的输出加工成**可判定的单元**，而不是信息。
人所看的表面只有 **一个 Decision Inbox**。raw output 只存储。

### 4.1 强制输出格式 (self-report)
```yaml
result:
  status: completed | blocked | needs_decision | rejected
  one_line: "做了什么"
  changed_files: []
  evidence: []          # 必须是 pointer（没有 decision 的长篇说明禁止）
  tests: []
  risks:
    - severity: high | medium | low
      summary: ""
      action_needed: ""
  decisions_needed: []
  discardable_notes_ref: "..."   # raw output 只存放在这里
```

### 4.2 自报验证门禁 (Self-Report Validation Gate)

**问题**：上面的 `status`/`risks` 由智能体**自己**分类。如果低估自身风险（high→low），人只看 Inbox 的那一刻，被误分类的条目就会被淹没并通过。
**实测依据**：自报不可信——模型不会把没有依据的自我主张登记为事实，而在给出依据+代码后，会先验证再接受。

**解法**：在进入 Decision Inbox **之前**，由中继（交叉验证）**只重新判定 triage 标签**。

```text
验证对象：
  重新审查整个 raw output ❌          (这样会瓦解 §1 的 token 节省)
  重新判定 status / risk / decisions_needed / evidence pointer ✅
```

流程：
```text
Agent self-report
  → Relay reclassifies (仅标签)
  → agree    → 进入 Decision Inbox
  → disagree → 升级为 "needs_human_decision" (交给人)
```

防止无限循环：
```yaml
review_gate:
  required: true
  reviewer: cross_verified
  max_review_rounds: 1            # 禁止 Reviewer 再去叫 Reviewer
  disagreement_policy: human_decision   # 不一致 = 直接升级到 Inbox
```

### 4.3 基于风险的分支（不全部重新判定）

全部重新判定代价高昂。按风险划分。

**必须重新判定：**
```text
- status: completed 但有文件改动
- risk: high 或 unknown
- 存在 decisions_needed
- 与 architecture / schema / migration / deletion / security 相关
- 夜间批处理产出物（全部）
- methodology_backlog / decisions 的变更
```

**抽样（或省略）：**
```text
- low risk / 文档摘要 / 探索结果 / 只运行了测试的工作
```

### 4.4 缺少重新判定者时的回退（安全默认值）

`reviewer: cross_verified` 以存在另一个模型系列的重新判定者为前提。
**没有重新判定者时**（例如夜间 cross 会话未启动），即为未能完成验证，
相应条目自动归类为 **`needs_human_decision`**——既然没能验证，就不放行，而是上报给人。

### 4.5 人每天做的事 (Agent Output Triage)
```text
1. 批准的  2. 驳回的  3. 追加提问的  4. 丢弃的
```
规则：raw output 只存储，人只看 digest，digest 中必须有 evidence pointer，禁止没有 decision 的长篇文字。

### 4.6 schema 示例（task completion 扩展）
```yaml
triage:
  self_report:
    status: completed
    risk: low
    decisions_needed: []
  review_gate:
    required: true
    reviewer: cross_verified
    result: reclassified            # agreed | reclassified | no_reviewer
    final_status: needs_decision
    reason: "被分类为 low，但包含 schema 变更"
    max_review_rounds: 1
```

### 4.7 Gate 判定规则

目前没有自动验证工具（旧 strata 的 agent-ops.py 自 2026-06 起不再使用，DEC-2026-10-29-12）。下面的判定规则在准备评审和 Decision Inbox 时由人或 Builder 适用。

Gate 判定：
- `completed` + 有改动文件、`risk: high|unknown`、`decisions_needed`、architecture/schema/migration/security/decision 信号、夜间批处理产出物，均为 `review_gate.required: true`。
- 没有 reviewer 时为 `result: no_reviewer`、`final_status: needs_decision`。
- `max_review_rounds` 始终为 1。
- 有 `changed_files` 时，必须有 `evidence` pointer。

Decision Inbox item 只以 `approve | reject | question | discard` 中的一个 action 对外呈现。raw output 存放在
`discardable_notes_ref`，Inbox 里只放 pointer。

---

## 5. Shared Session Ledger（共享会话台账）

> 供三类工作者（**user / primary / reviewer**）共享同一条请求流并协作的**单一真相源 (source of truth)**。
> 各工具的 adapter 把 `primary`/`reviewer` 角色映射到实际的工具会话。Core schema 不把工具名作为 enum。
> 保存上下文的是这个文件，而不是 reviewer 会话的记忆——这是把 Strata 第一原则（“会话是消耗品，文档才持久”）应用到中继上。

### 5.1 为什么是 ledger（reviewer 会话管理的上位解法）

中继长期运行后，“如何维持 reviewer 会话”就成了问题。但是**把真相的单位放在共享 ledger 上，而不是 reviewer 会话上**，这个问题就消解了：

- reviewer 会话**可以是易失的**——上下文留在 ledger，而不是 reviewer 的记忆里。
- 下一个 relay packet 的 `decision_so_far` / `evidence` / `open_questions` 从 **ledger 生成**，而不是来自 reviewer 的记忆（§1 packet）。
- 无论用户从哪个工具开始，都读取同一份 ledger 并继续（与工具、起点无关）。

> **但是，reviewer 重置规则（§1 附近）不废止。** ledger 解决的是*上下文维持*问题，
> 而 reviewer 把 **packet 中没有的旧共识** 掺进自己判断的**污染**是另一回事。重置从“用于上下文维持”降格为
> **“防污染 hygiene”** 予以保留（目的不同，所以有了 ledger 也不会消失）。

### 5.2 位置 · 格式

```text
位置: $STRATA_VAULT/projects/{project}/sessions/session-{date}-{slug}.md
      (位于 Core 之外，持久、共享、适合建索引。.strata/local 是本机状态，不适合)
格式: Markdown 文件 + 按 actor 划分的 YAML block entry (兼顾人读与机器索引)
frontmatter 必填: session_id · project · status · actors · topic · created · next_session · nodes
      (nodes = 本会话所属的主题节点 — §5.7 覆盖率门禁从变更文件推导并核对)
actor: user | primary | reviewer | coordinator | archivist
tool: optional adapter label    (例: claude | codex — 不是 Core enum)
```

### 5.3 条目 schema

每个条目是 `## [actor] {ISO8601 timestamp}` 标题 + YAML 块。append-only，按时间顺序。

```markdown
## [user] 2026-06-01T12:34:00+09:00
​```yaml
intent: "define shared ledger"
request: "让 Claude/Codex/User 共享同一条请求流"
decision: null            # 用户的决定/中止判断 (如有)
​```

## [primary] 2026-06-01T12:40:00+09:00
​```yaml
tool: "claude"                         # optional adapter label
from_user: "shared ledger 提案"     # 收到了什么问题
action: "以更上层的框架分析"        # 如何处理的
to_reviewer:                        # 发给 reviewer 的 packet 摘要 (没有则为 null)
  intent: "review"
  decision_so_far: "ledger is source of truth"
  questions: []
outcome: "采纳 | 反驳 | 搁置"         # 对 reviewer 回应的处理 (如有)
​```

## [reviewer] 2026-06-01T12:45:00+09:00
​```yaml
tool: "codex"                          # optional adapter label
reviewed: "ledger proposal"          # 审查了什么
verdict: "agree | agree_with_caveat | disagree"
risks:
  - "single writer required"
returned: "返回的核心意见"
​```

## [primary] 2026-06-01T15:10:00+09:00
​```yaml
action: "重启信号 — 超过警戒线 | 同一假设失败两次"
confirmed: ["已确认的事实（用什么确认的）"]
assumed: ["未确认的推测"]
discarded: ["已放弃的假设（放弃理由）"]
​```

## next_session
​```yaml
next: "session-2026-06-01-qwer.md"   # close 时强制 (禁止 null — 防止链条断裂)
reason: "移交给下一条流程的原因"
​```
```

上例中的 `[primary] 2026-06-01T15:10` 条目是重启条目。因重启信号（session-splitting 5.1）把工作移到新会话时，写下与交接中事实与假设一节相同的三项（confirmed、assumed、discarded）。

### 5.4 单一 writer + 文件锁 (B3 — 防止并发写入污染)

为了不在 ledger 中重蹈刚刚实测到的会话文件污染（两个进程同时向一个文件 append）：

- 各工具的智能体进程**不直接写 ledger 文件。** 只通过单一入口 CLI（`python3 "$STRATA_KIT/kb" ledger`）来写。
- **单一 CLI ≠ 单一并发**：CLI 内部必须有**文件锁 (flock)**。即使多个 adapter 几乎同时调用 `append`，也会被串行化。
- ledger 与正在运行的 TUI 会话文件（`~/.claude/...`、`~/.codex/...`）是**不同的文件**——与 TUI 的占用无关，所以不是 lsof 守卫的对象。

### 5.5 append 触发时机 (B1 — 谁在何时记录)

条目不是自动记录，而是在**明确的触发时机**记录：

```text
- 中继前后: 发送 packet 时记 primary entry (to_reviewer)，收回应答时记 reviewer entry (verdict)
- 用户决定: user 判断采纳/驳回/中止时记 user entry (decision)
- 工作结束: close 时写入 next_session 指针 (§5.6)
```

### 5.6 会话链接 (B2 — 强制 next_session)

关闭 ledger 时**必须**填写 `next_session.next`。不得以 `null` 关闭——
一旦断开，下一位工作者就无法接续流程（与交接（handoff）里的“pending 必须有 blocker”是同一模式）。
如果没有要继续的工作，就写明 `next: "none"` + `reason`，留下这是*有意终止*的记录。

### 5.7 覆盖率门禁（会话结束时 — 代码变了但形态没变吗）

会话关闭时，会话结束门禁（handoff generator 与 ledger CLI 的 validate/close）会与未提交 decision 记录警告**在同一处**检查以下内容：

```text
输入: 本会话改动的代码文件列表 (任务 completion.files_modified/created，没有则用仓库 diff)
① 对每个改动文件，找出通过 covers 拥有该表面的规格 (覆盖率解析器)
② 汇总所拥有规格的 nodes，与 ledger·交接 frontmatter 的 nodes 核对 — 若有遗漏则警告补全
③ 若所拥有的规格中有本会话未更新的 (updated 早于会话开始)，且
   frontmatter 中没有 doc_change: none + doc_change_reason → 警告 + 记为该节点的债务
④ 若有改动文件没有所属规格 → “无主表面”警告 (需要创建规格或扩展 covers)
```

- **这是警告，不是阻断。** 与未提交记录警告同级。但如果无视，它会留在节点页面的“债务”面上，让下一个人看到。
- `doc_change: none` 与 §5.6 的 `next: "none"` 原则相同——禁止空值，要明确写 none + 理由。
- 债务的正本不是页面，而是“会话中没有 doc_change 声明”这一事实本身。偿还债务只有两种方法：更新规格（更新 updated·sources），或在该会话文档中追溯补记 doc_change 理由。
- 值的格式：`core/docs/zh/knowledge-base/document-format.md` 的“节点·覆盖率字段”一节。它是与评审政策 (90 天) 无关的另一种信号。

ledger frontmatter 的必填字段包含 `nodes` (§5.2)。值由 ② 中的解析器推导，只有没有代码改动的会话才由人直接选择。

---

## 6. 与其他轴的关系

```text
②多会话(扇出) ┐
③夜间批处理(生成) ├→ ④Decision Inbox + 验证门禁(扇入) ← 没有它，①②③ 会淹没人
①中继(密度↑)    ┘
⑤ledger ← ①~④ 的一切行为都记录在此的共享真相源 (与工具、起点无关)
```

- **Execution Mode**：仅引用 Agent Operations。（模式的判定/转换见 `core/docs/zh/methodology/execution-modes.md`）
- **Verification Tier**：验证门禁的 `reviewer: cross_verified` 原样使用 `core/docs/zh/methodology/verification-tier.md` 的 Cross-Verified Tier。
- **Methodology Feedback Loop**：Archivist 的 `open→triaged` 边界遵循 `core/docs/zh/methodology/task-spec-schema.md` 的 Promotion Gate 以及 backlog lifecycle。判定 (accepted) 由人做出。
- **交叉评审**：§1 packet 由 `skills/strata.review/SKILL.md` 生成，并发给全新上下文的评审者（Quilt `hub_send`）。以前的 Claude↔Codex 中继工具（strata bridge）是过去的实现，不再使用。

## 7. 引入优先级

```text
①中继 packet 结构化  → 可立即进行 (收益明确，风险低)
④Decision Inbox + 门禁 → 总钥匙 (②③ 的安全装置，先设计)
⑤Shared Session Ledger → 在让中继多轮往返之前 (以单一 writer+锁为前提)
②多会话 / ③夜间批处理  → ④⑤ 设计之后 (先做的话人会成为瓶颈/被淹没)
```

零件已经具备：交叉评审（strata.review，交叉验证过滤器）+ backlog lifecycle（判定队列）+ Verification Tier（可信度门禁）。fan-in guardrail（产出物自动验证）尚不存在——旧 agent-ops.py 不再使用。这不是发明，而是**组装**。

## 8. 未决事项

- 测量 `review_gate` 重新判定的实际 token 成本 (验证“薄门禁”的假设)。
- Coordinator 由智能体担任，还是由人兼任 (取决于多会话的规模)。
- 多会话 runner 与夜间 batch runner 尚未实现。当前实现仅到 plan/batch/self-report/Inbox 产出物的校验与 gate 规范化为止。
- `discardable_notes_ref` (raw output) 的保存位置 — 可能复用 vault 的 relays/。
- `kb ledger` (原 session-ledger.py) 已实现完成 (append/read/close/validate + flock)。其余打磨参见交叉验证队列。
- §5.7 覆盖率门禁已实现 — 接入 handoff generator (生成前检查 + 推导节点预填) 与 ledger CLI 的 validate/close (警告)，并在 close·handoff 之后重新生成节点页面。ledger 必填字段 `nodes` 处于引入期，因此为**警告级** (升级为错误要等追溯之后)。既有文档的追溯 (nodes/covers)·各项目的 toc.yaml 尚未着手 (methodology-backlog MB-strata-2026-007)。
- reviewer 重置触发条件 (topic_change / max_rounds 3~5 / decision_accepted / packet_drift / high_risk) 如何与 ledger entry 联动。
