# 09 — Context Protocol: Constraint-Aware Context Loading

> Canonique : strata-kit `core/docs/fr/methodology/context-protocol.md` (migré le 2026-10-29 depuis strata `docs/09-context-protocol.md`, DEC-2026-10-29-11).

> Sur la base des principes des cartes du kit (`rec.context.entry-view-budget`, `rec.session.split-at-task-boundary`, `rec.session.state-in-files`) et de `core/docs/fr/methodology/session-splitting.md`, ce document définit les règles de chargement de contexte tenant compte des contraintes.

## 1. Définition du problème

Les chemins par lesquels une contrainte de domaine décidée dans un ADR (par exemple « hard-delete interdit », « Bitemporal obligatoire ») se perd au moment de l'implémentation :

1. La prose de l'ADR est trop longue pour être lue en entier à chaque fois
2. Les détails de l'ADR se perdent lors du compaction
3. Un Worker a un contexte indépendant — il ne connaît pas la discussion sur l'ADR de la session du Builder
4. Si la spécification de la tâche omet une contrainte de domaine, le Worker ne peut pas la détecter

## 2. Solution : les contraintes entrent dans la vue d'entrée sous forme de résumé ; le registry complet se lit au besoin

### Niveaux de contexte

```
T0 — Universal (toujours chargé, 12KB au maximum — rec.context.entry-view-budget)
  ├── AGENTS.md + CLAUDE.md            (guide généré — résumé des cartes must, résumé des contraintes de 2KB au maximum)
  └── active/{session-id}.yaml         (active-task par session — DEC-2026-08-19-05)

T1 — Session (au démarrage de la session)
  ├── Le dernier fichier de handoff
  ├── decisions.yaml                   (index généré, au besoin — la source de vérité est constituée des enregistrements de decisions/)
  └── constraint-registry.yaml         (au besoin — via le lien de la vue d'entrée)

T2 — Domain (selon la cible de la tâche)
  ├── La page de nœud du nœud thématique (jointure de la forme finale, de la politique, des décisions, de l'historique de travail et de la dette — générée, le point d'entrée)
  ├── La Constraint Card complète de ce domaine
  └── La section Decision Outcome de l'ADR concerné

T3 — Implementation (à l'implémentation)
  ├── Les fichiers source cibles
  ├── Les fichiers de test
  └── layer-rules.yaml (la section de cette couche)
```

### Règles de constraint-registry.yaml

- **Emplacement** : `.strata/constraint-registry.yaml` (dans le projet)
- **Limite de taille** : 3KB au maximum. Le guide généré ne porte qu'un résumé de 2KB et renvoie au fichier complet par un lien
- **Au-delà de 3KB** : déplacer les éléments `severity: should` dans un fichier séparé. Ne garder dans le registry que `must`/`must-not`
- **Moment de mise à jour** : en même temps que le passage d'un ADR à accepted et que la création d'une Constraint Card
- **Format** : le même index YAML que `decisions.yaml`

```yaml
constraints:
  - id: CC-NNN-01
    source: ADR-NNN
    severity: must
    scope: {domains: [{domain}], layers: [{layer}]}
    rule: "{règle exécutable en une ligne}"
    status: active
```

### Règles de decisions.yaml (corrigées le 2026-08-19)

- Le `decisions.yaml` lu au besoin est un **index compact régénéré à partir des enregistrements (`.strata/decisions/DEC-*.yaml`)**. Toute modification manuelle est interdite.
- Seule la **CLI decision writer** ajoute des décisions, attribue les numéros et régénère l'index (sérialisé avec flock — sûr avec plusieurs sessions simultanées, DEC-2026-08-19-05. Correspondance rôle → implémentation : `python3 -m kb --help`, `core/docs/fr/kb-engine.md`).
- Lorsque le détail est nécessaire, on charge l'enregistrement complet via le chemin `record:` de l'entrée de l'index — le même pattern que le détail par couches Registry (1 ligne) → Card (~50 lignes) → ADR (~200 lignes) (résumé de l'index → enregistrement complet).
- L'emplacement physique de Tier P suit le placement profile (`core/docs/fr/environment/data-placement.md` §1.5 — embedded=repo, detached=vault `projects/{n}/strata/`).

## 3. Chargement de Context par Agent Role

### Builder

| Situation | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| Création d'une tâche | ✓ constraint-registry filtré | ✓ | Page de nœud → les Cards de ce domaine | - |
| Rédaction d'un ADR | ✓ | ✓ | Page de nœud (vérifier la chaîne de décisions) | - |
| Extraction d'une Constraint | ✓ | - | - | - |

Le Builder lit constraint-registry.yaml, filtre selon le domaine/la couche de la tâche
et injecte les constraints correspondantes dans `scope.constraints` de la spécification de la tâche.
De la même façon, il trouve avec le résolveur de couverture la spécification qui possède le périmètre de la modification (`covers`) et l'injecte dans `scope.docs_to_update`.
La page de nœud est le point d'entrée de ces deux injections — ouvrir un nœud affiche sur un seul écran la spécification en vigueur, les contraintes actives et les décisions en vigueur.

### Worker

| Situation | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| Exécution d'une tâche | CLAUDE.md seulement | - | - | ✓ |

**Le Worker ne lit pas directement constraint-registry.yaml.** Il ne lit pas non plus directement les pages de nœud.

Il n'utilise que ce que le Builder a injecté dans `scope.constraints` et `scope.docs_to_update` de la spécification de la tâche.
Cela correspond au principe d'**autonomie** de la spécification de la tâche.

```yaml
# La spécification de tâche que reçoit un Worker
scope:
  layer: "L2_DataLayer"
  constraints:
    - id: "CC-NNN-01"
      rule: "Une contrainte qui s'applique à ce scope"
    - id: "CC-NNN-02"
      rule: "Une autre contrainte"
```

Le Worker convertit ce `scope.constraints` en `constraint_compliance` du rapport d'achèvement.

### Supporter

| Situation | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| Recherche de constraints | ✓ recherche dans le registry | - | Résultats de la recherche seulement | - |

À la demande du Builder, le Supporter recherche les constraints d'un domaine/d'une couche précis.

## 4. Règles de Context Budget

```
CB-1 : T0 (AGENTS.md + CLAUDE.md) sous 12KB, sous 14KB guide hérité compris (wizard verify)
  → le registry des contraintes et l'index des décisions ne font pas partie de T0 ; les contraintes entrent dans le guide généré sous forme d'un résumé de 2KB
  → si le guide devient trop volumineux, le réduire d'abord en table des matières (centrée sur les références)
  → le chemin d'entrée que lit using-strata (corps du skill, registry du core, constitution) est signalé à part par verify (2026-10-29, sans plafond)

CB-2 : Une Constraint Card de T2 fait au maximum 10KB par domaine
  → au-delà de 10KB, ne charger que le résumé d'une ligne du registry au lieu de la Card complète

CB-3 : Le chargement total de .strata/ est de 30KB au maximum (T0+T1+T2 cumulés)
  → en cas de dépassement, remplacer T2 par les lignes correspondantes du registry

CB-4 : L'ADR complet n'est chargé que par le Builder (rédaction d'un ADR / extraction d'une Constraint)
  → les autres rôles accèdent à la décision de l'ADR par la Constraint Card
  → c'est la raison d'être de la Constraint Card

CB-5 : Une page de nœud fait au maximum 8KB par nœud (avec le budget de Card de CB-2, cela maintient le plafond de T2)
  → le générateur réduit la section d'historique de travail aux 5 dernières entrées et la section de décisions à la décision en vigueur plus la précédente, pour tenir dans le budget
  → si cela dépasse encore, ne garder que les sections de forme finale et de politique et remplacer le reste par des liens
```

## 5. Résilience au Compaction

```
Avant le compaction :   l'ADR complet + la discussion détaillée (présents dans le contexte)
Après le compaction :   il ne reste qu'un résumé — risque de perdre le détail de l'ADR

Chemin de récupération de la Constraint :
  constraint-registry.yaml (c'est un fichier, on peut donc toujours le relire)
  → le résumé d'une ligne montre immédiatement « ce qu'il faut respecter »
  → si le détail est nécessaire, consulter la Constraint Card individuelle (T2)
  → si un contexte plus profond est nécessaire, consulter source_adr

Détail par couches (Layered Detail) :
  Registry (1 ligne)  →  Page de nœud (~100 lignes)  →  Card (~50 lignes)  →  ADR (~200 lignes)
  résumé en vue d'entrée  une fois, à l'entrée du domaine   chargée au besoin    presque jamais chargé
```

La page de nœud ne remplace ni la Card ni l'ADR. C'est un point d'entrée qui indique quelle Card, quel ADR et quelle spécification sont en vigueur ; le contenu se trouve au-delà des liens.

## 6. Relation avec la gestion de contexte existante

| Existant (cartes du kit · session-splitting.md) | Ce document (extension) |
|---|---|
| Conception des niveaux de CLAUDE.md (§2·§4, `wizard verify`) | Conservée — le résumé des contraintes va dans le guide généré, le registry complet se lit au besoin |
| Protocole de handoff (`strata.handoff`, session-splitting.md §5) | Conservé — l'état de l'extraction des constraints est ajouté au handoff |
| Défense contre le compaction (execution-modes.md, `kb pre-compact`, SessionStart compact) | Renforcée — le registry est une ancre de récupération supplémentaire |
| Guide du budget de tokens (session-splitting.md §5.2) | Étendu — ajout des règles CB-1~5 |
| Distinction Memory vs Handoff vs KB (§7, rec.session.state-in-files, rec.kb.session-records-in-vault) | Conservée — les Constraint Cards sont placées dans la KB |
| (nouveau) Nœud thématique | Point d'entrée de T2 — la page de nœud est un produit de la couche Index, pas une source de vérité (core/docs/fr/knowledge-base/vault-structure.md) |

## 7. Mémoire, passation et KB

La mémoire du harnais (pour Claude Code, `~/.claude/projects/<projet>/memory/`) est lue à chaque démarrage de session par son index ; ce qu'on y met change donc le jugement de la session suivante.

| Quoi | Où | Pourquoi |
|---|---|---|
| État d'avancement — le travail en cours, la suite, les changements non commités, les blocages | Le fichier actif (`.strata/local/active/`) et la passation | Il se périme à la fin de la session ; en mémoire, la session suivante lit un état passé comme un fait présent |
| Faits durables — préférences de l'utilisateur, consignes sur la façon de travailler, emplacement des ressources externes | La mémoire du harnais | Ce que chaque session doit lire sans le demander |
| Décisions et politiques | Registres de décision, cartes | La source de vérité relue ; un retour en mémoire qui devient une politique passe ici |
| Conception, spécifications, connaissances | La KB de la vault | Liées au code par les liens et la couverture |

**L'état d'avancement ne va pas en mémoire.** À la clôture d'une session, les faits d'état d'avancement qu'elle a écrits en mémoire passent dans la passation (étape de vérification de la mémoire de `strata.handoff`, DEC-2026-10-31-16).

**Date de vérification.** L'en-tête d'un fait de mémoire porte le dernier jour où il a été confirmé correct, sous la forme `verified: YYYY-MM-DD` (DEC-2026-10-31-14·34). Le `modified` du harnais est le jour où il a changé ; `verified` est le jour où on l'a vu encore juste. L'agent l'écrit quand il écrit ou modifie un fait, et la vérification de la passation le met à jour pour les faits que la personne confirme encore justes.

**Nettoyage.** `python3 -m kb hygiene --memory` liste les candidats au nettoyage dans la mémoire du dossier courant, avec leurs motifs : périmé (verified, sinon modified, de plus de 60 jours — configuration utilisateur `memory.stale_days`), sans date, correspondance d'expressions d'état, format inconnu, paires de retours peut-être contradictoires, et un index qui ne correspond pas aux fichiers. L'outil ne fait que lire et n'affiche jamais le corps. Une correspondance d'expressions d'état est une correspondance, pas un verdict : une règle qui nomme un état correspond aussi. Déplacer, fusionner et supprimer ne se fait que pour les faits que la personne approuve un par un. Une suppression déplace le fichier dans `_archive/` du même répertoire, écrit `retired` et `retired_reason` dans son en-tête et retire la ligne de l'index (DEC-2026-10-31-17). `wizard verify` montre la taille de l'index de mémoire et avertit au-delà de 12 Ko sans échouer (DEC-2026-10-31-19). La mémoire de Codex reste hors périmètre pour l'instant (DEC-2026-10-31-13).
