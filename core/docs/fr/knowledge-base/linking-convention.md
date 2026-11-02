# Knowledge Base — Convention de liens

> Source canonique : strata-kit `core/docs/fr/knowledge-base/linking-convention.md` (migré le 2026-10-29 depuis strata `docs/07-knowledge-base/linking-convention.md`, DEC-2026-10-29-11).

## Vue d'ensemble

Les liens à l'intérieur du vault placent la compatibilité avec Obsidian en priorité absolue.
Les références vers ce qui est hors du vault (strata-kit, projects) reposent sur des variables d'environnement.

## Types de liens

### 1. Liens à l'intérieur du vault — utiliser des wikilinks

```markdown
<!-- Référencer un document du même vault -->
[[overview]]
[[decisions/001-use-jwt-auth]]
[[glossary#JWT]]

<!-- Changer le texte affiché -->
[[decisions/001-use-jwt-auth|décision d'authentification JWT]]
```

**Règles :**
- À l'intérieur du vault, utilisez toujours `[[wikilink]]`
- Le chemin est relatif à la racine du vault
- Omettez l'extension `.md`
- Les relations sont visualisées dans le Graph View d'Obsidian

### 2. Références vault → kit — variable d'environnement

```markdown
<!-- Quand un document du vault référence la méthodologie du kit -->
Voir les règles de couches dans `$STRATA_KIT/core/rules/layer-rules.yaml`.
```

**Règles :**
- Les chemins absolus sont interdits
- Utilisez toujours la variable d'environnement `$STRATA_KIT`
- Réduisez au minimum les références au kit depuis les documents du vault (le vault est la connaissance, le kit est la méthodologie)

### 3. Références vault → project — variable d'environnement

```markdown
<!-- Quand un document du vault référence du code du projet -->
Implémentation : `$STRATA_PROJECTS/{project-name}/src/auth/AuthService.ts`
```

**Règles :**
- Utilisez la variable d'environnement `$STRATA_PROJECTS`
- Pour les références au code, n'enregistrez que le chemin (copier du code est interdit)

### 4. CLAUDE.md du projet → références au vault — syntaxe @

```markdown
<!-- Quand le CLAUDE.md d'un projet référence le vault -->
Connaissance du projet : @$STRATA_VAULT/projects/my-api/
```

**Règles :**
- Utilisez la syntaxe de chargement différé `@` de Claude Code
- Le chemin est résolu par la variable d'environnement

### 5. CLAUDE.md du projet → références au kit — syntaxe @

```markdown
<!-- Quand le CLAUDE.md d'un projet référence le kit -->
Règles de couches : @$STRATA_KIT/core/rules/layer-rules.yaml
```

### 6. typed frontmatter link — le type de relation comme donnée

Un wikilink dans le corps ne dit que « lié à ». Le **type** de relation s'écrit dans un champ du frontmatter (DEC-2026-08-19-03). Les générateurs, la validation et les pages de nœud ne lisent que ces champs et ne lisent pas les liens du corps.

| Champ | Direction | Types qui l'utilisent | Signification |
|---|---|---|---|
| `sources` | Knowledge → Archive | KB, pattern | Les sessions et tâches sur lesquelles repose ce document. Obligatoire lors d'une mise à jour de Knowledge |
| `up` | enfant → parent | Tous les documents | Le concept supérieur ou MOC qui contient ce document |
| `decisions` | document → décision | KB, session, task | Les décisions que ce document suit ou a produites |
| `supersedes` / `superseded_by` | nouvelle décision → ancienne / ancienne → nouvelle | decision | Les deux extrémités d'une relation de remplacement. La validation vérifie la symétrie |
| `nodes` | document → nœud thématique | decision, session, task, specification, concept, constraint | L'unité de la table des matières à laquelle appartient ce document |
| `covers` | spécification → surface de code | specification, concept | Les chemins de code, symboles, endpoints et tables dont ce document est la **source de vérité** |
| `related` | document ↔ document | Tous les documents | Relation de mention ou de référence. Ce n'est pas de la propriété |

**Règles :**
- Les valeurs de `sources`, `up`, `decisions`, `supersedes` et `related` sont des `[[wikilink]]`. Les valeurs de `nodes` sont des ids de nœud de toc.yaml, et celles de `covers` sont des pointeurs relatifs au dépôt. Ni les unes ni les autres ne sont des wikilinks.
- Omettez un champ de relation quand il n'a pas de valeur. Si vous laissez un tableau vide, la validation demande si ce vide est intentionnel.
- Écrire la même relation aussi sous forme de wikilink dans le corps est permis (pour le graphe d'Obsidian). Mais la source de vérité est le frontmatter.
- Sources de vérité des formats de valeur : pour `nodes`, `covers`, `doc_change` et `supersedes`, la section « champs de nœud et de couverture » de document-format.md ; pour `sources`, le schéma de frontmatter du même document.

### 7. Règles pour que les liens pointent toujours vers le document en vigueur (DEC-2026-09-30-03)

- **La cible d'un wikilink doit se résoudre par nom de fichier (ou chemin relatif au vault).** N'utilisez pas de liens qui ne se résolvent que par le `id:` du frontmatter ou par `aliases` (comme des ids de tâche), car ils se cassent dans Obsidian. Quand vous déplacez ou renommez un fichier, gardez l'ancien nom dans `aliases:` (pour la recherche et les unlinked mentions), mais corrigez le lien lui-même vers le nouveau nom de fichier comme l'indique le vérificateur.
- **N'enveloppez pas du texte libre dans un lien.** Un lien dont le document cible n'existe pas, comme `[[restdocs 양식 정렬]]`, est interdit. Si une explication est nécessaire, utilisez un texte affiché (`[[session-2026-09-02-x|task05 후속]]`).
- **Remplacez les liens du corps qui pointent vers un document remplacé par des liens vers le document en vigueur.** Les champs de relation de remplacement (`supersedes`, `superseded_by`) et les phrases qui expliquent l'historique sont des exceptions. Le vérificateur ne sait pas les distinguer, donc ce point n'est signalé qu'à titre indicatif (avertissement).
- **Désignez le code par symbole plutôt que par chemin.** Écrivez des noms de classes et de fonctions dans `covers.symbols`, et dans le corps écrivez aussi des symboles comme `CollaboratorCommandService.invite`. N'écrivez les chemins que jusqu'au niveau du module ou du paquet. En effet, les noms de symboles changent rarement même quand les fichiers sont déplacés.
- **Vérification :** `python3 "$STRATA_KIT/kb" link-check` trouve les wikilinks cassés, les liens en texte libre, les liens qui ne se résolvent que par id et les liens du corps vers des documents remplacés. Les violations dans les documents générés ou importés (notes DEC, pages de nœud, documents sources de planification, `_index/`) ne peuvent pas être corrigées à la main ; elles sont donc seulement signalées et ne bloquent pas (l'endroit où corriger est le générateur). La porte de fin de session ne regarde que les documents du projet de cette session. Les violations existantes sont regroupées dans une ligne de base (`$STRATA_VAULT/.kb/link-baseline.json`), et la vérification **n'échoue que s'il y a une nouvelle violation hors de la ligne de base**. La fin de session (`python3 "$STRATA_KIT/kb" ledger close`) arrête la synchronisation du vault sur cette vérification, tandis que la génération de la passation (`python3 "$STRATA_KIT/kb" handoff`) ne fait qu'avertir. Seulement en cas d'urgence, rétrogradez en avertissement avec `STRATA_LINK_CHECK=warn`. Réduisez la ligne de base avec `--shrink-baseline` autant que vous avez corrigé.
- **Recoupement avec le code :** si vous passez `--code-root {project}=<repo>`, il vérifie aussi si les `covers.paths` du KB existent dans le dépôt et si les noms de `covers.symbols` se retrouvent dans le code (uniquement sur une machine qui possède le dépôt de code).

## Interdictions

| Motif interdit | Raison | Alternative |
|---|---|---|
| Chemins absolus dans le vault (`/home/alice/...`) | Non compatibles d'une machine à l'autre | Utiliser `$STRATA_KIT`, `$STRATA_VAULT` |
| Liens Markdown `[text](path)` dans le vault | N'apparaissent pas dans l'Obsidian Graph | Utiliser `[[wikilink]]` |
| Copier des blocs de code | Pourrissement du code | N'enregistrer que des références de chemin |
| Références directes entre projets | Créent une dépendance | Extraire en motif commun dans vault/patterns/ |
| Ne s'appuyer que sur les liens du corps pour le type de relation | Les générateurs et la validation ne peuvent pas le lire | §6 typed frontmatter link |

Les pointeurs de code de `covers` n'ont pas besoin d'être des wikilinks. Un chemin relatif au dépôt dans le frontmatter n'est pas visé par « pas de liens Markdown dans le vault ».

## Intégrations

La syntaxe d'intégration d'Obsidian peut aussi être utilisée :

```markdown
<!-- Intégrer une section précise d'un autre document -->
![[decisions/001-use-jwt-auth#결정]]

<!-- Intégrer une image -->
![[architecture-diagram.png]]
```

Une intégration reflète automatiquement les changements du document référencé ; on la recommande donc plutôt que d'écrire des doublons.
