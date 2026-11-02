# 백엔드·네이티브 Rust Convention

> 정본: strata-kit `profiles/service.rust/docs/ko/backend-rust.md` — strata `docs/05-conventions/backend-rust.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> 바탕: [Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html) (2026-10-22 공개). 이 문서는 그 가이드 가운데 우리가 지키기로 한 것과 Strata 레이어 마커를 Rust 에 어떻게 적는지만 적는다. 가이드 본문을 다시 쓰지 않는다.
> 적용 대상: Rust 로 쓰는 모든 코드 — 서비스 백엔드, Tauri 같은 네이티브 셸, 도구.

## 도구가 결정하는 것은 도구에 맡긴다

- 포맷은 `rustfmt` 기본값(최대 100칸)이다. 저장소에 `rustfmt.toml` 을 두지 않는다. `#[rustfmt::skip]` 은 수동 정렬이나 생성 코드에만 쓴다.
- `cargo clippy --no-deps` 경고 0 이 CI 게이트다. 경고를 `#[allow]` 로 덮을 때는 그 줄에 이유를 적는다.
- 불안정(nightly) 기능은 쓰지 않는다.

## 이름

- 표준 라이브러리의 관례를 따른다. `as_`·`to_`·`into_` 접두는 `self` 소유 방식과 맞춘다. getter 는 `foo()`, `foo_mut()`, `set_foo()`, `take_foo()`; 생성자는 `new()`·`new_with_foo()`, 실패할 수 있으면 `try_new()`.
- 확장 트레이트는 `Ext` 접미. 제네릭은 짧게(`T`, `K`), 수명은 뜻이 보이게.
- 바깥 사람이 모를 약어와 글자를 뺀 축약은 쓰지 않는다.

## 모듈·파일·import

- 파일 하나에 주 항목 하나, 파일 이름은 그 항목(`Foo` → `foo.rs`). 잎이 아닌 모듈은 `mod` 선언과 재노출만 둔다.
- `use` 한 줄은 모듈 하나에서 가져온다. `{}` 안에 `::` 를 넣지 않는다. 글롭(`*`)은 `use super::*`(인라인 테스트 모듈)와 열거형 메서드 안의 `use Enum::*` 외에는 쓰지 않는다.
- 타입은 짧은 이름으로 가져와 쓰고(`Regex`), 최상위 함수는 모듈로 한정해 부른다(`mem::transmute`). `io::Error` 처럼 겹치는 이름만 한정한다.

## 오류·패닉

- 실패가 단순하고 뻔하면 `Option`, 호출자가 사정을 알아야 하면 `Result`, 버그·불변식 위반이면 `panic!`.
- `unwrap()` 대신 이유를 적은 `expect("...")`, 그보다 패턴 매칭·`ok_or` 로 호출자에게 돌려주는 쪽을 먼저 고른다. `is_some()` 뒤의 `unwrap()` 은 쓰지 않는다.
- `panic::catch_unwind` 는 쓰지 않는다. `assert!` 에는 조건을 되풀이하지 말고 왜 성립해야 하는지를 적는다.

## 함수의 입력·출력

- 매개변수는 `&str`·`&[T]`·`&T`·`Option<&T>`. `&String`·`&Vec<T>`·`&Box<T>`·`&Option<T>` 는 받지 않는다.
- 뜻이 안 보이는 `bool` 매개변수는 열거형으로 바꾼다. 남겨야 하면 호출부에 `/* what */` 주석.
- 라이브러리는 이터레이터를 돌려주고 `impl IntoIterator` 를 받는다. 응용 코드는 `Vec`·슬라이스로 단순하게 해도 된다. `impl Into<T>` 는 응용 코드에서 거의 쓰지 않는다.
- 공개 옵션 구조체는 `Default` 를 구현한다. 무시하면 오류인 반환값과 그 타입에는 `#[must_use]`.

## 타입·트레이트·소유

- 뜻이 다른 값은 별칭이 아니라 newtype. 튜플보다 이름 있는 필드.
- 팀 밖에서 쓰는 공개 열거형·공개 필드 구조체는 `#[non_exhaustive]`. `len()` 을 두면 `is_empty()` 도 둔다. `FromStr`·`From`·`Display` 같은 표준 트레이트를 직접 만든 메서드보다 먼저 구현하고, 가능하면 `#[derive]`.
- 트레이트는 제네릭·`dyn`·확장 트레이트가 필요할 때만 만든다. 코드를 묶으려고 만들지 않는다.
- `Rc`/`Arc` 와 `.clone()` 보다 소유와 빌림을 먼저 쓴다. 중독된 뮤텍스 안을 읽지 않는다.

## unsafe

- 안전한 구현이 없을 때만 쓰고, 안전한 추상 안에 가둬 업무 코드와 떼어 둔다. 모든 `unsafe` 블록에 `// SAFETY:` 로 왜 맞는지 적고, 성능이 이유면 수치를 적는다.

## 주석·문서

- 항목은 `///`, 모듈·크레이트는 파일 머리의 `//!`, 구현 설명은 `//`. 공개 API 는 문서화하고 예시를 크레이트 어딘가에 둔다.
- 이름을 되풀이하는 주석은 쓰지 않는다. 언어 기초를 설명하지 않는다.

## Strata 마커

Rust 에서는 문서 주석에 적는다. 형식은 Swift 와 같다 (`core/rules/naming-convention.yaml` `markers.language_format.rust`).

```rust
/// @strata:port L2-InventoryQueryService
pub struct InventoryQueryService { /* … */ }

/// @strata:layer Contract
pub struct OrderDto { /* … */ }
```

## 검사

- CI: `cargo fmt --check`, `cargo clippy --no-deps -- -D warnings`, `cargo test`.
- 리뷰에서 보는 것: `unwrap()`, `&String`/`&Vec` 매개변수, 이름 없는 `bool` 인자, `SAFETY:` 없는 `unsafe`, `{}` 안의 `::`.
