# Backend and Native Rust Convention

> Canonical: strata-kit `profiles/service.rust/docs/en/backend-rust.md` — migrated from strata `docs/05-conventions/backend-rust.md` (order 2026.10.29-06, 2026-10-29). The rule YAML is in `core/rules/`.

> Basis: [Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html) (published 2026-10-22). This document records only which parts of that guide we have chosen to follow and how to write Strata layer markers in Rust. It does not rewrite the guide.
> Applies to: all code written in Rust — service backends, native shells such as Tauri, tools.

## Leave to tools what tools decide

- Formatting is the `rustfmt` default (100 columns max). Do not put a `rustfmt.toml` in the repository. Use `#[rustfmt::skip]` only for manual alignment or generated code.
- Zero `cargo clippy --no-deps` warnings is the CI gate. When you cover a warning with `#[allow]`, write the reason on that line.
- Do not use unstable (nightly) features.

## Names

- Follow the standard library's conventions. The `as_`, `to_`, `into_` prefixes match how `self` is owned. Getters are `foo()`, `foo_mut()`, `set_foo()`, `take_foo()`; constructors are `new()` and `new_with_foo()`, and `try_new()` if they can fail.
- Extension traits take the `Ext` suffix. Keep generics short (`T`, `K`) and make lifetimes meaningful.
- Do not use abbreviations that outsiders will not know, or shortenings that drop letters.

## Modules, Files, Imports

- One main item per file, and the file is named after that item (`Foo` → `foo.rs`). A non-leaf module holds only `mod` declarations and re-exports.
- One `use` line imports from one module. Do not put `::` inside `{}`. Do not use globs (`*`) except `use super::*` (inline test modules) and `use Enum::*` inside enum methods.
- Import types by their short name and use them that way (`Regex`); call top-level functions qualified by their module (`mem::transmute`). Qualify only names that collide, such as `io::Error`.

## Errors and Panics

- Use `Option` when the failure is simple and obvious, `Result` when the caller needs to know the circumstances, and `panic!` for bugs and invariant violations.
- Prefer `expect("...")` with a reason over `unwrap()`, and before that prefer returning to the caller through pattern matching or `ok_or`. Do not use `unwrap()` after `is_some()`.
- Do not use `panic::catch_unwind`. In `assert!`, do not repeat the condition; write why it must hold.

## Function Inputs and Outputs

- Parameters are `&str`, `&[T]`, `&T`, `Option<&T>`. Do not accept `&String`, `&Vec<T>`, `&Box<T>`, `&Option<T>`.
- Replace a `bool` parameter whose meaning is unclear with an enum. If it must stay, add a `/* what */` comment at the call site.
- Libraries return iterators and accept `impl IntoIterator`. Application code may keep it simple with `Vec` and slices. `impl Into<T>` is almost never used in application code.
- Public option structs implement `Default`. Put `#[must_use]` on return values that are errors if ignored, and on their types.

## Types, Traits, Ownership

- Values with different meanings get a newtype, not an alias. Prefer named fields over tuples.
- Public enums and public-field structs used outside the team get `#[non_exhaustive]`. If you provide `len()`, also provide `is_empty()`. Implement standard traits such as `FromStr`, `From`, `Display` before hand-made methods, and use `#[derive]` when possible.
- Create a trait only when you need generics, `dyn`, or an extension trait. Do not create one just to group code.
- Use ownership and borrowing before `Rc`/`Arc` and `.clone()`. Do not read inside a poisoned mutex.

## unsafe

- Use it only when no safe implementation exists, and confine it inside a safe abstraction, apart from business code. Put a `// SAFETY:` comment on every `unsafe` block explaining why it is correct, and give numbers if performance is the reason.

## Comments and Documentation

- Use `///` for items, `//!` at the top of the file for modules and crates, and `//` for implementation notes. Document public APIs and put examples somewhere in the crate.
- Do not write comments that repeat the name. Do not explain language basics.

## Strata Markers

In Rust, write them in doc comments. The format is the same as Swift (`core/rules/naming-convention.yaml` `markers.language_format.rust`).

```rust
/// @strata:port L2-InventoryQueryService
pub struct InventoryQueryService { /* … */ }

/// @strata:layer Contract
pub struct OrderDto { /* … */ }
```

## Checks

- CI: `cargo fmt --check`, `cargo clippy --no-deps -- -D warnings`, `cargo test`.
- What to look for in review: `unwrap()`, `&String`/`&Vec` parameters, unnamed `bool` arguments, `unsafe` without `SAFETY:`, `::` inside `{}`.
