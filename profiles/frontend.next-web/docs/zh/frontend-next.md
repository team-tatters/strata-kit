# 前端 Next.js Convention

> 正本：strata-kit `profiles/frontend.next-web/docs/zh/frontend-next.md` — 从 strata `docs/05-conventions/frontend-next.md` 迁移（订单 2026.10.29-06，2026-10-29）。规则 YAML 位于 `core/rules/`。

> Core 边界：`core/docs/zh/architecture/frontend-web.md`

本文档说明 Next.js 项目如何映射 Core 的 Route Surface 和 App Shell。
Next.js 不是 Core 的必要前提。

## App Router

- route file（`page.tsx`）是 Route Surface。
- layout/provider/shell file 是 App Shell。
- 可复用的界面片段拆分为 Feature Block（`Section`）。
- route params、search params、metadata、authorization boundary 在 Route Surface 中解析。

### page.tsx 预算

`page.tsx` 只做 **params 解析 · 认证守卫 · metadata · 放置一个 Section**。服务端状态 hook（query/mutation）和 transport 调用被禁止 — 下沉到 Feature Block。
如果需要两个或更多 Section，就在 Feature 区域放一个 `{Route}Page` 组装组件，page.tsx 只渲染这一个组件。

## Pages Router

Pages Router 作为遗留 variant 或项目 migration zone 进行管理。
新的目标区域优先采用 App Router 映射。`pages/**` 在 layer-map 中映射为 Route Surface，并将 zone 设为 legacy。

## Server / Client Boundary

是否使用 Server Component、Client Component、server action 属于 framework convention。
Core 边界是相同的。直接调用 transport 以及 DataState 调用的位置不得破坏层规则。

## Multi-zone

在多个应用（zone）通过 rewrite 合并到同一个域名下的结构中：

- 跨 zone 的壳包（导航·会话 provider）是 **App Shell**。不得引用 Feature Block。
- 各 zone 的 QueryClient 可能没有分离，因此 query key 的第一个元素是 zone 标识符（`profiles/frontend.next-web/docs/zh/frontend-query-state.md`）。
- zone 之间的跳转只通过链接（URL）进行。不得 import 其他 zone 的 Feature Block。
