# Moteur de la KB : contrat de stockage

La base de connaissances est un graphe de documents, de surfaces de code, de décisions, de sessions et de cartes, conservé dans un unique magasin basé sur des fichiers, à côté du vault. Tout ce que contient le magasin est généré à partir de sources (rec.kb.generated-views) ; le magasin est un cache qui peut toujours être reconstruit.

## Pourquoi un seul magasin

Aujourd'hui le vault possède un index FTS5, des pages de nœud, des miroirs de notes de décision, des correspondances de coverage et des lignes de base de liens, chacun produit par son propre script et conservé dans son propre fichier. La décision sur le graphe de code (strata DEC-2026-10-28-05) ajoute des symboles de code et des arêtes d'impact. Les embeddings ajoutent des vecteurs. Si chacun garde son propre fichier, les questions qui comptent (quel document possède cette fonction modifiée ; quelle décision a remplacé la règle sur laquelle cette session s'est appuyée ; quelles sessions ont touché ce nœud) exigent des jointures entre outils. Un seul magasin avec un seul schéma y répond en une requête, et le backend peut changer sans que le schéma change.

## Schéma

```text
nodes(id, kind, project, path, title, status, updated, revision, payload_json)
  kind ∈ {doc, code, decision, session, order, task, card, node, profile}
edges(src, dst, kind, confidence, source_ref, created)
  kind ∈ {covers, supersedes, kb_updates, orders, decisions_made, relay, calls, imports, tests, member_of, links, implementation}
  confidence ∈ {declared, extracted, inferred}
chunks(node_id, seq, heading, text, title, tags, locale, embedding?, meta_json)
  unités de recherche plein texte et vectorielle ; heading·title·tags sont placés à côté du texte pour que l'index FTS (unicode61, quatre colonnes) classe comme l'index legacy ; meta_json contient heading_level·line_start·line_end·char_count. Les documents, les décisions et les ordres partagent une table FTS et une échelle bm25 ; la parité avec le classement de l'index legacy n'est pas un objectif (DEC-2026-10-28-08)
baselines(gate, project, key, recorded)                lignes de base des liens et du coverage
revisions(store_rev, kit_rev, built_at, sources_hash)  provenance de l'ensemble du magasin
```

Les arêtes déclarées proviennent du frontmatter (covers, supersedes, orders, kb_updates, decisions_made) et des enregistrements de décision. Les arêtes extraites et inférées proviennent du fournisseur de graphe (imports, calls, tests) et gardent l'étiquette de confiance du fournisseur. Rien dans le magasin n'est écrit à la main.

## Backends

| Backend | Rôle | Statut |
|---|---|---|
| SQLite (FTS5 + sqlite-vec) | référence : un fichier par vault, sans serveur, intégré au processus MCP | actuel (FTS5), vec en attente |
| DuckDB | analyses sur les mêmes tables (rapports de coverage, fraîcheur, requêtes inter-projets), export parquet pour le partage | adaptateur en attente |
| RocksDB | clé-valeur pour les flux de session à forte écriture issus d'un orchestrateur (paquets de relay, approbations) avant leur intégration dans les nœuds/arêtes | adaptateur en attente |

Tous les backends implémentent le même contrat : `put_nodes`, `put_edges`, `query(sql-like)`, `search_text`, `search_vector`, `rebuild(sources)`. Le moteur ne dépend jamais d'une fonctionnalité propre à un backend en dehors de son adaptateur.

## Fournisseurs

| Fournisseur | Produit | Contrat |
|---|---|---|
| scanner du vault | nœuds doc (chaque fichier markdown ; ceux qui sont indexés ont des chunks, les miroirs générés sont signalés), arêtes déclarées, arêtes `links` du corps | frontmatter + taxonomy |
| enregistrements de décision | nœuds decision, arêtes supersedes | sortie du decision writer |
| graphe de code — le fournisseur propre au kit (`kb/providers/code_graph.py`) | par dépôt : nœuds de code répertoire · fichier · symbole de type (fichiers suivis par git uniquement ; Kotlin · Java · TS/JS · Python), `member_of` (extracted), `imports` (extracted ; les imports avec joker et de package sont inferred et pointent vers le répertoire), `tests` (inferred). Résout les cibles covers du vault (`code:<p>:paths:<dir>/`, `code:<p>:symbols:<Name>`) | strata DEC-2026-10-28-05. `python3 -m kb code deps · impact · tests-for · symbol · owner-gate` ; flow(request) reste du ressort d'un adaptateur externe facultatif |
| flux de l'orchestrateur (Quilt) | arêtes de relay et d'approbation entre nœuds de session | rec.decision.orchestrator-decisions-flow-to-records |
| embedder (local ou cloud sur option) | vecteurs de chunks | sensible à la locale ; jamais requis pour que le moteur fonctionne |

## Portes (gates) qui lisent le magasin

- porte de coverage : nœuds de code modifiés → arêtes covers → document propriétaire ; un nœud modifié sans propriétaire et sans déclaration doc_change est une nouvelle violation (rec.kb.covers-owner).
- porte de liens : les wikilinks et liens markdown du corps sont des arêtes `links` (source_ref consigne comment la cible a été résolue : file · id · alias · none · md). Les liens cassés, ceux résolus uniquement par id ou uniquement par alias, et les documents de connaissance qui pointent vers des cibles remplacées sont des violations au-delà de la ligne de base (rec.kb.link-currency). La ligne de base de référence reste dans `.kb/link-baseline.json` ; la table baselines du magasin en est le miroir. Les cibles de lien non markdown et les vérifications `--code-root` sont confirmées sur le système de fichiers et dans git (DEC-2026-10-28-07).
- fraîcheur : nœuds doc dont la révision du code couvert est plus récente que leur champ updated.
- recherche : une table FTS (bm25) sur heading·text·title·tags ; les vecteurs denses du fournisseur embedder (BAAI/bge-m3, local) sont mis en cache dans `embeddings(model, text_hash, dim, vector)` et rattachés aux chunks, cosinus par force brute (pas besoin d'ANN à cette échelle) ; hybride = reciprocal-rank fusion des deux. `python3 -m kb search-eval` mesure le recall@k par rapport au jeu de requêtes du vault (DEC-2026-10-28-09).
- convergence : nœud de spécification visée face au nœud de document as-built pour le même sujet (rec.spec.desired-vs-as-built).

## Migration depuis strata/scripts

Le moteur a atterri dans `strata-kit/kb/` selon l'approche navette (strata-kit DEC-2026-10-28-01 de ce dépôt) : chaque `strata/scripts/<name>.py` est un appel léger vers `strata-kit/kb`, les hooks continuent de fonctionner, et les navettes sont supprimées lorsque tous les appelants pointent vers le kit.

Le premier jalon, la parité, a été franchi ; le suivant a retiré l'index FTS legacy (`.kb/kb.sqlite`, DEC-2026-10-28-13). Le vault ne contient désormais qu'un seul magasin.

- `python3 -m kb build-index` est le build de fin de session : il reconstruit l'ensemble du magasin, puis en dérive les pages de nœud (`kb.views.node_pages`), les sortspecs d'Obsidian, la boîte de revue (`.kb/review-candidates.json`, `_index/review-needed.md`), `manifest.json` et les avertissements de validation de la taxonomy (une violation block sort avec exit 2). `--project` ne restreint que le rapport ; le magasin est toujours complet.
- Les règles des documents (découverte, frontmatter, chunks, fusion de la taxonomy, validation) vivent en un seul endroit, `kb/docrules.py`. Le scanner place `discovered` (l'ensemble découvert) et `diagnostics` (résultats de validation) dans le payload de chaque nœud de document, de sorte que le build signale les avertissements sans index.
- La fraîcheur relève de `engine.ensure_fresh_store` (mtime des sources). L'ancien `kb_freshness.py` et le build incrémental par hash du manifest n'existent plus.
- Preuve : le 2026-10-28, le constructeur d'origine (strata@b4b0c86) et `kb build-index` ont produit les mêmes pages de nœud, sortspecs, boîte de revue, fichiers du manifest, lignes d'avertissement et code de sortie sur deux copies du vrai vault (760 documents, 66 pages de nœud). Les scripts de comparaison ont été supprimés une fois l'index legacy retiré (ordre 2026.10.29-11).
