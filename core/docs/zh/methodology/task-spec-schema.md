# 任务规格 Schema (Task Specification Schema)

> 正本：strata-kit `core/docs/zh/methodology/task-spec-schema.md`（2026-10-29 自 strata `docs/04-agents/task-spec-schema.md` 迁移，DEC-2026-10-29-11）。

> 定义由 Builder 生成、Worker 消费的任务规格的结构。
> 任务规格必须**自包含** — Worker 必须仅凭规格就能完成代码。

## 存放位置

```
$STRATA_VAULT/projects/{project-name}/tasks/
  {yyyy.mm.dd}/
    {nn}-{short-kebab-title}/      # Work Order 文件夹
      _order.yaml                   # 工作指令书 (由 Builder 生成)
      task-{nn}-{title}.yaml        # Worker 执行规格
```

### 选择该位置的理由

- `$STRATA_VAULT` — 不影响项目仓库 (独立仓库)
- `tasks/` — 与 KB 文档 (knowledge-base/) 分开，不是搜索索引的对象
- `{yyyy.mm.dd}/` — 按时间顺序追踪，认知负担最小
- `{nn}-{title}/` — 以序号加标题区分同一天的多个工作指令

### 命名规则

| 要素 | 格式 | 示例 |
| ------------- | ------------------------------ | ------------------------------- |
| 日期文件夹 | `yyyy.mm.dd` | `2026.04.23` |
| Work Order 文件夹 | `{nn}-{kebab-title}` | `01-debounce-mongo-sync` |
| 工作指令书 | `_order.yaml` | 始终固定 (下划线 = 排在最前) |
| 任务文件 | `task-{nn}-{kebab-title}.yaml` | `task-01-redis-dirty-mark.yaml` |

### 序号规则

- 该日期文件夹中已有条目数 + 1
- 多台机器同时工作时编号可能冲突 → **title 才是真正的标识符**
- 编号冲突只影响排序，没有功能性问题

---

## _order.yaml — 工作指令书

Builder 拆分任务后生成的清单 (manifest)。

### 必填字段

```yaml
order:
  id: "2026.04.23-01"                # {日期}-{序号}
  title: "基于 Redis Debounce 优化 MongoDB 同步"
  date: "2026-04-23"
  mode: "task"                        # task | verbal (escalated)
  project: "shop-api"

  goal: |
    描述工作的目的和背景。
    为什么需要这项工作，完成时应处于什么状态。

  context:
    prior_session: "session-2026-04-22-01"    # 引用上一次交接
    prior_decisions:                           # 影响本工作的既有决策
      - "PostProcessJob 采用 polling 方式 (@Scheduled fixedDelay=5000)"
    blocker_resolved: "PostProcessJob 系统已实现 (4/21)"
    kb_references:                             # 相关 KB 文档
      - "$STRATA_VAULT/projects/shop-api/knowledge-base/03-orders/checkout.md"

  tasks:
    - id: "task-01"
      title: "为 CacheGenericOperator 添加 SET 运算"
      model_tier: "standard"
      layer: "L2_DataLayer"
      depends_on: []

    - id: "task-02"
      title: "实现 DirtyMarkService"
      model_tier: "standard"
      layer: "L3_Composite"
      depends_on: ["task-01"]

    - id: "task-03"
      title: "将 DataUpsertListener 切换为 debounce"
      model_tier: "deep"
      layer: "L3_Composite"
      depends_on: ["task-01", "task-02"]

  acceptance:
    - "已完成从现有即时处理流程到 dirty mark 流程的切换"
    - "全部单元测试通过"
    - "层级违规 0 件"

  status: "open"                       # drafting | open | in_progress | completed | cancelled
  completed_tasks: []                  # 已完成的任务 id 列表
```

### 可选字段

```yaml
  escalated_from: "verbal"             # 由 verbal 转为 task 时
  completed_before_spec:               # 转换前以 verbal 方式完成的项目
    - "为 CacheGenericOperator 添加 SET 运算"
  
  estimated_sessions: 1                # 预计会话数
  priority: "high"                     # high | medium | low
  deadline: "2026-04-25"              # 绝对日期

  verification_tier: "self_verified"  # solo | self_verified | cross_verified (enum 值)
                                      #   省略时 verbal = solo。Task Mode 建议显式声明。
                                      #   详情: core/docs/zh/methodology/verification-tier.md
  entry_point: "change"               # design_first | dev_first | spec_first | change — 产出物 (Spec·Design·Impl) 的入口。
                                      #   不固定顺序。一致性检查才是门禁。详情: core/docs/zh/architecture/frontend-design-contract.md
  design_verified: "self"             # none | self | designer | cross — 设计一致性验证的独立性 (core/docs/zh/methodology/verification-tier.md)。
                                      #   不是 UI 工作则为 none。
  methodology_feedback:               # 方法论反馈回路 (可选)
    enabled: true
    backlog_ref: "$STRATA_VAULT/projects/{name}/backlog/methodology-backlog.yaml"
```

> **但是，变更 Core source-of-truth 的工作** (layer-rules / naming-convention / task-spec-schema / agent-roles)
> 必须设置 `verification_tier: cross_verified` (`core/docs/zh/methodology/verification-tier.md`)。
> 仅在这种情况下，verification_tier 不是可选字段而是必填字段。

### status 生命周期

```
drafting → open → in_progress → completed
                              → cancelled
```

| 状态 | 含义 | 转换条件 |
|------|------|----------|
| `drafting` | Builder 正在拆分任务 | Builder 开始编写 _order.yaml |
| `open` | 工作指令已确定，Worker 可执行 | 所有任务规格编写完毕 |
| `in_progress` | 部分任务正在执行 | 第一个 Worker 开始执行 |
| `completed` | 全部任务完成 | 所有 acceptance 均已满足 |
| `cancelled` | 取消 | 明确的取消决定 |

处于 `drafting` 状态的工作指令，由 Builder 在下一次会话中接续完成或废弃。

---

## _order.md — 工作指令书的新格式 (2026-08-19, DEC-2026-08-19-03)

新的 order 以 `_order.md` 编写 — **YAML frontmatter 就是 order 本体** (schema 与上面的 `_order.yaml` 相同)，
正文是为纳入 Obsidian 链接图而写的最小 markdown。

```markdown
---
order:
  id: "2026.08.20-01"
  # ... (_order.yaml schema 原样)
---

# {order title}

- Design: [[design-doc]]
- Decisions: [[DEC-YYYY-MM-DD-NN]]
```

- 机器解析的对象只有 frontmatter — 消费 order 的脚本同时支持 `_order.yaml` 和 `_order.md` (frontmatter)。
- 正文必须保留指向 design 文档和相关 DEC 的 `[[wikilink]]` (主干（交接链接：orders、kb_updates、decisions_made）的边 — session→order→design+DEC)。
- 既有的 `_order.yaml` 不追溯转换。`task-{nn}.yaml` 保持 yaml (纳入图由 order 笔记负责)。

---

## task-{nn}.yaml — Worker 执行规格

Worker 接收的自包含任务文档。

### 完整 schema

```yaml
task:
  id: "2026.04.23-01/task-01"          # {order-id}/{task-id}
  title: "为 CacheGenericOperator 添加 SET 运算"
  order_ref: "_order.yaml"             # 引用上级工作指令书

execution:
  model_tier: "standard"               # deep | standard | light (模型名由工具适配器映射)
  model_reason: "沿用现有 CacheGenericOperator 的模式"
  estimated_turns: 8
  estimated_files: 2

scope:
  layer: "L2_DataLayer"
  module: "domain:common-cache"
  nodes: ["common.cache"]                         # 本任务所属的主题节点 — 覆盖解析器依据 directories 推导
  can_reference: ["L1_Component"]
  cannot_reference: ["L3_Composite", "Route_Controller"]
  constraints:                                    # 从 ADR 中提取的领域约束
    - id: "CC-NNN-NN"
      rule: "{适用于该 scope 的约束的一行规则}"
  docs_to_update:                                 # 通过 covers 拥有 directories·module 的规格 — 由覆盖解析器注入
    - node: "common.cache"
      doc: "[[kb-shop-api-common-cache-spec]]"
      reason: "covers.paths 一致 — 添加 SET 运算会改变规格的运算列表"
  directories:
    - "domain/common-cache/src/main/kotlin/com/example/domain/common_cache/components/"

inputs:
  reference_files:
    - path: "domain/common-cache/.../CacheGenericOperator.kt"
      reason: "参考现有模式 — ReactiveRedisOperations 的用法"
    - path: "docs/architecture/layer-rules.yaml#L2_DataLayer"
      reason: "确认层级规则"

  requirements: |
    需要实现内容的详细规格。
    - 方法签名
    - 行为说明
    - 约束条件

  conventions: |
    需要应用的约定摘要 (让 Worker 无需另行阅读文件)。
    - 必须有 PAL 标记 (@pal-port, @pal-layer, @pal-domain, @Comment)
    - 命名: {Domain}{ServiceType}

  design_ref:                          # 构建 UI 的任务必填。指向设计产出物的指针 (core/docs/zh/architecture/frontend-design-contract.md)
    kind: "figma"                      # figma | storybook | claude_design | none
    ref: "file/abc?node-id=12:34"      # 文件·节点·story id·画布 URL
    version: "2026-04-23"              # 工具版本或快照日期 — 一致性检查的基准点
    reason: null                       # kind: none 时必填 (例: "纯文本管理页面")

deliverables:
  files:
    - path: "domain/common-cache/.../CacheGenericOperator.kt"
      action: "modify"                  # create | modify | create_or_modify
      description: "添加 4 个 SET 运算方法"
    - path: "domain/common-cache/.../CacheGenericOperatorTest.kt"
      action: "create_or_modify"
      description: "SET 运算的单元测试"

acceptance_criteria:
  - "实现 addToSet, popFromSet, getSetSize, getSetMembers"
  - "现有方法签名无变化"
  - "单元测试通过"
  - "无层级违规"

context_budget:
  max_reference_files: 5
  max_loaded_tokens: 20000
  compaction_strategy: "file-based"

status: "pending"                       # pending | in_progress | completed | blocked
completion: null                        # 完成时由 Worker 填写 (见下)
```

**`scope.nodes` 与 `scope.docs_to_update`** — Builder 注入拥有该任务所改动代码面的规格 (frontmatter `covers`) 及该规格的主题节点。原理与 `scope.constraints` 相同。Worker 不运行解析器，只读取被注入的值。
- 对于没有所属规格的代码面 (新功能)，要么把创建规格列入 `deliverables.files`，要么写 `docs_to_update: []`，并在 `inputs.requirements` 中写明有意留空的理由。没有理由的空数组会在验证时告警。
- 值格式的正本是 core/docs/zh/knowledge-base/document-format.md 的“节点·覆盖字段”一节。

### completion 部分 (由 Worker 填写 — 但 `triage.review_gate` 例外)

`completion.self_report` 和产出物列表由 Worker 填写，但 **`triage.review_gate` 由
独立的复判者 (reviewer/relay) 填写** — 自报验证门禁的前提 (代理 ≠ 复判者，
`core/docs/zh/methodology/agent-operations.md` §4) 决定了：如果 Worker 自己填写，门禁就会失效。

```yaml
completion:
  status: "completed"                   # completed | blocked | partial
  completed_at: "2026-04-23T14:30:00+09:00"
  files_created:
    - "domain/common-cache/.../CacheGenericOperatorTest.kt"
  files_modified:
    - "domain/common-cache/.../CacheGenericOperator.kt"
  tests:
    total: 4
    passed: 4
    failed: 0
  layer_violations: 0
  naming_violations: 0
  constraint_compliance:                # scope.constraints 各项的遵守结果
    - id: "CC-NNN-NN"
      met: true
      note: "{遵守的依据或特殊事项}"
  design_sync: "aligned"                # aligned | stale | waived | none — Impl↔Design 一致性 (有 inputs.design_ref 时必填)
  design_sync_reason: ""                # waived 时必填: 理由 + until YYYY-MM-DD。stale 时不能宣告完成
  doc_change: "updated"                 # updated | none — scope.docs_to_update 的处理结果 (与会话 frontmatter 同一个键)
  doc_change_reason: ""                 # none 时必填 (例: "仅重构 — 外部契约·策略无变化")
  docs_updated:                         # updated 时为已更新的文档 (在 updated 戳记·sources 中加入本任务)
    - "[[kb-shop-api-common-cache-spec]]"
  notes: "无特殊事项"
  methodology_signals:                  # 可选 — 方法论改进信号 (列表，没有则 [] 或省略)
    - type: "incomplete_spec"           # incomplete_spec | scope_issue | constraint_conflict | rule_gap | drift | design_drift
                                        #   design_drift: 发现 alias 之外的值·契约 (轴·状态) 不一致 → 令牌/设计契约的改进候选
      severity: "minor"                 # minor | major | blocking
      scope: "methodology"              # project | methodology
      affected_core:                    # scope: methodology 时至少 1 项必填
        - "core/docs/zh/methodology/task-spec-schema.md"
      summary: "任务规格中没有测试命令字段，导致完成验证的标准不稳定"
  triage:                               # 可选 — Agent Operations 输出分类 (供 Decision Inbox 使用)
    self_report:
      status: "completed"               # completed | blocked | needs_decision | rejected
      risk: "low"                       # high | medium | low | unknown
      decisions_needed: []
    review_gate:                        # 自报验证门禁 (需要复判时)
      required: true
      reviewer: "cross_verified"
      result: "agreed"                  # agreed | reclassified | no_reviewer
      final_status: "completed"         # 复判后确定的 status
      max_review_rounds: 1
```

`methodology_signals` 是 Worker 报告其在工作中发现的**方法论本身的缺口**的通道。
一次 completion 中可能同时出现多个缺口 (例: incomplete_spec + rule_gap)，因此它是**列表**。
Builder 逐项单独分类。
与一般的 `scope_issue` (当前任务受阻) 不同，它指向规则/schema/约定的改进候选。
Builder 在交接时将其载入 backlog 并判定是否晋升
(→ 见下面的“Promotion Gate”一节)。

`triage` 是在把输出送往供人查看的 Decision Inbox 之前所做的分类。`self_report` 由代理填写，
`review_gate` 由交叉验证对该标签进行复判 (因为自报不可信)。规则、基于风险的分支、没有复判者时的
回退，见 → `core/docs/zh/methodology/agent-operations.md` “Decision Inbox + 自报验证门禁”。

---

## methodology-backlog.yaml — 累积改进候选

用于累积方法论改进候选的独立文件。与 decisions.yaml (决策记录) 分开 —
backlog 是*候选*，其生命周期 (审查→采纳/驳回) 不同。
本节是 backlog **字段 schema 与生命周期 enum** 的 source of truth。
信号流和 Promotion Gate 也由本节定义 (见下面的“Promotion Gate”一节, DEC-2026-10-29-12)。

```
project backlog:  $STRATA_VAULT/projects/{name}/backlog/methodology-backlog.yaml  # vault (Tier V)
core backlog:     $STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml  # Strata Core 改进候选
```

```yaml
methodology_backlog:
  - id: "MB-shop-api-2026-001"   # {project} 前缀可防止集中晋升时冲突
    scope: "methodology"              # project | methodology
    source:
      project: "shop-api"
      type: "worker_rejection"        # worker_rejection | reviewer_finding | repeated_warning
      ref: "tasks/2026.05.31/01-sync/task-02.yaml"
    signal: "incomplete_spec"
    severity: "major"
    affected_core:                    # scope: methodology 时至少 1 项必填
      - "core/docs/zh/methodology/task-spec-schema.md"
      - "core/roles/agent-roles.yaml"
    summary: "因缺少测试命令，Worker 判定无法验证完成"
    proposed_action: "在 task schema 中添加 verification.commands 字段"
    status: "open"                    # open → triaged → accepted | rejected → applied
    promoted_to: null                 # 晋升时为 "$STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml#<id>"
```

### 生命周期

```
open → triaged → accepted → applied
              → rejected
```

| 状态 | 含义 |
|------|------|
| `open` | 信号已载入，尚未审查 |
| `triaged` | Builder 已完成对 scope/重复/affected_core 的确认 |
| `accepted` | 已采纳为 Core 的改进对象 (已晋升) |
| `rejected` | 判定无需改进 (记录理由) |
| `applied` | 已反映到 Strata Core，模板/适配器已重新生成 |

---

### Promotion Gate

backlog 条目按 `scope` 走不同的处理路径。

- `scope: project` — 作为该项目的规则、layer-map、AGENTS.md、KB、决定的改进候选来处理。
- `scope: methodology` — 晋升到 core backlog (`$STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml`)。

对于 `scope: methodology` 的条目, Builder 执行以下步骤。

1. 确认是否重复。
2. 确认 `affected_core` 至少有 1 个。
3. 在 core backlog 中添加晋升条目。
4. 在原项目条目上记录 `promoted_to`。
5. 在反映到 kit 之前, status 保持 `triaged` 或 `accepted`。反映之后写入 `applied` 和 `applied_in` (提交·DEC)。

判定 (`accepted`、`rejected`) 由人做出。此前的 strata 中央 backlog (`strata/methodology-backlog.yaml`) 已迁移到 kit backlog (DEC-2026-10-29-12)。

## 自包含检查清单

Builder 编写完任务规格后、交给 Worker 之前进行验证:

```
□ scope.layer 是单一层级吗?
□ scope.can_reference 与 layer-rules.yaml 一致吗?
□ scope.constraints 包含适用于该领域/层级的约束吗?
□ 有 scope.nodes，且 scope.docs_to_update 与覆盖解析器的结果一致吗?
  (若没有所属规格，deliverables 中是否有创建规格，或是否有有意留空的理由?)
□ inputs.reference_files 中明确列出了 Worker 需要的所有文件吗?
□ inputs.requirements 不需口头说明也能看懂吗?
□ inputs.conventions 中概括了该层级的约定吗?
□ deliverables.files 中列出了所有要创建/修改的文件吗?
□ acceptance_criteria 是可验证的形式吗? (测试通过、违规 0 件等)
□ acceptance_criteria 包含对约束遵守的验证吗?
□ acceptance_criteria 包含对 docs_to_update 的处理 (更新规格，或 doc_change: none + 理由) 吗?
□ context_budget.max_reference_files ≤ 5 吗?
```

**只要有一项不满足，就不交给 Worker。**

Worker 接收任务时的验证:

```
□ 明确写出了 scope.layer 吗?
□ scope.docs_to_update 为空时，写明了有意留空的理由吗?
□ inputs.reference_files 中的文件确实存在吗?
□ inputs.requirements 不为空吗?
□ deliverables.files 不为空吗?
□ acceptance_criteria 至少有 1 项吗?
```

**发现未满足的项目时，立即退回给 Builder (报告 scope_issue)。**

---

## 任务清理策略

| 时点 | 行动 |
|------|------|
| 任务完成 | `status: completed` + 填写 completion 部分 |
| 工作指令全部完成 | `_order.yaml` 的 `status: completed` |
| 冲刺 (sprint) 结束 | 已完成的日期文件夹予以保留 (不删除) |
| 超过 90 天 | 已完成的工作指令文件夹可归档 |

已完成任务的关键决策已经回流到交接和 KB 中，
因此任务文件本身仅作为**审计轨迹 (audit trail)** 保留。
