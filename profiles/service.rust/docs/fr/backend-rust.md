# Convention backend et Rust natif

> Référence : strata-kit `profiles/service.rust/docs/fr/backend-rust.md` — migré depuis strata `docs/05-conventions/backend-rust.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles est dans `core/rules/`.

> Base : [Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html) (publié le 2026-10-22). Ce document consigne seulement les parties de ce guide que nous avons choisi de suivre et la manière d'écrire en Rust les marqueurs de couche de Strata. Il ne réécrit pas le texte du guide.
> S'applique à : tout le code écrit en Rust — backends de service, shells natifs comme Tauri, outils.

## Ce que les outils décident, on le laisse aux outils

- Le format est la valeur par défaut de `rustfmt` (100 colonnes au maximum). Ne mettez pas de `rustfmt.toml` dans le dépôt. N'utilisez `#[rustfmt::skip]` que pour un alignement manuel ou du code généré.
- Zéro avertissement de `cargo clippy --no-deps` est la porte (gate) de la CI. Quand vous masquez un avertissement avec `#[allow]`, écrivez la raison sur cette ligne.
- N'utilisez pas de fonctionnalités instables (nightly).

## Noms

- Suivez les conventions de la bibliothèque standard. Les préfixes `as_`, `to_`, `into_` correspondent à la manière dont `self` est possédé. Les getters sont `foo()`, `foo_mut()`, `set_foo()`, `take_foo()` ; les constructeurs sont `new()` et `new_with_foo()`, et `try_new()` s'ils peuvent échouer.
- Les traits d'extension prennent le suffixe `Ext`. Gardez les génériques courts (`T`, `K`) et donnez un sens visible aux lifetimes.
- N'utilisez pas d'abréviations que des personnes extérieures ne connaissent pas, ni de raccourcis qui suppriment des lettres.

## Modules, fichiers, imports

- Un élément principal par fichier, et le fichier porte le nom de cet élément (`Foo` → `foo.rs`). Un module qui n'est pas une feuille ne contient que des déclarations `mod` et des réexportations.
- Une ligne `use` importe depuis un seul module. Ne mettez pas de `::` dans `{}`. N'utilisez pas de globs (`*`), sauf `use super::*` (modules de test en ligne) et `use Enum::*` dans les méthodes d'enum.
- Importez les types par leur nom court et utilisez-les ainsi (`Regex`) ; appelez les fonctions de niveau supérieur qualifiées par leur module (`mem::transmute`). Ne qualifiez que les noms qui entrent en collision, comme `io::Error`.

## Erreurs et paniques

- Utilisez `Option` quand l'échec est simple et évident, `Result` quand l'appelant doit connaître les circonstances, et `panic!` pour les bugs et les violations d'invariants.
- Préférez `expect("...")` avec une raison à `unwrap()`, et avant cela préférez renvoyer l'erreur à l'appelant par filtrage de motifs ou `ok_or`. N'utilisez pas `unwrap()` après `is_some()`.
- N'utilisez pas `panic::catch_unwind`. Dans `assert!`, ne répétez pas la condition ; écrivez pourquoi elle doit être vraie.

## Entrées et sorties des fonctions

- Les paramètres sont `&str`, `&[T]`, `&T`, `Option<&T>`. N'acceptez pas `&String`, `&Vec<T>`, `&Box<T>`, `&Option<T>`.
- Remplacez par un enum un paramètre `bool` dont le sens n'est pas clair. S'il doit rester, ajoutez un commentaire `/* what */` à l'endroit de l'appel.
- Les bibliothèques renvoient des itérateurs et acceptent `impl IntoIterator`. Le code applicatif peut rester simple avec `Vec` et des slices. `impl Into<T>` n'est presque jamais utilisé dans le code applicatif.
- Les structs d'options publiques implémentent `Default`. Mettez `#[must_use]` sur les valeurs de retour qui sont une erreur si on les ignore, et sur leurs types.

## Types, traits, possession

- Les valeurs de sens différent reçoivent un newtype, pas un alias. Préférez des champs nommés aux tuples.
- Les enums publics et les structs à champs publics utilisés hors de l'équipe reçoivent `#[non_exhaustive]`. Si vous fournissez `len()`, fournissez aussi `is_empty()`. Implémentez les traits standard comme `FromStr`, `From`, `Display` avant des méthodes faites à la main, et utilisez `#[derive]` quand c'est possible.
- Ne créez un trait que lorsque vous avez besoin de génériques, de `dyn` ou d'un trait d'extension. Ne le créez pas simplement pour regrouper du code.
- Utilisez la possession et l'emprunt avant `Rc`/`Arc` et `.clone()`. Ne lisez pas à l'intérieur d'un mutex empoisonné (poisoned).

## unsafe

- À n'utiliser que lorsqu'il n'existe aucune implémentation sûre, en le confinant dans une abstraction sûre, à l'écart du code métier. Mettez sur chaque bloc `unsafe` un commentaire `// SAFETY:` expliquant pourquoi il est correct, et donnez des chiffres si la raison est la performance.

## Commentaires et documentation

- Utilisez `///` pour les éléments, `//!` en tête de fichier pour les modules et les crates, et `//` pour les notes d'implémentation. Documentez les API publiques et mettez des exemples quelque part dans le crate.
- N'écrivez pas de commentaires qui répètent le nom. N'expliquez pas les bases du langage.

## Marqueurs Strata

En Rust, on les écrit dans les commentaires de documentation. Le format est le même qu'en Swift (`core/rules/naming-convention.yaml` `markers.language_format.rust`).

```rust
/// @strata:port L2-InventoryQueryService
pub struct InventoryQueryService { /* … */ }

/// @strata:layer Contract
pub struct OrderDto { /* … */ }
```

## Vérifications

- CI : `cargo fmt --check`, `cargo clippy --no-deps -- -D warnings`, `cargo test`.
- Ce qu'on regarde en revue : `unwrap()`, paramètres `&String`/`&Vec`, arguments `bool` sans nom, `unsafe` sans `SAFETY:`, `::` dans `{}`.
