# 后端 Go — 概念模型的投影

> 正本: strata-kit `profiles/backend.go-service/docs/zh/backend-go.md` (2026-10-29, DEC-2026-10-29-06)
> 概念模型: `core/docs/zh/architecture/backend-cqrs.md` — 层的含义、依赖方向、同层引用禁令以该文档为正本。本文档只规定在 Go 中如何体现这些内容。

## 摘要

- Go 的封装单位是**包**。因此不把层展开成目录(`internal/component/`、`internal/data/` ……),而是**功能(领域)包在前**,层以其中的**角色文件**体现。Go 社区回避的不是 CQRS,而是"按层建目录、按结构体建接口"。
- 基准技术栈: 标准库 `net/http`(Go 1.22 模式路由)、`pgx`、`sqlc`(从 SQL 生成带类型的查询函数)、`log/slog`。框架(gin、echo)可选,投影相同。
- 接口由**使用方**定义,并保持小("accept interfaces, return structs")。这与六边形架构中端口归使用方所有的原则相同。
- 边界由编译器(禁止循环 import)、`internal/` 目录和 `depguard`(golangci-lint)来拦截。

## 布局

```
cmd/api/main.go                 Route 装配 — 启动服务器、连接依赖(手写 DI)
internal/
  platform/                     LM1 — db 连接池、事务辅助、配置 (pgxpool, slog)
  kit/                          L1 — 纯函数、错误码、分页类型 (不 import 框架)
  order/                        一个功能包 = 一个领域
    order.go                    L1(领域) — 实体类型、值对象、纯计算
    store.go                    L2 下层 — 封装 sqlc 生成的 Queries 的查询与保存 (Repository、Template 的角色)
    command.go                  L2 上层 — CommandService: 事务内的创建、修改、删除
    query.go                    L2 上层 — QueryService: 只读,直接返回 DTO
    coordinate.go               LM2 — 同一关注点的 L2 组合 (仅在需要时)
    usecase.go                  L3 — CompositeService: 用例
    http.go                     Route — 处理器: 校验、认证上下文、响应转换,只调用 usecase
    queries.sql / db/           sqlc 的输入与生成物
  payment/ …
```

| 概念层 | 在 Go 中 | 名称 |
|---|---|---|
| L1 | `internal/kit` 包、功能包中的类型与纯函数 | `PageRequest`, `func Convert(...)` |
| LM1 | `internal/platform` | `NewPool`, `WithTx` |
| L2 下层 | `store.go` — sqlc `Queries` 的封装 | `type store struct{ q *db.Queries }` (小写: 对包外隐藏) |
| L2 上层 | `command.go` · `query.go` | `type CommandService struct`, `type QueryService struct` |
| LM2 | `coordinate.go` 或 `internal/<关注点>` 包 | `type PaymentCoordinator struct` |
| L3 | `usecase.go` | `type CommandCompositeService struct` (包即领域,故为 `order.CommandCompositeService`) |
| Route | `http.go`, `cmd/api` | `func (h *Handler) CreateOrder(w, r)` |

- 由于在同一个包内,Go 编译器无法阻止文件之间的引用。**同层引用禁令靠评审和 linter 来保证**: L2 上层的类型不互相作为字段持有,`store` 不知道服务类型。
- 下层(`store`)和生成的 sqlc 代码使用**小写类型**,使包外(其他领域、处理器)无法直接使用。其他包可以使用的只有服务类型和用例类型。
- 避免名称重复(stutter): 用 `order.CommandService`,而不是 `order.OrderService`。

## 依赖与接口

```go
// internal/order/usecase.go — L3
type CommandCompositeService struct {
    cmd      *CommandService
    payments PaymentAuthorizer          // 其他领域通过使用方定义的小接口接入
}

type PaymentAuthorizer interface {     // 端口: 由使用方(order)拥有
    Authorize(ctx context.Context, orderID int64, amount Money) error
}

func (s *CommandCompositeService) PlaceOrder(ctx context.Context, in PlaceOrderInput) (OrderID, error) {
    id, err := s.cmd.Create(ctx, in.toNew())
    if err != nil { return 0, err }
    return id, s.payments.Authorize(ctx, int64(id), in.Total)
}
```

- 领域包之间互不 import(禁止 L3 ↔ L3)。所需的能力通过使用方的接口接收,由 `cmd/api/main.go` 连接实现。
- 不要为每个结构体预先创建接口。接口只放在需要替换(测试替身、其他实现)的边界上。

## 命令与查询

- 写: `CommandService` 的方法在 `platform.WithTx(ctx, pool, func(q *db.Queries) error {...})` 内执行。事务只放在 L2 上层。
- 读: `QueryService` 直接把 sqlc 生成的查询函数(含连接)的结果作为 DTO 返回。不必经过领域类型。

## 强制执行

| 对象 | 工具 |
|---|---|
| 禁止领域包之间 import,`kit` 不 import 任何东西 | `golangci-lint` 的 `depguard` 规则(按包路径)或 `go-arch-lint` |
| 阻止对包外暴露 | 小写标识符、`internal/` |
| 循环依赖 | 编译器 |
| 格式与静态检查 | `gofmt`, `go vet`, `staticcheck` |
| 测试 | `go test ./...` (store 使用 testcontainers 的真实 PG) |

## 标记

Go 把标记放在 godoc 注释中,不带 `@`(`core/rules/naming-convention.yaml` markers.language_format.go,`core/docs/zh/conventions/strata-markers.md`):

```go
// strata:layer L2-QueryService
type QueryService struct{ … }
```
