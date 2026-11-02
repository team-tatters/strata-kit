# Knowledge Base — 链接规则

> 正本: strata-kit `core/docs/zh/knowledge-base/linking-convention.md` (2026-10-29 从 strata `docs/07-knowledge-base/linking-convention.md` 迁移, DEC-2026-10-29-11)。

## 概述

vault 内部的链接以 Obsidian 兼容性为最优先。
对 vault 之外 (strata-kit、projects) 的引用基于环境变量。

## 链接类型

### 1. vault 内部链接 — 使用 Wikilink

```markdown
<!-- 引用同一 vault 内的文档 -->
[[overview]]
[[decisions/001-use-jwt-auth]]
[[glossary#JWT]]

<!-- 更改显示文本 -->
[[decisions/001-use-jwt-auth|JWT 认证决定]]
```

**规则:**
- vault 内部始终使用 `[[wikilink]]`
- 路径是相对于 vault 根的相对路径
- 省略扩展名 `.md`
- 在 Obsidian Graph View 中可以看到关系的可视化

### 2. vault → kit 引用 — 环境变量

```markdown
<!-- vault 文档引用 kit 方法论时 -->
层规则参见 `$STRATA_KIT/core/rules/layer-rules.yaml`。
```

**规则:**
- 禁止使用绝对路径
- 必须使用 `$STRATA_KIT` 环境变量
- vault 文档对 kit 的引用要尽量少 (vault 是知识, kit 是方法论)

### 3. vault → project 引用 — 环境变量

```markdown
<!-- vault 文档引用项目代码时 -->
实现: `$STRATA_PROJECTS/{project-name}/src/auth/AuthService.ts`
```

**规则:**
- 使用 `$STRATA_PROJECTS` 环境变量
- 代码引用只记录路径 (禁止复制代码)

### 4. project CLAUDE.md → vault 引用 — @ 语法

```markdown
<!-- 项目 CLAUDE.md 引用 vault 时 -->
项目知识: @$STRATA_VAULT/projects/my-api/
```

**规则:**
- 使用 Claude Code 的 `@` 延迟加载语法
- 路径由环境变量解析

### 5. project CLAUDE.md → kit 引用 — @ 语法

```markdown
<!-- 项目 CLAUDE.md 引用 kit 时 -->
层规则: @$STRATA_KIT/core/rules/layer-rules.yaml
```

### 6. typed frontmatter link — 把关系的种类写成数据

正文中的 wikilink 只表示"相关"。关系的**种类**写在 frontmatter 字段中 (DEC-2026-08-19-03)。生成器、校验、节点页只读取这些字段, 不读取正文中的链接。

| 字段 | 方向 | 使用的 type | 含义 |
|---|---|---|---|
| `sources` | Knowledge → Archive | KB·pattern | 作为本文档依据的会话和任务。更新 Knowledge 时必填 |
| `up` | 子 → 父 | 所有文档 | 包含本文档的上位概念·MOC |
| `decisions` | 文档 → 决定 | KB·session·task | 本文档所遵循或产生的决定 |
| `supersedes` / `superseded_by` | 新决定 → 旧决定 / 旧 → 新 | decision | 取代关系的两端。校验会检查对称性 |
| `nodes` | 文档 → 主题节点 | decision·session·task·specification·concept·constraint | 本文档所属的目录单元 |
| `covers` | 规格 → 代码面 | specification·concept | 本文档作为**正本**的代码路径·符号·端点·表 |
| `related` | 文档 ↔ 文档 | 所有文档 | 提及·参考关系。不是所有权 |

**规则:**
- `sources`·`up`·`decisions`·`supersedes`·`related` 的值是 `[[wikilink]]`。`nodes` 的值是 toc.yaml 中的节点 id, `covers` 的值是相对于仓库的指针。这两者不是 wikilink。
- 关系字段没有值时就省略。如果放一个空数组, 校验会询问"是否有意留空"。
- 同一关系也在正文中用 wikilink 书写是允许的 (为了 Obsidian 图谱)。但正本是 frontmatter。
- 值格式的正本: `nodes`·`covers`·`doc_change`·`supersedes` 见 document-format.md 的"节点·覆盖率字段"一节, `sources` 见同一文档的 frontmatter 模式。

### 7. 让链接始终指向现行文档的规则 (DEC-2026-09-30-03)

- **wikilink 的目标必须能通过文件名 (或 vault 相对路径) 解析。** 只能通过 frontmatter 的 `id:` 或 `aliases` (如任务 id) 解析的链接在 Obsidian 中会失效, 所以不要使用。移动文件或改名时, 把旧名字留在 `aliases:` 中 (用于搜索、unlinked mention), 但链接本身要按检查器指出的改成新文件名。
- **不要用链接包裹自由文本。** 像 `[[restdocs 양식 정렬]]` 这种目标文档不存在的链接是禁止的。需要说明时使用显示文本 (`[[session-2026-09-02-x|task05 후속]]`)。
- **指向已被取代文档的正文链接要改成现行文档。** 取代关系字段 (`supersedes`·`superseded_by`) 和说明历史的句子是例外。检查器无法区分两者, 所以这一项只作为参考 (警告) 报告。
- **指向代码时用符号而不是路径。** 在 `covers.symbols` 中写类名·函数名, 正文中也像 `CollaboratorCommandService.invite` 这样用符号书写。路径只写到模块·包的层级。因为文件被移动时, 符号名称通常不会变。
- **检查:** `python3 "$STRATA_KIT/kb" link-check` 会找出失效的 wikilink、自由文本链接、只能通过 id 解析的链接、指向已被取代文档的正文链接。生成·导入的文档 (DEC 笔记、节点页、规划原文、`_index/`) 中的违规无法手工修复, 所以只报告, 不阻断 (要修的地方是生成器)。会话结束闸门只看该会话所属项目的文档。既有违规以基线 (`$STRATA_VAULT/.kb/link-baseline.json`) 固定, **只有基线之外出现新违规时才失败**。会话结束 (`python3 "$STRATA_KIT/kb" ledger close`) 会因这项检查而停止 vault 同步, 生成交接 (`python3 "$STRATA_KIT/kb" handoff`) 只发出警告。仅在紧急时用 `STRATA_LINK_CHECK=warn` 降级为警告。基线按修好的数量用 `--shrink-baseline` 缩减。
- **与代码核对:** 传入 `--code-root {project}=<repo>` 时, 还会检查 KB 的 `covers.paths` 是否存在于仓库中, `covers.symbols` 的名称能否在代码中搜到 (仅限有代码仓库的机器)。

## 禁止事项

| 禁止的模式 | 原因 | 替代 |
|---|---|---|
| vault 内的绝对路径 (`/home/alice/...`) | 机器之间不兼容 | 使用 `$STRATA_KIT`、`$STRATA_VAULT` |
| vault 内的 Markdown 链接 `[text](path)` | 不会显示在 Obsidian Graph 中 | 使用 `[[wikilink]]` |
| 复制代码块 | 代码腐化 | 只记录路径引用 |
| 项目之间直接引用 | 产生依赖 | 作为通用模式提取到 vault/patterns/ |
| 关系的种类只依赖正文链接 | 生成器·校验读取不到 | §6 typed frontmatter link |

`covers` 的代码指针不必是 wikilink。frontmatter 中相对于仓库的路径不属于"vault 内禁止 Markdown 链接"的对象。

## 嵌入

也可以使用 Obsidian 的嵌入语法:

```markdown
<!-- 嵌入另一文档的特定章节 -->
![[decisions/001-use-jwt-auth#결정]]

<!-- 嵌入图片 -->
![[architecture-diagram.png]]
```

被引用文档的内容变化时, 嵌入会自动反映, 所以比起重复书写更推荐嵌入。
