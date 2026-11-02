# 前端 Atomic Variant 层架构

> 正本：strata-kit `core/docs/zh/architecture/frontend-atomic.md` — 从 strata `docs/03-architecture/frontend-atomic.md` 迁移而来（订单 2026.10.29-06，2026-10-29）。规则 YAML 位于 `core/rules/`。

> 机器可读规则：`core/rules/layer-rules.yaml` → `frontend.variants.atomic`
> 新建 Web 项目的默认 variant 是 `frontend.variants.web`，详见 `core/docs/zh/architecture/frontend-web.md`。
> **状态：保留（兼容旧版）** — 不建议新项目采用。Molecule/Organism 按大小分类的做法，已被 web variant 的 Composition Legality (`core/docs/zh/architecture/frontend-design-contract.md`) 取代。

## 映射到 web variant

| Atomic | web variant | 判定标准 |
|---|---|---|
| Atom | Primitive UI | 不感知领域，仅有 alias token + variant 轴 |
| Molecule | Semantic Component **或** Feature Block | 调用 DataState 则为 Feature Block，否则为 Semantic Component。**不按大小判定** |
| Organism | （废弃） | 并入 Feature Block |
| Partial | Feature Block (`{UseCase}Section`) | 没有路由的画面片段 |
| Page · Layout | Route Surface · App Shell | 保持不变 |
| L2 Hook | DataState adapter | `useQuery{Name}` → `use{Entity}Query` |
| LM | Contract + DataState transport | ViewModel、DTO 归 Contract，API Client 归 `{name}.service` |

## 层结构

```
Page / Layout
    ↓
Partial (页面级公共 UI 集合)
    ↓
Molecule (行为专用组件)
    ↓
Atomic (纯 UI 组件)
    ↓
L2 (状态管理 Hook)
    ↓
LM (ViewModel, DTO, API Client)
    ↓
L1 (纯函数, 类型, 常量)
```

## L1 — 纯函数层

与后端 L1 原则相同。不依赖 UI 框架的纯逻辑。
允许纯状态管理 Hook，但禁止调用 API。

**示例：** useDebounce, useLocalStorage, formatDate, validateEmail

## LM — 数据模型层

负责与服务器通信的中间层。

**构成：** ViewModel（仅用于显示的数据结构）、DTO（服务器请求/响应的映射）、
API Port/Client Interface（transport 调用边界）、Interface（契约定义）

**规则：** 禁止 UI 渲染逻辑。只负责数据转换与通信。

## L2 — 状态管理层

服务器/客户端状态的 adapter Hook。

**规则：** 使用 LM 的 API Client 同步服务器状态。
不直接渲染 UI 组件。只 export Hook。

## Atomic — 最小单元 UI

去除了 L2 及以下所有依赖的纯 UI 组件。
仅靠 Props 工作，禁止访问全局状态。

**示例：** Button, Input, Badge, Avatar, Tooltip, Card

## Molecule — 行为专用 UI

组合 Atomic 并绑定 L2 Hook 的组件。
专用于某个特定的领域行为。

**示例：** SearchBar (Input + Button + useSearchStore),
OrderCard (Card + Badge + useOrderQuery)

## Partial — 页面级公共集合

在多个页面之间共享的 UI 块。
是 Molecule 与 Atomic 的组合。

**示例：** OrderListPartial, UserProfilePartial, NotificationPanel

## Page — 路由对象

映射到实际 URL 的顶层组件。
组合 Layout、Partial、Molecule、Atomic，构成完整的画面。

## Layout — 结构性包装

定义导航、侧边栏、页脚等页面结构。
以 children 的形式接收 Page 组件。
