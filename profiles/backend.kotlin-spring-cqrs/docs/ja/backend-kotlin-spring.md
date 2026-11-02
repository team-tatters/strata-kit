# バックエンド Kotlin/Spring Convention

> 正本: strata-kit `profiles/backend.kotlin-spring-cqrs/docs/ja/backend-kotlin-spring.md` — strata `docs/05-conventions/backend-kotlin-spring.md` から移管（オーダー 2026.10.29-06、2026-10-29）。ルール YAML は `core/rules/`。

> Core の境界: `core/docs/ja/architecture/backend-cqrs.md`, `core/rules/layer-rules.yaml`
> 前払い原則と 3 つの境界（データ所有・ドメイン間の書き込み・ドメイン間の読み取り）: `core/docs/ja/architecture/prepaid-structure.md`

この文書は、Kotlin + Spring のプロジェクトが Core の CQRS レイヤーを実装するときの慣習を説明します。
Kotlin/Spring は Core の必須の前提ではありません。

## レイヤー ↔ パッケージのマッピング

JVM でレイヤーを識別する第一のキーは、ディレクトリではなく**パッケージセグメント**です
（`core/rules/layer-rules.yaml` の `language_patterns.kotlin.package_identifier`）。

| レイヤー | パッケージセグメント | 例 |
|---|---|---|
| L1_Component | `..component..` | `com.example.order.component.MoneyUtil` |
| LM1_Inherite | `..inherite..` | `com.example.order.inherite.BaseEntity` |
| L2_DataLayer | `..data.{domain}..` | `com.example.order.data.payment.PaymentQueryService` |
| LM2_Coordinate | `..coordinate.{domain}..` | `com.example.order.coordinate.payment.PaymentQueryCoordinator` |
| L3_Composite | `..composite.{domain}..` | `com.example.order.composite.checkout.CheckoutCommandCompositeService` |
| Route_Controller | `..controller..` | `com.example.order.controller.CheckoutController` |

ファイル名は Core のデフォルトである PascalCase パターン（`{Domain}QueryService.kt` など）にそのまま従います。L3 の接尾辞は `CompositeService` です（`{Domain}CommandCompositeService`、振る舞いを示す必要があるときは `{Domain}{Action}CompositeService` — DEC-2026-10-29-05）。

実際のプロジェクトは、上のセグメントとは異なるパッケージを使うことがあります。たとえば shop-api は L3 を `rest/<domain>/services/` に、LM2 を `rest/<domain>/coordinator/` に置きます。レイヤーはパッケージ名ではなく、プロジェクトの `layer-map.yaml` にあるパスのマッピングで判定されるので、マッピングさえ合っていれば構いません。

## L2 の 2 段と同じ段の参照

| 段 | Kotlin の要素 | 参照 |
|---|---|---|
| 下の段 | `*Repository`（Spring Data JPA インターフェース）、`*Template`（jOOQ・QueryDSL の DSL） | 上の段を知らない。Repository ↔ Template は禁止 |
| 上の段 | `*CommandService`（`@Transactional`）、`*QueryService`（`readOnly`） | 下の段をコンストラクタ注入で使う。サービス ↔ サービスの注入は禁止 |

- 2 つのサービスが同じ組み合わせを繰り返すなら、LM2 の `*Coordinator` に引き上げる。基準は、同じドメインの関心事かどうかである。
- 単位換算や算式のように注入が要らない計算は、`object` に切り出して段の外に置く（例: `UnitConversions.convert(...)`）。
- エンティティモジュールの内部でだけ使うサービス・ヘルパーは、Kotlin の `internal` で隠す。`internal` は同じ Gradle ソースセット内でのみ見えるので、サービスモジュールの L3 がそれを迂回して呼ぶことをコンパイラが防ぐ。コンストラクタを受け取る public クラスには `internal constructor` を付ける。

## モジュール境界（Gradle マルチモジュール）

- ドメインの境界は、可能であれば Gradle モジュールに分離します。モジュールの依存が
  `build.gradle.kts` に宣言されていなければ import がコンパイルエラーになるため、「L2 間の相互参照禁止」のような規則が
  ツールなしでコンパイラのレベルで強制されます。
- モジュールの依存は `implementation` を基本とします。`api` は、その型がモジュールの公開契約で
  あるときにだけ使います — 推移的な依存の漏れは、レイヤー迂回の経路になります。
- モジュール内部のレイヤーの向きは、ArchUnit テストが正本として検証します（下の執行構造）。

## Spring バインディングの慣習

- **依存性注入はコンストラクタ注入のみ**を使います。フィールドへの `@Autowired` や `lateinit var` による注入は禁止です。
  コンストラクタ注入はバイトコードに型参照を残し、これが静的なレイヤー検証が動作するための前提です。
- **文字列による Bean 取得の禁止**: `applicationContext.getBean("...")` や `@Qualifier` の乱用など、
  型参照を隠すパターンはレイヤー検証を迂回するため禁止です（ArchUnit が遮断）。
- **トランザクション境界は L2 の CommandService**: `@Transactional` は CommandService に置きます
  （Core の規則）。QueryService は読み取り専用です — `@Transactional(readOnly = true)` か、省略します。
- **JPA Entity を L2 の外へ返しません**: LM1 の共通エンティティ定義を除き、
  Entity は L2 の内部で DTO/ドメイン型に変換してから上位へ渡します。
  Controller が `..entity..` や Entity 型を参照すれば違反です。
- **Controller は薄く**: URI の定義、パラメータ検証（`@Valid`）、認証コンテキストの注入、
  Response DTO への変換だけを行います。ビジネス上の分岐は L3 へ。
- L1_Component は Spring の import 自体を禁止します（Core の規則「外部フレームワークの import 禁止」）。

## 執行構造（3 段）

| 階層 | 担当 | 強度 |
|---|---|---|
| Gradle マルチモジュール | モジュール（ドメイン）の境界 | コンパイラによる強制 |
| ArchUnit | レイヤーの向き + ドメインスライスの隔離 + getBean の遮断 | CI blocking（正本） |
| Hook | 編集時のリアルタイムなフィードバック | ヒューリスティック（warning） |

ArchUnit テストは `core/rules/layer-rules.yaml` を実行時に直接読むため、規則をテストコードに
複製しません。テンプレートと適用方法: `profiles/backend.kotlin-spring-cqrs/enforcement/README.md`

## マーカー

KDoc 形式を使います（`core/docs/ja/conventions/strata-markers.md`）:

```kotlin
/** @strata:port L2-PaymentQueryService */
```
