# 02 — 会话拆分指南

> 正本：strata-kit `core/docs/zh/methodology/session-splitting.md`（2026-10-29 自 strata `docs/02-session-splitting.md` 迁移，DEC-2026-10-29-11）。

> Builder 在编写工作指令书之前必须参阅的文档。
> 会话拆分是“防止上下文丢失”最有效的策略。

## 1. 拆分判断矩阵

### 1.1 定量标准

| 指标 | 单个会话 | 2-3 个会话 | 4+ 个会话 |
|---|---|---|---|
| 变更文件数 | ≤15 | 16-40 | 40+ |
| 影响层级数 | 1-2 | 3 | 4+ |
| 引用文件数 | ≤10 | 11-25 | 25+ |
| 预计对话轮次 | ≤20 | 21-40 | 40+ |
| 新领域数 | 1 | 2 | 3+ |
| 所需探索步骤 | ≤2 | 3-4 | 5+ |

### 1.2 定性标准

**需要立即拆分的情形：**
- “先调查 A，再根据结果决定 B 的方向” → 探索会话 + 实现会话
- “一边重构现有代码，一边添加新功能” → 重构会话 + 功能添加会话
- “同时修改前端和后端” → FE 会话 + BE 会话
- “先写测试，实现后再验证” → TDD 会话 (Writer/Reviewer 模式)

**单个会话即可的情形：**
- 单文件缺陷修复
- 添加与现有模式相同的 CRUD
- 补充测试
- 文档更新
- 配置变更

## 2. 拆分模式目录

### 2.1 按层级顺序拆分 (Layer-Sequential)

最常见的模式。需要从底层开始构建新功能时使用。

```
请求: “请新实现订单 (Order) 领域”

Session 1: L1 + LM1 (基础)
├── 定义 OrderEntity, OrderStatus enum, OrderType
├── MongoDB Document 映射
└── 设置继承公共 Audit Entity
    → 交接: 实体/类型已确定，下一步是 L2

Session 2: L2 DataLayer (数据)
├── OrderCommandService (create, update, delete)
├── OrderQueryService (findById, findByStatus, search)
├── OrderRepository, OrderTemplate
└── 单元测试
    → 交接: L2 完成，下一步是 LM2 或 L3

Session 3: L3 Composite (业务)
├── OrderCompositionService
├── 支付对接逻辑 (使用 PaymentCoordinator)
├── 库存扣减逻辑 (使用 InventoryCoordinator)
└── 集成测试
    → 交接: L3 完成，下一步是 Controller

Session 4: Route Controller (API)
├── OrderController (端点定义)
├── Request/Response DTO
├── Validation 设置
└── 生成 API 文档
```

### 2.2 按领域并行拆分 (Domain-Parallel)

在同一层级同时处理多个领域时使用。

```
请求: “请实现 User, Order, Product 领域的全部 L2”

Session A: L2 — User 领域 (独立)
Session B: L2 — Order 领域 (独立)
Session C: L2 — Product 领域 (独立)

前提: L1 Component 必须事先确定
前提: 各领域之间不得有 L2 相互引用 (由 Strata 规则保证)
```

### 2.3 探索-实现拆分 (Explore-Implement)

用于方向不确定的工作。

```
请求: “请找出性能慢的部分并优化”

Session 1: 探索 (Explore)
├── 代码分析并识别瓶颈
├── 解读性能分析 (profiling) 结果
├── 得出 3 种优化策略
└── 将探索结果记录到 $STRATA_VAULT/projects/{name}/sessions/ (Tier V)
    → 交接: 优化策略已确定，详细实现计划

Session 2-N: 实现 (Implement)
├── 按已确定的策略修改代码
├── 性能测试
└── 记录结果
```

### 2.4 TDD 拆分 (Writer/Reviewer)

Anthropic 推荐的 Writer/Reviewer 模式。

> **与验证轴的关系：** 这种 Writer/Reviewer 模式是用会话拆分来实现 `core/docs/zh/methodology/verification-tier.md` 中 **Verification Tier**
> (Self-Verified / Cross-Verified) 的**案例之一**。
> Tier 的定义以 `core/docs/zh/methodology/verification-tier.md` 为 source of truth，此处不重复定义。
> - Reviewer 属于同一工具系列 → **Self-Verified**
> - 属于不同的模型系列 → **Cross-Verified** (实现: `skills/strata.review/SKILL.md`)

```
Session 1: 编写测试 (Writer)
├── 基于需求编写测试用例
├── 确认所有测试都失败
└── 提交 (commit) 测试文件

Session 2: 实现 (Writer)
├── 编写能让 Session 1 的测试通过的代码
├── 确认所有测试通过
└── 提交 (commit) 实现代码

Session 3 (可选): 评审 (Reviewer)
├── 在全新的上下文中评审代码
├── 验证 Session 2 的代码是否遵守层级规则
└── 提出重构建议
```

### 2.5 前后端拆分 (Frontend-Backend)

```
请求: “请同时实现订单功能的 UI 和 API”

Session BE: 后端
├── 实现 L2-L3-Controller
├── 确定 API 规格文档 ($STRATA_VAULT/projects/{name}/tasks/.../api-specs/order.yaml, Tier V)
└── 交接: API 端点 + DTO 已确定

Session FE: 前端
├── 参考 API 规格 (Contract) — 先决条件是 **Contract 已确定**，而不是 BE 已完成。可以先用 mock transport 推进
├── 按 Frontend variant 的 Contract/DataState/Feature 顺序
├── 声明 entry_point (design_first | dev_first | spec_first | change) — 顺序不固定，一致性检查才是门禁 (core/docs/zh/architecture/frontend-design-contract.md)
└── API 集成测试 + 确认 Impl↔Design 一致性 (design_sync)
```

Contract 一旦确定，BE 会话和 FE 会话就可以并行。FE 先行的 `dev_first` 也被允许 — 此时 Contract 是 FE 会话的产出物，由 BE 会话对其进行验证。

## 3. 工作指令书 (Task Specification) 格式

Builder 为每个会话编写的文档：

```yaml
# $STRATA_VAULT/projects/{name}/tasks/{date}/{nn}-{title}/task-{id}.yaml
task:
  id: "ORD-L2-001"
  title: "实现 Order L2 DataLayer"
  session_type: "implement"      # explore | implement | review | refactor
  estimated_turns: 15
  estimated_files: 8

scope:
  layer: "L2_DataLayer"
  domain: "order"
  directories:
    - "src/data/order/"
    - "test/data/order/"
  
constraints:
  layer_rule: "@core/rules/layer-rules.yaml#L2_DataLayer"
  naming_rule: "@core/rules/naming-convention.yaml#backend.L2"
  can_reference:
    - "L1_Component"
    - "LM1_Inherite"
  cannot_reference:
    - "L2_DataLayer (其他领域)"
    - "LM2_Coordinate"
    - "L3_Composite"

inputs:
  prior_session: "ORD-L1-001"    # 上一个会话 ID (没有则为 null)
  entities:
    - "@src/components/order/OrderEntity.ts"
    - "@src/components/order/OrderStatus.ts"
  reference_implementation:
    - "@src/data/user/UserCommandService.ts"  # 模式参考

deliverables:
  files:
    - path: "src/data/order/OrderCommandService.ts"
      description: "CUD 事务服务"
    - path: "src/data/order/OrderQueryService.ts"
      description: "只读查询服务"
    - path: "src/data/order/OrderRepository.ts"
      description: "MongoDB Repository 实现"
    - path: "test/data/order/OrderCommandService.test.ts"
      description: "CommandService 单元测试"
    - path: "test/data/order/OrderQueryService.test.ts"
      description: "QueryService 单元测试"

acceptance_criteria:
  - "所有单元测试通过"
  - "无层级依赖违规 (Hook 验证通过)"
  - "遵守命名约定"
  - "一个方法只管理一个实体"

context_budget:
  max_reference_files: 5
  max_loaded_tokens: 20000       # 引用文件的 token 上限
  compaction_strategy: "file-based"  # 决策写入文件，上下文保持轻量
```

## 4. Builder 的拆分建议协议

Builder 收到用户请求时执行的分析流程：

```
用户: “请整体实现订单管理功能”

Builder 分析:
┌─────────────────────────────────────────┐
│ 📋 工作范围分析                          │
│                                          │
│ 影响层级: L1, L2, LM2, L3, Route (5)    │
│ 预计变更文件: ~35 个                      │
│ 预计引用文件: ~15 个                      │
│ 预计对话轮次: ~60 次                      │
│                                          │
│ ⚠ 判定: 需要拆分会话 (建议 4 个会话)      │
│                                          │
│ 建议:                                    │
│ Session 1: L1 实体/类型 (15 分钟, ~8 轮)  │
│ Session 2: L2 DataLayer (30 分钟, ~15 轮) │
│ Session 3: L3 Composite (30 分钟, ~15 轮) │
│ Session 4: Controller + API (20 分钟, ~12 轮) │
│                                          │
│ 可并行: 拆分 Session 2 的子领域           │
│ 依赖链: S1 → S2 → S3 → S4               │
└─────────────────────────────────────────┘
```

Builder 会**先向用户展示这份分析并获得批准**，然后再生成工作指令书。

## 5. 会话结束信号

Builder 应结束当前会话并进行交接的时机：

| 信号 | 应对 |
|---|---|
| 对话轮次超过 15 次 | 完成当前工作单元后交接 |
| 发生 Compaction | 立即保存状态，尽可能完成当前单元后交接 |
| 需要重新解释“我之前说过……” | 上下文丢失的征兆 — 立即准备交接 |
| 进入跨越层级边界的工作 | 完成当前层级后转入下一个会话 |
| 依据探索结果转变方向 | 将探索结果文档化，实现放到新会话 |
| 用户变更需求 | 将变更文档化，重新分析后制定新计划 |
| 对话超过警戒线（默认约 40 万令牌） | 完成手头的单元，在下一个任务边界交接（含事实与假设一节）后开启新会话；最迟在上限线（默认约 60 万）之前 — 5.1 |
| 同一假设的尝试两次受阻 | 不寻找第三种绕行办法，停下来报告实测事实和可选方案 — 5.1 |

### 5.1 重启信号：令牌警戒线与同一假设失败两次

这两个信号不是让你在原地中断工作的标准，而是让你完成手头的单元、在下一个任务边界拆分的信号（卡片 `rec.session.split-at-task-boundary`）。压缩在窗口几乎填满时触发，所以窗口越大介入越晚；而纠缠于一个假设的对话，不论长短都会让判断变得模糊。两个信号针对的正是这两种情况。

**令牌警戒线与上限线。** 对话超过约 40 万令牌时，完成当前单元，在下一个任务边界写好交接，转入新会话。即使下一个边界还远，也要在约 60 万令牌之前转出。两个值都是固定的令牌数，而不是窗口的比例（DEC-2026-10-31-09，数值见 DEC-2026-10-31-33）。它们是在默认使用 1M 窗口时、远在压缩之前整理会话的起始值，目前还没有来自我们自己工作的实测依据。用用户配置 `~/.strata/config.yaml` 中的 `session.restart_tokens`、`session.restart_limit` 修改，启动头部的 `restart signal` 行显示当前值。在 Claude Code 中用 `/context` 命令或状态栏查看当前大小；代理无法直接读取时由人告知。

**同一假设失败两次。** 尝试两次受阻时，不要寻找第三种绕行办法，而是停下来报告实测事实和可选方案。同一假设指同一个原因推测：即使修改的位置不同，只要"原因是 X"这一推测相同，就是同一假设。失败指想要确认的症状（同一个测试失败、同一个错误）依然存在。报告之后由人决定方向，或在交接中写下已放弃的假设，在新会话中重新审视。

**交接中的事实与假设一节。** 因重启信号结束的会话，在交接的"事实与假设"一节中分别写下已确认的事实（连同用什么确认的）、未确认的推测和已放弃的假设（连同放弃的理由）（DEC-2026-10-31-11）。下一个会话先读这一节，不再拾起已放弃的假设。通过原账本工作的会话在重启条目中写下同样的三项（agent-operations 5.3）。

### 5.2 对话令牌预算与压缩时点

| 窗口 | 默认自动压缩 | `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` 时 | 与 40 万警戒线、60 万上限线的关系 |
|---|---|---|---|
| 20 万令牌 | 20 万（窗口上限） | 16 万 | 压缩先到；在这个窗口中由压缩发生的信号承担警戒线的作用 |
| 100 万令牌 | 约 96.7 万 | 约 77 万–80 万 | 警戒线和上限线都在压缩之前到来 |

固定开销是工具框架的系统提示、工具定义、指引、启动头部和记忆。strata-kit 增加的指引和头部约 8–12KB（大约 3 千–5 千令牌）（`wizard verify`），其余取决于工具框架和所连接的 MCP 服务器数量，用 `/context` 查看。

默认压缩时点取自 Claude Code 文档（model-config）。自动压缩窗口（`autoCompactWindow` 设置、`/autocompact` 命令、`CLAUDE_CODE_AUTO_COMPACT_WINDOW` 环境变量，10 万–100 万）是填到多少就压缩的值，`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` 是乘在这个窗口上的比例，只能让压缩提前。环境变量只有在 v2.1.304 及以后才读取 `500k` 这样的单位写法。在大窗口中，压缩远在警戒线之后才到来，因此整理会话的是警戒线和上限线，而不是压缩。是否修改压缩设置由用户决定。

## 6. /split-session 命令的运行流程

用户执行 `/split-session` 时，Builder 执行的流程：

```
1. 分析当前请求的范围
2. 应用拆分矩阵 (参见第 1 节)
3. 向用户提出拆分计划
4. 获得批准后:
   a. 为每个会话生成 task-{id}.yaml
   b. 更新 TASK_TRACKER.md
   c. 明确依赖顺序
   d. 立即开始第一个会话，或仅保存整体计划
```
