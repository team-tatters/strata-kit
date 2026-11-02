# Knowledge Base — Protocole d'indexation

> Source canonique : strata-kit `core/docs/fr/knowledge-base/indexing-protocol.md` (migré le 2026-10-29 depuis strata `docs/07-knowledge-base/indexing-protocol.md`, DEC-2026-10-29-11).

> **Mis à jour le 2026-10-29** : ce document décrit le moteur actuel (un seul `store.sqlite`, `python3 "$STRATA_KIT/kb"`).
> L'ancien `.kb/kb.sqlite`, la construction incrémentale par hash de manifest et la conception sqlite-vec ont été abandonnés (DEC-2026-10-28-13).
> La source canonique du schéma de stockage, des backends et des portes (gate) est `core/docs/fr/kb-engine.md` ; ce document traite du périmètre d'indexation, de l'usage de la recherche et des vues générées.

## Vue d'ensemble

Les documents KB du vault sont indexés par fragments (chunks) dans `store.sqlite`, ce qui réduit la consommation de tokens de l'agent et permet une recherche précise.
L'index est un cache qu'on peut reconstruire à tout moment à partir de ses sources (documents du vault, enregistrements de décision (decision record), surface de code), et chaque environnement le construit en local.

## Définition du problème

| Problème | Description |
|---|---|
| Parcours complet imposé | Pour atteindre la section voulue, l'agent doit lire _index.md puis le fichier entier |
| Consommation de tokens entre fichiers | Parcourir 17 fichiers (68K chars) gaspille la fenêtre de contexte |
| Absence d'ordre | Les pages n'ont pas d'ordre logique entre elles, et l'agent doit décider comment naviguer |
| Pas de recherche sémantique | Sans correspondance de mots-clés, impossible de trouver les documents liés (complété par la recherche par embeddings) |

## Phases

| Phase | Contenu | État |
|---|---|---|
| **FTS** | FTS5 (bm25) par chunk + tri par `page_order` du frontmatter | Appliqué — la fraîcheur est vérifiée automatiquement à l'entrée de la recherche |
| **Vectoriel / hybride** | Embeddings locaux BAAI/bge-m3 + fusion RRF avec FTS | Implémenté — les vecteurs n'existent qu'après avoir lancé `python3 "$STRATA_KIT/kb" embed` (DEC-2026-10-28-09). Le mode par défaut de MCP `search_docs` est hybrid ; celui de la CLI `kb search` est FTS (bascule avec `--semantic` ou `--hybrid`) |

L'ancienne répartition en « Phase 1 (FTS5 + hash de manifest) / Phase 2 (sqlite-vec, `--with-vectors`, implémenté mais non appliqué) » a été abandonnée. L'index n'est pas scindé en deux ; il y a un seul store, et les vecteurs se rattachent aux chunks du store.

## Architecture

### Organisation des fichiers

```
vault/
├── .kb/
│   ├── store.sqlite            # .gitignore — l'unique index (résultat d'une construction locale)
│   ├── manifest.json           # non suivi — métadonnées de l'index, produites sur chaque machine (DEC-2026-10-29-04)
│   ├── link-baseline.json      # ligne de base de la porte des liens (mise à jour uniquement à la baisse)
│   └── review-candidates.json  # .gitignore — candidats à la revue (généré)
│
├── .gitignore
└── projects/{name}/knowledge-base/
    └── *.md                    # sources de l'index
```

`.kb/store.sqlite` et ses fichiers `-wal` et `-shm` figurent dans le `.gitignore` du vault. Pour vérifier, voir la section « KB store » de `.gitignore`.
Le schéma est défini par le code (`kb/store.py`), pas par un fichier. Il n'existe pas de `schema.sql` (DEC-2026-10-28-13).

### Organisation du moteur de construction

```
strata-kit/
└── kb/                         # suivi par git — moteur d'indexation (python3 "$STRATA_KIT/kb" build-index)
```

Le moteur de construction se trouve dans le dépôt strata-kit. À l'exécution, il localise le vault grâce à la variable d'environnement `$STRATA_VAULT`.

### Flux de données

```
Modifier un fichier MD → git commit + push
                    ↓
Autre environnement : git pull
                    ↓
À l'entrée de la recherche (kb search / MCP), automatiquement :  engine.ensure_fresh_store
  comparer le mtime de la source au built_at du store (sans hash, faible coût)
    ├─ frais → interroger directement
    ├─ stale → reconstruire tout le store (1-2 s)
    └─ store absent (nouvelle machine) → généré automatiquement par le même chemin
                    ↓
store.sqlite (nodes · edges · chunks + FTS5 · cache d'embeddings)
                    ↓
Agent : kb search / MCP search_docs → renvoie chunk + file:line
```

- Il n'y a pas de réindexation incrémentale. Le store est reconstruit en entier à chaque fois (1-2 s). La comparaison de hash de manifest qui ne retenait que les fichiers modifiés a été abandonnée.
- L'exécution manuelle (`python3 "$STRATA_KIT/kb" build-index`) et MCP `build_index` sont possibles, mais **le chemin quotidien est automatique**.
- Un échec de la vérification de fraîcheur ou de la reconstruction ne bloque pas les requêtes (avertissement, puis utilisation du store existant). Échappatoire : `KB_NO_REFRESH=1`.
- Après avoir reconstruit le store, `build-index` émet les vues générées (pages de nœud, sortspec Obsidian, Inbox de revue, `manifest.json`) et les avertissements de validation de taxonomy. En cas de violation block, il sort avec exit 2. Pour le comportement et les rôles, voir `core/docs/fr/kb-engine.md`.
- `build-index` ne calcule pas les embeddings. `python3 "$STRATA_KIT/kb" embed` ne calcule que les chunks manquants et les place dans le store ; les vecteurs calculés restent dans le cache `embeddings` et sont réutilisés même quand le store est reconstruit.

### Couverture de l'index (2026.08.19-06 B1)

- **Knowledge** : `projects/*/knowledge-base/` — indexation en texte intégral (existant). Depuis le 2026-09-08, `patterns/`, `_index/glossary.md` (valeur de projet `vault`) et `projects/*/overview.md` sont aussi indexés en texte intégral — conformément au périmètre Knowledge du tableau à trois couches de vault-structure.md.
- **Archive** : fichiers `.md` de `projects/*/sessions/` et `tasks/` — seuls sont indexés **les métadonnées (topic · orders · kb_updates · decisions_made · nodes · doc_change) +
  la partie de résumé du corps (40 premières lignes)**. `nodes` figure dans la liste blanche, car sans lui on ne peut pas construire la facette « historique de travail » d'une page de nœud. On les distingue et les filtre par les facettes category=`archive`, topic=`sessions|tasks`
  (filtre `category` de MCP). Le but est de répondre par la recherche à « dans quelle session cela a-t-il été traité ? ». **Archive et Planning sont exclus des valeurs par défaut de la recherche** (DEC-2026-09-30-03) —
  pour inclure l'historique, utilisez `kb search --include-history`, MCP `search_docs(include_history=true)` ou indiquez `category` explicitement. `--include-history` recherche aussi les enregistrements de décision et d'ordre.
- La validation KB (lifecycle, etc.) ne s'applique pas à Archive — le status du ledger (open/closed) est hors du contrat KB.
  **Exception** : `node_id_check` (la valeur de nodes figure-t-elle dans toc.yaml ?) s'applique aussi à Archive, car une faute de frappe dans un nœud fait disparaître la session de la facette d'historique de travail.
- **Planning** : `projects/*/planning/{source}/` — **indexation en texte intégral** du texte d'origine de planification + validation KB (required_fields · lifecycle_override · node_id). Facettes category=`planning`, topic=`{source}`. C'est la source de la facette « planification » de la page de nœud. Son status est un état de planification (pas active), donc hors de la politique des candidats à la revue (DEC-2026-09-09-01).
- Les **pages de nœud** (`projects/*/nodes/`) sont `indexed: metadata` — seulement la partie de résumé, puisque le texte d'origine de chaque facette est déjà indexé.
- Les **notes DEC** (`projects/*/decisions/`) ne sont pas indexées comme documents (inchangé). Le provider d'enregistrements de décision place les décisions dans le store comme nœuds de décision, et le générateur de pages de nœud lit `nodes` dans l'enregistrement canonique pour déterminer le nœud d'appartenance d'une décision.
- Les liens symboliques (`latest.md`) et les yaml ne sont pas indexés.

## KB Result Contract — abandonné (DEC-2026-08-19-06)

Le contrat commun de schéma de résultats a été **abandonné**. Depuis son établissement, aucun consommateur (kb-search, strata-mcp) ne l'a implémenté,
chacun fonctionne de façon stable avec sa propre forme de résultat, et les multiples consommateurs que le contrat présupposait (strata-kb-server, Hub) n'existent pas.

- **Condition de rétablissement** : si une seconde surface de consommation (comme Hub) apparaît réellement, on repense le contrat à partir des champs réellement utilisés à ce moment-là.
- Le générateur de pages de nœud produit des sorties à l'intérieur du vault ; ce n'est donc pas une « seconde surface de consommation ». Cette décision d'abandon n'est pas remise en cause.
- Pour le texte intégral du contrat avant l'abandon, voir l'historique git (ce fichier, avant le 2026-08-19).

## Schéma de stockage

La source canonique du schéma (`nodes`, `edges`, `chunks`, `baselines`, `revisions`, la table virtuelle FTS5 `chunks_fts` et le cache `embeddings`) est la section « Schéma » de `core/docs/fr/kb-engine.md`. On n'indique ici que ce dont la recherche a besoin.

- L'unité de recherche est `chunks`. Un chunk possède heading, text, title, tags et `meta_json` (heading_level · line_start · line_end · char_count). Documents, décisions et ordres partagent une table FTS et une échelle bm25.
- FTS5 indexe avec `unicode61` les quatre colonnes heading, text, title et tags.
- Les facettes de taxonomy du document (category · topic · section_name · page_order, etc.) sont dans le payload du nœud du document, et sont lues par les filtres de `kb search` et par le tri de `--toc`.
- Les liens sont des arêtes `links` ; les relations entre documents (supersedes, etc.) et `covers` sont aussi des arêtes. L'ancienne table `document_links` n'existe pas.

L'ancien schéma (les tables `documents`, `chunks`, `chunks_fts` (colonnes doc_title et doc_tags), `document_links` et `coverage`, les colonnes `sha256` et `section_name`, et `chunks_vec`) appartient à l'index legacy (`.kb/kb.sqlite`) et a été abandonné par DEC-2026-10-28-13. L'interrogation directe en SQL a disparu avec lui. Les requêtes se font par `kb search`, MCP et `kb coverage`.

### Nœuds thématiques et couverture

Le frontmatter `stable_id`, `nodes`, `covers` et `doc_change` d'un document devient le payload de nœud du store et les arêtes `covers`. Les règles de requête inverse de la surface de code vers le document sont inchangées.

- « Quelle spécification possède ce chemin ? » : `python3 "$STRATA_KIT/kb" coverage resolve|nodes|unowned|docs-to-update`
- « Quel document est la forme finale de ce nœud ? » : `kb coverage node` (utilisé par le générateur de pages de nœud)
- « Le document propriétaire a-t-il été mis à jour après le changement de ce chemin ? » : la porte de fin de session `kb coverage-gate`
- L'arbre des nœuds lit directement `_meta/toc.yaml`. `endpoints` et `tables` ne sont pas résolus comme chemins de fichier ; ils servent à l'affichage sur les pages de nœud.

Validations à la construction (toutes en warn) : `node_id_check` (format, existence et inscription dans toc.yaml — s'applique aussi à Archive), `covers_path_check` (structure · chemins relatifs · entrées au niveau fichier interdites),
`supersedes_symmetry_check` (A.supersedes=B ⇔ B.status=superseded ∧ B.superseded_by=A), et les valeurs et motifs de doc_change. Les candidats à la revue sont consignés comme artefact généré (l'Inbox de revue), et la transition ne se fait que par une commande explicite (`build-index --apply-review`).

## Détection des changements et synchronisation multi-environnements

La détection des changements compare le mtime du fichier source au `built_at` du store (`engine.ensure_fresh_store`), et non un hash de manifest. Il n'y a donc pas d'état d'index sur lequel les environnements doivent s'accorder. Seuls sont partagés les documents du vault et les enregistrements de décision ; chaque environnement construit le store en local.

```
[Environnement A — modification de documents]
1. Modifier les fichiers MD
2. git commit + push   (en fin de session, handoff synchronise le vault)

[Environnement B — synchronisation]
1. git pull
2. À l'entrée de la recherche, le store est reconstruit automatiquement — à la main : python3 "$STRATA_KIT/kb" build-index
```

**Principe clé :** le store est un cache, il n'est donc pas versionné dans git (`.gitignore`). Pas de conflits binaires, et n'importe quelle machine reproduit le même résultat à partir des mêmes sources.

DEC-2026-10-29-04 décide quels artefacts générés sont suivis et qui les écrit.

| Artefact | Suivi | Écrit par |
|---|---|---|
| `.kb/store.sqlite` | Non | L'entrée de recherche de chaque machine et `build-index` |
| `.kb/manifest.json` | Non (trace de comparaison par machine) | Le `build-index` de chaque machine |
| Notes DEC (`projects/*/decisions/`) | Oui | La CLI de décision — la session qui a consigné la décision les commite avec l'enregistrement |
| Pages de nœud et `_index/review-needed.md` | Oui | Le librarian, une fois par jour, avec `kb views-publish` (après build-index, commit-push de ces seuls fichiers). Le `build-index` d'une session ordinaire ne met à jour que l'index local et ne commite pas ces fichiers |
| `.kb/link-baseline.json` | Oui | Mis à jour uniquement à la baisse |

L'ancienne méthode « partager `manifest.json` via git pour s'accorder sur l'état des fichiers et n'indexer que les changements » était une conception legacy et a été abandonnée (DEC-2026-10-28-13, DEC-2026-10-29-04).

## Protocole de recherche de l'agent

### Priorité de recherche

```
① Recherche FTS5 par mot-clé (quand on connaît le terme exact)
② Recherche FTS5 composée (combinaisons AND/OR, filtres --category et --topic)
③ Consultation des métadonnées (--toc sommaire trié, --doc chunks d'un document)
④ Recherche hybride / sémantique (requêtes en langage naturel — nécessite des vecteurs)
```

Les agents utilisent `kb search` ou MCP `search_docs` (mode : hybrid par défaut · dense · fts), et non SQL. Les résultats renvoient l'emplacement `file:Lligne-ligne` du chunk et le nombre de caractères.

### Exemples d'utilisation

**Recherche par mot-clé — renvoie les chunks pertinents :**
```bash
python3 "$STRATA_KIT/kb" search "환불수수료" --limit 5
```

**Recherche composée — AND + filtres :**
```bash
python3 "$STRATA_KIT/kb" search "정산식 AND Payment" --category domain
python3 "$STRATA_KIT/kb" search "정산식" --category domain --topic orders
```

**Consultation du sommaire trié :**
```bash
python3 "$STRATA_KIT/kb" search --toc --category domain
```

**Renvoi d'un emplacement précis — enchaînement avec l'outil Read :**
```
kb search "FormulaBaseStructure"
# Résultat : domain/orders/payment-shipping.md  emplacement : L46-101
# → passer offset=46, limit=55 à l'outil Read
```

## Référence de la syntaxe de recherche FTS5

`kb search` entoure de guillemets chaque token de la requête avant de la passer à FTS5. Seule la syntaxe ci-dessous fonctionne donc.

| Syntaxe | Exemple | Description |
|---|---|---|
| Mot-clé unique | `환불수수료` | Chunks contenant ce token |
| Séparés par des espaces | `Transactional Composite` | Contient les deux tokens (AND) |
| AND | `Transactional AND Composite` | Contient les deux tokens |
| OR | `Payment OR Shipping` | En contient au moins un |
| NOT | `환불 NOT Coupon` | Condition d'exclusion |
| prefix | `Refund*` | Tokens commençant par Refund |

Syntaxe qui ne fonctionne pas : spécificateurs de colonne (`doc_tags:orders`, `tags:orders` — aucun résultat ; utilisez à la place les filtres `--category` et `--topic`, et `--tags` pour ne regarder que les étiquettes), recherche de phrase (`"REST Docs"` — les guillemets sont retirés et cela devient un AND de deux tokens) et `NEAR`. Les noms de colonnes `doc_tags:` et `content:` des documents antérieurs sont des colonnes de l'index legacy (les colonnes actuelles sont heading, text, title et tags).

## Extension du frontmatter — le champ page_order

On ajoute un champ de tri au frontmatter du document-format.md existant :

```yaml
---
title: "Order Payment & Shipping"
type: concept        # domain est une catégorie (répertoire), pas un type de document
project: shop-api
tags: [orders, payment, shipping]
created: 2026-04-07
updated: 2026-04-07
page_order: 3              # ★ nouveau — ordre du document dans la section
---
```

`--toc` trie d'abord selon l'ordre de category et de topic de la taxonomy, puis, à l'intérieur, selon `page_order` (les documents des répertoires à préfixe NN antérieurs à la taxonomy utilisent `section_order`).
`page_order` est indiqué explicitement dans le frontmatter pour définir l'ordre logique à l'intérieur de la section.

## Économie de tokens (mesurée)

Les chiffres ci-dessous ont été mesurés sur le vault d'un projet backend à l'époque de l'index FTS5 legacy (2026-04) (15 documents, 210 chunks, 68K chars). Le principe de lecture par chunk est le même dans le store actuel, mais les chiffres n'ont jamais été re-mesurés avec le moteur actuel.

| Requête de recherche | Avant (tout lire) | FTS5 (chunk) | Économie |
|-----------|-----------------|-------------|--------|
| "환불수수료" | 68,242 chars | 3,473 chars | **95%** |
| "TransactionalExecutor" | 68,242 chars | 1,181 chars | **99%** |
| "정산식 AND Payment" | 13,939 chars (3 fichiers) | 6,758 chars | **52%** |

## Recherche vectorielle (hybride bge-m3)

Source canonique : la section de recherche de `core/docs/fr/kb-engine.md`, DEC-2026-10-28-09.

### Résumé

| Élément | Actuel |
|---|---|
| Modèle | BAAI/bge-m3, exécution locale (sentence-transformers ; MPS sur Apple Silicon), vecteurs normalisés de 1024 dimensions |
| Stockage | `chunks.embedding` dans le store + le cache `embeddings(model, text_hash, dim, vector)` qui survit aux reconstructions |
| Recherche vectorielle | cosinus numpy en force brute (quelques ms pour environ 7 000 chunks — pas besoin d'ANN) |
| Hybride | Fusion RRF (k=60) de FTS (bm25) et des vecteurs |
| Jugement de l'efficacité | `python3 "$STRATA_KIT/kb" search-eval` — recall@k (fts · dense · hybrid) sur le jeu de requêtes de `_meta/search-eval.yaml` du vault |
| Calcul des embeddings | `python3 "$STRATA_KIT/kb" embed` (seulement les chunks manquants. `--model` · `--batch` · `--max-seq` · `--max N`) |

### Alternatives et raisons de leur non-adoption

| Alternative | Décision |
|---|---|
| sqlite-vec | On basculera via un adaptateur au-delà de 100 000 chunks (DEC-2026-10-28-09). Inutile pour l'instant |
| BD vectorielles externes comme LanceDB | Entre en conflit avec le contrat à stockage unique (DEC-2026-10-28-04) et n'apporte aucun gain à cette échelle — non adopté |
| khoj | Application avec son propre hôte, son UI et sa BD — non adopté |
| paraphrase-multilingual-MiniLM-L12-v2 (384 dimensions) | Le modèle de la conception legacy. Remplacé par bge-m3 |
| ONNX Runtime · API d'embeddings dans le cloud | Non adoptés. Le provider d'embedder est remplaçable (kb-engine.md), mais l'implémentation actuelle ne comprend que bge-m3 en local |

L'ancien `build-index --with-vectors`, `apsw` (pour charger sqlite-vec) et la table virtuelle `chunks_vec` relevaient d'une conception legacy et n'existent pas.

## Aide-mémoire des outils de recherche

### Construction

```bash
# Au quotidien : inutile — si le store est stale, il est reconstruit automatiquement à l'entrée de la recherche

# Construction manuelle du store + vues générées (pages de nœud · sortspec · Inbox de revue · manifest)
python3 "$STRATA_KIT/kb" build-index

# Limiter seulement le périmètre du rapport à un projet (le store reste toujours entier)
python3 "$STRATA_KIT/kb" build-index --project shop-api

# Reconstruire seulement le store / statistiques
python3 "$STRATA_KIT/kb" build-store
python3 "$STRATA_KIT/kb" store-stats

# Calculer les embeddings des chunks manquants (avant la recherche sémantique / hybride)
python3 "$STRATA_KIT/kb" embed

# Faire passer les candidats à la revue à status: review-needed et reconstruire
python3 "$STRATA_KIT/kb" build-index --apply-review
```

`--force` est une option de compatibilité sans effet (le store est reconstruit en entier à chaque fois). Il n'y a pas de `--with-vectors`.

### Recherche (kb search)

> `kb search` ci-dessous est l'abréviation de `python3 "$STRATA_KIT/kb" search`.

```bash
# ─── Recherche FTS5 par mot-clé ───
kb search "환불수수료"                          # mot-clé unique
kb search "Transactional AND Composite"       # AND composé
kb search "Payment OR Shipping"                  # OR
kb search "Refund*"                         # prefix
kb search "정산식" --category domain --topic orders   # filtres de catégorie et de sujet (au lieu de la syntaxe de spécificateur de colonne)
kb search "환불수수료" --limit 10 --content      # nombre de résultats + aperçu du contenu
kb search "jwt" --category architecture       # filtre de catégorie (--topic, --status et --project existent aussi)
kb search "환불수수료" --include-history         # inclut le texte des sessions, tâches et planification, ainsi que décisions et ordres

# ─── Recherche sémantique / hybride (après avoir créé les vecteurs avec kb embed) ───
kb search "환불 금액을 계산하는 흐름?" --semantic
kb search "인증 토큰 만료 시 처리" --hybrid --content

# ─── Navigation ───
kb search --toc                               # sommaire complet (trié)
kb search --toc --category domain             # filtre de catégorie
kb search --doc "domain/orders/payment-shipping.md"       # sommaire des chunks d'un document
kb search --tags orders                          # recherche par étiquette (étiquettes seules, sans terme de requête)
kb search --stats                             # statistiques de l'index
```

`--section` est un filtre de compatibilité pour les répertoires NN-section antérieurs à la taxonomy. Pour les nouveaux documents, utilisez `--category` et `--topic`.

### FTS5 ou sémantique — lequel utiliser et quand

| Situation | Recommandé | Raison |
|------|------|------|
| On connaît le nom exact de la classe ou de la fonction | FTS5 | `FormulaBaseStructure` → correspondance exacte, immédiate |
| Recherche d'un terme précis | FTS5 | `환불수수료`, `TransactionalExecutor` → rank BM25 |
| Question en langage naturel | **Sémantique / hybride** | "환불 금액을 계산하는 흐름?" → surmonte l'absence de correspondance de mots-clés |
| FTS5 ne renvoie rien | **Sémantique** | "인증 토큰 만료 처리" → 0 résultat en FTS5, la sémantique en renvoie |
| Après avoir restreint par catégorie/sujet | FTS5 | filtre `--category domain --topic orders` |
| On ne sait pas par où commencer la lecture | `--toc` | Sommaire trié → saisir la structure des documents |

## Guide de découpage des mots-clés pour FTS5

Le tokenizer `unicode61` de FTS5 **ne sépare les tokens que selon les espaces et la ponctuation**.
Il ne fait aucune analyse morphologique du coréen ; la stratégie de découpage des mots-clés est donc importante lors de la recherche.

### Problème : pourquoi il faut découper les mots-clés

```
Texte d'origine :  "환불수수료 변경 시 재계산 처리"
              ↓ tokenisation unicode61
Tokens :       ["환불수수료", "변경", "시", "재계산", "처리"]
```

| Requête de recherche | Correspondance | Raison |
|-----------|----------|------|
| `환불수수료` | ✅ | Token identique |
| `환불수수료변경` | ❌ | Le token « 환불수수료변경 » n'existe pas |
| `환불수수료 AND 변경` | ✅ | Les deux tokens existent séparément |
| `환불` | ❌ | Une sous-chaîne de « 환불수수료 » ne correspond pas |
| `환불*` | ✅ | La recherche par prefix correspond à « 환불수수료 » |

### Règles de découpage

**1. Séparez par des espaces les termes coréens composés et cherchez avec AND**

```bash
# ❌ Collés : aucune correspondance
kb search "환불수수료변경"

# ✅ Découpé + AND
kb search "환불수수료 AND 변경"
```

**2. Utilisez prefix (*) quand il faut une correspondance partielle**

```bash
# ❌ « 환불 » seul ne trouve pas « 환불수수료 »
kb search "환불"

# ✅ Le prefix correspond à « 환불수수료 », « 환불금액 » et « 환불요청 »
kb search "환불*"
```

**3. Les noms de classe anglais ne sont pas sensibles à la casse, et il n'y a pas de découpage CamelCase**

```bash
# ✅ unicode61 normalise la casse
kb search "formulabasestructure"      # correspond à FormulaBaseStructure

# ❌ Le découpage à l'intérieur du CamelCase ne marche pas
kb search "Formula AND Base"          # les deux mots doivent exister séparément

# ✅ Contournez avec un prefix
kb search "Formula*"
```

**4. Requêtes mêlant coréen et anglais**

```bash
# ✅ Reliez par AND les tokens de chaque langue
kb search "Payment AND 정산식"

# ✅ Combinez filtres de catégorie et de sujet avec la recherche de contenu
kb search "Payment" --category domain --topic orders
```

**5. Si le découpage des mots-clés ne suffit pas → passez à la recherche sémantique / hybride**

```bash
# Requête en langage naturel difficile à trouver avec FTS5
kb search "인증 토큰이 만료되면 어떻게 처리하나요?" --hybrid
```

La part que FTS manque à cause des particules et des mots composés du coréen (4-8 % sur le jeu d'évaluation) est confiée aux vecteurs, et il a été décidé de la renforcer après évaluation avec une table trigram FTS5 ou bge-m3 sparse (DEC-2026-10-28-09).

### Arbre de décision de recherche de l'agent

```
Question reçue
  │
  ├─ Connaît-on le terme/nom de classe exact ?
  │   └─ OUI → FTS5 : kb search "terme"
  │
  ├─ Terme coréen composé ?
  │   └─ OUI → FTS5 : découper par espaces + AND
  │            ex. : "환불수수료 AND 변경 AND 재계산"
  │
  ├─ Correspondance partielle nécessaire ?
  │   └─ OUI → FTS5 : prefix(*)
  │            ex. : "Refund*", "환불*"
  │
  ├─ Question en langage naturel ?
  │   └─ OUI → hybride/sémantique : kb search "question" --hybrid
  │
  └─ FTS5 a renvoyé 0 résultat ?
      └─ Réessayer en sémantique
```

## Décisions clés de conception

| Décision | Justification |
|------|------|
| Un seul `store.sqlite` est l'unique index et n'est pas versionné dans git | Supprime les conflits de merge binaires et la duplication de schéma et de garde de fraîcheur qu'engendraient deux index (DEC-2026-10-28-13) |
| La fraîcheur est une comparaison du mtime de la source, et le store est reconstruit en entier à chaque fois | À 1-2 s l'incrémental est inutile. Une construction partielle qui tronquerait le store ferait perdre les vues des autres projets (DEC-2026-10-28-13) |
| `manifest.json` n'est pas suivi | Trace de comparaison par machine que personne ne lit (DEC-2026-10-29-04) |
| Le moteur de construction se trouve dans le dépôt strata-kit | Géré comme outil de la méthodologie elle-même, indépendant des projets |
| Le frontmatter est la single source of truth | Obsidian, FTS5 et Dataview consultent les mêmes données |
| Le chunk porte ensemble heading, title, tags et meta | Une table FTS et une échelle bm25 classent documents, décisions et ordres, et affichent l'emplacement (DEC-2026-10-28-08) |
| Embeddings bge-m3 + force brute numpy + RRF avec FTS | Performant sur le coréen et l'anglais mêlés, et ses 8192 tokens évitent de tronquer les longs chunks. Pas d'ANN nécessaire à cette échelle (DEC-2026-10-28-09) |
| L'effet des vecteurs est jugé par le recall@k d'un jeu d'évaluation | `kb search-eval` |

Décisions legacy abandonnées : suivi git de manifest.json et `.gitignore` de kb.sqlite, construction incrémentale par hash SHA256, `paraphrase-multilingual-MiniLM-L12-v2`, `apsw` et sqlite-vec, et l'interprétation de cosine distance de 0 à 1 (pour MiniLM). Toutes ont disparu avec l'index legacy par DEC-2026-10-28-13 ou ont été remplacées par DEC-2026-10-28-09.

## Résumé des dépendances

| Paquet | Usage | Quand il est nécessaire |
|--------|------|-----------|
| Python 3 | Exécuter `kb` | Toujours |
| SQLite 3 (avec FTS5) | store | Toujours (fourni par l'OS) |
| PyYAML | Analyse du frontmatter et de la taxonomy | Toujours |
| sentence-transformers (avec PyTorch, ~500MB) | Calcul des embeddings bge-m3 | Seulement avec `kb embed` |
| numpy | Cosinus des vecteurs | En recherche sémantique / hybride |

sqlite-vec et apsw ne sont plus utilisés. Sans embeddings, la recherche FTS et toutes les vues générées fonctionnent. La liste exacte des dépendances se fonde sur les import de `kb/`.

### Environnement d'exécution

- Pas de processus résident. Pas de GPU nécessaire (sur Apple Silicon, les embeddings sont rapides grâce à MPS).
- La reconstruction du store prend 1-2 s (environ 760 documents et 7 000 chunks, mesuré dans DEC-2026-10-28-13 et 09).
- Le calcul des embeddings est long la première fois ; ensuite, seuls les chunks modifiés sont calculés, grâce au cache `embeddings`.

## Limites

| Limite | Description | Réponse |
|---|---|---|
| Morphologie coréenne (FTS5) | unicode61 ne sépare que par espaces — « 환불수수료변경 » ne correspond pas | Suivre le guide de découpage des mots-clés, utiliser la recherche sémantique en parallèle |
| Pas de découpage CamelCase (FTS5) | FormulaBaseStructure → un seul token | Recherche par prefix (*) ou saisie du nom complet |
| Pas de spécificateur de colonne, de phrase ni de NEAR | Tous les tokens de la requête sont entourés de guillemets, la syntaxe avancée de FTS5 ne fonctionne donc pas | Utiliser à la place les filtres `--category` et `--topic` et AND |
| La recherche sémantique demande une préparation | Il faut d'abord créer les vecteurs avec `kb embed`, et la première requête est lente à cause du chargement du modèle | FTS5 en premier, la sémantique en fallback |
| Rank BM25 uniquement (FTS) | Aucune pondération par structure ou importance du document | Trier le sommaire avec page_order, utiliser l'hybride en parallèle |
| Obsidian non exécuté | Les requêtes Dataview sont impossibles | FTS5/sémantique fonctionnent indépendamment d'Obsidian |
