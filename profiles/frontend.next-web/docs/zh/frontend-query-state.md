# 前端 Query / State Convention

> 正本：strata-kit `profiles/frontend.next-web/docs/zh/frontend-query-state.md` — 从 strata `docs/05-conventions/frontend-query-state.md` 迁移（订单 2026.10.29-06，2026-10-29）。规则 YAML 位于 `core/rules/`。

> Core 边界：`core/docs/zh/architecture/frontend-web.md`

本文档是将 DataState 层映射到特定库的 convention。
Core 的 source of truth 是“UI 不直接调用 transport”，本文档说明实现上的选择。

## DataState 内的两个区段

| 区段 | 文件 | 职责 | 可引用 |
|---|---|---|---|
| transport | `{name}.service.ts` | 调用 HTTP client，返回 DTO | Foundation · Contract |
| adapter | `use{Entity}Query.ts` · `use{Entity}{Action}Mutation.ts` · `use{Name}State.ts` | 服务端/客户端状态 hook | Foundation · Contract · **transport** |

只有 adapter 可以 import transport。组件（Section）·Route Surface·公共 hook 只能看到 adapter。

## Hook 命名

| 种类 | 名称 | 位置（层） |
|---|---|---|
| 读取服务端状态 | `use{Entity}Query` · `use{Entity}ListQuery` | DataState adapter |
| 写入服务端状态 | `use{Entity}{Action}Mutation`（Create · Update · Delete · Submit …） | DataState adapter |
| 拆分 Section 状态逻辑（可选） | `use{UseCase}Section` — 仅当其他 Section 复用或需要单独测试时。默认放在 Section 内 | Feature Block |
| 公共加工·计算 | `use{Thing}` — 两个或更多 Section 使用的逻辑 | Feature Block hooks 或 Foundation |
| 客户端状态 | `use{Name}State` · `use{Name}Store` | DataState adapter |
| 纯工具 | `use{Thing}` — 仅依赖框架 hook | Foundation |

**禁止前缀**：`useFetch · useGet · usePost · usePut · usePatch · useDelete`。HTTP 动词是 transport 的词汇，hook 使用领域词汇。
不改动现有代码，只检查新增行（`profiles/frontend.next-web/enforcement/`）。

## Query Key — 形态 · 所有权 · 强制执行

key 只能通过 key factory 创建 — 每个功能（领域）一个，放在该功能的 `{domain}.keys.ts` 中。

```ts
// features/{domain}/{domain}.keys.ts
export const orderKeys = {
  all:     ['shop', 'order'] as const,                       // [scope, domain]
  lists:   () => [...orderKeys.all, 'list'] as const,
  list:    (p: OrderListRequest) => [...orderKeys.lists(), p] as const,
  details: () => [...orderKeys.all, 'detail'] as const,
  detail:  (id: number) => [...orderKeys.details(), id] as const,
};
```

- **形态**：`[scope, domain, entity/scope…, params]`。第一个元素是应用·zone 标识符 — 多个应用可能共享 QueryClient，因此用它防止冲突。
- **层级**：`all → lists → list(p)`、`all → details → detail(id)`。扁平 key（`['orders']`）无法做部分失效，因此不合格。
- **所有权**：失效只能在 mutation hook 中进行，并且只针对该 hook **声明为受影响**的 key — 通过 mutation 的 `meta.invalidates` 中的标签列表，或 hook 内部的显式列表声明。声明的 key 可以是 `keys.lists()` 这样的部分树、`keys.detail(id)` 这样精确的 detail key，或其他领域的 key，但一律用所属功能的 key factory 构建。禁止在组件中直接调用 `invalidateQueries`。
- **强制执行**：静态依赖分析无法捕获内联字面量 — 用 diff 规则（`no-inline-query-key`、`no-component-invalidate`）仅拦截新增行。

## 基本规则

- 服务端状态用 query/mutation adapter 封装。
- mutation 之后的 cache invalidation 策略放在 DataState。
- 全局状态不是默认选项。先考虑 URL state、query cache、local state。
- 如果 props 传递过多，就在 Feature Block 内部设置 composition boundary 或 feature-local context。

## 禁止

- 在 UI 组件中直接调用 transport client
- Route Surface 持有按 use case 区分的 mutation 细节逻辑
- Semantic Component 直接调用 server-state adapter
- `*.keys.ts` 之外的 queryKey 字面量

## 库映射

在 React 系列项目中，DataState 可以用 query hook、mutation hook、client-state hook 来实现。
具体的库及其各版本 API 由项目 profile 或 framework convention 决定。
