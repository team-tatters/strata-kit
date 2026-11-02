# 前端设计契约 (Design Contract)

> 正本：strata-kit `core/docs/zh/architecture/frontend-design-contract.md` — 从 strata `docs/03-architecture/frontend-design-contract.md` 迁移而来（订单 2026.10.29-06，2026-10-29）。规则 YAML 位于 `core/rules/`。

> 机器可读规则：`core/rules/layer-rules.yaml` → `frontend.variants.web` (Foundation · Primitive_UI · Semantic_Component)，
> `core/rules/naming-convention.yaml` → `frontend.Foundation.token_alias` · `markers.token_exception`
> 本文档定义设计（token、变体、组合）与实现之间**可验证的契约**。
> 不预设任何特定的设计工具、CSS 工具或 UI 库。工具绑定见 `profiles/frontend.next-web/docs/zh/frontend-tokens.md`。

## 边界原则

Core 只回答两个问题：“这个组件做什么”和“这个组件的外观在哪里决定”。
“长什么样”必须由 token 与变体轴的组合推导出来，不得在组件代码内部直接决定。

“token”这一个词里混着三个概念，现将其分离。

| 概念 | 定义 | 所在位置 |
|---|---|---|
| Token | 值体系。原值（primitive）与意图（alias） | Foundation |
| Variant | 组件对外公开的轴 (variant · intent · size · state) | Primitive UI |
| Composition | 组件的组合。以**契约**（名称 = 含义，props = 意图，slots）表达，而不是以大小表达 | Semantic Component · Feature Block |

## 三层 token

| 层 | 作用 | 命名示例 | 允许的引用 | 设计工具 |
|---|---|---|---|---|
| T1 Primitive | 调色板刻度、间距、字体排印的原值 | `cool-neutral-30` · `blue-80` · `space-4` | 仅 T2。禁止组件引用 | 变量集合 "Primitive" |
| T2 Alias | 意图。**智能体、设计师与代码共用的唯一词汇** | `color.surface.default` · `color.text.muted` · `color.action.primary.bg.hover` · `color.status.pending.fg` | Primitive UI · Semantic · Feature | 变量集合 "Semantic"（模式：light/dark/density） |
| T3 Component | 按组件的 override。属于生成物，可选。指向 T2 alias，绝不指向 raw 值 | `button.solid.primary.bg` | 仅拥有它的组件（及其内部） | 默认不设 |

**Alias 命名**：`{category}.{object}.{role}.{state?}` — category（color · space · radius · shadow · typography）、object（surface · text · border · action · status · …）、role（default · muted · bg · fg · …）、state（hover · active · disabled · …）。
模式（浅色、深色、密度）在 alias 的**取值层**分流，名称只有一个。

**规则**
- T1 只能被 T2 引用。组件代码中出现 T1 名称即为违规。
- T3 组件 token 只能被拥有它的组件（及其内部）引用，并且指向 alias，绝不指向 raw 值。其他组件或界面需要同一取值时，将其升级为 alias。
- 在 Foundation 之外禁止 raw 值（hex · px · rgba · 调色板刻度名），按设计属性逐项适用：颜色、间距、字号与行高、圆角、阴影、z-index。运行时计算或测量得到的值（虚拟滚动偏移、测得的参照宽度、数据列宽等连续尺寸）作为标注 `@strata:computed <reason>` 的例外允许（无有效期；空的 reason 不算数）。引用 alias 变量的任意值不是 raw 值。工具类 CSS 的类名必须原样映射 alias 名称。
- 新增 alias 属于架构决策 — 必须有决策记录（`@strata:token-exception` 是带有效期的临时逃生口，见下文 §例外策略）。

## Variant 轴

Primitive UI 公开的轴有四个。**轴的取值不使用调色板名称** — 取值依据“含义是什么”而不是“长什么样”。

| 轴 | 取值（默认词汇） | 备注 |
|---|---|---|
| `variant` | solid · outline · subtle · clean | 形态 |
| `intent` | primary · neutral · danger · success · warning · info | 意图。项目可以把领域状态轴（例如 `status: pending · completed`）作为**独立的轴**来扩展。不要混入同一个轴 |
| `size` | sm · md · lg | 项目可以重新定义取值 |
| `state` | default · hover · focus · active · disabled | 交互状态。**数据状态**（loading · empty · error）从 Semantic Component 开始拥有 |

设计工具中的组件属性名与代码中的 props 名必须**一致**。这是一致性检查的前提。

## Composition Legality — 组合的合法性

> Semantic Component 与 Feature Block 的外观必须是**（其下 Primitive UI 的 variant 轴取值）×（Alias token）的纯函数**。

这里的“外观”指组件自身的视觉属性：颜色、字体排印、内边距（padding）、边框以及各状态的样子。组件之间的摆放、外边距、视口与响应式行为、内容与素材不在此规则范围内；它们属于由父级放置的布局元素（grid、stack 等）。raw 值检查与调色板检查度量的正是这一范围。

这一行取代了 Atomic Design 的 Molecule/Organism（按大小分类）。组合按合法性判定，而不是按大小。

| 判定 | 示例 |
|---|---|
| 合法 | `<Button intent="danger" variant="outline">` + `color.text.muted` · 引用 alias 变量的任意值 · 附有理由注释的运行时测量宽度 |
| 违规 | `bg-blue-80`（直接引用 T1）· `style={{color:'#303140'}}`（raw 值）· `className="bg-[#fff]"`（任意值） |

与 Atomic variant 的对应遵循 `core/docs/zh/architecture/frontend-atomic.md` 的 §映射。要点：Atom → Primitive UI，Molecule → Semantic Component（不感知数据）或 Feature Block（调用 DataState），Organism 废弃，Partial → Feature Block (Section)。

## 设计产物与一致性

一个功能有三种产物。每种都有版本，且**任何一种**都可以作为入口。门禁不是顺序，而是成对产物之间的一致性检查。

| 产物 | 承载内容 | 形式 |
|---|---|---|
| Spec | 做什么 — 需求、行为、状态 | 任务规格 · KB specification |
| Design | 长什么样 | `design_ref`（见下） |
| Impl | 代码 | 仓库 |

**design_ref**（`core/docs/zh/methodology/task-spec-schema.md` → `inputs.design_ref`）

| kind | 含义 |
|---|---|
| `figma` | 对设计工具文件或节点的引用 |
| `storybook` | story 即设计产物（无设计工具时为正本） |
| `claude_design` | 草稿画布。`spec_first` 入口的产物，确认后升级为 `storybook` 或 `figma` |
| `none` | **明确**声明没有设计产物 — 必须有 `reason`（例如内部工具、纯文本） |

**一致 (aligned) 的定义**：组件契约 — 名称、variant 轴及其取值、所用 alias、状态轴 — 在 Design 与 Impl 中相同。
工具在此定义之上做比较（属性名比对、story 渲染与画框比对）。人工评审也使用同一定义。

**对齐状态** (`completion.design_sync`)

```text
aligned   Design ↔ Impl 契约一致
stale     一方已变更，需要重新检查 — 此状态下不能宣告完成
waived    有意的不一致。必须有 reason + until（到期日）
none      design_ref.kind: none 的工作
```

**入口** (`_order.entry_point`)

```text
design_first   Design → (Design↔Spec) → Impl → (Impl↔Design)
dev_first      Impl → (Impl↔Spec) → Design(retrofit) → (Impl↔Design)
spec_first     Spec → Design·Impl 并行 → 两个一致性检查
change         任一产物变更 → 其余变为 stale → 在一致性恢复之前视为未完成   (默认值)
```

评审不是单独的阶段，而是**每一次产物转换都会触发的事情**。不固定顺序。
验证的独立性由 `core/docs/zh/methodology/verification-tier.md` 的 `design_verified` 轴定义。

## 设计工具的正本范围

放在设计工具（例如 Figma）里的内容要划得窄。

| 正本候选 | 参考（非正本） | 不放入 |
|---|---|---|
| T1·T2 token 变量（含模式） | Feature 级别的画面框架 | 组合逻辑 · 数据流 · hook 边界 |
| Primitive UI 组件与 variant 属性 | | i18n 文案（key 在代码中，工具中只放 key 注释） |
| Semantic Component 的状态轴 (loading · empty · error) | | 路由 · 权限边界 · 布局原值 |

**token 的正本是代码仓库中的 token 文件**（推荐）。原因：智能体和 CI 可以稳定读取，可以生成符合上下文预算（`core/docs/zh/methodology/context-protocol.md` CB-1）的 alias 目录，并且不依赖设计工具的可访问性。
允许从设计工具向代码同步，但冲突用决策记录解决。相反的选择（以工具为正本）可以通过项目 profile 的决策来实现。

**token 的解析点只有一个** — Foundation 构建阶段（token 文件 → CSS 变量 · TS 常量 · 工具变量）。组件引用 alias 名称；组件 token 只能被拥有它的组件引用。

## 没有设计工具时

规则只有一条 — **Primitive UI 与 Semantic Component 拥有 story。** 没有设计工具时，story 就是 `design_ref`；有了工具之后，就进入 story↔工具 的一致性检查。
草稿工具（Claude Design 等）的产物只在确认之前充当 `design_ref`，确认后升级。

## 例外策略

当设计师引入的一次性取值无法用 alias 表达时：

1. **升级** — 连同决策记录一起新增 alias。修改 token 文件的 PR 引用 DEC id。
2. **例外标记** — `@strata:token-exception {reason} until {YYYY-MM-DD}`。到期后检查失败。语法见 `core/docs/zh/conventions/strata-markers.md`。
3. **度量** — 按 diff 口径、按设计属性逐项计数，把 Foundation 之外的 raw 值数量保持为 0 (`profiles/frontend.next-web/enforcement/`)。

运行时计算或测量得到的值（虚拟滚动偏移、测得的参照宽度、数据列宽等连续尺寸）不是一次性的设计取值。它们作为例外留在代码中，每处标注 `@strata:computed <reason>`，不计入 raw 值。一次性的设计取值使用会到期的 `@strata:token-exception`。

## Core / Convention / Profile 分离

| 性质 | 位置 | 示例 |
|---|---|---|
| 可验证的契约 | 本文档 · `core/rules/layer-rules.yaml` · `core/rules/naming-convention.yaml` | 组件引用 alias（组件 token 只能由其所有者引用）、一致性的定义、入口 enum |
| 工具绑定 | `profiles/frontend.next-web/docs/zh/frontend-tokens.md` · `profiles/frontend.next-web/docs/zh/frontend-styling.md` | token 文件格式、生成器、工具类 CSS 类名映射、story 工具 |
| 项目策略 | 项目 Tier P (`layer-map.yaml` · decisions) | token 文件路径、intent 扩展轴、正本方向、各 zone 的执行强度 |
