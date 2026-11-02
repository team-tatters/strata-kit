# 后端与原生 Rust Convention

> 正本: strata-kit `profiles/service.rust/docs/zh/backend-rust.md` — 从 strata `docs/05-conventions/backend-rust.md` 迁移而来 (订单 2026.10.29-06, 2026-10-29)。规则 YAML 在 `core/rules/`。

> 依据: [Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html) (2026-10-22 发布)。本文档只记录该指南中我们决定遵守的部分,以及 Strata 层标记在 Rust 中如何书写。不重写指南正文。
> 适用对象: 所有用 Rust 编写的代码 — 服务后端、Tauri 之类的原生外壳、工具。

## 工具能决定的交给工具

- 格式采用 `rustfmt` 默认值(最大 100 列)。仓库中不放 `rustfmt.toml`。`#[rustfmt::skip]` 只用于手工对齐或生成的代码。
- `cargo clippy --no-deps` 警告为 0 是 CI 门禁。用 `#[allow]` 压制警告时,要在该行写明理由。
- 不使用不稳定(nightly)特性。

## 命名

- 遵循标准库的惯例。`as_`、`to_`、`into_` 前缀要与 `self` 的所有权方式一致。getter 为 `foo()`、`foo_mut()`、`set_foo()`、`take_foo()`; 构造函数为 `new()`、`new_with_foo()`,可能失败时为 `try_new()`。
- 扩展 trait 使用 `Ext` 后缀。泛型保持简短(`T`, `K`),生命周期要让含义可见。
- 不使用外部人员不认识的缩写,也不使用省略字母的缩写。

## 模块、文件、import

- 一个文件一个主要条目,文件名取该条目名(`Foo` → `foo.rs`)。非叶子模块只放 `mod` 声明和重新导出。
- 一行 `use` 只从一个模块导入。不要在 `{}` 中放 `::`。除 `use super::*`(内联测试模块)和枚举方法内的 `use Enum::*` 之外,不使用通配符(`*`)。
- 类型以短名导入并使用(`Regex`),顶层函数用模块限定后调用(`mem::transmute`)。只对重名的名称加限定,如 `io::Error`。

## 错误与 panic

- 失败简单且显而易见时用 `Option`,调用方需要了解情况时用 `Result`,bug 或违反不变式时用 `panic!`。
- 用写明理由的 `expect("...")` 代替 `unwrap()`,更优先的是通过模式匹配、`ok_or` 把错误返回给调用方。不要在 `is_some()` 之后使用 `unwrap()`。
- 不使用 `panic::catch_unwind`。`assert!` 中不要重复条件本身,而要写明它为何必须成立。

## 函数的输入与输出

- 参数使用 `&str`、`&[T]`、`&T`、`Option<&T>`。不接收 `&String`、`&Vec<T>`、`&Box<T>`、`&Option<T>`。
- 含义不明的 `bool` 参数改为枚举。必须保留时,在调用处加 `/* what */` 注释。
- 库返回迭代器并接收 `impl IntoIterator`。应用代码可以用 `Vec`、切片保持简单。`impl Into<T>` 在应用代码中几乎不用。
- 公开的选项结构体实现 `Default`。对被忽略即为错误的返回值及其类型加 `#[must_use]`。

## 类型、trait、所有权

- 含义不同的值使用 newtype,而不是别名。比起元组,优先用具名字段。
- 团队之外使用的公开枚举、公开字段结构体加 `#[non_exhaustive]`。提供 `len()` 时也要提供 `is_empty()`。`FromStr`、`From`、`Display` 这类标准 trait 要先于自制方法实现,可能的话使用 `#[derive]`。
- 只有在需要泛型、`dyn`、扩展 trait 时才创建 trait。不要为了归拢代码而创建。
- 先用所有权和借用,再考虑 `Rc`/`Arc` 与 `.clone()`。不读取已中毒(poisoned)的互斥锁内部。

## unsafe

- 只在没有安全实现时使用,并把它封闭在安全抽象之内,与业务代码分开。每个 `unsafe` 块都用 `// SAFETY:` 写明为何正确,若理由是性能则写出数值。

## 注释与文档

- 条目用 `///`,模块和 crate 用文件头部的 `//!`,实现说明用 `//`。公开 API 要写文档,并在 crate 的某处放上示例。
- 不写重复名称的注释。不解释语言基础知识。

## Strata 标记

在 Rust 中写在文档注释里。格式与 Swift 相同(`core/rules/naming-convention.yaml` `markers.language_format.rust`)。

```rust
/// @strata:port L2-InventoryQueryService
pub struct InventoryQueryService { /* … */ }

/// @strata:layer Contract
pub struct OrderDto { /* … */ }
```

## 检查

- CI: `cargo fmt --check`, `cargo clippy --no-deps -- -D warnings`, `cargo test`。
- 评审中要看的: `unwrap()`、`&String`/`&Vec` 参数、没有名称的 `bool` 实参、没有 `SAFETY:` 的 `unsafe`、`{}` 中的 `::`。
