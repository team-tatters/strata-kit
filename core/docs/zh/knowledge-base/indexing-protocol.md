# Knowledge Base — 索引协议

> 正本：strata-kit `core/docs/zh/knowledge-base/indexing-protocol.md`（2026-10-29 从 strata `docs/07-knowledge-base/indexing-protocol.md` 迁移，DEC-2026-10-29-11）。

> **2026-10-29 现行化**：本文档描述现行引擎（一个 `store.sqlite`，`python3 "$STRATA_KIT/kb"`）。
> 早先的 `.kb/kb.sqlite`、基于 manifest 哈希的增量构建和 sqlite-vec 设计已废弃（DEC-2026-10-28-13）。
> 存储 schema、后端和门禁（gate）的正本是 `core/docs/zh/kb-engine.md`，本文档处理索引范围、检索用法和生成视图。

## 概述

把 vault 的 KB 文档按分块（chunk）为单位索引进 `store.sqlite`，以减少智能体的 token 消耗并实现精准检索。
索引是随时可以从源头（vault 文档、决策记录（decision record）、代码表面）重新生成的缓存，由各环境在本地构建。

## 问题定义

| 问题 | 说明 |
|---|---|
| 被迫全量遍历 | 智能体必须读 _index.md → 相关文件全文，才能到达想要的 section |
| 跨文件 token 消耗 | 遍历 17 个文件（68K chars）会浪费上下文窗口 |
| 缺少排序 | 页面之间没有逻辑顺序，需要智能体自己判断如何导航 |
| 无法语义检索 | 没有关键词匹配就找不到相关文档（用嵌入检索来补足） |

## 阶段划分

| 阶段 | 内容 | 状态 |
|---|---|---|
| **FTS** | 按分块的 FTS5（bm25）+ 按 frontmatter `page_order` 排序 | 已应用 — 进入检索时自动检查新鲜度 |
| **向量·混合** | 本地 BAAI/bge-m3 嵌入 + 与 FTS 的 RRF 融合 | 已实现 — 向量只有运行 `python3 "$STRATA_KIT/kb" embed` 才会生成（DEC-2026-10-28-09）。MCP `search_docs` 的默认 mode 是 hybrid，`kb search` CLI 的默认是 FTS（用 `--semantic`·`--hybrid` 切换） |

早先“Phase 1（FTS5 + manifest 哈希）/ Phase 2（sqlite-vec·`--with-vectors`，已实现·未应用）”的划分已废弃。索引不再分成两个，只有一个 store，向量附在 store 的分块上。

## 架构

### 文件布局

```
vault/
├── .kb/
│   ├── store.sqlite            # .gitignore — 唯一的索引（本地构建产物）
│   ├── manifest.json           # 不追踪 — 索引元数据，每台机器各自生成 (DEC-2026-10-29-04)
│   ├── link-baseline.json      # 链接门禁基线（只向减少的方向更新）
│   └── review-candidates.json  # .gitignore — 评审候选（生成物）
│
├── .gitignore
└── projects/{name}/knowledge-base/
    └── *.md                    # 索引源文件
```

`.kb/store.sqlite` 及其 `-wal`、`-shm` 都在 vault 的 `.gitignore` 中。确认方法：`.gitignore` 的“KB store”一节。
schema 不由文件定义，而由代码（`kb/store.py`）定义。没有 `schema.sql`（DEC-2026-10-28-13）。

### 构建引擎布局

```
strata-kit/
└── kb/                         # git 追踪 — 索引引擎 (python3 "$STRATA_KIT/kb" build-index)
```

构建引擎位于 strata-kit 仓库。运行时通过 `$STRATA_VAULT` 环境变量引用 vault 路径。

### 数据流

```
编辑 MD 文件 → git commit + push
                    ↓
其他环境: git pull
                    ↓
进入检索(kb search / MCP)时自动执行:             engine.ensure_fresh_store
  比较源文件 mtime 与 store 的 built_at (无哈希，低成本)
    ├─ 新鲜 → 直接查询
    ├─ stale → 重新生成整个 store (1~2 秒)
    └─ store 不存在(新机器) → 通过同一路径自动生成
                    ↓
store.sqlite (nodes · edges · chunks + FTS5 · 嵌入缓存)
                    ↓
智能体: kb search / MCP search_docs → 返回 chunk + file:line
```

- 没有增量重新索引。store 每次都整体重建（1~2 秒）。只挑选变更部分的 manifest 哈希比较已废弃。
- 可以手动运行（`python3 "$STRATA_KIT/kb" build-index`）和 MCP `build_index`，但**日常路径是自动的**。
- 新鲜度检查或重新生成失败不会阻止查询（给出警告后使用现有 store）。逃生口：`KB_NO_REFRESH=1`。
- `build-index` 重新生成 store 之后，会输出生成视图（节点页面·Obsidian sortspec·评审 Inbox·`manifest.json`）和 taxonomy 校验警告。若有 block 违规则 exit 2。行为与职责见 `core/docs/zh/kb-engine.md`。
- 嵌入不由 `build-index` 计算。`python3 "$STRATA_KIT/kb" embed` 只计算缺失的分块并放入 store，计算出的向量保留在 `embeddings` 缓存中，即使重建 store 也会复用。

### 索引覆盖范围 (2026.08.19-06 B1)

- **Knowledge**：`projects/*/knowledge-base/` — 全文索引（沿用）。自 2026-09-08 起，`patterns/`·`_index/glossary.md`（项目值 `vault`）·`projects/*/overview.md` 也做全文索引 — 与 vault-structure.md 三层表中 Knowledge 的范围一致。
- **Archive**：`projects/*/sessions/`·`tasks/` 下的 `.md` — **只索引元数据（topic·orders·kb_updates·decisions_made·nodes·doc_change）+
  正文摘要部分（前 40 行）**。缺了 `nodes` 就无法生成节点页面的“工作历史”面，所以把它列入白名单。以 category=`archive`、topic=`sessions|tasks` 分面来区分和过滤
  （MCP `category` 过滤）。目的是让检索能回答“哪个会话处理过它”。**检索默认排除 Archive·Planning**（DEC-2026-09-30-03） —
  想看历史，用 `kb search --include-history`、MCP `search_docs(include_history=true)`，或明确指定 `category`。`--include-history` 也会一并检索决策·订单记录。
- Archive 不适用 KB 校验（lifecycle 等） — ledger 的 status（open/closed）在 KB 契约之外。
  **例外**：`node_id_check`（nodes 的值是否在 toc.yaml 中）也适用于 Archive。因为节点拼写错误会让会话从工作历史面消失。
- **Planning**：`projects/*/planning/{source}/` — 策划原文**全文索引** + KB 校验（required_fields·lifecycle_override·node_id）。category=`planning`、topic=`{source}` 分面。是节点页面“策划”面的来源。status 是策划状态（不是 active），因此不在评审候选策略之内 (DEC-2026-09-09-01)。
- **节点页面**（`projects/*/nodes/`）是 `indexed: metadata` — 各面的原文已被索引，所以只索引摘要部分。
- **DEC 笔记**（`projects/*/decisions/`）不作为文档索引（保持现状）。决策由决策记录 provider 作为 store 的决策节点放入，决策所属的节点由节点页面生成器读取记录正本中的 `nodes` 得出。
- 符号链接（`latest.md`）和 yaml 不索引。

## KB Result Contract — 已废弃 (DEC-2026-08-19-06)

通用的结果 schema 契约**已废弃**。制定之后没有任何消费者（kb-search、strata-mcp）实现它，
它们各自以自己的结果形态稳定运行，而契约的前提——多个消费者（strata-kb-server、Hub）——并不存在。

- **复活条件**：当第二个消费界面（如 Hub）真正出现时，基于当时实际使用的字段重新设计契约。
- 节点页面生成器是 vault 内部的生成物，不算“第二个消费界面”。不推翻这一废弃决定。
- 废弃前的契约全文见 git 历史（本文件，2026-08-19 之前）。

## 存储 schema

schema（`nodes`·`edges`·`chunks`·`baselines`·`revisions`、FTS5 虚拟表 `chunks_fts`、`embeddings` 缓存）的正本是 `core/docs/zh/kb-engine.md` 的“Schema”一节。这里只写检索所需的部分。

- 检索单位是 `chunks`。分块有 heading·text·title·tags 和 `meta_json`（heading_level·line_start·line_end·char_count）。文档·决策·订单共用一个 FTS 表、一个 bm25 尺度。
- FTS5 用 `unicode61` 索引 heading·text·title·tags 四列。
- 文档的 taxonomy 分面（category·topic·section_name·page_order 等）在文档节点的 payload 中，由 `kb search` 的过滤器和 `--toc` 排序读取。
- 链接是 `links` 边，文档之间的关系（supersedes 等）和 `covers` 也是边。早先的 `document_links` 表已不存在。

早先的 schema（`documents`·`chunks`·`chunks_fts`（doc_title·doc_tags 列）·`document_links`·`coverage` 表、`sha256`·`section_name` 列、`chunks_vec`）属于 legacy 索引（`.kb/kb.sqlite`），已由 DEC-2026-10-28-13 废弃。直接用 SQL 查询的方式也一并消失。查询请使用 `kb search`·MCP·`kb coverage`。

### 主题节点·覆盖

文档的 `stable_id`·`nodes`·`covers`·`doc_change` frontmatter 会成为 store 的节点 payload 和 `covers` 边。从代码表面反查文档的规则不变。

- “拥有这个路径的规格是什么”：`python3 "$STRATA_KIT/kb" coverage resolve|nodes|unowned|docs-to-update`
- “这个节点的最终形态是哪份文档”：`kb coverage node`（节点页面生成器使用）
- “这个路径变更之后，所属文档更新了吗”：会话结束门禁 `kb coverage-gate`
- 节点树本身直接读取 `_meta/toc.yaml`。`endpoints`·`tables` 不按文件路径解析，仅用于节点页面显示。

构建时校验（全部为 warn）：`node_id_check`（格式，toc.yaml 是否存在·是否登记 — 也适用于 Archive）、`covers_path_check`（结构·相对路径·禁止文件粒度）、
`supersedes_symmetry_check`（A.supersedes=B ⇔ B.status=superseded ∧ B.superseded_by=A）、doc_change 的值·理由。评审候选作为生成物（评审 Inbox）记录，状态转换只通过明确的命令（`build-index --apply-review`）进行。

## 变更检测与多环境同步

变更检测不是 manifest 哈希，而是比较源文件 mtime 与 store 的 `built_at`（`engine.ensure_fresh_store`）。因此环境之间没有需要达成一致的索引状态。共享的只有 vault 文档和决策记录，store 由各环境在本地构建。

```
[环境 A — 编辑文档]
1. 编辑 MD 文件
2. git commit + push   (会话结束时 handoff 同步 vault)

[环境 B — 同步]
1. git pull
2. 进入检索时 store 自动重新生成 — 手动则用 python3 "$STRATA_KIT/kb" build-index
```

**核心原理：**store 是缓存，所以不提交到 git（`.gitignore`）。没有二进制冲突，在任何机器上都能从同样的源头重新生成同样的结果。

生成物中哪些被追踪以及由谁写入，由 DEC-2026-10-29-04 规定。

| 生成物 | 追踪 | 写入方 |
|---|---|---|
| `.kb/store.sqlite` | 否 | 各机器进入检索时·`build-index` |
| `.kb/manifest.json` | 否（每台机器的比较记录） | 各机器的 `build-index` |
| DEC 笔记（`projects/*/decisions/`） | 是 | 决策 CLI — 记录该决策的会话连同记录一起提交 |
| 节点页面·`_index/review-needed.md` | 是 | librarian 每天一次 `kb views-publish`（build-index 之后只 commit-push 这些文件）。普通会话的 `build-index` 只更新本地索引，不提交这些文件 |
| `.kb/link-baseline.json` | 是 | 只向减少的方向更新 |

早先“通过 git 共享 `manifest.json` 以对齐文件状态、只索引变更部分”的方式是 legacy 设计，已废弃（DEC-2026-10-28-13、DEC-2026-10-29-04）。

## 智能体检索协议

### 检索优先级

```
① FTS5 关键词检索 (知道确切术语时)
② FTS5 复合检索 (AND/OR 组合，--category·--topic 过滤)
③ 元数据查询 (--toc 排序后的目录，--doc 文档内分块)
④ 混合·语义检索 (自然语言查询 — 需要向量)
```

智能体使用 `kb search` 或 MCP `search_docs`（mode：hybrid 默认 · dense · fts），而不是 SQL。结果返回分块的 `file:L行-行` 位置和字符数。

### 使用示例

**关键词检索 — 返回相关 chunk：**
```bash
python3 "$STRATA_KIT/kb" search "환불수수료" --limit 5
```

**复合检索 — AND + 过滤：**
```bash
python3 "$STRATA_KIT/kb" search "정산식 AND Payment" --category domain
python3 "$STRATA_KIT/kb" search "정산식" --category domain --topic orders
```

**查询排序后的目录：**
```bash
python3 "$STRATA_KIT/kb" search --toc --category domain
```

**返回精确位置 — 与 Read tool 衔接：**
```
kb search "FormulaBaseStructure"
# 结果: domain/orders/payment-shipping.md  位置: L46-101
# → 向 Read tool 传入 offset=46, limit=55
```

## FTS5 检索语法参考

`kb search` 会把查询的每个 token 用引号括起来再传给 FTS5。因此只有下列语法有效。

| 语法 | 示例 | 说明 |
|---|---|---|
| 单个关键词 | `환불수수료` | 包含该 token 的 chunk |
| 空格并列 | `Transactional Composite` | 两个 token 都包含 (AND) |
| AND | `Transactional AND Composite` | 两个 token 都包含 |
| OR | `Payment OR Shipping` | 至少包含一个 |
| NOT | `환불 NOT Coupon` | 排除条件 |
| prefix | `Refund*` | 以 Refund 开头的 token |

无效的语法：列指定（`doc_tags:orders`·`tags:orders` — 无结果，请改用 `--category`·`--topic` 过滤，只看标签时用 `--tags`）、短语检索（`"REST Docs"` — 引号会被去掉，变成两个 token 的 AND）、`NEAR`。旧文档中的 `doc_tags:`·`content:` 列名属于 legacy 索引（现行的列是 heading·text·title·tags）。

## Frontmatter 扩展 — page_order 字段

在现有 document-format.md 的 frontmatter 中增加排序字段：

```yaml
---
title: "Order Payment & Shipping"
type: concept        # domain 是类别（目录），不是文档类型
project: shop-api
tags: [orders, payment, shipping]
created: 2026-04-07
updated: 2026-04-07
page_order: 3              # ★ 新增 — 章节内的文档顺序
---
```

`--toc` 先按 taxonomy 的 category·topic 顺序，再在其内按 `page_order` 排序（taxonomy 之前的 NN-prefix 目录文档使用 `section_order`）。
`page_order` 在 frontmatter 中明确写出，用来定义章节内的逻辑顺序。

## token 节省效果（实测）

下面是 legacy FTS5 索引时期（2026-04）在某个后端项目的 vault 上的实测（15 篇文档，210 chunks，68K chars）。按分块读取的原理在现行 store 中相同，但数值从未用现行引擎重新测过。

| 检索查询 | 原有（全文读取） | FTS5（chunk） | 节省率 |
|-----------|-----------------|-------------|--------|
| "환불수수료" | 68,242 chars | 3,473 chars | **95%** |
| "TransactionalExecutor" | 68,242 chars | 1,181 chars | **99%** |
| "정산식 AND Payment" | 13,939 chars (3 个文件) | 6,758 chars | **52%** |

## 向量检索 (bge-m3 混合)

正本：`core/docs/zh/kb-engine.md` 的检索一节，DEC-2026-10-28-09。

### 摘要

| 项目 | 现行 |
|---|---|
| 模型 | BAAI/bge-m3，本地运行（sentence-transformers，Apple Silicon 用 MPS），1024 维归一化向量 |
| 存储 | store 的 `chunks.embedding` + 重建后仍保留的 `embeddings(model, text_hash, dim, vector)` 缓存 |
| 向量检索 | numpy 余弦暴力计算（约 7 千个分块的规模下仅需数 ms — 不需要 ANN） |
| 混合 | FTS（bm25）与向量的 RRF（k=60）融合 |
| 效果判断 | `python3 "$STRATA_KIT/kb" search-eval` — 用 vault `_meta/search-eval.yaml` 的查询集计算 recall@k（fts · dense · hybrid） |
| 嵌入计算 | `python3 "$STRATA_KIT/kb" embed`（只算缺失的分块。`--model` · `--batch` · `--max-seq` · `--max N`） |

### 备选方案及未采用的理由

| 备选方案 | 判断 |
|---|---|
| sqlite-vec | 分块超过 10 万个时通过适配器切换（DEC-2026-10-28-09）。现在不需要 |
| LanceDB 等外部向量数据库 | 与“只有一个存储”的契约（DEC-2026-10-28-04）不符，且在这个规模下没有收益 — 不引入 |
| khoj | 是带有独立主机·UI·数据库的应用，所以不引入 |
| paraphrase-multilingual-MiniLM-L12-v2 (384 维) | legacy 设计的模型。由 bge-m3 取代 |
| ONNX Runtime · 云端嵌入 API | 不采用。embedder provider 可以替换（kb-engine.md），但当前实现只有本地 bge-m3 |

早先的 `build-index --with-vectors`、`apsw`（用于加载 sqlite-vec）、`chunks_vec` 虚拟表是 legacy 设计，并不存在。

## 检索工具速查表

### 构建

```bash
# 日常: 不需要 — 进入检索时若 store 是 stale 则自动重新生成

# 手动构建 store + 生成视图(节点页面·sortspec·评审 Inbox·manifest)
python3 "$STRATA_KIT/kb" build-index

# 只把报告范围限定为一个项目 (store 始终是全部)
python3 "$STRATA_KIT/kb" build-index --project shop-api

# 只重新生成 store / 统计
python3 "$STRATA_KIT/kb" build-store
python3 "$STRATA_KIT/kb" store-stats

# 计算缺失分块的嵌入 (在语义·混合检索之前)
python3 "$STRATA_KIT/kb" embed

# 把评审候选转换为 status: review-needed 并重新构建
python3 "$STRATA_KIT/kb" build-index --apply-review
```

`--force` 是兼容用的标志，没有效果（store 每次都整体重新生成）。没有 `--with-vectors`。

### 检索 (kb search)

> 下面的 `kb search` 是 `python3 "$STRATA_KIT/kb" search` 的简称。

```bash
# ─── FTS5 关键词检索 ───
kb search "환불수수료"                          # 单个关键词
kb search "Transactional AND Composite"       # AND 复合
kb search "Payment OR Shipping"                  # OR
kb search "Refund*"                         # prefix
kb search "정산식" --category domain --topic orders   # 类别·主题过滤 (代替列指定语法)
kb search "환불수수료" --limit 10 --content      # 结果数 + 内容预览
kb search "jwt" --category architecture       # 类别过滤 (还有 --topic、--status、--project)
kb search "환불수수료" --include-history         # 连同会话·任务·策划原文以及决策·订单

# ─── 语义·混合检索 (用 kb embed 生成向量之后) ───
kb search "환불 금액을 계산하는 흐름?" --semantic
kb search "인증 토큰 만료 시 처리" --hybrid --content

# ─── 导航 ───
kb search --toc                               # 完整目录 (已排序)
kb search --toc --category domain             # 类别过滤
kb search --doc "domain/orders/payment-shipping.md"       # 文档内的 chunk 目录
kb search --tags orders                          # 标签检索 (无查询词，仅标签)
kb search --stats                             # 索引统计
```

`--section` 是为 taxonomy 之前的 NN-section 目录保留的兼容过滤器。新文档请使用 `--category`·`--topic`。

### FTS5 vs 语义 — 何时用哪个

| 情形 | 推荐 | 理由 |
|------|------|------|
| 知道确切的类名/函数名 | FTS5 | `FormulaBaseStructure` → 精确匹配，立即返回 |
| 检索特定术语 | FTS5 | `환불수수료`、`TransactionalExecutor` → BM25 rank |
| 自然语言问题 | **语义·混合** | "환불 금액을 계산하는 흐름?" → 克服关键词不匹配 |
| FTS5 没有结果 | **语义** | "인증 토큰 만료 처리" → FTS5 为 0 条，语义有返回 |
| 先用类别/主题缩小范围之后 | FTS5 | `--category domain --topic orders` 过滤 |
| 不知道从哪里开始读 | `--toc` | 排序后的目录 → 掌握文档结构 |

## FTS5 关键词拆分指南

FTS5 的 `unicode61` 分词器**只按空白和标点切分 token**。
它不做韩语词素分析，所以检索时关键词的拆分策略很重要。

### 问题：为什么需要拆分关键词

```
文档原文:  "환불수수료 변경 시 재계산 처리"
              ↓ unicode61 分词
token:     ["환불수수료", "변경", "시", "재계산", "처리"]
```

| 检索查询 | 是否匹配 | 理由 |
|-----------|----------|------|
| `환불수수료` | ✅ | token 完全一致 |
| `환불수수료변경` | ❌ | 不存在“환불수수료변경”这个 token |
| `환불수수료 AND 변경` | ✅ | 两个 token 各自存在 |
| `환불` | ❌ | “환불수수료”的子串不会匹配 |
| `환불*` | ✅ | 通过 prefix 检索匹配“환불수수료” |

### 拆分规则

**1. 复合的韩语术语用空格拆开，再做 AND 检索**

```bash
# ❌ 连写则不匹配
kb search "환불수수료변경"

# ✅ 拆分 + AND
kb search "환불수수료 AND 변경"
```

**2. 需要部分匹配时使用 prefix(*)**

```bash
# ❌ 只用 "환불" 找不到 "환불수수료"
kb search "환불"

# ✅ 用 prefix 同时匹配 "환불수수료"、"환불금액"、"환불요청"
kb search "환불*"
```

**3. 英文类名不区分大小写，也不做 CamelCase 拆分**

```bash
# ✅ unicode61 会规范化大小写
kb search "formulabasestructure"      # 匹配 FormulaBaseStructure

# ❌ 无法在 CamelCase 内部拆分
kb search "Formula AND Base"          # 两个单词必须各自存在

# ✅ 用 prefix 绕过
kb search "Formula*"
```

**4. 韩语 + 英语混合查询**

```bash
# ✅ 用 AND 连接各语言的 token
kb search "Payment AND 정산식"

# ✅ 类别·主题过滤 + 内容检索组合
kb search "Payment" --category domain --topic orders
```

**5. 关键词拆分仍不行 → 切换到语义·混合检索**

```bash
# FTS5 难以找到的自然语言查询
kb search "인증 토큰이 만료되면 어떻게 처리하나요?" --hybrid
```

FTS 因韩语助词·合成词而漏掉的部分（以评估集为准为 4~8%）交给向量，并决定在评估之后用 FTS5 trigram 表或 bge-m3 sparse 来加强（DEC-2026-10-28-09）。

### 智能体检索决策树

```
收到问题
  │
  ├─ 知道确切的术语/类名吗?
  │   └─ YES → FTS5: kb search "术语"
  │
  ├─ 是复合的韩语术语吗?
  │   └─ YES → FTS5: 按空格 + AND 拆分
  │            例: "환불수수료 AND 변경 AND 재계산"
  │
  ├─ 需要部分匹配吗?
  │   └─ YES → FTS5: prefix(*)
  │            例: "Refund*", "환불*"
  │
  ├─ 是自然语言问题吗?
  │   └─ YES → 混合/语义: kb search "问题" --hybrid
  │
  └─ FTS5 结果为 0 条吗?
      └─ 改用语义重试
```

## 核心设计决策

| 决策 | 依据 |
|------|------|
| 一个 `store.sqlite` 是唯一的索引，不提交到 git | 消除二进制 merge conflict，消除两个索引带来的 schema·新鲜度守卫重复 (DEC-2026-10-28-13) |
| 新鲜度比较源文件 mtime，store 每次整体重新生成 | 只需 1~2 秒，无需增量。部分构建会截断 store，丢失其他项目的视图 (DEC-2026-10-28-13) |
| 不追踪 `manifest.json` | 是没人读的、每台机器各自的比较记录 (DEC-2026-10-29-04) |
| 构建引擎位于 strata-kit 仓库 | 作为方法论自身的工具来管理，独立于项目 |
| frontmatter 是 single source of truth | Obsidian + FTS5 + Dataview 两边引用同一份数据 |
| 在分块中同时放 heading·title·tags·meta | 用一个 FTS 表、一个 bm25 尺度给文档·决策·订单排名，并输出位置 (DEC-2026-10-28-08) |
| bge-m3 嵌入 + numpy 暴力计算 + 与 FTS 的 RRF | 擅长韩英混用，8192 token 使长分块不必截断。这个规模不需要 ANN (DEC-2026-10-28-09) |
| 向量的效果用评估集的 recall@k 判断 | `kb search-eval` |

已废弃的 legacy 决策：manifest.json 的 git 追踪·kb.sqlite 的 `.gitignore`、基于 SHA256 哈希的增量构建、`paraphrase-multilingual-MiniLM-L12-v2`、`apsw`·sqlite-vec、cosine distance 0~1 的解释（针对 MiniLM）。它们都已随 legacy 索引一起通过 DEC-2026-10-28-13 消失，或被 DEC-2026-10-28-09 取代。

## 依赖汇总

| 包 | 用途 | 何时需要 |
|--------|------|-----------|
| Python 3 | 运行 `kb` | 始终 |
| SQLite 3 (含 FTS5) | store | 始终 (操作系统自带) |
| PyYAML | 解析 frontmatter·taxonomy | 始终 |
| sentence-transformers (含 PyTorch，~500MB) | 计算 bge-m3 嵌入 | 仅在使用 `kb embed` 时 |
| numpy | 向量余弦 | 语义·混合检索时 |

sqlite-vec·apsw 不再使用。没有嵌入时，FTS 检索和所有生成视图也能工作。准确的依赖清单以 `kb/` 中的 import 为准。

### 运行环境

- 无常驻进程。不需要 GPU（Apple Silicon 上用 MPS，嵌入很快）。
- store 重新生成需 1~2 秒（文档 760 篇·分块约 7 千个的规模，DEC-2026-10-28-13·09 实测）。
- 嵌入计算第一次耗时较长，之后借助 `embeddings` 缓存只计算变化的分块。

## 局限

| 局限 | 说明 | 对策 |
|---|---|---|
| 韩语词素 (FTS5) | unicode61 只按空白切分 — “환불수수료변경”不匹配 | 遵守关键词拆分指南，并行使用语义检索 |
| 不拆分 CamelCase (FTS5) | FormulaBaseStructure → 单个 token | 使用 prefix(*) 检索或输入完整名称 |
| 不支持列指定·短语·NEAR | 查询 token 全部被引号括起，FTS5 高级语法不起作用 | 用 `--category`·`--topic` 过滤和 AND 代替 |
| 语义检索需要预先准备 | 必须先用 `kb embed` 生成向量，且因加载模型首次查询较慢 | FTS5 为主，语义作为 fallback |
| 仅有 BM25 rank (FTS) | 没有文档结构/重要度的加权 | 用 page_order 排序目录，并行使用混合 |
| Obsidian 未运行时 | 无法执行 Dataview 查询 | FTS5/语义检索独立于 Obsidian 工作 |
