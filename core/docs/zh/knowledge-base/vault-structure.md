# Knowledge Base — Vault 结构

> 正本：strata-kit `core/docs/zh/knowledge-base/vault-structure.md`（2026-10-29 从 strata `docs/07-knowledge-base/vault-structure.md` 迁移，DEC-2026-10-29-11）。

## 概述

Vault 是所有项目共享的、兼容 Obsidian 的知识库。
它作为独立的 Git 仓库管理，与项目代码分离。

## 三层模型（Archive / Knowledge / Index）

vault 中的所有内容都属于三层之一，每一层的维护规范各不相同（DEC-2026-08-19-04）：

| 层 | 目录 | 规范 |
|---|---|---|
| **Archive** | `projects/*/sessions/`, `projects/*/tasks/`, `projects/*/relays/` | append-only。write-once 是**正常**的——没有修订或链接的义务。它是证据库，不是 KB |
| **Planning**（Archive 的变体） | `projects/*/planning/{source}/` | 从外部规划工具（Notion 等）导入的规划原文（`type: planning`）。**原文各节不可变**（Archive 规范），只更新文档末尾的 `## 구현 검토`（实现评审）一节——按策略条目用表格记录是否已实现、与规划的差异及依据，并以 frontmatter 的 `implementation.status` 分类。有实质内容的策略要提炼成 Knowledge 规格，该规格的 `sources:` 指向原文（DEC-2026-09-09-01） |
| **Knowledge** | `projects/*/knowledge-base/`, `patterns/`, `_index/glossary.md` | **必须 update-in-place**——更新时必须有 `updated:`，且必须有指向依据 Archive 文档的出处链接（`sources:` frontmatter） |
| **Index** | `_index/`, 各 `_index.md`, `projects/*/decisions/` 中的 DEC 笔记, `projects/*/nodes/` 中的节点页面 | **仅生成——禁止手工编辑。** 从正本（记录、frontmatter、toc.yaml）重新生成（DEC projection generator、节点页面生成器——实现对应：`python3 -m kb --help` · `core/docs/zh/kb-engine.md`） |

知识晋升（Archive → Knowledge）由提炼会话执行，并经过 Decision Inbox 门禁。
优先更新已有的 Knowledge 文档，而不是创建新文档（活文档原则）。

### 三种文档的角色与位置（DEC-2026-09-30-03）

| 文档 | 包含什么 | 放在哪里 | 默认搜索 |
|---|---|---|---|
| 规格（决策） | 针对代码和实现需求在实现时做出的决策及理由、目标代码符号、是现行还是已被取代 | decision 记录（Tier P）→ DEC 笔记镜像 | 建索引之前——直接读取索引（`decisions.yaml`）和 DEC 笔记（纳入索引是后续工作） |
| KB（Knowledge） | 以人能理解的目录和流程说明服务与领域的最终形态 | `knowledge-base/`，目录在 `_meta/toc.yaml` | 包含 |
| 工作历史（Archive·Planning） | 会话记录、任务规格、带日期的诊断与报告、外部规划原文 | `sessions/`, `tasks/`, `relays/`, `planning/` | 排除（仅在明确请求时） |

- **目录中的每个位置只有一份 KB 文档。** 不要为同一主题创建新文档，而是改写已有文档。若不得不用新文档取代，则用 `status: superseded` + `superseded_by` 关闭旧文档。
- **带日期的报告、诊断、快照不是 KB。** 文件名或标题中含日期的文档（如 `*-2026-09-16.md`）记录的是当天的事实，因此放在工作历史（`tasks/{date}/` 或 `sessions/`）中。KB 只反映由此改变的最终形态，并用 `sources:` 指向该报告。
- **默认搜索只看 KB。** 只有向搜索工具明确请求时才包含工作历史（`search_docs(include_history=true)` 或指定 `category`，CLI 的 `--include-history`）。这是为了避免历史把正本挤出搜索结果。

贯穿三层的关键是**主题节点**。节点是人阅读的目录的单位，其正本是项目的 `_meta/toc.yaml`。
文档通过 frontmatter 的 `nodes:` 声明归属，节点页面则通过**联接**指向该节点的 Knowledge（最终形态·策略）、决策和 Archive（工作历史）来生成。
节点页面不是晋升。它不新写任何内容，只是把已有的东西汇集到一个页面上；有空洞就让空洞可见。这个空洞就是对缺失的可视化。

## 目录结构

```
vault/
├── .obsidian/           Obsidian 应用设置（共享，git 跟踪）
│   └── plugins/         Custom Sort、Dataview 等插件设置
├── .kb/                 ★ KB 索引管理
│   ├── manifest.json    按文件的 SHA256 哈希（git 跟踪）
│   ├── schema.sql       DB 模式定义（git 跟踪）
│   └── store.sqlite     KB store（strata-kit kb，.gitignore——legacy 的 kb.sqlite 已由 DEC-2026-10-28-13 移除）
├── .local/              按机器的设置（.gitignore）
│   └── resolved-paths.yaml
├── .gitignore
├── env-config.yaml      已注册的机器 alias 及指纹（OS 机器标识的哈希，不含路径）
│
├── _index/              MOC (Map of Content)
│   ├── projects.md      项目列表 + 链接
│   ├── decisions.md     跨项目 ADR 索引
│   ├── patterns.md      模式/教训索引
│   └── glossary.md      领域术语表
│
├── _meta/               ★ 全局设置
│   └── taxonomy.yaml    分类体系定义（类别、类型、标签）
│
├── projects/            按项目的知识
│   └── {project-name}/
│       ├── overview.md          技术栈、目的、当前状态
│       ├── _meta/               项目设置
│       │   ├── taxonomy.yaml    项目扩展 taxonomy（继承全局）——目录轴
│       │   └── toc.yaml         ★ 主题节点树（人阅读的目录的正本）——主题轴
│       ├── knowledge-base/      ★ 项目 KB（索引对象）
│       │   ├── _index.md        MOC（Dataview 动态目录）
│       │   ├── domain/          领域知识（类别 1）
│       │   │   ├── _index.md    类别 MOC
│       │   │   ├── epics/       按 epic 的领域知识
│       │   │   └── {topic}/     主题目录（在项目 taxonomy 中定义）
│       │   │       ├── _index.md
│       │   │       └── *.md     KB 文档
│       │   ├── architecture/    技术架构（类别 2）
│       │   │   ├── _index.md
│       │   │   ├── decisions/   ADR
│       │   │   ├── constraints/ Constraint Card
│       │   │   ├── api-contracts/
│       │   │   ├── data-models/
│       │   │   ├── infrastructure/
│       │   │   └── *.md
│       │   ├── guides/          指南（类别 3）
│       │   │   ├── _index.md
│       │   │   ├── onboarding/
│       │   │   ├── conventions/
│       │   │   ├── troubleshooting/
│       │   │   └── *.md
│       │   └── references/      参考（类别 4）
│       │       ├── _index.md
│       │       └── *.md
│       ├── tasks/               ★ 任务规格（Builder→Worker）
│       │   └── {yyyy.mm.dd}/    按日期分组
│       │       └── {nn}-{title}/  Work Order 文件夹
│       │           ├── _order.yaml    工作指令书
│       │           └── task-{nn}-*.yaml  Worker 执行规格
│       ├── strata/              ★ detached profile 的 Tier P 正本（core/docs/zh/environment/data-placement.md §1.5）
│       │   ├── profile.yaml     placement profile manifest（新 PC 的 bootstrap 锚点）
│       │   ├── decisions/       decision 记录（DEC-*.yaml，一个决策 = 一个文件）
│       │   ├── decisions.yaml   生成式索引（禁止手工编辑）
│       │   ├── constraint-registry.yaml
│       │   └── layer-map.yaml
│       ├── decisions/           DEC 笔记——仅生成（DEC projection generator，禁止手工编辑）
│       │   └── DEC-YYYY-MM-DD-NN.md
│       ├── nodes/               节点页面——仅生成（节点页面生成器，禁止手工编辑）
│       │   └── {node-id}.md     例）orders.checkout-v2.coupon.md
│       ├── planning/            ★ 规划文档（type planning）——由规划文档导入器生成，原文不可变 + 实现评审节
│       │   └── {source-name}/   按来源（例：notion-orders-intake）。文件名 {原标题-slug}--{来源 id 前 8 位}.md——保留原标题的语言
│       └── sessions/            会话交接·ledger（Archive）
│           └── session-YYYY-MM-DD-{slug}.md
│
├── patterns/            跨项目模式
│   └── {pattern-name}.md
│
├── strata-feedback/     方法论反馈记录
│   └── {topic}.md       已应用/未应用的反馈
│
├── references/          外部参考、API 摘要
│   └── {reference-name}.md
└── assets/              二进制资产（图片、Excel 等——禁止放在 vault 根目录）
```

## 命名规则

| 对象 | 格式 | 示例 |
|---|---|---|
| 项目目录 | kebab-case | `my-api-server` |
| 文档文件名 | kebab-case.md | `auth-strategy.md` |
| DEC 笔记（生成） | DEC-YYYY-MM-DD-NN.md | `DEC-2026-08-19-01.md` |
| 节点页面（生成） | {node-id}.md——节点 id 原样，包含点(.) | `orders.checkout-v2.coupon.md` |
| 会话文档 | session-YYYY-MM-DD-{slug}.md | `session-2026-08-19-vault-restructure.md` |
| MOC 文件 | 单数名词 | `projects.md`, `glossary.md` |

会话文件名只使用上面这一种格式——`handoff-*` 前缀、无前缀的日期文件名、`.yaml` 会话文件均已废止（legacy 属于迁移对象）。真正的标识符是 slug，而不是序号（NN）。

## 稳定 ID（frontmatter `id:`）

每个 vault 文档的 frontmatter 中都有一个稳定 ID，在移动、改名时保持不变：

```yaml
id: "kb-shop-api-order-concepts"   # {前缀}-{project}-{slug} — 生成后不可变
aliases: ["旧文件名"]                   # 移动、改名时保留原标识符（吸收 Obsidian 的 unlinked mentions）
```

前缀覆盖所有文档类别（已反映 2026-08-19 的 cross-review）：

| 前缀 | 对象 | 示例 |
|---|---|---|
| `kb` | knowledge-base/、patterns/ 中的文档 | `kb-shop-api-order-concepts` |
| `session` | sessions/（交接·ledger） | `session-strata-2026-08-19-vault-restructure` |
| `order` | 工作指令书 `_order.md` | `order-strata-2026.08.19-01` |
| `task` | 任务规格文档 | `task-strata-2026.08.19-01-task-03` |
| `dec` | DEC 笔记（生成） | `dec-strata-2026-08-19-01` |
| `relay` | relays/ 的 packet·feedback | `relay-strata-2026-08-19-task01-core-spec-review` |
| `moc` | `_index/` 及各 `_index.md` 的 MOC | `moc-shop-api-knowledge-base` |
| `node` | `nodes/` 中的节点页面（生成） | `node-shop-api-orders.checkout-v2.coupon` |
| `plan` | `planning/` 中的规划文档（导入） | `plan-shop-api-0123456789abcdef0123456789abcdef`——slug 是来源（Notion）的 id，重新导入也不变 |
| `doc` | 不属于以上任何一类的其他文档 | `doc-vault-env-config` |

- **{project} 的取值**：`projects/{name}/` 之下用该项目名。**跨项目文档**（`patterns/`、`references/`、`_index/`、vault 根目录）使用 `vault`（例：`kb-vault-{slug}`、`moc-vault-decisions`）。
- 路径只是导航手段，不是长期身份。链接和引用的身份由 `id:` 承担。
- 迁移（移动、改名）时保留 `id:`，并把旧文件名加入 `aliases:`。
- **节点 id 与文档 id 是不同的命名空间。** 它是像 `orders.checkout-v2.coupon` 这样从祖先起用点(.)连接的路径，不遵循上面的前缀体系。文档在 `nodes:` 字段中写节点 id，只有节点页面的**文档** id 以 `node-{project}-{node-id}` 纳入前缀体系。只有 `node` 前缀允许 slug 中含点。

## KB 类别体系

在 taxonomy.yaml 中定义，由 4 个类别组成：

| 类别 | 目的 | depth 限制 | 主要类型 |
|----------|------|:---:|-----------|
| `domain` | 业务领域知识 | 3 | concept, specification, flow |
| `architecture` | 设计决策、API、基础设施、约束 | 2 | specification, decision, overview, constraint |
| `guides` | 上手引导、约定、故障排查 | 2 | guide, pattern, runbook |
| `references` | 外部标准、规范参考 | 2 | reference, glossary |

- 没有 NN 前缀——排序按 taxonomy 的 `order` 字段
- 类别由目录推导（不写入 frontmatter）
- `domain` 类别的 children 在项目 taxonomy 中定义
- 详细规则：`templates/vault/_meta/taxonomy.yaml`

类别是**目录轴**（文档放在哪里），主题节点是**主题轴**（文档讲的是什么）。两者是分开的。
类别不写入 frontmatter 是因为会与路径重复，而 `nodes:` 是无法从路径推导的信息，所以不算重复。一个文档可以属于多个节点，节点不创建目录。
节点树的正本与规则：项目的 `_meta/toc.yaml`，格式规则见全局 taxonomy 的 `topic_nodes` 节。

## 项目上手流程

向 vault 注册新项目时：

1. 创建 `vault/projects/{project-name}/` 目录
2. 编写 `overview.md`（含必需的 frontmatter，参见 document-format.md）
3. 更新 `_index/projects.md`（Index 层——转为生成式之后改为重新生成）
4. 创建 `_meta/taxonomy.yaml`（定义项目的领域主题）
5. 创建 `_meta/toc.yaml`（主题节点树——只要第一个节点就够了。起点是文档开始带有 `nodes:` 的时刻）
6. 在 `knowledge-base/` 下创建类别目录（`domain/`、`architecture/`、`guides/`、`references/`）
7. 创建 `sessions/`、`tasks/` 目录。若是 detached profile 项目，还要包含 `strata/`（Tier P）——必须有 `profile.yaml` manifest（core/docs/zh/environment/data-placement.md §1.5）。`decisions/` 和 `nodes/` 由生成器创建

### overview.md 的最低内容

```markdown
---
title: "{项目名}"
type: overview
project: {project-name}
tags: [{技术栈标签}]
created: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
status: active
---

## 目的
{用 1-2 句话写项目目的}

## 技术栈
- 语言：{language}
- 框架：{framework}
- DB：{database}

## Strata 层映射
{本项目目录 → Strata 层的映射}
```

## 绝不包含的内容

- 源代码（代码片段作为例外允许）
- 构建产物
- 因环境而异的绝对路径
- 密钥、密码、令牌
- 原始的交接 YAML（只保存摘要）

例外：frontmatter `covers:` 中的仓库**相对路径、符号、端点、表名**是指针而不是代码，因此允许。绝对路径和代码正文仍然禁止。
