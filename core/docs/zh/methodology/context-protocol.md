# 09 — Context Protocol: Constraint-Aware Context Loading

> 正本：strata-kit `core/docs/zh/methodology/context-protocol.md`（2026-10-29 自 strata `docs/09-context-protocol.md` 迁移，DEC-2026-10-29-11）。

> 以 kit 卡片（`rec.context.entry-view-budget`·`rec.session.split-at-task-boundary`·`rec.session.state-in-files`）与 `core/docs/zh/methodology/session-splitting.md` 的原则为基础，定义感知约束（Constraint）的上下文加载规则。

## 1. 问题定义

ADR 中决定的领域约束（例如"禁止 hard-delete"、"必须 Bitemporal"）在实现阶段丢失的路径：

1. ADR 正文太长，无法每次都读全文
2. Compaction 时 ADR 的细节丢失
3. Worker 是独立上下文 — 不知道 Builder 会话中关于 ADR 的讨论
4. 如果任务规格遗漏了领域约束，Worker 无从察觉

## 2. 解决方案：约束以摘要放入入口视图，注册表全文在需要时读取

### 上下文层级

```
T0 — Universal（始终加载，12KB 以内 — rec.context.entry-view-budget）
  ├── AGENTS.md + CLAUDE.md            （生成的指引 — must 卡片摘要，约束摘要 2KB 以内）
  └── active/{session-id}.yaml         （每个会话的 active-task — DEC-2026-08-19-05）

T1 — Session（会话开始时）
  ├── 最新的 handoff 文件
  ├── decisions.yaml                   （生成的索引，需要时读取 — 正本是 decisions/ 记录）
  └── constraint-registry.yaml         （需要时读取 — 通过入口视图的链接）

T2 — Domain（按任务对象）
  ├── 对应主题节点的节点页面（联接最终形态、策略、决策、工作历史、债务的生成物，入口点）
  ├── 对应领域的 Constraint Card 全文
  └── 相关 ADR 的 Decision Outcome 部分

T3 — Implementation（实现时）
  ├── 目标源文件
  ├── 测试文件
  └── layer-rules.yaml (对应层的部分)
```

### constraint-registry.yaml 规则

- **位置**：`.strata/constraint-registry.yaml`（项目内）
- **大小限制**：3KB 以内。生成的指引中只放 2KB 摘要，全文以链接形式保留
- **超过 3KB 时**：把 `severity: should` 的项目拆到单独文件。registry 中只保留 `must`/`must-not`
- **更新时机**：ADR 转为 accepted 时 + 创建 Constraint Card 时同步更新
- **格式**：与 `decisions.yaml` 相同的 YAML 索引

```yaml
constraints:
  - id: CC-NNN-01
    source: ADR-NNN
    severity: must
    scope: {domains: [{domain}], layers: [{layer}]}
    rule: "{一行可执行的规则}"
    status: active
```

### decisions.yaml 规则（2026-08-19 更正）

- 需要时读取的 `decisions.yaml` 是**由记录（`.strata/decisions/DEC-*.yaml`）重新生成的紧凑索引**。禁止手工编辑。
- 决策的添加、编号、索引的重新生成**只由 decision writer CLI** 执行（用 flock 串行化 — 多个会话同时运行也安全，DEC-2026-08-19-05。角色→实现映射：`python3 -m kb --help`、`core/docs/zh/kb-engine.md`）。
- 需要细节时，通过索引条目的 `record:` 路径加载记录全文 — 与 Registry（1 行）→ Card（~50 行）→ ADR（~200 行）逐层细化的模式相同（索引摘要 → 记录全文）。
- Tier P 的物理位置遵循 placement profile（`core/docs/zh/environment/data-placement.md` §1.5 — embedded=repo，detached=vault `projects/{n}/strata/`）。

## 3. 按 Agent Role 的 Context 加载

### Builder

| 情形 | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| 创建任务 | ✓ 过滤 constraint-registry | ✓ | 节点页面 → 对应领域的 Card | - |
| 编写 ADR | ✓ | ✓ | 节点页面（确认决策链） | - |
| 提取 Constraint | ✓ | - | - | - |

Builder 读取 constraint-registry.yaml，按任务的领域/层进行过滤，
把对应的 constraint 注入任务规格的 `scope.constraints`。
同样地，用覆盖率解析器找到拥有变更范围的规格（`covers`），注入 `scope.docs_to_update`。
节点页面是这两项注入的入口点 — 打开一个节点，现行规格、有效约束、现行决策就都在同一屏上。

### Worker

| 情形 | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| 执行任务 | 仅 CLAUDE.md | - | - | ✓ |

**Worker 不直接读取 constraint-registry.yaml。** 也不直接读取节点页面。

只使用 Builder 注入到任务规格 `scope.constraints` 与 `scope.docs_to_update` 中的内容。
这与任务规格的**自包含性**原则一致。

```yaml
# Worker 收到的任务规格
scope:
  layer: "L2_DataLayer"
  constraints:
    - id: "CC-NNN-01"
      rule: "适用于该 scope 的约束"
    - id: "CC-NNN-02"
      rule: "另一项约束"
```

Worker 把这个 `scope.constraints` 转换为完成报告中的 `constraint_compliance`。

### Supporter

| 情形 | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| 检索 Constraint | ✓ 检索 registry | - | 仅检索结果 | - |

Supporter 应 Builder 的请求，检索特定领域/层的 constraint。

## 4. Context Budget 规则

```
CB-1: T0 (AGENTS.md + CLAUDE.md) 在 12KB 以内，包括继承的指引在 14KB 以内 (wizard verify)
  → 约束注册表·决策索引不属于 T0。约束以 2KB 摘要放入生成的指引
  → 指引过大时，优先缩减为目录化（以引用为主）
  → using-strata 读取的入口路径（技能正文·核心注册表·宪法）由 verify 单独报告（2026-10-29，无上限）

CB-2: T2 的 Constraint Card 每个领域在 10KB 以内
  → 超过 10KB 时，不加载 Card 全文，只加载 registry 中的一行摘要

CB-3: .strata/ 的总加载量在 30KB 以内（T0+T1+T2 合计）
  → 超出时用 registry 的对应行替换 T2

CB-4: ADR 全文只由 Builder（编写 ADR/提取 Constraint）加载
  → 其他角色通过 Constraint Card 接触 ADR 的决策
  → 这就是 Constraint Card 存在的理由

CB-5: 节点页面每个节点在 8KB 以内（与 CB-2 的 Card 预算合计，维持 T2 上限）
  → 生成器把工作历史部分截取为最近 5 条，把决策部分截取为现行 + 前一条，使其落入预算
  → 仍然超出时，只保留最终形态、策略部分，其余用链接替代
```

## 5. Compaction 恢复能力

```
Compaction 前:  ADR 全文 + 详细讨论（存在于上下文中）
Compaction 后:  只剩摘要 — ADR 细节有丢失的风险

Constraint 恢复路径:
  constraint-registry.yaml (在文件中，随时可以重新读取)
  → 通过一行摘要立即确认"必须遵守什么"
  → 需要细节时参考单个 Constraint Card (T2)
  → 需要更深的背景时参考 source_adr

逐层细化 (Layered Detail):
  Registry (1 行)  →  节点页面 (~100 行)  →  Card (~50 行)  →  ADR (~200 行)
  摘要在入口视图      进入领域时加载一次       需要时加载         几乎不加载
```

节点页面不能取代 Card 和 ADR。它是告知哪个 Card、哪个 ADR、哪个规格为现行的入口点，正文在链接的另一端。

## 6. 与现有上下文管理的关系

| 现有（kit 卡片·session-splitting.md） | 本文档（扩展） |
|---|---|
| CLAUDE.md 层级设计 (§2·§4, `wizard verify`) | 保持 — 约束摘要放入生成的指引，注册表全文在需要时读取 |
| 交接协议 (`strata.handoff`, session-splitting.md §5) | 保持 — 在交接中加入 constraint 提取状态 |
| Compaction 防御 (execution-modes.md, `kb pre-compact`, SessionStart compact) | 加强 — registry 是额外的恢复锚点 |
| Token 预算指南 (session-splitting.md §5.2) | 扩展 — 增加 CB-1~5 规则 |
| Memory vs Handoff vs KB 的区分 (§7, rec.session.state-in-files, rec.kb.session-records-in-vault) | 保持 — Constraint Card 放在 KB 中 |
| （新增）主题节点 | T2 入口点 — 节点页面是 Index 层的生成物，不是正本 (core/docs/zh/knowledge-base/vault-structure.md) |

## 7. 记忆、交接与 KB 的区分

工具框架的记忆（Claude Code 为 `~/.claude/projects/<项目>/memory/`）在每次会话开始时都会通过索引自动读取，所以放什么会改变下一个会话的判断。

| 什么 | 放在哪里 | 原因 |
|---|---|---|
| 进行状态 — 手头的工作、下一步、未提交、受阻之处 | 活动文件（`.strata/local/active/`）和交接 | 会话结束就会过时；放在记忆里，下一个会话会把过去的状态当作现在的事实 |
| 长期有效的事实 — 用户的偏好、关于工作方式的指示、外部资源的位置 | 工具框架的记忆 | 每个会话都应自动读取的内容 |
| 决定与政策 | 决定记录、卡片 | 经过审查的正本；记忆中的反馈成为政策时移到这里 |
| 设计、规格、知识 | vault KB | 通过链接和覆盖与代码绑定 |

**进行状态不放进记忆。** 会话关闭时，该会话写入记忆的进行状态条目移到交接中（`strata.handoff` 的记忆检查步骤，DEC-2026-10-31-16）。

**确认日。** 记忆条目的前置信息中，用 `verified: YYYY-MM-DD` 写下最后确认其正确的日期（DEC-2026-10-31-14·34）。工具框架写的 `modified` 是改动的日期，`verified` 是确认内容仍然正确的日期。代理在写入或修改条目时写上，交接检查中人回答“仍然正确”的条目也要更新。

**整理。** `python3 -m kb hygiene --memory` 会列出当前文件夹记忆中的整理候选及其原因：过时（确认日，若无则修改日超过 60 天 — 用户配置 `memory.stale_days`）、无日期、状态用语匹配、格式未知、可能相互矛盾的反馈对、索引与文件不一致。工具只读，不输出正文。状态用语只是匹配而非判定 — 点名某种状态的规则也会被匹配。移动、合并、删除只针对人逐条批准的条目。删除时移到同一目录的 `_archive/`，在前置信息中写上 `retired`、`retired_reason`，并删去索引行（DEC-2026-10-31-17）。`wizard verify` 显示记忆索引的大小，超过 12KB 时只警告（DEC-2026-10-31-19）。Codex 的记忆暂不在范围内（DEC-2026-10-31-13）。
