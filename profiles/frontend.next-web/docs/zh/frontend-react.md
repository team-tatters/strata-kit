# 前端 React Convention

> 正本：strata-kit `profiles/frontend.next-web/docs/zh/frontend-react.md` — 从 strata `docs/05-conventions/frontend-react.md` 迁移（订单 2026.10.29-06，2026-10-29）。规则 YAML 位于 `core/rules/`。

> Core 边界：`core/docs/zh/architecture/frontend-web.md` · 设计契约：`core/docs/zh/architecture/frontend-design-contract.md`

本文档说明 React 项目实现 Core Web 层时的惯例。
React 不是 Core 的必要前提。

## 单向链 — Page → Section → View → Primitive

从路由到界面只沿一个方向流动。**Section 是其 use case 状态的所有者**（作为独立保存单元的子 Section 拥有自己的状态） — Section 声明 Props、持有状态，并且只向下传播。

```
route file (Route Surface)
  └─ params · guard · metadata · 仅一个 <XxxSection/>。hook 只有路由 hook
      └─ XxxSection (Feature Block) — 状态所有者
           │  useState · useEffect · 本地 hook · DataState adapter hook(use*Query · use*Mutation)在此直接调用
           ├─ <XxxView/>          Semantic Component — 只接收 props 并绘制
           └─ <XxxSubSection/>    必要时的同一领域下级 Section — 是独立保存单元时才是状态所有者：
                                  直接获取和保存自己 use case 的数据；只有与父级共享的状态以 props 传入。
                                  与父级一起 submit 或 cancel 的输入不是 Section，而是 View 或 controlled component；
                                  草稿和 submit 由父级所有(原子保存：一个命令或事务)
                └─ Primitive UI + alias 令牌
```

## Section 的状态所有权与拆分标准

放在 Section 内的和拿到外面的，按**种类而不是数量**区分。把状态逻辑拆分成 hook 不是义务。

| 种类 | 位置 | 原因 |
|---|---|---|
| 本地状态（`useState` · `useReducer`）、副作用（`useEffect`）、派生值（`useMemo`）、仅此 Section 使用的本地 hook | **Section 内** | 状态的所有者必须在一处可见 |
| 读取·写入服务端状态 | Section **调用** DataState adapter hook。实现位于 `query-hooks/` | transport 不出现在 Section 中 |
| 服务调用（HTTP · storage · 外部 SDK） | **始终在外** — DataState transport | 组件不知道 transport |
| 两个或更多 Section 使用的加工·计算·状态逻辑 | **外** — `features/{domain}/hooks/use{Thing}` 或 Foundation util | 公共层采用引用结构 |
| 其他 Section 要整体复用某个 Section 的状态逻辑，或必须单独测试时 | 可选 — 拆分为 `use{UseCase}Section` | 仅在需要时拆分。默认放在 Section 内 |

## 后缀含义

| 后缀 | 层 | DataState 调用 | 路由 hook | 备注 |
|---|---|---|---|---|
| `{Route}Page` / route file | Route Surface | 禁止 | 允许 | 原则是放置 1 个 Section。两个或更多时，放 `{Route}Page` 组装组件 — 无论放在哪里(routes 或 features)都是 Route Surface(它的 layer-map 映射在 Feature Block 之前)。不同领域的 Section 在这里并列放置 |
| `{UseCase}Section` | Feature Block | 允许 | 禁止 — 由 Page 注入 | 状态所有者。没有路由的界面片段，可在多个路由中复用。禁止 import 其他领域的 Section；同一领域的 Section 可以作为子级包含 |
| `{UseCase}Panel` · `Dialog` · `Table` | Feature Block | 允许 | 禁止 | 浮层·侧边·表格形态的 Section |
| `{Domain}{Purpose}View` | Semantic Component | 禁止 | 禁止 | 仅 props。只可持有本地 UI 状态（展开·悬停） |
| Primitive 组件 | Primitive UI | 禁止 | 禁止 | 仅 alias + variant 轴 |

禁止使用 `Container`·`Block`·`Partial` 后缀 — 使用 `Section`（或按形态使用 `Panel` · `Dialog` · `Table`）。

## Props 命名 — 把所有者和方向放进名称

当 Section 所拥有的状态和 hook 向下传给多个子组件时，仅凭 prop 名称就必须能知道**谁拥有 · 朝哪个方向流动 · 是值还是行为**。前缀·后缀表达这三点。机器可读：`core/rules/naming-convention.yaml` → `frontend.Props`。

| 角色 | 形式 | 示例 | 规则 |
|---|---|---|---|
| 父级拥有的状态的当前值（读取） | 名词，无前缀 | `selectedIds` · `filter` · `page` | 无前缀 = “父级拥有，子级只读” |
| 请求变更父级状态（子 → 父） | `on{State}Change` | `onSelectedIdsChange` · `onFilterChange` | 不直接传递 setter。禁止 `set*` prop |
| 触发父级行为（事件） | `on{Event}`（动词） | `onSubmit` · `onRowClick` · `onDelete` | 子级无需知道结果时 |
| 值 + 变更的配对被**多个子级共享** | `{state}Control` 打包 | `selectionControl={{ value, onChange }}` | 多重引用标记。类型 `{State}Control`。不要把同一状态拆成值和回调两个 prop 散给多个子级 |
| 派生·仅展示数据的打包 | `{name}Model` | `orderModel` | Contract 的 ViewModel。不放回调 |
| 初始值（子级拥有） | `default{State}` | `defaultPage` | 非受控。此后父级不再干预 |
| 布尔值 | `is` · `has` · `can` · `should` | `isEditing` · `canDelete` · `shouldAutoFocus` | 肯定形式。`disabled` 这样的 HTML 属性名为例外 |
| 服务端状态切片 | 数据名词 + `is{Entity}Loading` + `{entity}Error` | `orders` · `isOrdersLoading` · `ordersError` | 不整体传递 query 结果对象 |
| 渲染委托 | `render{Slot}` | `renderRow` | |
| ref | `{name}Ref` | `scrollRef` | |

**建议 — 多重引用用 Control 打包。** 当一个父级状态被三个子级读写时，把 `value`·`onChange`·派生值打包成一个 `{state}Control` 对象向下传递。名称后缀体现出这是“父级拥有、多处共享的状态”，子级增加时 prop 数量也不会增加。`shared*`·`section*` 这样的扁平前缀只说明了所有权，却没有说明方向（读/写），因此不使用。

```tsx
// Section — 状态所有者
const [selectedIds, setSelectedIds] = useState<number[]>([]);
const selectionControl: SelectionControl = { value: selectedIds, onChange: setSelectedIds, count: selectedIds.length };
const { data: orders = [], isLoading: isOrdersLoading } = useOrderListQuery(filter);

<OrderTableView orders={orders} isOrdersLoading={isOrdersLoading} selectionControl={selectionControl} onRowClick={handleRowClick} />
<OrderBulkActionView selectionControl={selectionControl} onDelete={handleDelete} />
```

内部处理函数的名称是 `handle{Event}`，传给子级的 prop 名称是 `on{Event}`。两者不使用相同的名称。

## Component Boundary

- 一个文件中放一个 exported component。
- 允许文件内部的辅助函数和 private subcomponent，但被复用时要拆分到单独的文件。
- DTO、ViewModel、schema、interface 移到 Contract。
- Semantic Component 不直接调用 DataState hook，而是通过 props/callback 接收注入。
- 数据状态轴（loading · empty · error）作为 View 的 props 接收并渲染。值由 Section 决定。

## State Boundary

- use case 组装和 DataState 调用从 Feature Block（Section）开始。
- 不要在 shared UI component 中引入服务端状态库的依赖。
- feature-local context 仅在 props 传递变深时有限使用。如果 Control 打包能解决，就不创建 context。
