# Strata マーカー

> 正本: strata-kit `core/docs/ja/conventions/strata-markers.md` — strata `docs/05-conventions/strata-markers.md` から移管（オーダー 2026.10.29-06、2026-10-29）。ルール YAML は `core/rules/`。

> 機械可読な定義: `core/rules/naming-convention.yaml` → `markers` セクション

ソースコードに挿入するコメントベースのアノテーションで、ファイルがどのレイヤー/ポート/ドメインに属するかを宣言します。

> **執行状況（2026-07 時点）**: マーカーは現在 **grep・人が読むためだけ**のものです。フックスクリプト
> （`check-layer-violation.py`、`validate-naming.py`）はまだマーカーを解析せず、
> `@strata:generated` を検証から除外する処理も未実装です（レイヤーの識別は layer-map/ディレクトリに基づく）。
> マーカーパーサーを実装するかどうかは、`methodology-backlog.yaml` の MB-strata-2026-003 にある執行委任の
> 戦略に従って決めます — JVM における正本の執行は ArchUnit（`profiles/backend.kotlin-spring-cqrs/enforcement/`）が担います。

## 文法

```
@strata:{tag} {value}
```

Go は `@` なしで使います（godoc の慣習）:

```
strata:{tag} {value}
```

## サポートするタグ

| タグ | 用途 | パターン | 例 |
|---|---|---|---|
| `port` | レイヤーポート（サービスインターフェース）の宣言 | `{Layer}-{ServiceName}` | `@strata:port L2-InventoryQueryService` |
| `layer` | ファイルが属するレイヤーの宣言 | `{Layer}` | `@strata:layer L2` |
| `domain` | ファイルが属するビジネスドメインの宣言 | `{domain}` | `@strata:domain inventory` |
| `generated` | 自動生成ファイル（レイヤー検証から除外） | （値なし） | `@strata:generated` |
| `adapter` | 外部ライブラリのアダプターの宣言 | `{library}` | `@strata:adapter sqlc` |
| `depends` | 明示的な依存ポートの宣言 | `{Layer}-{ServiceName}` | `@strata:depends L2-OrderQueryService` |
| `token-exception` | Foundation の外にある生のトークン値の一時的な許可。**期限日が必須** — 過ぎると diff 検査が失敗する（`core/docs/ja/architecture/frontend-design-contract.md` §例外ポリシー） | `{reason} until {YYYY-MM-DD}` | `@strata:token-exception デザイン確定までの仮の色 until 2026-10-31` |

## 言語ごとの形式

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

Go は `@` 接頭辞なしの `strata:` 形式を使います。

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

### Swift (ドキュメントコメント)

```swift
/// 今日の状態の変換規則 — 純粋関数のみ。
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

## 検索パターン

```bash
# 特定レイヤーのすべてのポートを検索
grep -r "@strata:port L2" --include="*.kt" --include="*.ts"
grep -r "strata:port L2" --include="*.go"

# 特定ドメインのすべてのファイルを検索
grep -r "strata:domain inventory" --include="*.kt" --include="*.go" --include="*.ts"

# 自動生成ファイルを検索
grep -r "strata:generated" --include="*.kt" --include="*.go" --include="*.ts"
```

## PAL マーカーからのマイグレーション

PAL（Port-Adapter Layered）マーカーは、strata 以前のプロジェクトレベルの慣習です。
PAL のレイヤー番号は strata の正式な番号と一致しないため、マイグレーションでは番号の変換が必要です。

| PAL マーカー | strata マーカー | 番号の変換 |
|---|---|---|
| `@pal-port L1-SomeService` | `@strata:port L2-SomeService` | PAL L1 → strata L2 |
| `@pal-layer l1` | `@strata:layer L2` | PAL L1 → strata L2 |
| `@pal-layer l2` | `@strata:layer L3` | PAL L2 → strata L3+Route |
| `@pal-domain inventories` | `@strata:domain inventories` | （同じ） |
| `@pal-generated` | `@strata:generated` | （同じ） |
| `@pal-adapter jooq` | `@strata:adapter jooq` | （同じ） |
| `@pal-depends L1-Other` | `@strata:depends L2-Other` | PAL L1 → strata L2 |

### マイグレーション手順

1. strata コアにマーカーの仕様を追加する（この文書）
2. 対象プロジェクトで PAL → strata を一括置換する（`sed` または IDE）
3. レイヤー番号のマッピングを適用する（PAL L1 → strata L2 など）
4. 既存の `PAL-MARKERS.md` を、この文書への参照に置き換える
