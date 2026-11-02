# 执行模式 (Execution Modes)

> 正本：strata-kit `core/docs/zh/methodology/execution-modes.md`（2026-10-29 自 strata `docs/04-agents/execution-modes.md` 迁移，DEC-2026-10-29-11）。

> 定义 Strata 方法论的双重执行模式。
> 每个会话在开始时必须明确声明执行模式。

## 原则

- **默认值是 Task Mode** — 未声明时视为 Task Mode
- **Verbal Mode 是有意设置的例外** — 只有明确选择后才能使用
- **模式切换是单向的** — 允许 Verbal → Task，禁止 Task → Verbal

> **与工作模式的对应（2026-10-29，DEC-2026-10-29-15·19）**：入口技能（using-strata 第 4 步）的四种工作模式是对这两种模式的细分。Verbal = 只读（调查、提问、评审）+ 不需要任务文件就能结束的单会话改动；Task = 多会话（有订单的工作）+ 编排（多个会话或角色并行）。会话承担的义务（活动文件、交接、订单）由工作模式决定，下面的量化标准用于判断能否以 Verbal 结束。
- **变更状态前先摘要并确认** — 对难以撤销或会改变可观察状态的操作（修改文件、向会话注入内容、调用外部 CLI、提交/部署），先给出将要执行内容的摘要，经用户确认后再执行

## 模式定义

### Task Mode（默认）

由 Builder 编写 `_order.yaml` + `task-{nn}.yaml` 规格，Worker 依据规格执行的模式。

**适用时机：**
- 以冲刺为单位的执行计划
- 多会话功能实现
- 变更 3 个以上文件
- 影响 2 个以上层
- 建立新的架构模式

**义务：**
- 编写 `_order.yaml`（工作指令书）
- 编写各个 `task-{nn}.yaml`（Worker 执行规格）
- 更新 TASK_TRACKER.md
- 编写交接文档
- 出现架构决策时回流到 KB

### Verbal Mode（例外）

由 Builder 直接执行，或通过口头指示快速处理的模式。

**适用情形：**
- 创意构思、探索、设计评审
- 单文件修改
- Bug 热修复（紧急）
- 文档修改、配置变更
- 可在 10 轮内完成的工作

**义务：**
- 不需要任务规格
- 不需要更新 TASK_TRACKER
- 交接为可选（有决策事项则记录）
- **出现决策时记录 decision 记录（decision writer CLI）不可豁免**（与模式无关的绝对规则 — `decisions.yaml` 是生成的索引，禁止手工编辑）

## 模式选择标准（量化）

```
IF (修改文件 ≤ 3) AND (影响层 ≤ 1) AND (预计轮数 ≤ 10)
   AND (新领域 = 0) AND (探索阶段 ≤ 1):
    → 允许 Verbal Mode
ELSE:
    → 强制 Task Mode
```

| 指标     | 允许 Verbal | 强制 Task |
| -------- | ----------- | --------- |
| 修改文件 | ≤ 3         | 4+        |
| 影响层   | 1           | 2+        |
| 预计轮数 | ≤ 10        | 11+       |
| 新领域   | 0           | 1+        |
| 探索阶段 | ≤ 1         | 2+        |

**只有所有条件都在 Verbal 范围内时才允许 Verbal。只要有一项超出，就强制 Task。**

## 模式声明

会话开始时，在本会话的文件 `.strata/local/active/{session}.yaml` 中记录模式，并把 harness 的会话 id（Claude Code 为 `CLAUDE_CODE_SESSION_ID`）写入 `harness_session_id` — 启动头部和压缩后的恢复通过这个字段或文件名找到本会话的文件：

```yaml
harness_session_id: "9496c8b3-…"   # CLAUDE_CODE_SESSION_ID
session:
  date: "2026-04-23"
  mode: "verbal"              # verbal | task
  declared_scope: "防抖设计评审与简报"
  escalation_threshold: 3     # 超过此文件数时切换到 task mode
  order_ref: null              # task mode 时为 _order.yaml 的路径
```

## 模式切换（Verbal → Task）

以 Verbal 开始但范围变大时：

1. 在 Builder 的 5 轮自我诊断中发现（检查文件数、层数）
2. 向用户报告"需要切换到 Task Mode"
3. 编写 `_order.yaml` — 包含 `escalated_from: "verbal"` 字段
4. 已完成的工作记录在 `_order.yaml` 的 `completed_before_spec` 部分
5. 之后的工作基于任务规格推进

```yaml
# _order.yaml（切换时）
order:
  id: "2026.04.23-01"
  title: "防抖 MongoDB 同步"
  escalated_from: "verbal"
  completed_before_spec:
    - "为 CacheGenericOperator 添加 SET 运算（在 verbal 阶段完成）"
  tasks:
    - id: "task-01"
      title: "实现 DirtyMarkService"
      # ... 之后的任务为正常规格
```

## 模型分配策略

Worker 任务要明确指定执行的**推理等级（reasoning tier）**。写等级而不是具体的模型名，等级→模型的映射由工具适配器负责（工具中立）。

### 按推理等级的分配标准

| 等级 | 分配标准 | 相对成本 | 代表性工作 |
|------|----------|----------|------------|
| **deep**（高推理） | 建立新模式、跨层推理、复杂重构 | 高 | 架构设计 + 实现、新系统 |
| **standard**（标准） | 沿用现有模式、单层 CRUD、测试、文档化 | 低 | REST Docs、添加 QueryService、KB 文档 |
| **light**（轻量） | 文档检索、规则查询、简单摘要 | 最低 | KB 检索、交接摘要 |

> **等级→模型的映射由工具适配器负责，而不是 Core。**（适配器示例 — Claude：`deep→Opus`、`standard→Sonnet`、`light→Haiku`。此映射属于适配器语境，不是 Core 规则。）

### 模型选择决策树

```
任务是否沿用现有模式？
  ├─ YES → 参考实现是否明确？
  │         ├─ YES → standard
  │         └─ NO  → deep（需要解读模式）
  └─ NO  → 是否需要新的架构判断？
            ├─ YES → deep
            └─ NO  → standard（简单的新代码）
```

### 在任务规格中标注等级

```yaml
execution:
  model_tier: "standard"
  model_reason: "沿用现有 REST Docs 模式，无需新的判断"
```

`model_reason` 为必填。Builder 必须写明选择模型的依据，下一个会话才能沿用同样的标准。

## 各代理的默认推理等级

| 代理 | 默认等级 | 可否变更 |
|------|----------|----------|
| Builder | deep | 不可（编排始终需要高水平推理） |
| Worker | 按任务指定 | 可（deep 或 standard） |
| Supporter | light/standard | 可（检索用 light，摘要用 standard） |

> 具体模型由工具适配器映射到等级（参见上面"等级→模型的映射"的注释）。Core 只规定等级。

## 验证轴 (Verification Tier)

验证轴与执行模式正交。执行模式是*如何工作*，验证轴则处理*结果由谁验证*。
enum 值为 `solo | self_verified | cross_verified`。
定义、默认值，以及变更 Core 正本（SoT）时 `cross_verified` 的必需范围，以 `core/docs/zh/methodology/verification-tier.md` 为 source of truth。
Cross-Verified 的评审通过 `skills/strata.review/SKILL.md`（把评审包一次性发给全新上下文的评审者）进行。

## 方法论反馈回路 (Methodology Feedback Loop)

Worker/Reviewer 发现的方法论缺口以 `methodology_signals` 上报，由 Builder 登记到 backlog 并晋升。
流程与 Promotion Gate 以 `core/docs/zh/methodology/task-spec-schema.md` 的“Promotion Gate”一节为 source of truth。
`methodology_signals` 与 `methodology-backlog.yaml` 的字段 schema 由 `core/docs/zh/methodology/task-spec-schema.md` 定义。

## 运营轴 (Agent Operations)

在执行模式和验证轴之上，把**多个、长时间**运行代理时的运营纪律作为单独的轴处理：
多会话（hub-and-spoke）、夜间批处理（budgeted batch）、Decision Inbox、自报式验证门禁。
→ `core/docs/zh/methodology/agent-operations.md`（本文档只做引用，规则定义在那里）

## 绝对规则（与模式无关）

> **本节不是正本**（DEC-2026-10-29-19）。哪些规则适用于本项目，由宪法（`core/constitution/constitution.yaml` 中的条款）和项目采用的卡片（向导写入的 `.strata/kit/registry.yaml` 中的 `must_cards`）决定，生成的指南（AGENTS.md）载入这一集合。规则措辞的正本是 `core/cards/` 中的卡片。
> 本节保留这些卡片所出自的原文及其依据（事故、理由）。从宪法 1.2.0 起，5 和 7 不再是条款，而是仅在项目采用时才适用的采用型 must。变更规则时修改卡片和宪法（决策记录），不修改本节。

原文（2026-09-30，DEC-2026-09-30-02 当时适用于所有会话的清单）：

1. **变更状态前，先给出将要执行内容的摘要并获得用户确认**
   - 对象：修改文件、注入会话文件/中继、调用外部 CLI、提交/部署/删除、长时间运行的工作、影响成本、权限、数据的工作
   - 摘要中要包含目的、将执行的工作、变更/影响范围、验证方法、回滚/中止条件
   - 不改变状态的调查，如单纯的查询、检索、读取文件，作为例外允许
   - **semantic vs mechanical**：改变含义、规则、契约的 semantic 变更必须获得批准。含义不变的 mechanical 变更（错别字、链接、格式）**只有在能够 static 证明时**才是自动许可的候选。含糊时归入需要批准一侧。不得把 LLM 自己的"mechanical"判断当作自动许可的依据
2. **出现架构决策时立即记录 decision 记录**（decision writer CLI — 索引和 vault DEC 笔记自动重新生成）
3. **禁止违反层规则** — 线束拦截的强度由项目的执行等级决定（DEC-2026-10-29-17）。无论等级如何，代理都不写新的违规
4. **遵守命名约定** — Hook 发出警告
5. **只使用 Soft Delete** — 采用型（宪法 1.2.0，DEC-2026-10-29-14）：有存储的项目采用时适用
6. **会话状态、进行中的工作、交接要保存在文件中，而不是对话上下文里** — 适用于改变状态的会话，只读会话没有需要保存的状态（DEC-2026-10-29-15）— 会话中断时把当前状态记录到 本会话的 `.strata/local/active/{session}.yaml`（单一文件 `active-task.yaml` 是旧格式，只在没有按会话文件时读取），交接与工作历史放在 vault 中
7. **只有在用户同意时才创建工作树（git worktree）**（DEC-2026-09-17-01）— 采用型（宪法 1.2.0）：在用户默认采用清单中或项目采用时适用
   - 自动模式下同样如此。工具适配器的工作树隔离（例如 Claude Code Agent 工具的 `isolation: "worktree"`、`EnterWorktree`）和 `git worktree add` 都属于此类
   - 默认是在用户所看到的检出（checkout）的单一分支上顺序工作。即使使用多个 Worker，也在同一个检出中按顺序执行
   - 只有并行会话、并行 Worker 确实需要工作树时，才把必要性、分支名称、清理计划作为一项提出，并且仅在被接受时才创建。一次接受只对该提议有效
   - 经同意创建的工作树，在任务结束后保留分支并清理，同时报告位置和分支
   - 原因：用工作树隔离后，对代理所写内容的评审、检查无法正常进行，用户无法直接确认变更和工作历史，形态追踪也变得困难
8. **为确认推测而进行的部署，仅限于只能靠部署才能复现的环境**（DEC-2026-09-18-01，strata）
   - 能通过阅读代码、日志、单元测试、本地运行确认的推测，不要用部署来确认。把东西放到共享环境（dev、stage）上，只是为了确认仅在该环境中才会复现的现象（基础设施、路由、与其他服务的联动、真实数据）
   - 部署前，要写明想确认什么，把已确认的事实与推测分开，并一并报告回滚方法（revert 提交、之前的镜像）
   - 认证、路由、会话这类会影响其他产品线或其他用户的变更，必须先用该产品线的用户流程（例如 2.0 登录和 3.0 登录两者）实测之后才能上线
   - 原因：2026-09-18 在 stage 上仅凭推测就晋升了网关路由，导致 2.0 登录损坏，修正推测后再次上线的部署一天内重复了好几次。部署回滚也要花时间，并且会阻塞他人的工作
9. **交接中的未决（pending）项必须同时写明受阻原因（blocker）和解除条件（unblocked_by）**
   - 禁止只写"等待"。如果下一个会话不知道在等什么，未决项就只会被不断结转
