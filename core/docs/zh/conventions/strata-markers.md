# Strata 标记

> 正本：strata-kit `core/docs/zh/conventions/strata-markers.md` — 从 strata `docs/05-conventions/strata-markers.md` 迁移而来（订单 2026.10.29-06，2026-10-29）。规则 YAML 在 `core/rules/`。

> 机器可读的定义：`core/rules/naming-convention.yaml` → `markers` 部分

这是插入源代码的基于注释的注解，用来声明文件属于哪个层/端口/领域。

> **执行状态（截至 2026-07）**：标记目前**仅供 grep 和人工阅读**。Hook 脚本
> （`check-layer-violation.py`、`validate-naming.py`）还不解析标记，
> 将 `@strata:generated` 排除在验证之外的功能也尚未实现（层的识别基于 layer-map/目录）。
> 是否实现标记解析器，按照 `methodology-backlog.yaml` MB-strata-2026-003 中的执行委托
> 策略来决定 — JVM 上的正本执行由 ArchUnit（`profiles/backend.kotlin-spring-cqrs/enforcement/`）负责。

## 语法

```
@strata:{tag} {value}
```

Go 不带 `@` 使用（godoc 惯例）：

```
strata:{tag} {value}
```

## 支持的标签

| 标签 | 用途 | 模式 | 示例 |
|---|---|---|---|
| `port` | 声明层端口（服务接口） | `{Layer}-{ServiceName}` | `@strata:port L2-InventoryQueryService` |
| `layer` | 声明文件所属的层 | `{Layer}` | `@strata:layer L2` |
| `domain` | 声明文件所属的业务领域 | `{domain}` | `@strata:domain inventory` |
| `generated` | 自动生成的文件（排除在层验证之外） | （无值） | `@strata:generated` |
| `adapter` | 声明外部库的适配器 | `{library}` | `@strata:adapter sqlc` |
| `depends` | 声明显式依赖的端口 | `{Layer}-{ServiceName}` | `@strata:depends L2-OrderQueryService` |
| `token-exception` | 临时允许 Foundation 之外出现原始 token 值。**必须有到期日** — 过期后 diff 检查失败（`core/docs/zh/architecture/frontend-design-contract.md` §例外策略） | `{reason} until {YYYY-MM-DD}` | `@strata:token-exception 设计定稿前的临时颜色 until 2026-10-31` |

## 各语言的格式

### Kotlin (KDoc)

```kotlin
/**
 * @strata:port L2-InventoryCommandService
 * @strata:layer L2
 * @strata:domain inventory
 */
class InventoryCommandService(
    private val repository: InventoryRepository
) { ... }
```

### Go (godoc)

Go 使用不带 `@` 前缀的 `strata:` 形式。

```go
// InventoryQueryRepository provides read-only access to inventory views.
//
// strata:port L2-InventoryQueryRepository
// strata:layer L2
// strata:domain inventory
type InventoryQueryRepository interface {
    FindByID(ctx context.Context, id uuid.UUID) (*InventoryView, error)
}
```

### Swift (文档注释)

```swift
/// 今日状态的转换规则 — 仅限纯函数。
/// @strata:layer Contract
/// @strata:domain today
enum StateEngine { … }
```

### TypeScript (JSDoc)

```typescript
/**
 * @strata:port L2-InventoryQueryService
 * @strata:layer L2
 * @strata:domain inventory
 */
export class InventoryQueryService {
    constructor(private readonly repo: InventoryRepository) {}
}
```

## 搜索模式

```bash
# 搜索特定层的所有端口
grep -r "@strata:port L2" --include="*.kt" --include="*.ts"
grep -r "strata:port L2" --include="*.go"

# 搜索特定领域的所有文件
grep -r "strata:domain inventory" --include="*.kt" --include="*.go" --include="*.ts"

# 搜索自动生成的文件
grep -r "strata:generated" --include="*.kt" --include="*.go" --include="*.ts"
```

## 从 PAL 标记迁移

PAL（Port-Adapter Layered）标记是 strata 之前的项目级惯例。
PAL 的层编号与 strata 的正式编号不一致，因此迁移时需要进行编号转换。

| PAL 标记 | strata 标记 | 编号转换 |
|---|---|---|
| `@pal-port L1-SomeService` | `@strata:port L2-SomeService` | PAL L1 → strata L2 |
| `@pal-layer l1` | `@strata:layer L2` | PAL L1 → strata L2 |
| `@pal-layer l2` | `@strata:layer L3` | PAL L2 → strata L3+Route |
| `@pal-domain inventories` | `@strata:domain inventories` | （相同） |
| `@pal-generated` | `@strata:generated` | （相同） |
| `@pal-adapter jooq` | `@strata:adapter jooq` | （相同） |
| `@pal-depends L1-Other` | `@strata:depends L2-Other` | PAL L1 → strata L2 |

### 迁移步骤

1. 在 strata 核心中添加标记规范（本文档）
2. 在目标项目中将 PAL 批量替换为 strata（`sed` 或 IDE）
3. 应用层编号映射（PAL L1 → strata L2 等）
4. 将现有的 `PAL-MARKERS.md` 替换为对本文档的引用
