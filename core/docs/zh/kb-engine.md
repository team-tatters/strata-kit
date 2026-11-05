# KB 引擎：存储契约

知识库是由文档、代码面、决策、会话和卡片组成的图，保存在 vault 旁边的一个基于文件的存储中。存储中的一切都由来源生成（rec.kb.generated-views）；存储是随时可以重建的缓存。

## 为什么只用一个存储

目前 vault 中有 FTS5 索引、节点页面、决策笔记镜像、coverage 对应表和链接基线，各由各自的脚本生成，保存在各自的文件里。代码图决策（strata DEC-2026-10-28-05）增加了代码符号和影响边，嵌入增加了向量。如果每一项都有自己的文件，那些真正重要的问题（哪个文档拥有这个被修改的函数；哪个决策取代了本会话所依赖的规则；哪些会话触及了这个节点）就需要跨工具做联接。只有一个存储、一套模式，一次查询就能回答，而且后端更换时模式不会变。

## 模式

```text
nodes(id, kind, project, path, title, status, updated, revision, payload_json)
  kind ∈ {doc, code, decision, session, order, task, card, node, profile}
edges(src, dst, kind, confidence, source_ref, created)
  kind ∈ {covers, supersedes, kb_updates, orders, decisions_made, relay, calls, imports, tests, member_of, links, implementation}
  confidence ∈ {declared, extracted, inferred}
chunks(node_id, seq, heading, text, title, tags, locale, embedding?, meta_json)
  全文检索和向量检索的单位；heading·title·tags 与正文放在一起，使 FTS 索引（unicode61，四列）的排序与 legacy 索引一致；meta_json 保存 heading_level·line_start·line_end·char_count（被切分的节还有 part·own_chars）。一个 chunk 是一个 H2–H4 节，只有嵌入输入（title·heading·正文）超过编码器 2,048 token 窗口的节才按段落 → 行 → 字符边界切成约 1,500 token 的片段（每片重复 heading，与前一片末尾重叠 150 字符，`kb/chunking.py`）。token 数用本地缓存的 bge-m3 分词器计算，没有时用保守的字符估计（字符数×0.75），估计只会多切，不会少切。文档、决策和 order 共用一张 FTS 表和同一个 bm25 尺度；与 legacy 索引的排序一致并不是目标 (DEC-2026-10-28-08)
baselines(gate, project, key, recorded)                链接与 coverage 基线
revisions(store_rev, kit_rev, built_at, sources_hash)  整个存储的来源记录
```

声明的边来自 frontmatter（covers、supersedes、orders、kb_updates、decisions_made）和决策记录。提取和推断的边来自图 provider（imports、calls、tests），并保留 provider 的置信度标签。存储中没有任何东西是手工编写的。

## 后端

| 后端 | 角色 | 状态 |
|---|---|---|
| SQLite (FTS5 + sqlite-vec) | 基线：每个 vault 一个文件，无需服务器，嵌入 MCP 进程 | 当前 (FTS5)，vec 待实现 |
| DuckDB | 在同样的表上做分析（coverage 报告、新鲜度、跨项目查询），导出 parquet 用于共享 | 适配器待实现 |
| RocksDB | 键值存储，用于承接来自编排器的高写入会话流（relay 数据包、审批），再将其折叠为节点/边 | 适配器待实现 |

所有后端都实现同一份契约：`put_nodes`、`put_edges`、`query(sql-like)`、`search_text`、`search_vector`、`rebuild(sources)`。引擎不会在适配器之外依赖任何后端特有的功能。

## provider

| provider | 产出 | 契约 |
|---|---|---|
| vault 扫描器 | doc 节点（每个 markdown 文件；被索引的会有 chunk，生成的镜像会被标记）、声明的边、正文的 `links` 边 | frontmatter + taxonomy |
| 决策记录 | decision 节点、supersedes 边 | decision writer 的输出 |
| 代码图——kit 自带的 provider（`kb/providers/code_graph.py`） | 每个仓库：目录 · 文件 · 类型符号的 code 节点（仅 git 跟踪的文件；Kotlin · Java · TS/JS · Python）、`member_of`（extracted）、`imports`（extracted；通配符和包导入为 inferred，指向目录）、`tests`（inferred）。解析 vault 的 covers 目标（`code:<p>:paths:<dir>/`、`code:<p>:symbols:<Name>`） | strata DEC-2026-10-28-05。`python3 -m kb code deps · impact · tests-for · symbol · owner-gate`；flow(request) 仍由可选的外部适配器负责 |
| 编排器流 (Quilt) | 会话节点之间的 relay 和审批边 | rec.decision.orchestrator-decisions-flow-to-records |
| 嵌入器（本地或需主动启用的云端） | chunk 向量 | 感知语言区域；引擎运行并不要求它 |

## 读取存储的门禁

- coverage 门禁：被修改的 code 节点 → covers 边 → 所属文档。没有所有者、也没有 doc_change 声明的被修改节点是新增违规（rec.kb.covers-owner）。
- 链接门禁：正文中的 wikilink 和 markdown 链接都是 `links` 边（source_ref 记录目标是如何解析的：file · id · alias · none · md）。断开的链接、仅靠 id 或仅靠别名解析的链接，以及指向已被取代目标的知识文档，属于超出基线的违规（rec.kb.link-currency）。记录在案的基线仍是 `.kb/link-baseline.json`；存储的 baselines 表是它的镜像。非 markdown 的链接目标和 `--code-root` 检查通过文件系统和 git 确认 (DEC-2026-10-28-07)。
- 新鲜度：所覆盖代码的 revision 比其 updated 字段更新的 doc 节点。
- 搜索：针对 heading·text·title·tags 的一张 FTS 表 (bm25)；来自嵌入器 provider（BAAI/bge-m3，本地）的稠密向量缓存在 `embeddings(model, text_hash, dim, vector)` 中并附加到 chunk，余弦相似度用暴力计算（这个规模不需要 ANN）；混合 = 两者的 reciprocal-rank fusion。`python3 -m kb search-eval` 针对 vault 的查询集测量 recall@k (DEC-2026-10-28-09)。 交叉编码器重排序（BAAI/bge-reranker-v2-m3，`kb/rerank.py`）默认关闭，可用 `kb search --rerank`、MCP `search_docs(rerank=true)` 或 `api.search(rerank=True)` 开启。开启后对前 30 个候选与查询重新打分（每对最多 384 个 token），重排后再按 limit 截断。2026-11-05 在 vault 查询集上实测：hybrid recall@5/@10 从 .887/.897 升至 .917/.926，代价是每次查询中位数多 1.25 秒、GPU 内存多 1.1–2.2GB、冷启动 3–4 秒。缺少模型或 sentence-transformers 时保持原顺序，并在结果的 mode 中注明跳过了重排序。`search-eval --rerank` 增加 hybrid+rerank 模式，在同一查询集上比较。
- 收敛：同一主题的目标规格节点与 as-built 文档节点的对照（rec.spec.desired-vs-as-built）。

## 从 strata/scripts 迁移

引擎以 shuttle 方式（本仓库的 strata-kit DEC-2026-10-28-01）落地到 `strata-kit/kb/`：每个 `strata/scripts/<name>.py` 都是对 `strata-kit/kb` 的一层薄调用，钩子继续工作，当所有调用方都指向 kit 时就移除 shuttle。

第一个里程碑，即等价性，已经通过；下一个里程碑退役了 legacy FTS 索引（`.kb/kb.sqlite`，DEC-2026-10-28-13）。现在 vault 只有一个存储。

- `python3 -m kb build-index` 是会话结束时的构建：它重建整个存储，然后从存储中派生节点页面（`kb.views.node_pages`）、Obsidian sortspec、评审收件箱（`.kb/review-candidates.json`、`_index/review-needed.md`）、`manifest.json` 以及 taxonomy 验证警告（block 违规则以 exit 2 退出）。`--project` 只缩小报告范围；存储始终是完整的。
- 文档规则（发现、frontmatter、chunk、taxonomy 合并、验证）集中在一处，`kb/docrules.py`。扫描器把 `discovered`（发现集合）和 `diagnostics`（验证结果）放入每个文档节点的 payload，因此构建无需索引即可报告警告。
- 新鲜度由 `engine.ensure_fresh_store`（源文件 mtime）负责。旧的 `kb_freshness.py` 和基于 manifest 哈希的增量构建已经没有了。
- 证据：2026-10-28，原始构建器（strata@b4b0c86）与 `kb build-index` 在真实 vault 的两份副本（760 个文档、66 个节点页面）上产出了相同的节点页面、sortspec、评审收件箱、manifest 文件、警告行和退出码。比较脚本在 legacy 索引退役后被删除（order 2026.10.29-11）。
