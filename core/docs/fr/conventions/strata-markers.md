# Marqueurs Strata

> Source canonique : strata-kit `core/docs/fr/conventions/strata-markers.md` — migré depuis strata `docs/05-conventions/strata-markers.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles se trouve dans `core/rules/`.

> Définition lisible par machine : `core/rules/naming-convention.yaml` → section `markers`

Ce sont des annotations à base de commentaires, insérées dans le code source, qui déclarent à quelle couche, quel port ou quel domaine appartient un fichier.

> **État d'application (à 2026-07)** : les marqueurs sont actuellement **réservés à grep et à la lecture humaine**. Les scripts de hook
> (`check-layer-violation.py`, `validate-naming.py`) n'analysent pas encore les marqueurs,
> et l'exclusion de la validation pour `@strata:generated` n'est pas non plus implémentée (la couche est identifiée à partir de layer-map et des répertoires).
> L'implémentation ou non d'un parseur de marqueurs sera décidée selon la stratégie de délégation
> d'application de `methodology-backlog.yaml` MB-strata-2026-003 — l'application canonique sur la JVM est assurée par ArchUnit (`profiles/backend.kotlin-spring-cqrs/enforcement/`).

## Syntaxe

```
@strata:{tag} {value}
```

Go l'utilise sans `@` (convention godoc) :

```
strata:{tag} {value}
```

## Balises prises en charge

| Balise | Usage | Motif | Exemple |
|---|---|---|---|
| `port` | Déclare un port de couche (interface de service) | `{Layer}-{ServiceName}` | `@strata:port L2-InventoryQueryService` |
| `layer` | Déclare la couche à laquelle appartient le fichier | `{Layer}` | `@strata:layer L2` |
| `domain` | Déclare le domaine métier auquel appartient le fichier | `{domain}` | `@strata:domain inventory` |
| `generated` | Fichier généré automatiquement (exclu de la validation des couches) | (sans valeur) | `@strata:generated` |
| `adapter` | Déclare un adaptateur de bibliothèque externe | `{library}` | `@strata:adapter sqlc` |
| `depends` | Déclare explicitement un port dont on dépend | `{Layer}-{ServiceName}` | `@strata:depends L2-OrderQueryService` |
| `token-exception` | Autorisation temporaire d'une valeur de token brute en dehors de Foundation. **La date d'expiration est obligatoire** — une fois dépassée, la vérification de diff échoue (`core/docs/fr/architecture/frontend-design-contract.md` §politique d'exception) | `{reason} until {YYYY-MM-DD}` | `@strata:token-exception couleur provisoire en attendant la validation du design until 2026-10-31` |

## Format par langage

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

Go utilise la forme `strata:` sans le préfixe `@`.

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

### Swift (commentaires de documentation)

```swift
/// Règles de traduction de l'état du jour — fonctions pures uniquement.
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

## Motifs de recherche

```bash
# Rechercher tous les ports d'une couche donnée
grep -r "@strata:port L2" --include="*.kt" --include="*.ts"
grep -r "strata:port L2" --include="*.go"

# Rechercher tous les fichiers d'un domaine donné
grep -r "strata:domain inventory" --include="*.kt" --include="*.go" --include="*.ts"

# Rechercher les fichiers générés
grep -r "strata:generated" --include="*.kt" --include="*.go" --include="*.ts"
```

## Migration depuis les marqueurs PAL

Les marqueurs PAL (Port-Adapter Layered) étaient une convention au niveau projet antérieure à strata.
Les numéros de couche de PAL ne correspondent pas aux numéros officiels de strata ; la migration exige donc une conversion des numéros.

| Marqueur PAL | Marqueur strata | Conversion du numéro |
|---|---|---|
| `@pal-port L1-SomeService` | `@strata:port L2-SomeService` | PAL L1 → strata L2 |
| `@pal-layer l1` | `@strata:layer L2` | PAL L1 → strata L2 |
| `@pal-layer l2` | `@strata:layer L3` | PAL L2 → strata L3+Route |
| `@pal-domain inventories` | `@strata:domain inventories` | (identique) |
| `@pal-generated` | `@strata:generated` | (identique) |
| `@pal-adapter jooq` | `@strata:adapter jooq` | (identique) |
| `@pal-depends L1-Other` | `@strata:depends L2-Other` | PAL L1 → strata L2 |

### Procédure de migration

1. Ajouter la spécification des marqueurs au noyau de strata (ce document)
2. Dans le projet cible, remplacer PAL par strata en masse (`sed` ou l'IDE)
3. Appliquer la correspondance des numéros de couche (PAL L1 → strata L2, etc.)
4. Remplacer le `PAL-MARKERS.md` existant par une référence à ce document
