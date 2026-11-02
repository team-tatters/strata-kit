# バックエンド Rust — 概念モデルの投影

> 正本: strata-kit `profiles/service.rust/docs/ja/backend-rust-layers.md` (2026-10-29, DEC-2026-10-29-06)
> 概念モデル: `core/docs/ja/architecture/backend-cqrs.md` · コードスタイル・マーカー: `profiles/service.rust/docs/ja/backend-rust.md` (Google Rust Style Guide が土台, DEC-2026-10-22-01)

## 要約

- Rust の境界の単位は**クレート**である。`Cargo.toml` に依存を宣言しなければ import 自体がコンパイルエラーになるので、レイヤーの方向を**コンパイル時に**遮断できる。そのため Rust の投影は、Cargo ワークスペースのクレート分割が中心になる。
- 基準スタック: `axum`(HTTP)・`tokio`(ランタイム)・`sqlx`(コンパイル時に検証される SQL)・`serde`・`thiserror`(ライブラリのエラー)/`anyhow`(バイナリのエラー)・`tracing`。
- クレート名は Rust 陣営で一般的な語彙(domain・app・infra・api)を使い、それぞれが概念レイヤーのどこに当たるかは下の表が定める。マーカー(`@strata:layer`)は概念レイヤー名を使う。
- トレイトは置き換えが必要な境界(リポジトリポート・外部システム)にだけ置く。コードをまとめるために作らない(backend-rust.md)。

## ワークスペース配置

```
Cargo.toml                [workspace] members = ["crates/*"]
crates/
  kit/          L1      純粋関数・エラーコード・ページ型。依存: なし(serde 程度)
  domain/       L1(ドメイン)・ポート  エンティティ・値オブジェクト・不変条件の検査・純粋な計算、リポジトリトレイト(ポート)。依存: kit
  infra/        LM1・L2 下段  sqlx PgPool・トランザクション、ポートの実装(Repository・クエリ)。依存: kit, domain
  app/          L2 上段・LM2・L3  CommandService・QueryService・Coordinator・CompositeService。依存: kit, domain (infra を知らない)
  api/          Route   axum Router・ハンドラー・抽出器・レスポンス変換、main で infra の実装を app に注入。依存: app, infra, kit
```

| 概念レイヤー | クレート・モジュール | 名前の例 |
|---|---|---|
| L1 | `kit`、`domain::<ドメイン>` の型・自由関数 | `PageRequest`, `fn convert_unit(...)` |
| LM1 | `infra::db` | `PgPool` の設定, `with_tx` |
| L2 下段 | `infra::<ドメイン>` — ポートの実装 | `PgOrderRepository`, `order_queries.rs` |
| L2 上段 | `app::<ドメイン>::{command, query}` | `OrderCommandService`, `OrderQueryService` |
| LM2 | `app::<関心事>::coordinator` | `PaymentCoordinator` |
| L3 | `app::<ドメイン>::usecase` | `OrderCommandCompositeService` |
| Route | `api::<ドメイン>` | `async fn create_order(State(app): State<AppState>, Json(body): Json<CreateOrder>)` |

- 要点は、`app` が `infra` に依存しないことである。`app` は `domain` のポートトレイトだけを見て、実装は `api`(組み立て地点)が注入する。この方向は `Cargo.toml` が強制する。
- クレート内の段の境界は**可視性**で表す: 他のクレートに公開するものだけ `pub`、クレート内だけで使うものは `pub(crate)`、モジュール内のものは非公開。たとえば `app` のエンティティ単位の書き込みヘルパーは `pub(crate)` にして、`api` が直接呼べないようにする。
- 同一段の参照禁止(サービス ↔ サービス、ドメイン usecase 同士)は `app` 内のモジュール境界なので、コンパイラは防げない。レビューと下の強制表で守る。

## ポートとコマンド・クエリ

```rust
// crates/domain/src/order/port.rs — ポート(利用側が所有)
pub trait OrderStore: Send + Sync {
    async fn insert(&self, tx: &mut Tx, new: NewOrder) -> Result<OrderId, StoreError>;
}

// crates/app/src/order/usecase.rs — L3
pub struct OrderCommandCompositeService<S: OrderStore, P: PaymentAuthorizer> {
    cmd: OrderCommandService<S>,
    payments: P,
}
```

- 書き込み: `OrderCommandService` がトランザクションを開く(トランザクション型は `domain` の抽象、または `infra` が渡すハンドル)。トランザクションは L2 上段だけに置く。
- 読み取り: `OrderQueryService` は `sqlx::query_as!` で結合結果を DTO にそのまま入れる。読み取りモデルはドメインエンティティを経由しなくてよい。
- ポートは上の例のように、ネイティブ `async fn`(Rust 1.75+)とジェネリクスで書くのが基本である。ネイティブ `async fn` のトレイトは `dyn` として使えないので、実行時に実装を差し替える必要があって `Arc<dyn Trait>` が要る場合は `async-trait` クレートを使う。

## 強制

| 対象 | ツール |
|---|---|
| レイヤーの方向(`app` → `infra` 禁止など) | 各クレートの `Cargo.toml` の依存宣言 — コンパイル時 |
| クレート外への露出 | `pub(crate)`・非公開モジュール |
| フォーマット・リント | `cargo fmt --check`, `cargo clippy --no-deps -D warnings` |
| テスト | `cargo test`、`sqlx` のオフラインメタデータ(`cargo sqlx prepare`)で CI でもクエリを検証 |

## マーカー

ドキュメントコメントに概念レイヤー名で書く(`backend-rust.md` §Strata マーカー):

```rust
/// @strata:layer L2-QueryService
pub struct OrderQueryService { … }
```
