# Convención de backend y Rust nativo

> Canónico: strata-kit `profiles/service.rust/docs/es/backend-rust.md` — migrado desde strata `docs/05-conventions/backend-rust.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Base: [Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html) (publicada el 2026-10-22). Este documento recoge solo qué partes de esa guía hemos decidido seguir y cómo se escriben en Rust los marcadores de capa de Strata. No reescribe el texto de la guía.
> Se aplica a: todo el código escrito en Rust — backends de servicio, shells nativos como Tauri, herramientas.

## Lo que deciden las herramientas se deja a las herramientas

- El formato es el valor por defecto de `rustfmt` (máximo 100 columnas). No pongas un `rustfmt.toml` en el repositorio. Usa `#[rustfmt::skip]` solo para alineación manual o código generado.
- Cero advertencias de `cargo clippy --no-deps` es la puerta (gate) de CI. Cuando tapes una advertencia con `#[allow]`, escribe el motivo en esa misma línea.
- No uses funcionalidades inestables (nightly).

## Nombres

- Sigue las convenciones de la biblioteca estándar. Los prefijos `as_`, `to_`, `into_` se ajustan a cómo se posee `self`. Los getters son `foo()`, `foo_mut()`, `set_foo()`, `take_foo()`; los constructores son `new()` y `new_with_foo()`, y `try_new()` si pueden fallar.
- Los traits de extensión llevan el sufijo `Ext`. Mantén los genéricos cortos (`T`, `K`) y haz que los lifetimes tengan sentido.
- No uses abreviaturas que gente ajena al equipo no conozca, ni acortamientos que omitan letras.

## Módulos, archivos, imports

- Un elemento principal por archivo, y el archivo lleva el nombre de ese elemento (`Foo` → `foo.rs`). Un módulo que no es hoja contiene solo declaraciones `mod` y reexportaciones.
- Una línea `use` importa de un solo módulo. No pongas `::` dentro de `{}`. No uses globs (`*`) salvo `use super::*` (módulos de prueba en línea) y `use Enum::*` dentro de métodos de enum.
- Importa los tipos por su nombre corto y úsalos así (`Regex`); llama a las funciones de nivel superior calificadas con su módulo (`mem::transmute`). Califica solo los nombres que colisionan, como `io::Error`.

## Errores y pánicos

- Usa `Option` cuando el fallo es simple y obvio, `Result` cuando quien llama necesita conocer las circunstancias, y `panic!` para bugs y violaciones de invariantes.
- Prefiere `expect("...")` con un motivo antes que `unwrap()`, y antes que eso prefiere devolver el error a quien llama mediante pattern matching u `ok_or`. No uses `unwrap()` después de `is_some()`.
- No uses `panic::catch_unwind`. En `assert!`, no repitas la condición; escribe por qué debe cumplirse.

## Entradas y salidas de las funciones

- Los parámetros son `&str`, `&[T]`, `&T`, `Option<&T>`. No aceptes `&String`, `&Vec<T>`, `&Box<T>`, `&Option<T>`.
- Sustituye por un enum el parámetro `bool` cuyo significado no sea claro. Si debe quedarse, añade un comentario `/* what */` en el sitio de la llamada.
- Las bibliotecas devuelven iteradores y aceptan `impl IntoIterator`. El código de aplicación puede mantenerlo simple con `Vec` y slices. `impl Into<T>` casi no se usa en código de aplicación.
- Las structs de opciones públicas implementan `Default`. Pon `#[must_use]` en los valores de retorno que son un error si se ignoran, y en sus tipos.

## Tipos, traits, propiedad

- Los valores con significado distinto usan un newtype, no un alias. Prefiere campos con nombre antes que tuplas.
- Los enums públicos y las structs con campos públicos que se usan fuera del equipo llevan `#[non_exhaustive]`. Si ofreces `len()`, ofrece también `is_empty()`. Implementa traits estándar como `FromStr`, `From`, `Display` antes que métodos hechos a mano, y usa `#[derive]` cuando sea posible.
- Crea un trait solo cuando necesites genéricos, `dyn` o un trait de extensión. No lo crees solo para agrupar código.
- Usa propiedad y préstamo antes que `Rc`/`Arc` y `.clone()`. No leas dentro de un mutex envenenado (poisoned).

## unsafe

- Úsalo solo cuando no exista una implementación segura, y confínalo dentro de una abstracción segura, separado del código de negocio. Pon en cada bloque `unsafe` un comentario `// SAFETY:` que explique por qué es correcto, y da cifras si el motivo es el rendimiento.

## Comentarios y documentación

- Usa `///` para elementos, `//!` al inicio del archivo para módulos y crates, y `//` para notas de implementación. Documenta las API públicas y pon ejemplos en algún lugar del crate.
- No escribas comentarios que repitan el nombre. No expliques los fundamentos del lenguaje.

## Marcadores de Strata

En Rust se escriben en los comentarios de documentación. El formato es el mismo que en Swift (`core/rules/naming-convention.yaml` `markers.language_format.rust`).

```rust
/// @strata:port L2-InventoryQueryService
pub struct InventoryQueryService { /* … */ }

/// @strata:layer Contract
pub struct OrderDto { /* … */ }
```

## Comprobaciones

- CI: `cargo fmt --check`, `cargo clippy --no-deps -- -D warnings`, `cargo test`.
- Qué mirar en la revisión: `unwrap()`, parámetros `&String`/`&Vec`, argumentos `bool` sin nombre, `unsafe` sin `SAFETY:`, `::` dentro de `{}`.
