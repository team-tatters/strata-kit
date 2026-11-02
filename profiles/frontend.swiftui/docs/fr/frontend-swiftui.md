# Convention frontend Swift/SwiftUI

> Source canonique : strata-kit `profiles/frontend.swiftui/docs/fr/frontend-swiftui.md` — migré depuis strata `docs/05-conventions/frontend-swiftui.md` (ordre 2026.10.29-06, 2026-10-29). Les règles en YAML se trouvent dans `core/rules/`.

> Frontière avec Core : `core/docs/fr/architecture/frontend-mobile.md` (`core/rules/layer-rules.yaml` → `frontend.variants.mobile`) · contrat de design : `core/docs/fr/architecture/frontend-design-contract.md` · application : `profiles/frontend.swiftui/enforcement/`
> v1 2026-09-10 (liaison avec la variante web, première application sur o-rot) → **v2 2026-09-11** (variante mobile — vocabulaire, assemblage des Feature, cibles, échelle d'application, hooks, DEC-2026-09-11-01)

Ce document est la convention pour une application SwiftUI qui implémente la variante mobile de Core (Foundation → … → App Shell).
SwiftUI n'est pas un prérequis de Core. Core décide seulement « par quelles couches doit passer chaque responsabilité » et les règles d'assemblage et de partage entre cibles ; ce document les rattache aux constructions de Swift.

## Résumé

- La clé de premier rang pour identifier une couche est **le rôle du type que contient un fichier**, et non le répertoire. `.strata/layer-map.yaml` reclasse par rôle, et les fichiers ne sont pas déplacés.
- **La source canonique de l'application des règles est le compilateur.** Plus on remonte de couches dans des paquets SPM locaux, plus les frontières apparaissent dans les `import`. Le vérificateur de références de types (`check-swift-layers.py`) est un appoint qui regarde la direction entre fichiers au sein d'un même module.
- Le propriétaire de l'état est le Feature Block : une vue qui crée son état avec `@StateObject` ou le reçoit avec `@EnvironmentObject`. Une vue qui ne reçoit que des `props` est un Semantic Component. La **création** des Store et la chaîne d'injection par l'environnement sont en un seul endroit, l'App Shell.
- Un Feature n'assemble que **parent → enfant** au sein du même arbre de domaine (`today` → `today/mood`). Une pièce partagée entre frères descend dans un Semantic Component.
- Partager entre cibles, c'est ajouter la cible, pas copier. Foundation, Contract, Primitive et Semantic sont libres ; DataState exige `stateful: true` et une séparation explicite des instances ; Feature, Route et Shell sont interdits.
- Pour les tokens, la source canonique est `tokens.json` dans le dépôt de code, et le fichier de tokens Swift est un artefact généré. Dans les vues, le hex, les polices système et les valeurs numériques brutes sont interdits.

## Couche ↔ constructions Swift

| Couche | Ce que c'est en Swift | Marqueur | Interdit |
|---|---|---|---|
| Foundation | Enums de tokens (`Color`, `Font`, spacing), `Shape` purs, enums de constantes, utilitaires purs comme les fuseaux horaires | `enum {Name}Tokens` · `static let` uniquement | `ObservableObject`, E/S, `UserDefaults`, vues |
| Contract | Modèles `Codable` et DTO, valeurs d'état d'écran `{Name}UiState`, règles de calcul pures (`enum` + `static func`), analyseurs de deep links, protocoles de port | types valeur · `import Foundation` uniquement | Importer SwiftUI, **propriétés d'affichage** comme la couleur ou l'icône, **le nom `ViewModel`** (sur mobile, il désigne un propriétaire d'état) |
| DataState | `Store` (propriétaire d'état sur l'acteur principal) + `Repository`/`Service`/`Session` (E/S isolées) | `@MainActor final class {Name}Store: ObservableObject` · `actor {Name}Repository` | Rendu de vues, référence directe au Store d'un autre domaine |
| Primitive UI | Vues du paquet de système de design, indépendantes du domaine (Button, Chip, Row, TabBar) | `public struct {Name}: View` · props d'axe (variant, intent, size) · **doit être un paquet distinct** | Modèles de domaine, Store |
| Semantic Component | Vues porteuses de sens qui dessinent à partir des seuls props/UiState — graphiques, scènes, en-têtes, états vides, extensions d'affichage des modèles | `struct {Domain}{Purpose}View: View` · `{Model}+Style.swift` · `@EnvironmentObject` 0 | Accès au Store, `@StateObject` |
| Feature Block | Propriétaire de l'état d'un fragment d'écran — détient un Store via `@StateObject`/`@EnvironmentObject` et propage les props vers le bas | `struct {UseCase}View` · `{UseCase}Sheet` · arbre de domaine `today/mood` | Référencer le Feature d'un domaine frère, posséder le graphe de navigation |
| Route Surface | Points d'entrée `TabView` et `NavigationStack`, `navigationDestination`, sélection d'onglet, résolution des deep links | `MainTabView` · `{Flow}Flow` | **Créer ou référencer** un Store (l'injection revient à l'App Shell), exporter de l'UI réutilisable |
| App Shell | `@main struct App`, création des Store globaux et chaîne `.environmentObject`, `WidgetBundle`, chrome du shell (barre d'onglets) | `{Name}App` · `{Name}Shell` · `{Name}Bundle` | Logique de cas d'usage du domaine, référence directe à un Feature |

`can_reference` est exactement le tableau de Core. On n'ajoute que trois points propres à SwiftUI.

- **L'injection par l'environnement est une référence.** `@EnvironmentObject var store: TodoStore` signifie que ce fichier référence `TodoStore`. Un Semantic Component ne doit pas avoir de `@EnvironmentObject`.
- **Créer avec `@StateObject`, c'est posséder.** Les Store sont créés dans l'App Shell, et l'état propre à un écran seulement dans un Feature Block. Qu'une Route Surface crée un Store est une violation (la forme où le `MainTabView` d'o-rot créait huit stores est à l'origine de cette règle).
- **`@main` est l'App Shell.** Si une décision de point d'entrée, comme l'aiguillage entre onboarding et principal, se trouve dans `@main`, on descend cet aiguillage dans une vue `{Name}Shell` et on ne laisse dans `@main` que la création et l'injection des Store. Tant que ce n'est pas séparé, on le garde dans `exceptions` du layer-map avec un DEC.

## Assemblage des Feature

```
Features/Today/TodayView.swift          domain: today        ← détient le Store via @EnvironmentObject
Features/Today/Mood/MoodSheetView.swift domain: today/mood   ← le parent (today) la présente avec .sheet
Features/Activity/ActivityView.swift    domain: activity     ← frère de today. Utiliser MoodSheetView est une violation
```

- Le domaine s'écrit dans le champ `domain:` de `layer-map.yaml` sous forme de chemin avec `/`. Le vérificateur ne laisse passer que les références parent → enfant.
- Si deux frères présentent la même feuille (sheet), la partie rendu de cette feuille descend dans un Semantic Component (`MoodPickerView`), et chaque Feature l'enveloppe avec son propre Store.
- Si l'on utilise TCA, le `Scope` du reducer parent est exactement cette arête. Aucun nom de patron n'est imposé — on respecte seulement le sens de l'arête.

## Cibles

- Téléphone, widget, montre, complication et intent sont chacun une cible. Partager, c'est **ajouter le fichier** aux `sources` de chaque cible dans `project.yml` ; on ne fait pas de copie.
- On recopie la liste des partages dans `targets.shared` de `layer-map.yaml`. Le vérificateur confronte les couches (`target_share`).
- Si deux cibles partagent un DataState (par exemple, la montre utilise le fichier `HealthStore` du téléphone), on le déclare `stateful: true`, et l'on documente que chaque cible a sa propre instance et ce que chacune lit.
- L'échange de données entre cibles (`UserDefaults` d'App Group, `WatchConnectivity`) est pris en charge par un seul fichier `{Name}Session`/`{Name}Bridge` de DataState. Une vue qui ouvre directement `UserDefaults(suiteName:)` est une violation.

## Possession de l'état et modèle d'observation

- Par défaut : `ObservableObject` + `@Published` + `@MainActor`. Les Store sont des classes, les modèles des structures.
- On n'utilise `@Observable` (le framework Observation) **que si la cible de déploiement est iOS 17 / watchOS 10 ou ultérieur**. Les deux modèles diffèrent par leurs property wrappers (`@StateObject` ↔ `@State`) et par la granularité des mises à jour ; les mélanger décale le moment de l'initialisation — un projet n'utilise qu'un seul modèle. ([Apple: Observation](https://developer.apple.com/documentation/observation), [Squires: not a drop-in replacement](https://www.jessesquires.com/blog/2024/09/09/swift-observable-macro/))
- Un Store ne connaît que son propre domaine. L'assemblage qui relie deux Store revient à un Feature Block. Si un Store référence un autre Store, c'est une violation de référence croisée entre domaines de DataState.
- La persistance se termine à l'intérieur du Store/Repository. Si `UserDefaults.standard` ou des E/S de fichiers apparaissent dans une vue ou dans Contract, c'est une violation.

## Concurrence

- Le mode de langage Swift 6 transforme les courses de données en erreurs de compilation. L'adoption se fait **progressivement** : `SWIFT_STRICT_CONCURRENCY = targeted` → `complete` → mode de langage 6. On n'active pas tout d'un coup. ([Apple: Adopting strict concurrency](https://developer.apple.com/documentation/swift/adoptingswift6))
- Tous les Store que touchent les vues sont `@MainActor`. Les E/S reviennent au Store via `actor {Name}Repository` ou `nonisolated` + `Task { @MainActor in … }`. Les callbacks de délégués (`WCSessionDelegate` et autres) suivent la même convention.
- Les modèles (structures) se conforment à `Sendable` par défaut. Si le paquet Contract n'exporte que du `Sendable`, les frontières d'acteurs s'alignent d'elles-mêmes.

## Nommage — les Swift API Design Guidelines telles quelles

La source canonique est les [swift.org API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/). Là où elles entrent en conflit avec `common.case_styles` de `core/rules/naming-convention.yaml` de Core, **la convention Swift l'emporte** (tableau ci-dessous). Le nom du fichier est identique à celui du type de premier niveau qu'il contient.

| Élément | Swift | Différence avec le défaut de Core |
|---|---|---|
| Types, protocoles | `UpperCamelCase` | Identique |
| Fonctions, variables, propriétés, case | `lowerCamelCase` | **Les case d'enum sont en lowerCamelCase** — on n'utilise pas le `UPPER_SNAKE` de Core |
| Constantes | `lowerCamelCase` (`static let graceDays`) | On n'utilise pas le `UPPER_SNAKE` de Core |
| Booléens | Se lisent comme des assertions — `isEmpty` · `hasWatch` · `canDelete` | Identique à la règle Props de Core |
| Valeur d'état d'écran | `{Name}UiState` (Contract) | On n'utilise pas le `{Name}ViewModel` de Core web — sur mobile, ViewModel est un propriétaire d'état |
| Propriétaire d'état | `{Name}Store` (DataState) | Équivalent du `use{Name}State` de Core web |
| Fabrique | `make…` | |
| Paire mutant/non mutant | `sort()` / `sorted()`, `append` / `appending` | |
| Protocole | Ce que c'est → nom, capacité → `-able` `-ible` `-ing` | |
| Acronymes | Casse uniforme — `hrvSeries` · `isHRV` (tout en majuscules seulement là où ça commence par une majuscule) | |
| Étiquettes d'argument | Se lisent comme une phrase. Si le premier argument est un groupe prépositionnel, l'étiquette est obligatoire | |
| Suffixes interdits | `Manager` · `Helper` · `Impl` | Identique à Core. `Handler` uniquement pour les méthodes de délégué |

Ce qui correspond aux Props, ce sont les arguments d'`init` de la vue et ses propriétés stockées. On applique la règle `Props` de Core : l'état du parent est un nom sans préfixe, la demande de changement est `on{State}Change`, l'événement est `on{Event}`, le gestionnaire interne est `handle{Event}`. En SwiftUI, `Binding<T>` est une « paire valeur + changement », il correspond donc au lot `{state}Control` de Core — si plusieurs enfants utilisent le même état, on descend un seul `Binding`.

Le bloc `naming:` de `layer-map.yaml` n'est pas appliqué par le vérificateur. Nom de fichier = nom du type de premier niveau est une convention, contrôlée en revue.

## Échelle d'application — le compilateur est la source canonique

| Niveau | Responsable de | Force |
|---|---|---|
| Paquet SPM local (`Package.swift`) | Isole Foundation, Contract, DataState et Primitive UI de la cible de l'application. Un paquet ne peut pas importer l'application, et les dépendances entre paquets ne vont que dans le sens déclaré dans `dependencies:` | **Imposé par le compilateur — source canonique** |
| Cible (`project.yml` / cible Xcode) | Application, widget, montre, tests. Les sources partagées sont ajoutées à la cible fichier par fichier | Imposé par le compilateur |
| `check-swift-layers.py` | Sens des couches entre fichiers **à l'intérieur** d'un module, isolation des domaines, assemblage des Feature, partage entre cibles | CI blocking |
| Règle `--style` / SwiftLint custom_rules | Nouvelle entrée de valeurs brutes, de polices système, de `Color(hex:)` et similaires | CI blocking, recommandé sur les lignes nouvelles |
| Hook d'édition | Le même vérificateur sur les **fichiers modifiés dans l'arbre de travail git** (`--changed`) | exit 2 → retour à l'agent |

- **Étapes de paquets.** Un projet brownfield commence par un seul paquet de système de design (Foundation + Primitive UI). Vient ensuite Contract (modèles, règles, valeurs `Sendable`), puis DataState. Chaque fois qu'on monte d'une étape, cette frontière apparaît dans `import`, de sorte que le hook de Core fondé sur les imports fonctionne aussi en Swift, et la part du vérificateur de références de types se réduit à l'intérieur de la cible de l'application (Semantic → Feature → Route → Shell). Squelette : `profiles/frontend.swiftui/enforcement/Package.swift.template`.
- **La gestion des paquets se fait avec SPM seul.** On n'adopte pas de nouveau CocoaPods ni Carthage. ([DECODE: modularize with SPM](https://decode.agency/article/project-modularization-swift-package-manager/), [Nimble](https://nimblehq.co/blog/modern-approach-modularize-ios-swiftui-spm))
- **On génère le projet de façon déclarative.** On n'édite pas `.xcodeproj` à la main ; on le génère depuis le `project.yml` de XcodeGen (ou Tuist). Le graphe de cibles doit être relu sous forme de texte pour que les décisions de couches et de cibles apparaissent dans la PR. ([XcodeGen vs Tuist](https://medium.com/@sayefeddineh/xcodegen-vs-tuist-choosing-the-right-tool-for-xcode-project-generation-bea093c6e105))
- On **épingle les versions** des paquets externes (`exact` ou `upToNextMinor`) et l'on commite `Package.resolved`.
- **On accroche le hook d'édition à git, pas à l'événement d'outil.** Si le PostToolUse de Claude Code n'est accroché qu'à `Write|Edit`, les éditions par Bash (sed, heredoc) échappent à la vérification. On fixe le matcher à `Write|Edit|Bash`, et sur un événement Bash le vérificateur se replie sur `--changed` (d'après git status). Modèle de configuration : `profiles/frontend.swiftui/enforcement/settings.json.template`.

## Tokens et typographie (liaison avec le contrat de design)

- La source canonique est `tokens.json` du dépôt. Le fichier de tokens Swift (`{Name}Tokens.swift`) en est l'artefact généré, et l'initialisation par `Color(hex:)` apparaît **uniquement dans ce fichier**.
- Les vues n'utilisent que des noms d'alias : `OrotColor.sage700` ○ / `Color(hex: "507663")` ✗ / `.font(.system(size: 13))` ✗ / `.padding(14)` doit passer par un token de spacing.
- Un nouvel alias est une décision d'architecture — enregistrement de décision + `tokens.json` → Swift, dans cet ordre. Une valeur temporaire s'écrit `/// @strata:token-exception … until YYYY-MM-DD`.
- Les tokens typographiques ont trois axes : échelle de texte (titre, corps, légende), **taille d'icône** (`icon.sm/md/lg` — remplace `.font(.system(size:))` pour les SF Symbol) et **échelle de plateforme** (la montre n'est pas une réduction du téléphone, mais une échelle distincte). Si un `.font(.system` subsiste faute d'un axe, le DEC d'ajout de token passe d'abord.
- L'accessibilité est portée par les tokens : seuls les alias dont le contraste de texte est d'au moins 4.5:1 servent pour le texte, et ceux en dessous sont signalés dans le nom comme réservés au non-texte. Dynamic Type est absorbé par le token via `Font.custom(_:size:relativeTo:)`.

## Format et lint

- Comme formateur, on utilise **swift-format** (`swift format`, `xcrun --find swift-format`), inclus dans la toolchain Xcode 16+. La configuration tient en un seul fichier `.swift-format` (modèle : `profiles/frontend.swiftui/enforcement/swift-format.json.template`). ([Xcode 16 swift-format](https://mjtsai.com/blog/2024/11/06/swift-format-in-xcode-16/))
- Le lint avec SwiftLint est **facultatif**. Strata n'exige que quelques `custom_rules`, donc même sans SwiftLint, `check-swift-layers.py --style` exécute les mêmes expressions régulières. Si l'on utilise SwiftLint, on fusionne `profiles/frontend.swiftui/enforcement/swiftlint-strata.yml.template` dans `.swiftlint.yml`. ([SwiftLint custom rules](https://github.com/realm/SwiftLint#defining-custom-rules))

## Marqueurs

On les place dans les commentaires de documentation `///` (`core/docs/fr/conventions/strata-markers.md`) :

```swift
/// Règles de traduction de l'état du jour — fonctions pures uniquement.
/// @strata:layer Contract
/// @strata:domain today
enum StateEngine { … }
```

## Tests

- La cible de tests unitaires vérifie Contract et DataState directement avec `@testable import {App}`. Une couche devenue paquet est testée dans la cible de tests du paquet lui-même. Les tests de vues ne sont pas des snapshots : ils vérifient le chemin **Store → état → texte de l'écran**.
- Les tests de Store s'isolent avec `UserDefaults(suiteName: UUID)` ou un répertoire temporaire. Les tests ne touchent pas à `.standard`.
- Les fichiers s'appellent `{Type}Tests.swift`, et le répertoire de la cible de tests est exclu dans le layer-map avec `_test`. Le vérificateur ignore silencieusement les fichiers hors de `swift.sources`.

## Procédure d'adoption en brownfield

1. Créez `.strata/layer-map.yaml` à partir de `profiles/frontend.swiftui/enforcement/layer-map.yaml.template` (`variant: mobile`). Classez **par rôle** et ne déplacez pas les fichiers. Écrivez les domaines de Feature comme un arbre avec `/`.
2. Amenez les non-mappés à 0 avec `check-swift-layers.py --summary`.
3. Recopiez dans `targets.shared` les sources partagées par cible de `project.yml`. Pour le partage de DataState, `stateful: true` + documentation.
4. Regardez les violations avec `--all`. Triez-les en trois — à corriger maintenant / à enregistrer dans `exceptions` avec un DEC / à figer avec `--write-baseline` en ne bloquant que le nouveau.
5. Activez `--style` et répétez la même procédure.
6. Mettez `--all --style --ignore-known` en CI. Le hook d'édition est `profiles/frontend.swiftui/enforcement/settings.json.template` (Write|Edit|Bash → stdin, `--changed` pour Bash).
7. Montez l'échelle des paquets : système de design → Contract → DataState. À chaque étape, mettez à jour `swift.sources` et le mappage du layer-map, et régénérez le baseline.

## Ce que ce document ne décide pas

Il ne décide pas du nom d'un patron d'architecture (MVVM, TCA, Clean). Quel que soit le nom utilisé, il suffit que « le Store soit du DataState, la possession de l'état revienne au Feature Block, les vues à props soient du Semantic, l'assemblage soit parent → enfant » soit respecté. La couche réseau et les outils de cache d'état serveur sont eux aussi laissés en constraint de projet — mais la règle de Core est la même : le transport n'est visible qu'à l'intérieur de DataState et n'est pas exposé aux vues. Pour la liaison Compose/Android, il n'existe que le tableau de correspondance de `core/docs/fr/architecture/frontend-mobile.md` §Android, et il n'y a pas encore de document distinct.
