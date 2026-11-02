# Architecture des couches du frontend Web

> Source canonique : strata-kit `core/docs/fr/architecture/frontend-web.md` — migré depuis strata `docs/03-architecture/frontend-web.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles se trouve dans `core/rules/`.

> Règles lisibles par machine : `core/rules/layer-rules.yaml` → `frontend.variants.web`
> Ce document est le détail lisible par des humains de la variante (variant) de frontend web indépendante du framework.
> La cohérence entre les tokens, les variantes, les compositions et les livrables de design est définie par `core/docs/fr/architecture/frontend-design-contract.md`.

## Principes de frontière

Les consignes frontend de Strata Core ne définissent ni framework d'UI, ni routeur, ni bibliothèque de gestion d'état, ni outil de style particuliers.
Core ne pose que des frontières de responsabilité vérifiables par import, par chemin et par analyse statique.

La relation entre couches est un DAG, et non un arbre linéaire unique.
Le `can_reference` du tableau ci-dessous est la source of truth ; les références à des couches absentes du tableau, ainsi que les références croisées de même niveau entre couches portant `cross_reference: false`, sont interdites (pour Feature Block, cela signifie entre domaines ; voir plus bas).

| Layer | can_reference |
|---|---|
| Foundation | aucune |
| Contract | Foundation |
| DataState | Foundation, Contract |
| Primitive UI | Foundation |
| Semantic Component | Foundation, Contract, Primitive UI |
| Feature Block | Foundation, Contract, DataState, Primitive UI, Semantic Component |
| Route Surface | Foundation, Contract, Feature Block, App Shell |
| App Shell | Foundation, Contract, DataState, Primitive UI, Semantic Component |

## Variants

Le frontend Strata prend en charge trois variants.

| Variant | Usage | État |
|---|---|---|
| `atomic` | La structure existante L1/LM/L2/Atomic/Molecule/Partial/Page/Layout et la compatibilité avec les projets hérités | Maintenu |
| `web` | Frontières d'application web indépendantes du framework | Par défaut |
| `mobile` | UI mobile native (SwiftUI, Compose) — les couches et can_reference sont les mêmes que pour web, mais le vocabulaire, l'assemblage et les règles de cible diffèrent (`core/docs/fr/architecture/frontend-mobile.md`) | 2026-09-11 |

Le choix de chaque projet se place dans `variant` ou `frontend_variant` de `.strata/layer-map.yaml`.
En l'absence de valeur choisie, la valeur par défaut de Core est `web`.

## Foundation

Contient les tokens sémantiques, les fonctions pures, les constantes et les types primitifs.

**Autorisé :** token, const, type, util

**Interdit :** rendu d'UI, appels transport, accès à l'état global, implémentations dépendantes du framework

## Contract

Le contrat stable entre l'UI et transport.
Il contient les DTO, ViewModel, schema, API port/interface et cache key contract.

**Règles :**
- Ne référence que Foundation.
- Ne référence ni les couches d'UI ni DataState.
- N'appelle pas directement les implémentations de transport.
- Les interface/type qui ont tendance à se disperser dans les fichiers de composants sont regroupés dans cette couche.

## DataState

La couche d'adapter pour l'état serveur, les mutation et l'état client.
La bibliothèque concrète est choisie dans la convention ; Core ne définit que la frontière qui empêche l'UI de voir transport directement.

**Règles :**
- Ne référence que Foundation et Contract.
- Ne rend aucun composant d'UI.
- N'expose pas le transport client directement à l'UI.
- Les cache key et les contrats DTO/ViewModel renvoient à Contract.

**Deux tronçons :** transport (`{name}.service` — appels HTTP, renvoie des DTO) et adapter (`use{Entity}Query` · `use{Entity}{Action}Mutation` · `use{Name}State`).
Seul l'adapter peut importer transport. Les couches supérieures ne voient que l'adapter.

## Primitive UI

UI de bas niveau liée aux tokens sémantiques.
Elle ne doit connaître ni le sens du domaine ni l'état serveur.

**Règles :**
- Ne référence que Foundation.
- Ne référence ni les modèles de domaine de Contract, ni DataState, ni transport.
- Fonctionne avec les seuls Props et tokens de Foundation.

## Semantic Component

Un composant d'UI porteur d'un sens utilisateur ou métier.
Plutôt qu'une classification par taille comme Atomic/Molecule, il exprime « ce que fait le composant » par son nom et sa responsabilité.

**Frontière centrale vérifiable :** un Semantic Component n'appelle pas DataState directement.
L'état serveur et les mutation sont injectés par props ou callback.

Le composant détaché comme moitié rendu d'un Feature Block se nomme `{Domain}{Purpose}View`. L'axe d'état des données (loading · empty · error) est reçu par props.
L'apparence est décidée uniquement par une combinaison de valeurs de l'axe variant de Primitive UI et d'alias de Foundation (Composition Legality — `core/docs/fr/architecture/frontend-design-contract.md`).

## Feature Block

La couche qui assemble un fragment d'écran d'un cas d'usage précis, avec ses données et son état.
Les appels à DataState sont autorisés à partir de cette couche.

**Règles :**
- Les références directes entre Feature Block de domaines différents sont interdites. Au sein d'un même domaine, une Section peut contenir une autre Section comme enfant. Quand des écrans de domaines différents doivent apparaître ensemble, le `{RouteName}Page` de la Route Surface place côte à côte la Section de chaque domaine et les relie par des props et des événements.
- Un domaine est un répertoire situé directement sous la racine des features (`feature_root` du layer-map, ou à défaut le préfixe de `Feature_Block.domain_slice` dans layer-rules). Les fichiers Feature Block hors de la racine ne sont pas isolés par domaine. Cette frontière est une frontière de tranches de code et ne garantit pas le sens d'un domaine métier.
- Assemble Semantic Component, Primitive UI, DataState et Contract.
- N'assume aucune responsabilité de routage ni de provider au niveau de l'app.

Le suffixe est `{UseCase}Section` (un fragment d'écran sans route — l'équivalent du Partial de la variant atomic) ; selon la forme, on utilise `Panel` · `Dialog` · `Table`. Les suffixes `Block`, `Container` et `Partial` sont interdits (`core/rules/naming-convention.yaml` → `Feature_Block.forbidden_suffixes`).
La Section est le **propriétaire de l'état de son cas d'usage** (une Section enfant qui est une unité d'enregistrement indépendante possède le sien) : elle déclare les Props, détient directement l'état local, les effets et les hooks d'adapter de DataState, et ne propage que vers le bas. Le rendu est confié à une `View` (Semantic Component) :
`Route Surface → Section → View → Primitive UI`. La propriété de l'état se divise en trois — posséder un brouillon local, observer le cache serveur et être responsable de la commande d'enregistrement. Une Section enfant du même domaine ne possède le brouillon et les mutations que lorsqu'il s'agit de son propre cas d'usage et d'une unité d'enregistrement indépendante ; seul l'état partagé avec le parent arrive en props. Un brouillon modifié par plusieurs Section a un seul propriétaire, et le submit, le cancel ou l'enregistrement atomique entre Section reviennent à un seul coordinateur (la Section parente), les inputs internes étant des View ou des controlled components. L'atomicité vient d'une seule commande ou transaction DataState/API, et non d'une invalidation après plusieurs mutations. Plusieurs Section qui observent la même query key ne constituent pas une propriété en double. Séparer la logique d'état en hooks n'est pas une obligation ; seuls l'appel de service (transport) et le traitement commun utilisé par au moins deux Section sont placés à l'extérieur, comme structure de référence. Le critère de séparation et le nommage des Props se trouvent dans `profiles/frontend.next-web/docs/fr/frontend-react.md`.

## Route Surface

Prend en charge le point d'entrée par URL, les route params, la frontière de permissions et l'assemblage des écrans.

**Règles :**
- Place des Feature Block — en principe une seule Section. S'il y en a deux ou plus, on ajoute un composant d'assemblage `{RouteName}Page`. Ce composant d'assemblage est une Route Surface où qu'il se trouve (routes ou features) — dans le layer-map, placez son mapping avant celui de Feature Block.
- Ne s'exporte pas comme UI réutilisable.
- Les appels directs à transport sont interdits. Les appels aux hooks de DataState le sont aussi — DataState ne figure pas dans `can_reference`.

Les règles de fichiers propres à chaque routeur sont définies dans la convention du framework, et non dans Core.

## App Shell

Prend en charge les provider globaux, la navigation et le layout au niveau de l'app.

**Règles :**
- Ne référence pas directement les Feature Block.
- Ne contient aucune logique de cas d'usage du domaine.
- Ne traite que les provider globaux et le layout au niveau du shell.
- Un paquet de shell partagé par plusieurs apps (zones) est aussi un App Shell. Le passage d'une app à une autre se fait uniquement par URL.

## Séparation Core / Convention / Profile

| Nature | Emplacement | Exemple |
|---|---|---|
| Frontière d'architecture vérifiable | Core `core/docs/fr/architecture/frontend-web.md`, `core/rules/layer-rules.yaml` | Interdiction de référencer DataState depuis un Semantic Component |
| Contrat de design (tokens · variantes · composition · cohérence) | Core `core/docs/fr/architecture/frontend-design-contract.md` | Le composant référence des alias (les tokens de composant uniquement depuis leur propriétaire), design_ref et état d'alignement |
| Liaison avec un framework/une bibliothèque | `profiles/<id>/docs/fr/` | query hook, router, outil de style, mappage des fichiers de tokens |
| Politique héritée/de transition du projet | `.strata/` du projet | legacy/bridge/target zone |

Strata Core ne définit pas « quelle bibliothèque est utilisée », mais « quelle responsabilité doit traverser quelle couche ».
