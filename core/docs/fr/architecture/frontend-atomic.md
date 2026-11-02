# Architecture en couches de la variante Atomic du frontend

> Canonique : strata-kit `core/docs/fr/architecture/frontend-atomic.md` — migré depuis strata `docs/03-architecture/frontend-atomic.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles se trouve dans `core/rules/`.

> Règles lisibles par machine : `core/rules/layer-rules.yaml` → `frontend.variants.atomic`
> La variante par défaut des nouveaux projets web est `frontend.variants.web` ; voir `core/docs/fr/architecture/frontend-web.md` pour le détail.
> **Statut : maintenue (compatibilité héritée)** — son adoption pour du nouveau travail n'est pas recommandée. La classification par taille en Molecule/Organism a été remplacée par la Composition Legality de la variante web (`core/docs/fr/architecture/frontend-design-contract.md`).

## Correspondance avec la variante web

| Atomic | Variante web | Critère |
|---|---|---|
| Atom | Primitive UI | Indifférent au domaine, uniquement des tokens alias + des axes de variante |
| Molecule | Semantic Component **ou** Feature Block | Feature Block s'il appelle DataState, sinon Semantic Component. **Ne se juge pas par la taille** |
| Organism | (supprimé) | Absorbé dans Feature Block |
| Partial | Feature Block (`{UseCase}Section`) | Un fragment d'écran sans route |
| Page · Layout | Route Surface · App Shell | Inchangé |
| L2 Hook | DataState adapter | `useQuery{Name}` → `use{Entity}Query` |
| LM | Contract + DataState transport | ViewModel et DTO vont dans Contract, l'API Client va dans `{name}.service` |

## Structure des couches

```
Page / Layout
    ↓
Partial (ensemble d'UI commune au niveau de la page)
    ↓
Molecule (composant spécifique à un comportement)
    ↓
Atomic (composant d'UI pur)
    ↓
L2 (Hook de gestion d'état)
    ↓
LM (ViewModel, DTO, API Client)
    ↓
L1 (fonctions pures, types, constantes)
```

## L1 — couche de fonctions pures

Même principe que le L1 du backend. Logique pure, indépendante de tout framework d'UI.
Les Hooks de gestion d'état purs sont autorisés, mais les appels d'API sont interdits.

**Exemples :** useDebounce, useLocalStorage, formatDate, validateEmail

## LM — couche de modèle de données

La couche intermédiaire qui gère la communication avec le serveur.

**Composition :** ViewModel (structure de données réservée à l'affichage), DTO (mapping des requêtes/réponses du serveur), 
API Port/Client Interface (la frontière de l'appel de transport), Interface (définition du contrat)

**Règles :** Aucune logique de rendu d'UI. Elle ne gère que la transformation des données et la communication.

## L2 — couche de gestion d'état

Hooks adapter pour l'état serveur/client.

**Règles :** Utiliser l'API Client de LM pour synchroniser l'état serveur.
Ne pas rendre directement de composants d'UI. N'exporter que des Hooks.

## Atomic — UI de plus petite unité

Un composant d'UI pur dont toutes les dépendances de L2 et des couches inférieures ont été retirées.
Il fonctionne avec les seules props, et l'accès à l'état global est interdit.

**Exemples :** Button, Input, Badge, Avatar, Tooltip, Card

## Molecule — UI spécifique à un comportement

Un composant qui combine des Atomics et lie un Hook de L2.
Il est spécialisé dans un comportement de domaine particulier.

**Exemples :** SearchBar (Input + Button + useSearchStore),
OrderCard (Card + Badge + useOrderQuery)

## Partial — ensemble commun au niveau de la page

Un bloc d'UI partagé entre plusieurs pages.
Une combinaison de Molecules et d'Atomics.

**Exemples :** OrderListPartial, UserProfilePartial, NotificationPanel

## Page — cible de route

Le composant de niveau supérieur associé à une URL réelle.
Il combine Layout, Partial, Molecule et Atomic pour former un écran complet.

## Layout — enveloppe structurelle

Définit la structure de la page : navigation, barre latérale, pied de page, etc.
Reçoit le composant Page en tant que children.
