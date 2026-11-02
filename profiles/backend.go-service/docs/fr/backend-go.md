# Backend Go — Projection du modèle conceptuel

> Référence : strata-kit `profiles/backend.go-service/docs/fr/backend-go.md` (2026-10-29, DEC-2026-10-29-06)
> Modèle conceptuel : `core/docs/fr/architecture/backend-cqrs.md` — le sens des couches, le sens des dépendances et l'interdiction de références au sein d'un même niveau y sont définis. Ce document décide seulement comment Go les exprime.

## Résumé

- L'unité d'encapsulation en Go est le **paquet**. Les couches ne sont donc pas déployées en répertoires (`internal/component/`, `internal/data/` …) : le **paquet de fonctionnalité (domaine) vient d'abord**, et les couches apparaissent à l'intérieur sous forme de **fichiers par rôle**. Ce que la communauté Go évite n'est pas CQRS, mais « un répertoire par couche et une interface par struct ».
- Pile de référence : `net/http` standard (routage par motifs de Go 1.22), `pgx`, `sqlc` (génère des fonctions de requête typées à partir de SQL), `log/slog`. Un framework (gin, echo) est facultatif et la projection reste la même.
- Les interfaces sont définies **du côté de l'utilisateur** et restent petites (« accept interfaces, return structs »). C'est le même principe que la propriété des ports dans l'architecture hexagonale.
- Les frontières sont imposées par le compilateur (pas d'import circulaire), le répertoire `internal/` et `depguard` (golangci-lint).

## Disposition

```
cmd/api/main.go                 Assemblage de Route — démarrage du serveur, câblage des dépendances (DI écrite à la main)
internal/
  platform/                     LM1 — pool db, aides de transaction, configuration (pgxpool, slog)
  kit/                          L1 — fonctions pures, codes d'erreur, types de page (aucun import de framework)
  order/                        un paquet de fonctionnalité = un domaine
    order.go                    L1 (domaine) — types d'entité, objets valeur, calcul pur
    store.go                    L2 niveau inférieur — lecture et persistance enveloppant les Queries générés par sqlc (rôle de Repository/Template)
    command.go                  L2 niveau supérieur — CommandService : création, modification, suppression dans une transaction
    query.go                    L2 niveau supérieur — QueryService : lecture seule, renvoie directement des DTO
    coordinate.go               LM2 — combinaison de L2 pour un même sujet (seulement si nécessaire)
    usecase.go                  L3 — CompositeService : cas d'usage
    http.go                     Route — handler : validation, contexte d'authentification, conversion de la réponse, n'appelle que usecase
    queries.sql / db/           entrée et sortie générée de sqlc
  payment/ …
```

| Couche conceptuelle | En Go | Nom |
|---|---|---|
| L1 | le paquet `internal/kit`, types et fonctions pures d'un paquet de fonctionnalité | `PageRequest`, `func Convert(...)` |
| LM1 | `internal/platform` | `NewPool`, `WithTx` |
| L2 niveau inférieur | `store.go` — enveloppe des `Queries` de sqlc | `type store struct{ q *db.Queries }` (minuscule : caché hors du paquet) |
| L2 niveau supérieur | `command.go` · `query.go` | `type CommandService struct`, `type QueryService struct` |
| LM2 | `coordinate.go` ou un paquet `internal/<sujet>` | `type PaymentCoordinator struct` |
| L3 | `usecase.go` | `type CommandCompositeService struct` (le paquet est le domaine, donc `order.CommandCompositeService`) |
| Route | `http.go`, `cmd/api` | `func (h *Handler) CreateOrder(w, r)` |

- Comme tous les fichiers sont dans le même paquet, le compilateur Go ne peut pas empêcher les références entre fichiers. **L'interdiction de références au sein d'un même niveau est tenue par la revue et les linters** : les types du niveau supérieur de L2 ne se détiennent pas mutuellement comme champs, et `store` ne connaît pas les types de service.
- Le niveau inférieur (`store`) et le code sqlc généré utilisent des **types en minuscule** pour que rien hors du paquet (autres domaines, handlers) ne puisse les utiliser directement. Les seuls éléments que d'autres paquets peuvent utiliser sont les types de service et de cas d'usage.
- Évitez le bégaiement dans les noms : `order.CommandService`, et non `order.OrderService`.

## Dépendances et interfaces

```go
// internal/order/usecase.go — L3
type CommandCompositeService struct {
    cmd      *CommandService
    payments PaymentAuthorizer          // les autres domaines arrivent sous forme d'une petite interface définie par l'utilisateur
}

type PaymentAuthorizer interface {     // port : appartient au consommateur (order)
    Authorize(ctx context.Context, orderID int64, amount Money) error
}

func (s *CommandCompositeService) PlaceOrder(ctx context.Context, in PlaceOrderInput) (OrderID, error) {
    id, err := s.cmd.Create(ctx, in.toNew())
    if err != nil { return 0, err }
    return id, s.payments.Authorize(ctx, int64(id), in.Total)
}
```

- Les paquets de domaine ne s'importent jamais mutuellement (L3 ↔ L3 interdit). Ce dont on a besoin arrive sous forme d'interface côté consommateur, et `cmd/api/main.go` câble l'implémentation.
- Ne créez pas d'avance une interface par struct. Les interfaces n'existent qu'aux frontières qui exigent une substitution (doublures de test, implémentations alternatives).

## Commandes et requêtes

- Écriture : les méthodes de `CommandService` s'exécutent dans `platform.WithTx(ctx, pool, func(q *db.Queries) error {...})`. Les transactions ne vivent que dans le niveau supérieur de L2.
- Lecture : `QueryService` renvoie directement sous forme de DTO les fonctions de requête générées par sqlc (jointures comprises). Il n'a pas à passer par les types de domaine.

## Application des règles

| Quoi | Outil |
|---|---|
| Pas d'import entre paquets de domaine ; `kit` n'importe rien | règles `depguard` de `golangci-lint` (par chemin de paquet) ou `go-arch-lint` |
| Bloquer l'exposition hors du paquet | identifiants en minuscule, `internal/` |
| Dépendances circulaires | le compilateur |
| Formatage et vérifications statiques | `gofmt`, `go vet`, `staticcheck` |
| Tests | `go test ./...` (store contre un vrai PG via testcontainers) |

## Marqueurs

En Go, le marqueur se place dans le commentaire godoc sans le `@` (`core/rules/naming-convention.yaml` markers.language_format.go, `core/docs/fr/conventions/strata-markers.md`) :

```go
// strata:layer L2-QueryService
type QueryService struct{ … }
```
