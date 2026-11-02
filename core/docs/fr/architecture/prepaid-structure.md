# Le principe de la structure prépayée

> Source canonique : strata-kit `core/docs/fr/architecture/prepaid-structure.md` — migré depuis strata `docs/03-architecture/prepaid-structure.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles est dans `core/rules/`.

> Source canonique lisible par machine des règles de couches : `core/rules/layer-rules.yaml` / description par couche : `core/docs/fr/architecture/backend-cqrs.md`
> Ce document est le principe de niveau supérieur qui explique « pourquoi cette structure est mise en place dès le départ ». (DEC-2026-09-30-01, strata)

## Résumé

- **Principe :** si le coût de structure payé maintenant compense suffisamment le coût des changements ultérieurs, cette structure est mise en place dès le départ. Une structure qui ne le compense pas n'est pas construite avant d'être nécessaire.
- **Trois critères de jugement :** le coût maintenant, le coût quand ce changement deviendra nécessaire plus tard, et la probabilité que ce changement se produise réellement.
- **On ne réduit pas les couches selon l'échelle.** Les rôles des couches et le sens des dépendances sont les mêmes à toute échelle. Seuls le nombre de domaines et les unités de déploiement varient avec l'échelle.
- **Le but est que les couches changent à peine lors du passage d'un monolithe à MSA.** Les coûts que les couches ne couvrent pas se concentrent en trois endroits — la propriété des données, les écritures entre domaines et les lectures entre domaines —, donc les règles de ces trois points sont elles aussi fixées à l'avance.
- **Une structure prépayée ne se maintient que si elle est appliquée.** Une frontière que ni le compilateur ni la CI ne bloquent fuit peu à peu avec le temps, et la valeur payée d'avance disparaît d'autant.

## Liste des verdicts

### Structures toujours mises en place

| Structure | Coût maintenant | Coût de changement compensé |
|---|---|---|
| Rôles des couches et dépendance à sens unique | L'effort d'ajuster l'emplacement des fichiers et les chemins d'appel aux règles | Le coût de ne pas pouvoir prévoir ce qui vient avec une fonctionnalité quand on la déplace ou la détache |
| Services séparés en commande et requête (CQS) | Les fichiers de service doublent et il faut avoir à l'esprit l'emplacement de la transaction | Le coût de devoir démonter le code d'écriture quand on détache le modèle de lecture ou qu'on le déplace vers un cache ou une réplique |
| Modules de build séparés en modules d'entité et modules de service | Configuration du build, déclaration des dépendances entre modules, complexité du traitement transactionnel, synchrone et asynchrone | Le coût de retracer les frontières du code lors de la séparation des services. Les modules deviennent eux-mêmes des unités de déploiement candidates |
| Ports et adaptateurs aux frontières des systèmes externes (BD, messagerie, API externes) | Une interface et une implémentation par frontière | Le coût de remplacer un système externe, ou de transformer un appel dans le processus en appel réseau |

### Structures mises en place seulement quand c'est nécessaire

| Structure | Moment de la mise en place |
|---|---|
| Event sourcing (variante `es-cqrs`) | Quand la piste d'audit, la reconstitution d'instants passés ou le rejeu d'événements sont confirmés comme exigences |
| Stockage de lecture séparé | Quand la charge de requêtes ou le modèle de requête s'est réellement séparé du modèle d'écriture |

### Structures non mises en place

| Structure | Raison |
|---|---|
| Abstractions d'interface à chaque couche interne | Les implémentations internes sont rarement remplacées, donc il n'y a pas de coût de changement à compenser. La seule règle de sens des couches produit le même effet |
| Une architecture hexagonale complète | Les ports et adaptateurs n'apportent de la valeur qu'aux frontières externes. Les étendre à l'intérieur ne fait qu'augmenter le coût |

## Trois frontières que les couches ne couvrent pas

Quand on détache un service d'un monolithe, le code des couches se déplace presque tel quel. Le coût restant apparaît aux trois endroits ci-dessous. Ces trois points sont fixés par des règles dès le départ.

### Propriété des données

- Une table appartient à un module d'entité. L'historique des changements de schéma de la table (changelog) appartient aussi à ce module.
- Les autres modules n'écrivent pas directement dans cette table. L'écriture passe par le service de commande du module propriétaire.
- Raison : lors de la séparation des services, le coût de division de la BD augmente à mesure que « qui écrit dans quelle table » est dispersé.

### Écritures entre domaines

- On ne lie pas les écritures de deux domaines dans une même transaction. Une fois l'écriture d'un domaine terminée, on publie un événement, et l'autre domaine reçoit cet événement et effectue sa propre écriture.
- L'enregistrement de publication est sauvegardé dans la transaction (approche outbox, p. ex. la table de publication d'événements de Spring Modulith). Le point qui passe d'une livraison dans le processus en monolithe à une livraison par broker en MSA se réduit alors à cet unique endroit.
- Raison : deux domaines liés dans une transaction deviennent un problème de transaction distribuée dès qu'on les sépare en services.

### Lectures entre domaines

- Le chemin de lecture des données d'un autre domaine est fixé en un seul endroit par domaine. On choisit l'un des deux — un guichet de consultation seule (un service de requête ou une couche de coordination) ou une consultation de tables externes au niveau de la BD (FDW, etc.) — et on ne les mélange pas.
- On n'utilise pas directement les types d'entité d'un autre domaine. Le résultat de la requête est reçu dans des types de son propre domaine.
- Raison : si le chemin de lecture est un seul endroit, il suffit, lors de la séparation des services, de transformer cet unique endroit en requête réseau.

## Échelle et unités de déploiement

- Même un petit projet a la même structure de couches et de modules. S'il n'y a qu'un seul domaine, il y a simplement un seul module de domaine.
- La différence entre monolithe et MSA se lit comme « combien de modules sont regroupés dans un processus pour être déployés ». Déplacer un module vers un autre processus revient à changer le mode de livraison des trois frontières ci-dessus.
- Selon le budget et les conditions d'exploitation, les unités de déploiement peuvent être fusionnées ou divisées à tout moment. Tant que les frontières des couches et des modules sont respectées, ce choix n'est pas une décision de refaire la structure du code.

## Frontières de compilation bon marché par langage

Le moyen de réduire le plus le coût prépayé est d'utiliser les frontières que le langage et ses outils de build fournissent déjà. Chaque binding de langage indique « avec quoi on crée la frontière de module, et avec quoi on bloque le sens des couches à l'intérieur d'un module ».

| Langage | Frontière de module (imposée par le compilateur) | Sens des couches dans un module | Cycles |
|---|---|---|---|
| Kotlin / Java | Gradle multi-modules (`implementation` par défaut) | ArchUnit (bloque en CI) | Gradle rejette les cycles entre modules |
| Go | Modules et paquets `internal/` | Règles d'import comme depguard | Les cycles d'import entre paquets sont des erreurs de compilation |
| Rust | Crates du workspace cargo | Séparation en crates ou visibilité de module (`pub(crate)`) | cargo rejette les cycles entre crates |
| TypeScript / JavaScript | Paquets du workspace (surface publique limitée par `exports`) | dependency-cruiser, eslint-plugin-boundaries | Le gestionnaire de paquets les autorise, donc une règle `no-circular` est indispensable |
| Swift | Paquets et targets SwiftPM | Séparation des targets + vérificateur (`profiles/frontend.swiftui/enforcement/`) | SwiftPM rejette les cycles entre targets |

Les documents de binding sont dans `profiles/<id>/docs/fr/`. Un nouveau binding de langage est ajouté quand un vrai projet apparaît.

## Un exemple d'application du même principe au frontend

- Les trois niveaux de tokens (valeur brute → alias → composant) prépayent la couche d'alias, de sorte que le coût de changement de thème ou de marque se réduit à une seule définition d'alias. Détails : `core/docs/fr/architecture/frontend-design-contract.md`
- La hiérarchie des composants ne s'utilise que de haut en bas. Détails : `core/docs/fr/architecture/frontend-web.md`

## Préservation du prépaiement

- Les frontières de module sont bloquées par l'outil de build, et le sens des couches dans un module par les tests d'architecture de la CI. Les hooks au moment de l'édition ne sont qu'un retour rapide, pas le verdict canonique.
- Si des violations se sont accumulées dans le code existant, on les fige en base de référence et on ne bloque que les nouvelles violations. La base de référence ne se met à jour que dans le sens de la diminution.

## Cas de preuve (un projet backend, 2026-09)

- Lors du transfert de la conception 3.0 du module de commandes vers le module de facturation (billing), le travail s'est achevé en créant de nouveaux modules d'entité, de document et de service et en faisant tourner le chemin de la passerelle. Les règles de couches et la forme du code de service n'ont pas changé (décision de ce projet du 2026-09-08).
- Les coûts qui ont réellement posé problème étaient le dispositif permettant à deux modules de coexister dans la même BD, et le déplacement des données. Cette expérience est le fondement de l'élévation de la frontière « propriété des données » au rang de règle.
- Lors de la mesure ArchUnit de 2026-07, près de 1 500 violations de couches à l'intérieur des modules sont apparues. La frontière de module était tenue par le compilateur, mais la frontière interne au module ne reposait que sur des avertissements. C'est le fondement de la section « Préservation du prépaiement ».
