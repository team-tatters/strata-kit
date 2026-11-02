# Convention backend Kotlin/Spring

> Source canonique : strata-kit `profiles/backend.kotlin-spring-cqrs/docs/fr/backend-kotlin-spring.md` — migré depuis strata `docs/05-conventions/backend-kotlin-spring.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles se trouve dans `core/rules/`.

> Frontières de Core : `core/docs/fr/architecture/backend-cqrs.md`, `core/rules/layer-rules.yaml`
> Le principe du prépaiement et les trois frontières (propriété des données, écriture inter-domaines, lecture inter-domaines) : `core/docs/fr/architecture/prepaid-structure.md`

Ce document décrit les conventions par lesquelles un projet Kotlin + Spring implémente les couches CQRS de Core.
Kotlin/Spring n'est pas un prérequis de Core.

## Correspondance couche ↔ paquet

Sur la JVM, la clé première d'identification d'une couche est le **segment de paquet**, et non le répertoire
(`language_patterns.kotlin.package_identifier` de `core/rules/layer-rules.yaml`).

| Couche | Segment de paquet | Exemple |
|---|---|---|
| L1_Component | `..component..` | `com.example.order.component.MoneyUtil` |
| LM1_Inherite | `..inherite..` | `com.example.order.inherite.BaseEntity` |
| L2_DataLayer | `..data.{domain}..` | `com.example.order.data.payment.PaymentQueryService` |
| LM2_Coordinate | `..coordinate.{domain}..` | `com.example.order.coordinate.payment.PaymentQueryCoordinator` |
| L3_Composite | `..composite.{domain}..` | `com.example.order.composite.checkout.CheckoutCommandCompositeService` |
| Route_Controller | `..controller..` | `com.example.order.controller.CheckoutController` |

Les noms de fichier suivent tel quel le motif PascalCase par défaut de Core (`{Domain}QueryService.kt`, etc.). Le suffixe de L3 est `CompositeService` (`{Domain}CommandCompositeService`, ou `{Domain}{Action}CompositeService` lorsque le comportement doit apparaître — DEC-2026-10-29-05).

Un projet réel peut utiliser des paquets différents des segments ci-dessus. Par exemple, shop-api place L3 dans `rest/<domain>/services/` et LM2 dans `rest/<domain>/coordinator/`. La couche n'est pas déterminée par le nom du paquet mais par la correspondance de chemins du `layer-map.yaml` du projet ; il suffit donc que la correspondance soit exacte.

## Les deux étages de L2 et la référence au sein d'un même étage

| Étage | Élément Kotlin | Références |
|---|---|---|
| Étage inférieur | `*Repository` (interface Spring Data JPA), `*Template` (DSL jOOQ · QueryDSL) | Ne connaît pas l'étage supérieur. Repository ↔ Template est interdit |
| Étage supérieur | `*CommandService` (`@Transactional`), `*QueryService` (`readOnly`) | Utilise l'étage inférieur par injection par constructeur. L'injection service ↔ service est interdite |

- Si deux services répètent la même combinaison, on la remonte dans un `*Coordinator` de LM2. Le critère est de savoir s'il s'agit de la même préoccupation de domaine.
- Les calculs qui n'ont pas besoin d'injection, comme les conversions d'unités ou les formules, sont extraits dans un `object` et laissés hors des étages (par exemple `UnitConversions.convert(...)`).
- Les services et helpers utilisés uniquement à l'intérieur d'un module d'entités sont masqués avec `internal` de Kotlin. `internal` n'est visible qu'au sein du même source set Gradle ; le compilateur empêche donc le L3 d'un module de service de les contourner pour les appeler. Une classe public qui reçoit un constructeur est déclarée avec `internal constructor`.

## Frontières de module (Gradle multimodule)

- Dans la mesure du possible, on sépare les frontières de domaine en modules Gradle. Si la dépendance entre modules n'est pas
  déclarée dans `build.gradle.kts`, l'import devient une erreur de compilation ; des règles comme « pas de référence mutuelle entre L2 »
  sont donc imposées au niveau du compilateur, sans outil.
- Les dépendances entre modules utilisent `implementation` par défaut. `api` n'est utilisé que lorsque ce type est
  le contrat public du module — la fuite de dépendances transitives devient une voie de contournement des couches.
- La direction des couches à l'intérieur d'un module est vérifiée de façon canonique par les tests ArchUnit (voir la structure d'application ci-dessous).

## Conventions de liaison avec Spring

- **Pour l'injection de dépendances, on n'utilise que l'injection par constructeur.** L'injection par `@Autowired` sur un champ et par `lateinit var` est interdite.
  L'injection par constructeur laisse la référence de type dans le bytecode, ce qui est la condition pour que la vérification statique des couches fonctionne.
- **Recherche de bean par chaîne interdite** : les motifs qui masquent la référence de type, comme
  `applicationContext.getBean("...")` ou l'abus de `@Qualifier`, contournent la vérification des couches et sont interdits (ArchUnit les bloque).
- **La frontière de transaction est le CommandService de L2** : `@Transactional` se place sur le CommandService
  (règle de Core). Le QueryService est en lecture seule — `@Transactional(readOnly = true)` ou omis.
- **Ne pas renvoyer d'Entity JPA hors de L2** : hormis la définition des entités communes de LM1,
  l'Entity est convertie en DTO ou en type de domaine à l'intérieur de L2 avant d'être transmise vers le haut.
  C'est une violation si un Controller référence `..entity..` ou un type Entity.
- **Controller mince** : seulement la définition des URI, la validation des paramètres (`@Valid`), l'injection du contexte d'authentification
  et la conversion en Response DTO. Les branchements métier vont dans L3.
- L1_Component interdit tout import de Spring (règle de Core « import de framework externe interdit »).

## Structure d'application (3 niveaux)

| Niveau | Responsable | Force |
|---|---|---|
| Gradle multimodule | Frontières de module (domaine) | Imposé par le compilateur |
| ArchUnit | Direction des couches + isolation des tranches de domaine + blocage de getBean | CI blocking (canonique) |
| Hook | Retour en temps réel pendant l'édition | Heuristique (warning) |

Les tests ArchUnit lisent directement `core/rules/layer-rules.yaml` à l'exécution ; les règles ne sont donc pas
dupliquées dans le code de test. Modèle et méthode d'application : `profiles/backend.kotlin-spring-cqrs/enforcement/README.md`

## Marqueurs

On utilise le format KDoc (`core/docs/fr/conventions/strata-markers.md`) :

```kotlin
/** @strata:port L2-PaymentQueryService */
```
