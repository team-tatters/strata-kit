# Architecture en couches du frontend Mobile

> Canonique : strata-kit `core/docs/fr/architecture/frontend-mobile.md` — migré depuis strata `docs/03-architecture/frontend-mobile.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles se trouve dans `core/rules/`.

> Règles lisibles par machine : `core/rules/layer-rules.yaml` → `frontend.variants.mobile` (DEC-2026-09-11-01)
> Ce document est la description détaillée, lisible par des personnes, de la variante d'UI mobile native (SwiftUI, Jetpack Compose).
> Liaisons : `profiles/frontend.swiftui/docs/fr/frontend-swiftui.md` (vérifiée, o-rot) · il n'existe pas encore de liaison Compose (§Android).
> Les tokens, les variantes, la composition et l'alignement des artefacts de design sont définis par `core/docs/fr/architecture/frontend-design-contract.md`.

## Pourquoi une variante différente de web

Les huit couches et le tableau `can_reference` sont **exactement les mêmes** que pour `web`. Lors de la première adoption de SwiftUI (o-rot, 2026-09-10), les 46 violations
étaient toutes des problèmes de frontière de fichier et aucune n'était un problème de conception ; la sémantique des couches est donc reprise telle quelle. Quatre choses diffèrent.

| Axe | web | mobile |
|---|---|---|
| Vocabulaire | Points d'entrée par URL, `use*Query`, `.service.ts`, le `{Name}ViewModel` du Contract = forme des données | Points d'entrée du graphe de navigation, `Store`/`Repository`, le Contract utilise `UiState`/`UiModel`. **Le nom ViewModel désigne un propriétaire d'état ; on ne l'emploie donc pas dans Contract** |
| Assemblage des Feature | Les références entre Feature Blocks sont interdites | L'assemblage **parent → enfant** au sein d'un même arbre de domaine est autorisé (`composition: parent_child`). Les frères et le sens inverse sont interdits |
| Targets | Zones et paquets | L'app, le widget, la montre et l'intent **placent des fichiers dans plusieurs targets** pour les partager. C'est Core qui décide quelles couches peuvent être partagées |
| Échelle d'application | Analyse statique des chemins d'import | Le compilateur (frontière de module) est canonique ; le vérificateur de références de types est un complément **à l'intérieur** du module |

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

## Couches ↔ constructions mobiles

| Layer | SwiftUI | Compose (non vérifié) |
|---|---|---|
| Foundation | `enum` de tokens, `Shape` pur, utilitaires de fuseau horaire | `object` de tokens, extensions de `MaterialTheme`, utilitaires purs |
| Contract | Structs `Codable`, `{Name}UiState`, `enum` de règles pures + `static func`, parseur de deep links | `data class`, `sealed interface UiState`, fonctions pures de use case |
| DataState | `@MainActor final class {Name}Store: ObservableObject` + `actor {Name}Repository` | `ViewModel` (propriétaire de l'état) + `Repository` (`suspend` + `Dispatchers.IO`), Room/DataStore |
| Primitive UI | `public struct: View` du paquet du système de design | Composables sans état dans le module `core:designsystem` |
| Semantic Component | Vues qui ne reçoivent que des props, `@EnvironmentObject` 0, `{Model}+Style.swift` | Composables qui ne reçoivent que `UiState`, `hiltViewModel()` 0 |
| Feature Block | Fragments d'écran qui détiennent `@StateObject`/`@EnvironmentObject` | `{UseCase}Screen` + `hiltViewModel()` |
| Route Surface | `TabView`, `NavigationStack`, `navigationDestination`, résolution des deep links | `NavHost`, routes type-safe, deep links |
| App Shell | `@main App`, création des Stores globaux et chaîne de `.environmentObject`, `WidgetBundle` | `Application`, `MainActivity`, modules Hilt, `Scaffold` |

## Assemblage des Feature (composition)

Un écran mobile est une hiérarchie : l'écran Aujourd'hui présente une feuille d'humeur, et l'onglet Activité présente une feuille de fin de session. Si l'on conservait tel quel le « pas de références entre Feature Blocks » de web,
tout cet assemblage serait une violation. Mobile utilise le domaine comme chemin.

- Un domaine forme un arbre avec `/`, comme `today` et `today/mood`. On le déclare dans `domain:` de `.strata/layer-map.yaml`.
- **Un parent peut référencer son enfant.** Le Feature Block de `today` assemble la feuille de `today/mood`.
- Enfant → parent et entre frères (`today` ↔ `activity`) sont interdits. Si deux domaines utilisent le même fragment, ce fragment descend en Semantic Component.
- La portée reducer parent → reducer enfant de TCA et celle de Screen parent → Screen enfant de Compose suivent la même règle.

## Targets

Sur les plateformes Apple, l'app, le widget, la montre, la complication de montre et les App Intents sont chacun un target ; sur Android, ce sont les modules app, widget et Wear. Il est d'usage de placer un fichier dans plusieurs targets,
et copier est le germe de la dérive (drift). Core décide seulement **ce qui peut être partagé**.

| Couche | Partage | Condition |
|---|---|---|
| Foundation · Contract · Primitive UI · Semantic Component | Libre | Elles n'ont pas d'état |
| DataState | Conditionnel | `layer-map targets.shared[].stateful: true` + le document doit indiquer que **chaque target a sa propre instance** (par exemple, le HealthStore de la montre lit son propre HealthKit) |
| Feature Block · Route Surface · App Shell | Interdit | Chaque target a des écrans, des points d'entrée et un shell différents |

Le vérificateur lit `targets.shared` dans `layer-map.yaml` et le recoupe avec les couches (violation `target_share`). La source canonique est le fichier du projet
(`sources` par target dans `project.yml`), et le layer-map transcrit cette déclaration.

## Échelle d'application

| Niveau | Responsable | Force |
|---|---|---|
| Frontière de module (paquet SPM / module Gradle) | Isole Foundation · Contract · DataState · Primitive UI du target de l'app. Un paquet ne peut pas importer l'app | **Imposé par le compilateur — canonique** |
| Target | App, widget, montre, tests. Le partage se fait en ajoutant un target par fichier | Imposé par le compilateur |
| Vérificateur de références de types (`check-swift-layers.py`) / ArchUnit · Konsist | Direction entre fichiers **à l'intérieur** d'un module, isolation des domaines, assemblage, partage des targets | CI blocking |
| règles de style | Nouvelle introduction de valeurs raw, de polices système, de `Color(hex:)` | CI blocking, sur les nouvelles lignes uniquement |
| Hook d'édition | Les mêmes commandes que ci-dessus sur les fichiers modifiés — **d'après l'arbre de travail git** (et non d'après les événements d'outil) | warning → exit 2 comme retour à l'agent |

Chaque fois qu'un paquet est créé, la part du vérificateur diminue. Quand Contract et DataState deviennent des paquets, cette frontière apparaît dans `import`,
et le hook de Core fondé sur les imports fonctionne aussi en Swift. Un projet brownfield commence par un paquet du système de design, puis élève Contract, puis DataState, dans cet ordre.

## Android (non vérifié)

L'équivalent Compose se réduit à la colonne de droite du tableau ci-dessus, et il n'a pas été vérifié sur un projet réel. Points à confirmer lors de l'application :

- Les trois niveaux UI / Domain / Data du guide officiel de Google correspondent à (Primitive+Semantic+Feature+Route) / Contract / DataState de mobile. C'est un affinement, non un conflit.
- L'application réutilise Gradle multi-modules ainsi que le mode brownfield (layer-map) de `profiles/backend.kotlin-spring-cqrs/enforcement/`. Les imports de Kotlin sont explicites ; un vérificateur de références de types n'est donc pas nécessaire.
- La restauration après la mort du processus (`SavedStateHandle`), la collecte sensible au cycle de vie, le placement des modules de DI (App Shell) et le `commonMain` de KMP (partage de Contract + DataState) sont décidés par le document de liaison Compose. Backlog de méthodologie MB-o-rot-2026-004.

## Séparation Core / Convention / Profile

- **Core** (ce document + `core/rules/layer-rules.yaml`) : règles de couches, `can_reference`, assemblage et partage des targets. Indépendant de la plateforme.
- **Convention** (`profiles/frontend.swiftui/docs/fr/frontend-swiftui.md`, plus tard `frontend-compose.md`) : comment rattacher les couches aux constructions du langage, concurrence, nommage, gestion des paquets.
- **Profile** (`.strata/layer-map.yaml` · `constraint-registry.yaml` du projet) : mappage des fichiers, arbre des domaines, liste de partage des targets, exceptions.
