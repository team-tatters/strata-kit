# Knowledge Base — 文档格式

> 正本：strata-kit `core/docs/zh/knowledge-base/document-format.md`（2026-10-29 从 strata `docs/07-knowledge-base/document-format.md` 迁移，DEC-2026-10-29-11）。

## 概述

vault 内的所有 `.md` 文件都必须包含 YAML frontmatter。
采用 Obsidian 和 MCP 服务器（Phase 3）都能解析的格式。

## Frontmatter 模式

```yaml
---
# === 必填字段 ===
title: "文档标题"
id: "{前缀}-{project}-{slug}"  # 稳定 ID — 移动、改名后不变（前缀体系：core/docs/zh/knowledge-base/vault-structure.md 的稳定 ID 一节）
type: overview | decision | session | pattern | reference | glossary
      | concept | specification | flow | guide | runbook | constraint | epic | moc | node
created: YYYY-MM-DD

# === 有条件必填 ===
project: {project-name}       # 针对特定项目的文档（横跨项目的文档在 id 的 project 位置写 vault）
status: draft | active | review-needed | superseded | archived
sources: ["[[来源会话/任务]]"]  # 更新 Knowledge 层文档（KB、pattern）时必填 — 依据的 Archive 链接（DEC-2026-08-19-03）
nodes: ["{node-id}"]          # 所属主题节点 — decision、session、specification、concept、constraint 必填（“节点与覆盖字段”一节）

# === 可选字段 ===
tags: [namespace/value, ...]  # 建议使用带命名空间的标签
updated: YYYY-MM-DD           # 最后修改日期
updated_by: {git user}@{machine}  # 最后更新者 — 写入钩子用 git identity 和机器 alias 盖章（DEC-2026-09-09-05）
page_order: 1                 # 类别内的文档顺序（用于 KB 索引）
author: builder | worker | manual  # 撰写主体
machine: {alias}              # 撰写所用机器——本机 alias（STRATA_ENV，env-config.yaml）。写着其他机器的会话记录会被 vault-git 拒绝
superseded_by: "[[新文档]]"   # status 为 superseded 时（被取代一方 → 取代一方）
supersedes: ["[[之前的决策]]"]   # decision — 这条决策所取代的之前的决策（与 superseded_by 方向相反）
covers: {paths, symbols, endpoints, tables}  # specification、concept — 以本文档为正本的代码面
doc_change: none              # session、task — 声明已修改代码但未更新现状形态（必须附 doc_change_reason）
aliases: ["旧文件名"]         # 移动、改名时保留原标识符
related: ["[[相关文档1]]"]     # Obsidian wikilink — 提及关系（所有权关系用 covers）
---
```

## 按 type 划分的必填字段

| type | 额外必填字段 | 说明 |
|---|---|---|
| `overview` | `project` | 项目或类别的概述 |
| `decision` | `project`, `status`, `nodes` | ADR。包含决策的背景与依据。可选 `supersedes` |
| `session` | `project`, `machine`, `nodes` | 会话交接、ledger。**只为元数据和摘要部分建立索引**（Archive — 2026.08.19-06）。可选 `doc_change` |
| `pattern` | — | 跨项目复用的模式 |
| `reference` | — | 外部文档、标准、规范的摘要引用 |
| `glossary` | — | 领域或技术术语的定义 |
| `concept` | `nodes` | 领域概念、业务规则、原理说明。可选 `covers` |
| `specification` | `status`, `nodes` | 功能规格、需求、约束条件、验收标准。节点的最终形态。建议 `covers` |
| `flow` | — | 业务流程、数据流、时序 |
| `guide` | — | 步骤指引、How-to 文档 |
| `runbook` | `status` | 运维/故障应对手册 |
| `constraint` | `source_adr`, `severity`, `scope`, `rule`, `verification`, `status`, `nodes` | 从 ADR 中提取的单条可执行约束 |
| `epic` | `constraints`, `domains`, `layers`, `personas`, `status` | PRD 的功能单元。必须有 constraint 链接 |
| `planning` | `project`, `status`, `nodes`, `source`, `implementation` | 从外部策划工具导入的策划原文（PRD、政策、Epic/Story）。原文不可变 + `## 实现评审` 一节。`implementation.status` 对评审结果分类。status 是策划状态（lifecycle_override） |
| `moc` | — | 目录（Map of Content）。`_index/` 和各 `_index.md`，以及生成的静态索引。**仅限生成** |
| `node` | `project`, `node` | 主题节点页面。汇合最终形态、政策、决策、策划、工作历史和债务。**仅限生成** |

`moc` 和 `node` 属于 Index 层。不要手写，而要从正本（frontmatter、记录、toc.yaml）重新生成。

## 节点与覆盖字段

主题节点（node）是人阅读的目录单位。一个节点就是把最终形态（规格）、政策（约束）、决策和工作历史汇集在同一屏的钥匙。节点树的正本是项目的 `_meta/toc.yaml`，文档通过下面四个字段把自己连到节点和代码上。**本节是取值格式的正本。** taxonomy 只规定是否必填。

### `nodes` — 本文档所属的主题节点

```yaml
nodes: ["orders.checkout-v2.coupon"]   # toc.yaml 中定义的节点 id，允许多个
```

- 节点 id 与文档 id（`{前缀}-{project}-{slug}`）属于**不同的命名空间**。它是从祖先起用点（.）连接的路径，每一段都是 kebab-case。
- decision、session、specification、concept、constraint 必填。任务规格也使用同一字段（参见 `core/docs/zh/methodology/task-spec-schema.md`）。
- 会话和任务的节点由覆盖解析器（变更文件 → 拥有该文件的规格 → 该规格的节点）推导。只有没有代码变更的会话才由人来选。
- 允许空数组，但校验会给出警告。如果有意不设节点，要在正文中写明原因。

### `covers` — 以本文档为正本的代码面

```yaml
covers:
  paths: ["service/order-api/src/main/kotlin/com/example/order/refund/"]   # 仓库相对路径，子串匹配
  symbols: ["RefundCalculationService"]                              # 类、函数名称
  endpoints: ["POST /v1/orders/{id}/refunds"]                    # METHOD + 路径前缀
  tables: ["refund_items"]                                      # 表名
```

- 只在 specification、concept 中使用。会话、决策、约束没有 `covers`。它们只通过 `nodes` 指向节点。
- 不使用文件级路径。只使用模块、包、控制器、路由前缀这类在移动中保持稳定的标识符。匹配规则与 layer-map 的路径匹配相同（子串，自上而下）。
- 一个代码面恰好由一份文档拥有。重叠时校验会发出警告。上位的概念文档用 `up` 连接。
- `covers` 是**所有权**关系，不是提及。提及放在 `related`。这个区分一旦模糊，一个文件就会被五份文档拥有，覆盖门禁就会变成噪音而被忽略。
- 代码路径指针与“vault 中不放源代码”的原则并不冲突。记录的是仓库相对路径，而不是代码（`core/docs/zh/knowledge-base/vault-structure.md`“绝不包含的内容”）。

### `doc_change` — 已修改代码但未更新现状形态时

```yaml
doc_change: none
doc_change_reason: "仅做重构 — 外部契约、政策无变化"
```

- 用于 session、task。如果 `covers` 的路径发生了变更，而拥有该代码面的文档没有更新，也没有这个字段，会话结束门禁会把它记为对应节点的**债务**并发出警告。
- 禁止留空。取值为 `none` 时必须附上原因。这与 ledger 要求 `next: "none"` 必须带 reason 是同一原则。

### `supersedes` — 本决策所取代的之前的决策

```yaml
supersedes: ["[[DEC-2026-08-13-05]]"]
```

- 用于 decision。**被取代一方的状态不存储，而是推导**（DEC-2026-09-30-03）：出现在某条记录的 `supersedes` 中的决策，会在索引和 DEC 笔记中自动获得 `status: superseded` 和 `superseded_by`。不修改被取代一方的记录文件。
- 要给已记录的决策事后补上取代关系，使用 `python3 "$STRATA_KIT/kb" decision supersede --id 新 --target 旧`；要在没有取代决策的情况下撤回，使用 `python3 "$STRATA_KIT/kb" decision withdraw --id X --reason ...`。仅在正文里写“取代”“撤回”不会被识别为状态。
- KB 文档（decision 以外）仍然要在被取代一方亲手写上 `status: superseded` 和 `superseded_by`。
- `superseded_by` 是方向相反（被取代一方 → 取代一方）的既有字段。二者是同一事实的两端。
- 节点页面的“决策”面把这条链的末端显示为现行决策，其余显示为历史。

## 文档生命周期

```
draft → active → review-needed → superseded → archived
                      ↓                ↓
                   active           archived
```

| 状态 | 含义 | 可转换到 |
|------|------|-----------|
| `draft` | 撰写中，尚未评审 | active, archived |
| `active` | 有效的现行文档 | review-needed, superseded, archived |
| `review-needed` | 需要更新（超过 90 天自动标记） | active, superseded, archived |
| `superseded` | 已被新文档取代。必须有 `superseded_by` 字段。若取代它的决策声明了 `supersedes`，则纳入对称性校验 | archived |
| `archived` | 已失效。降低搜索权重 | — |

**按 type 的例外**：`constraint` 使用专属的生命周期 —
`active → superseded → retired`（taxonomy.yaml `lifecycle_override`）。
约束没有 draft 状态，在 ADR 被 accepted 时以 active 创建，废止标记为 `retired`。

## 正文规则

### 通用规则

- Markdown 格式（CommonMark + Obsidian 扩展）
- 标题从 `##` 开始（避免 `#` 与 frontmatter 的 title 重复）
- 一份文档只聚焦一个主题（MECE 原则）
- 最大长度：概述/模式/概念 500 行，ADR 200 行，会话摘要 100 行，规格 1000 行，目录和节点页面 300 行
- 正文各节标题的正本是 taxonomy 的 `document_types.{type}.body_sections`。下面的结构块是它的渲染结果，生成器从 taxonomy 生成标题

### 可读性规则（必须）

- **自足的术语**：文档必须只读它自己就能理解。不要原样使用没有外部技术背景就无法理解其含义的术语 — 英文专业术语、实现内部的概念、作者自造的合成词。确实需要时，要在**第一次出现时用一行解释并定义**。（例如：不要用“materialize”“resolve”“single-flight”“degraded”这样的词，而要把**动作讲开**，如“首次请求时先建好”“查询后组装”。）
- **正文与收尾的脉络一致**：文档末尾的“未决/需确认/请求答复”条目，只能从正文中实际定义并展开过的内容里引出。不要在收尾的章节里第一次提出正文中没有的新概念。读者必须能一一找到每个未决条目对应正文的哪一部分。
- **判定标准**：“第一次看到这份文档的同组同事，不借助外部搜索，只读正文，能否理解所有术语和未决条目？”如果不能，就把它讲开，或者在正文中补充依据。

### 供人阅读的文档规则（必须 — DEC-2026-09-10-01）

读者是人。不要写成便于代理解析的形态。适用于 KB 文档、会话交接、决策记录和聊天报告。

- **只使用人能够理解的整理方式。** 不写读一遍无法明白意思的段落和表格。不要罗列代码符号、路径、决策 ID 来代替说明。表格的一个单元格只放一个事实，表格里不嵌套表格。
- **禁止重复和冗长，用同一脉络来写。** 不在多个章节里重复同一事实。章节切换时不要改变视角，保持一条连贯的叙述。
- **摘要在前，依据在后。** 叙述变长时，在最前面放结论摘要，代码位置、实测值和引用附在后面的依据章节。只读摘要就应能做出判断。
- **不使用代码式的顺序标签。** 不要用 `A1·A2·B3` 这样由字母和数字组合的代码来对任务、文档顺序、条目分类。顺序和条目用能体现含义的短句来写。（不写“A3 hub 修剪”，而写“删除 hub 中不再使用的画面”。）只有在引用已带标签的既有文档时，才把原文标签加在括号里。

### Decision（ADR）正文结构

```markdown
## 맥락
{需要做出决策的背景}

## 결정
{所选方向及理由}

## 대안
{考虑过但未选择的方向及理由}

## 결과
{这项决策带来的影响、权衡}
```

声明了 `supersedes` 的决策，要在 `## 结果` 中留一行，说明取代了什么、为什么取代。节点页面展示决策链时，这一行就是说明。

### Session 摘要正文结构

```markdown
## 완료
- {已完成的条目}

## 진행 중
- {未完成的条目及当前状态}

## 결정 사항
- {本次会话中做出的决策}

## 주의 사항
- {下一次会话需要知道的警告/问题}
```

- 上面四节是交接**摘要部分**的结构。ledger 的 actor 条目和 `next_session` 块的格式，以 `core/docs/zh/methodology/agent-operations.md` §5.3 为正本，并与这一结构并存。
- 如果修改了代码却没有更新最终形态，要在 frontmatter 中声明 `doc_change: none` 及原因，并在 `## 注意事项` 中写下同样的原因。

### Pattern 正文结构

```markdown
## 문제
{该模式要解决的问题}

## 해결
{模式说明}

## 적용 예시
{代码片段或结构示例}

## 적용 프로젝트
- [[project-a]] — {如何应用}
```

### Constraint Card 正文结构

从 ADR 中提取的单条可执行约束。简洁地写，控制在 50 行以内。

```yaml
---
title: "{约束标题 — 一行名词短语}"
type: constraint
created: YYYY-MM-DD
status: active
source_adr: "[[NNN-adr-slug|ADR-NNN]]"
severity: must-not        # must | must-not | should
scope:
  domains: [{领域}]     # 该约束适用的业务领域
  layers: [{层}]      # 该约束适用的 Strata 层
rule: "{一行可执行规则 — MUST/MUST NOT 句子}"
verification: code-review  # code-review | unit-test | integration-test | static-analysis
tags: [constraint, severity/{level}, layer/{layer}, domain/{domain}]
aliases: [CC-NNN-NN]       # 唯一 ID（ADR 编号-序号）
---
```

```markdown
## 근거
{由 ADR 的哪一节推导而来，为什么需要这条约束，1-3 行}

## 위반 시 영향
{这条约束被破坏会出现什么问题，1-3 行}

## 검증 방법
{代码评审、测试、静态分析等具体的确认方法}
```

**Constraint Card 编写规则：**
- ADR 转为 accepted 时，在同一会话内提取（Builder 的义务）
- 1 个 ADR → N 张 Card（通常 3-10 张）
- severity 依据 ADR 原文的措辞决定：“必须/必需/MUST”→ must，“禁止/NEVER”→ must-not，“建议/SHOULD”→ should
- scope 是该约束适用的领域和层的范围
- 同时在 constraint-registry.yaml 中登记一行摘要

### Epic 正文结构

PRD 的功能单元。通过 constraints 字段与 ADR 约束相连。

```yaml
---
title: "{功能单元标题}"
type: epic
project: {project-name}
created: YYYY-MM-DD
status: draft
constraints:                # ★ 必填 — 该 Epic 必须遵守的 Constraint Card
  - "[[CC-NNN-01]]"
  - "[[CC-NNN-02]]"
domains: [{领域}]
layers: [{受影响的层}]
personas: [{目标用户画像}]  # 项目中定义的 persona ID
tags: [epic, domain/{domain}]
---
```

```markdown
## 目标
{该 Epic 要解决的用户问题，1-3 行}

## 验收标准
- {可验证的完成条件}

## 约束摘要
{constraints 字段中的每张 Constraint Card 如何应用于该 Epic 的摘要}
```

**Epic 编写规则：**
- constraints 字段必填。空数组是评审信号（需要判别是有意留空还是遗漏）
- 拆分任务时，Builder 把 Epic 的 constraints 分配到各任务的 scope.constraints

### Planning 正文结构

从外部策划工具（Notion 等）导入的策划原文。多数文档的请求已经完成或决策已经落实，所以把它看作**策划**，而不是“请求”（DEC-2026-09-09-01）。
原文是 as-intended，Knowledge 规格是 as-built。不要把两者混在一份文档里 — 原文各节不修改，只更新文档末尾的 `## 实现评审` 一节。

```yaml
---
title: "{原标题}"
id: plan-{project}-{来源 id}          # 重新导入时保持不变
type: planning
project: {project-name}
status: realized                      # 策划状态 — requested | planned | in-progress | realized | on-hold | archived
nodes: ["orders.payments-v2"]           # Inbox 批准后记录（导入器只给出候选）
source: "notion:{32hex}"              # 来源标识符（必填）
source_name: notion-orders-intake        # planning/ 下的子目录
source_path: "{来源导出的相对路径}"  # 版本追踪
up: "[[plan-{project}-{上位 id}]]"    # 像 Epic/Story 那样存在上位文档时
topic: "分类：… · 任务分组：… · 冲刺：…"   # 来源属性的一行 — 节点回填规划器的搜索对象
owner: "{姓名}"                       # 可选 — 规划的负责人；规划遗漏的判定向此人询问（没有则问用户，DEC-2026-10-31-35）
implementation:                       # ★ 必填 — 实现评审结果的分类
  status: unreviewed                  # unreviewed | implemented | partial | diverged | not-implemented | superseded
  reviewed: YYYY-MM-DD                # unreviewed 时省略
  spec: "[[kb-…]]"                    # 提炼出的最终形态文档（如有）
created: YYYY-MM-DD
---
```

```markdown
# {原标题}
{原文 — 不修改}

## 구현 검토

| 项目 | 策划 | 实现 | 差异 | 依据 |
|---|---|---|---|---|
| {政策项} | {策划所述} | {代码所做} | {无 · 不同 · 未实现} | {代码路径·符号·规格链接} |
```

**Planning 编写规则：**
- `## 实现评审` 按条目（政策语句、复选框、Story）来写。文档的一行摘要由 `implementation.status` 承担 — 若为 diverged、partial，表中必须有差异行。
- 如果评审促成了规格更新，就把本文档加入该规格的 `sources:`，并用 `implementation.spec` 反向指回。
- `status`（策划状态）和 `implementation.status`（实现评审）是不同的维度。“已上线”的策划也可能与代码不同 — 这就是 diverged。
- 节点页面的“策划”面只汇合这一 type，并用徽章（未评审·已实现·部分实现·与策划不同·未实现·已被取代）展示。unreviewed 的数量以及 diverged、partial 的文档会计入债务。
- 规划与实现不一致时，不要停在 `## 实现评审` 的差异行，而要留下判定请求（`python3 -m kb divergence add`；关卡的重新核对行用 `kb coverage-gate --divergence-inbox`）。判定只由人做，取四者之一：一致（没有差异）、文档过时（让规划·规格跟上实现）、规划遗漏（请 `owner` 补全规划）、实现缺陷（缺陷任务）。记录判定（`kb divergence judge`）会把 `implementation.reviewed` 设为当天，同样的变更不会再要求重新核对；`implementation.status` 按判定修改（DEC-2026-10-31-35）。

### 规划资料包 (strata.planning)

整理外部规划来源时，使用资料包，而不是单一的原始文档（DEC-2026-11-01-04·05）。带有 `audit/` 文件夹的 `planning/<bundle>/` 文件夹就是一个资料包。资料包之外的规划文档（上面的格式）仍是原始文档。

| 位置 | 内容 | 注入 · 共享 |
|---|---|---|
| `source/`（或 `category: source`） | 原始来源，从不编辑 | 否——依据 |
| `audit/facts*.md` | 事实清单 `# \| source location \| type \| content \| role \| axes \| subtopic` | 否——依据 |
| `audit/coverage*.md` | 对照表 `# \| source location \| destination \| note`——七种去向 | 否——依据 |
| `audit/defects*.md`、`audit/isolated*.md` | 缺陷（`# \| kind \| content \| handling`）、被隔离的规则 | 否——依据 |
| 直接位于资料包中的 `*.md` | 整理稿：`planning_doc: prd \| tech-spec \| terms \| tree` | 是 |

- 整理稿不写代码，也不写架构（表、列、模式；类、模块、服务名；API 路径、HTTP 状态码；框架、库、供应商）。这类事实归入对照表的 `code` 去向。
- 表格按列位置读取，因此表头可以使用任何语言。去向用英语（`isolated:` `defect:` `code` `background` `duplicate:#n` `out of scope:`）或韩语（`격리:` `결함:` `코드` `배경` `중복:#n` `범위 밖:`）书写；其他任何值都按 `<refined document> R<n>` 读取。
- 知识检索只会找到整理稿。`python3 -m kb planning check <bundle>` 检查对照表和整理稿；`python3 -m kb planning boundary [--list]` 输出注入边界。

## 标签命名空间

建议所有标签都使用 `namespace/value` 格式。taxonomy.yaml 中定义的命名空间：

| 命名空间 | 模式 | 说明 | 取值限制 |
|-------------|------|------|---------|
| `project` | `project/{name}` | 项目范围 | 自由 |
| `layer` | `layer/{name}` | Strata 架构层 | L1, LM1, L2, LM2, L3, Route, Atomic, Molecule, Partial, Page, Layout, Foundation, Contract, DataState, Primitive_UI, Semantic_Component, Feature_Block, Route_Surface, App_Shell |
| `domain` | `domain/{domain}` | 业务领域 | 自由 |
| `tech` | `tech/{technology}` | 技术或框架 | 自由 |
| `audience` | `audience/{role}` | 目标读者 | developer, planner, devops, all |

示例：`tags: [project/my-api, layer/L2, domain/auth, tech/jwt]`

没有命名空间的标签也可以使用，但构建时会产生警告。
详细校验规则：`core/templates/vault/_meta/taxonomy.yaml` → `tag_namespaces`, `validation`
