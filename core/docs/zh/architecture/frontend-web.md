# 前端 Web 层架构

> 正本：strata-kit `core/docs/zh/architecture/frontend-web.md` — 从 strata `docs/03-architecture/frontend-web.md` 迁移而来（订单 2026.10.29-06，2026-10-29）。规则 YAML 在 `core/rules/`。

> 机器可读的规则：`core/rules/layer-rules.yaml` → `frontend.variants.web`
> 本文档是与框架无关的 Web 前端 variant 的人类可读详细说明。
> token、变体、组合与设计产出物之间的一致性，由 `core/docs/zh/architecture/frontend-design-contract.md` 定义。

## 边界原则

Strata Core 的前端指引不定义具体的 UI 框架、路由器、状态管理库或样式工具。
Core 只放置可以通过 import、路径和静态分析来验证的职责边界。

层之间的关系不是单一的线性树，而是 DAG。
下表中的 `can_reference` 是 source of truth，表外的层引用，以及 `cross_reference: false` 的层之间的同级交叉引用，一律禁止（对 Feature Block 而言指跨领域；见下文）。

| Layer | can_reference |
|---|---|
| Foundation | 无 |
| Contract | Foundation |
| DataState | Foundation, Contract |
| Primitive UI | Foundation |
| Semantic Component | Foundation, Contract, Primitive UI |
| Feature Block | Foundation, Contract, DataState, Primitive UI, Semantic Component |
| Route Surface | Foundation, Contract, Feature Block, App Shell |
| App Shell | Foundation, Contract, DataState, Primitive UI, Semantic Component |

## Variants

Strata 前端支持三种 variant。

| Variant | 用途 | 状态 |
|---|---|---|
| `atomic` | 现有的 L1/LM/L2/Atomic/Molecule/Partial/Page/Layout 结构，以及与遗留项目的兼容 | 保留 |
| `web` | 与框架无关的 Web 应用边界 | 默认 |
| `mobile` | 原生移动端 UI（SwiftUI、Compose）— 层和 can_reference 与 web 相同，词汇、组装和目标规则不同（`core/docs/zh/architecture/frontend-mobile.md`） | 2026-09-11 |

各项目的选择放在 `.strata/layer-map.yaml` 的 `variant` 或 `frontend_variant` 中。
没有选择值时，Core 的默认值是 `web`。

## Foundation

放置语义 token、纯函数、常量和基本类型。

**允许：** token, const, type, util

**禁止：** UI 渲染、transport 调用、全局状态访问、依赖框架的实现

## Contract

UI 与 transport 之间的稳定契约。
放置 DTO、ViewModel、schema、API port/interface 和 cache key contract。

**规则：**
- 只引用 Foundation。
- 不引用 UI 层和 DataState。
- 不直接调用 transport 实现。
- 容易散落在组件文件中的 interface/type，集中到这一层。

## DataState

服务端状态、mutation 和客户端状态的 adapter 层。
具体的库由 convention 决定，Core 只定义不让 UI 直接看到 transport 的边界。

**规则：**
- 只引用 Foundation 和 Contract。
- 不渲染 UI 组件。
- 不向 UI 直接暴露 transport client。
- cache key 和 DTO/ViewModel 契约引用 Contract。

**两个区段：** transport（`{name}.service` — HTTP 调用，返回 DTO）和 adapter（`use{Entity}Query` · `use{Entity}{Action}Mutation` · `use{Name}State`）。
只有 adapter 可以 import transport。上层只看到 adapter。

## Primitive UI

绑定到语义 token 的底层 UI。
它必须不了解领域含义和服务端状态。

**规则：**
- 只引用 Foundation。
- 不引用 Contract 的领域模型、DataState 和 transport。
- 仅凭 Props 和 Foundation token 就能工作。

## Semantic Component

带有用户含义或领域含义的 UI 组件。
它不是 Atomic/Molecule 那样按大小分类，而是通过名称和职责来表达“这个组件做什么”。

**可验证的核心边界：** Semantic Component 不直接调用 DataState。
服务端状态和 mutation 通过 props 或 callback 注入。

从 Feature Block 中拆出渲染那一半的组件，命名为 `{Domain}{Purpose}View`。数据状态轴（loading · empty · error）通过 props 接收。
外观只由 Primitive UI 的 variant 轴取值与 Foundation alias 的组合来决定（Composition Legality — `core/docs/zh/architecture/frontend-design-contract.md`）。

## Feature Block

为特定 use case 组装画面片段及其数据/状态的层。
从这一层开始允许调用 DataState。

**规则：**
- 禁止不同领域的 Feature Block 之间直接引用。在同一领域内，Section 可以把另一个 Section 作为子级包含。当不同领域的画面需要一起显示时，由 Route Surface 的 `{RouteName}Page` 把各领域的 Section 并列放置，并通过 props 和事件连接。
- 领域是 feature 根目录下的一个直接子目录（layer-map 的 `feature_root`，否则为 layer-rules 中 `Feature_Block.domain_slice` 的前缀）。根目录之外的 Feature Block 文件不做领域隔离。这个边界是代码切片的边界，不保证业务领域的含义。
- 组装 Semantic Component、Primitive UI、DataState 和 Contract。
- 不承担路由和 app 级 provider 的职责。

后缀是 `{UseCase}Section`（没有路由的画面片段 — 相当于 atomic variant 的 Partial），根据形态使用 `Panel` · `Dialog` · `Table`。禁止使用 `Block`、`Container`、`Partial` 后缀（`core/rules/naming-convention.yaml` → `Feature_Block.forbidden_suffixes`）。
Section 是**其 use case 状态的所有者**（作为独立保存单元的子 Section 拥有自己的状态） — 它声明 Props，直接持有本地状态、effect 和 DataState adapter hook，并且只向下传播。渲染交给 `View`（Semantic Component）：
`Route Surface → Section → View → Primitive UI`。状态所有权分为三种 — 拥有本地草稿、观察服务器缓存、对保存命令负责。同一领域的子 Section 只有在它是自己的 use case 且是独立保存单元时，才拥有草稿和 mutation；只有与父级共享的状态才以 props 传入。被多个 Section 编辑的草稿只有一个所有者，跨 Section 的 submit、cancel 或原子保存由一个协调者（父 Section）负责，内部的输入作为 View 或 controlled component。原子性来自单个 DataState/API 命令或事务，而不是多个 mutation 之后的 invalidation。多个 Section 观察同一个 query key 不算重复所有。把状态逻辑拆成 hook 并不是义务，只有服务调用（transport）和被两个以上 Section 使用的公共加工，才作为引用结构放到外面。拆分标准和 Props 命名见 `profiles/frontend.next-web/docs/zh/frontend-react.md`。

## Route Surface

负责 URL 入口、route params、权限边界和画面组装。

**规则：**
- 放置 Feature Block — 原则上一个 Section。如果有两个以上，则设置 `{RouteName}Page` 组装组件。这个组装组件无论放在哪里（routes 或 features）都是 Route Surface — 在 layer-map 中，把它的映射放在 Feature Block 映射之前。
- 不作为可复用 UI 导出。
- 禁止直接调用 transport。也禁止调用 DataState hook — `can_reference` 中没有 DataState。

各路由器的文件规则不在 Core 中，而在框架 convention 中定义。

## App Shell

负责全局 provider、navigation 和 app 级 layout。

**规则：**
- 不直接引用 Feature Block。
- 不持有领域 use case 逻辑。
- 只处理全局 provider 和 shell 级 layout。
- 由多个 app（zone）共享的 shell 包也是 App Shell。跨越 app 边界的跳转只通过 URL 进行。

## Core / Convention / Profile 的划分

| 性质 | 位置 | 示例 |
|---|---|---|
| 可验证的架构边界 | Core `core/docs/zh/architecture/frontend-web.md`, `core/rules/layer-rules.yaml` | 禁止 Semantic Component 引用 DataState |
| 设计契约（token · 变体 · 组合 · 一致性） | Core `core/docs/zh/architecture/frontend-design-contract.md` | 组件引用 alias（组件 token 只能由其所有者引用），design_ref 与对齐状态 |
| 框架/库的绑定 | `profiles/<id>/docs/zh/` | query hook、router、样式工具、token 文件映射 |
| 项目的遗留/迁移策略 | 项目的 `.strata/` | legacy/bridge/target zone |

Strata Core 定义的不是“使用哪个库”，而是“哪种职责必须经过哪一层”。
