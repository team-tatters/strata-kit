# バックエンド・ネイティブ Rust Convention

> 正本: strata-kit `profiles/service.rust/docs/ja/backend-rust.md` — strata `docs/05-conventions/backend-rust.md` から移管 (オーダー 2026.10.29-06, 2026-10-29)。ルール YAML は `core/rules/`。

> 土台: [Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html) (2026-10-22 公開)。この文書は、そのガイドのうち私たちが守ると決めたものと、Strata のレイヤーマーカーを Rust でどう書くかだけを記す。ガイド本文は書き直さない。
> 適用対象: Rust で書くすべてのコード — サービスバックエンド、Tauri のようなネイティブシェル、ツール。

## ツールが決めることはツールに任せる

- フォーマットは `rustfmt` のデフォルト(最大 100 桁)である。リポジトリに `rustfmt.toml` を置かない。`#[rustfmt::skip]` は手作業の整列や生成コードにだけ使う。
- `cargo clippy --no-deps` の警告 0 が CI ゲートである。警告を `#[allow]` で覆うときは、その行に理由を書く。
- 不安定(nightly)機能は使わない。

## 名前

- 標準ライブラリの慣例に従う。`as_`・`to_`・`into_` の接頭辞は `self` の所有の仕方に合わせる。getter は `foo()`, `foo_mut()`, `set_foo()`, `take_foo()`、コンストラクタは `new()`・`new_with_foo()`、失敗しうるなら `try_new()`。
- 拡張トレイトには `Ext` 接尾辞を付ける。ジェネリクスは短く(`T`, `K`)、ライフタイムは意味が見えるようにする。
- 外部の人が知らない略語や、文字を抜いた省略形は使わない。

## モジュール・ファイル・import

- 1 ファイルに主要項目 1 つ、ファイル名はその項目(`Foo` → `foo.rs`)。葉でないモジュールには `mod` 宣言と再公開だけを置く。
- `use` の 1 行は 1 つのモジュールから取り込む。`{}` の中に `::` を入れない。グロブ(`*`)は `use super::*`(インラインテストモジュール)と列挙型メソッド内の `use Enum::*` 以外では使わない。
- 型は短い名前で取り込んで使い(`Regex`)、トップレベル関数はモジュールで修飾して呼ぶ(`mem::transmute`)。`io::Error` のように衝突する名前だけ修飾する。

## エラー・パニック

- 失敗が単純で自明なら `Option`、呼び出し側が事情を知る必要があるなら `Result`、バグ・不変条件の違反なら `panic!`。
- `unwrap()` の代わりに理由を書いた `expect("...")`、それよりもパターンマッチ・`ok_or` で呼び出し側に返す方を先に選ぶ。`is_some()` の後の `unwrap()` は使わない。
- `panic::catch_unwind` は使わない。`assert!` には条件を繰り返さず、なぜ成り立たなければならないかを書く。

## 関数の入力・出力

- 引数は `&str`・`&[T]`・`&T`・`Option<&T>`。`&String`・`&Vec<T>`・`&Box<T>`・`&Option<T>` は受け取らない。
- 意味が見えない `bool` 引数は列挙型に変える。残す必要があるなら呼び出し側に `/* what */` コメントを付ける。
- ライブラリはイテレータを返し `impl IntoIterator` を受け取る。アプリケーションコードは `Vec`・スライスで単純にしてもよい。`impl Into<T>` はアプリケーションコードではほとんど使わない。
- 公開オプション構造体は `Default` を実装する。無視するとエラーになる戻り値とその型には `#[must_use]`。

## 型・トレイト・所有

- 意味が異なる値はエイリアスではなく newtype。タプルより名前付きフィールド。
- チーム外で使う公開列挙型・公開フィールド構造体は `#[non_exhaustive]`。`len()` を置くなら `is_empty()` も置く。`FromStr`・`From`・`Display` のような標準トレイトを自作メソッドより先に実装し、可能なら `#[derive]`。
- トレイトはジェネリクス・`dyn`・拡張トレイトが必要なときだけ作る。コードをまとめるために作らない。
- `Rc`/`Arc` や `.clone()` より先に所有と借用を使う。毒された(poisoned)ミューテックスの中を読まない。

## unsafe

- 安全な実装がないときだけ使い、安全な抽象の中に閉じ込めて業務コードから切り離す。すべての `unsafe` ブロックに `// SAFETY:` でなぜ正しいかを書き、性能が理由なら数値を書く。

## コメント・ドキュメント

- 項目には `///`、モジュール・クレートにはファイル先頭の `//!`、実装の説明には `//`。公開 API はドキュメント化し、例をクレートのどこかに置く。
- 名前を繰り返すコメントは書かない。言語の基礎を説明しない。

## Strata マーカー

Rust ではドキュメントコメントに書く。形式は Swift と同じ(`core/rules/naming-convention.yaml` `markers.language_format.rust`)。

```rust
/// @strata:port L2-InventoryQueryService
pub struct InventoryQueryService { /* … */ }

/// @strata:layer Contract
pub struct OrderDto { /* … */ }
```

## 検査

- CI: `cargo fmt --check`, `cargo clippy --no-deps -- -D warnings`, `cargo test`。
- レビューで見るもの: `unwrap()`、`&String`/`&Vec` 引数、名前のない `bool` 引数、`SAFETY:` のない `unsafe`、`{}` 内の `::`。
