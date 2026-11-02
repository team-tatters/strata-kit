# 验证层级 (Verification Tier)

> 正本：strata-kit `core/docs/zh/methodology/verification-tier.md`（2026-10-29 自 strata `docs/04-agents/verification-tier.md` 迁移，DEC-2026-10-29-11）。

> 与执行模式（Verbal/Task）正交的验证独立性轴。
> 执行模式是*如何工作*，验证层级则定义*结果由谁验证*。
> `verification_tier` enum 的 source of truth 是本文档。

## Tier 定义

| Tier | enum 值 | 定义 | 验证独立性 |
|------|---------|------|------------|
| **Solo** | `solo` | 执行主体用自己的检查清单验证 | 无 |
| **Self-Verified** | `self_verified` | 同一执行环境/工具族内的独立 Reviewer 验证 | 中 |
| **Cross-Verified** | `cross_verified` | 不同执行环境、工具族、模型系列的 Reviewer 验证 | 高 |

- 工具名称不写入 Core。"X 执行 → Y 验证"这类映射放在各工具的适配器（AGENTS.md、settings）中。
- Reviewer 看到的不是整个对话，而只有**请求 + diff + 规则 + 测试结果 + 检查清单**。
- 显示名为 `Cross-Verified`，写入 `_order.yaml` 的 enum 值为 `cross_verified`。

## 默认值与必需范围

```text
Verbal Mode: 省略 verification_tier 时 → solo
Task Mode:   建议在 _order.yaml 中明确写出 verification_tier
变更 Core source-of-truth (layer-rules / naming-convention / task-spec-schema / agent-roles):
             → 必须 cross_verified
其他 Core 文档与适配器变更 (core/docs/、core/templates/ 等):
             → 建议 cross_verified
```

不要让人为每个小修改都声明 Tier。声明成本一旦超过验证收益，Strata 就会变得沉重。

## 实现模式

TDD Writer/Reviewer（`core/docs/zh/methodology/session-splitting.md` §2.4）是 Self/Cross-Verified Tier 的实现模式之一。
如何拆分会话由 session-splitting 文档负责，验证独立性的含义和 enum 由本文档负责。

Cross-Verified 的具体工具实现由 `skills/strata.review/SKILL.md` 负责。
该技能是实际执行本文档 `cross_verified` 的流程，本文档不定义该流程。

## 与其他轴的关系

- **Execution Mode**：Verbal/Task 的选择与切换由 `core/docs/zh/methodology/execution-modes.md` 定义。
- **Agent Operations**：Decision Inbox 的 `reviewer: cross_verified` 使用此 Tier。运营纪律由 `core/docs/zh/methodology/agent-operations.md` 定义。
- **Methodology Feedback Loop**：Reviewer 发现的方法论缺口，按 `core/docs/zh/methodology/task-spec-schema.md` 的 Promotion Gate 流程登记到 backlog 并晋升。

## 设计验证轴 (design_verified)

与执行模式、验证层级正交的第三条轴。定义**设计产出物与实现的一致性**（`core/docs/zh/architecture/frontend-design-contract.md` §设计产物与一致性）由谁确认。
`_order.yaml` 的 `design_verified` enum 以本文档为 source of truth。

| 值 | 定义 |
|---|---|
| `none` | 没有 UI 产出物（`design_ref.kind: none`），或未验证 |
| `self` | 实现者按一致性定义（名称、轴、alias、状态轴）自行比对 |
| `designer` | 设计产出物的所有者（设计师或设计工具负责人）确认 |
| `cross` | 不同执行环境、模型的 Reviewer 通过比对 story 渲染/帧来确认 |

默认值与必需范围：

```text
没有 design_ref 或 kind: none → none
Primitive UI · Semantic Component 新增/变更 (共享 UI 包) → 建议 designer 及以上
Feature Block · Route Surface → self 及以上
```

`completion.design_sync` 为 `stale` 时，无论本轴的值如何，都不算完成。`waived` 带有理由和到期日。
