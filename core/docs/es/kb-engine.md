# Motor de la KB: contrato de almacenamiento

La base de conocimiento es un grafo de documentos, superficies de código, decisiones, sesiones y tarjetas, contenido en un único almacén basado en archivos junto al vault. Todo lo que hay en el almacén se genera a partir de fuentes (rec.kb.generated-views); el almacén es una caché que siempre puede reconstruirse.

## Por qué un solo almacén

Hoy el vault tiene un índice FTS5, páginas de nodo, espejos de notas de decisión, mapeos de coverage y líneas base de enlaces, cada uno producido por su propio script y guardado en su propio archivo. La decisión del grafo de código (strata DEC-2026-10-28-05) añade símbolos de código y aristas de impacto. Los embeddings añaden vectores. Si cada uno conserva su propio archivo, las preguntas que importan (qué documento es dueño de esta función modificada; qué decisión sustituyó a la regla en la que se apoyó esta sesión; qué sesiones tocaron este nodo) requieren uniones entre herramientas. Un único almacén con un único esquema las responde en una sola consulta, y el backend puede cambiar sin que cambie el esquema.

## Esquema

```text
nodes(id, kind, project, path, title, status, updated, revision, payload_json)
  kind ∈ {doc, code, decision, session, order, task, card, node, profile}
edges(src, dst, kind, confidence, source_ref, created)
  kind ∈ {covers, supersedes, kb_updates, orders, decisions_made, relay, calls, imports, tests, member_of, links, implementation}
  confidence ∈ {declared, extracted, inferred}
chunks(node_id, seq, heading, text, title, tags, locale, embedding?, meta_json)
  unidades de búsqueda de texto completo y vectorial; heading·title·tags van junto al texto para que el índice FTS (unicode61, cuatro columnas) clasifique como el índice legacy; meta_json contiene heading_level·line_start·line_end·char_count (y part·own_chars en una sección dividida). Un chunk es una sección H2–H4; solo se corta una sección cuya entrada de embedding (title·heading·texto) supera la ventana de 2.048 tokens del codificador, por párrafos, luego líneas, luego caracteres, en piezas de unos 1.500 tokens (heading repetido en cada pieza, 150 caracteres de solapamiento, `kb/chunking.py`). Los tokens se cuentan con el tokenizador bge-m3 de la caché local o, si no está, con una estimación conservadora por caracteres (caracteres × 0,75), que divide más secciones, nunca menos. Documentos, decisiones y órdenes comparten una tabla FTS y una escala bm25; la paridad con la clasificación del índice legacy no es un objetivo (DEC-2026-10-28-08)
baselines(gate, project, key, recorded)                líneas base de enlaces y coverage
revisions(store_rev, kit_rev, built_at, sources_hash)  procedencia de todo el almacén
```

Las aristas declaradas provienen del frontmatter (covers, supersedes, orders, kb_updates, decisions_made) y de los registros de decisión. Las aristas extraídas e inferidas provienen del proveedor del grafo (imports, calls, tests) y conservan la etiqueta de confianza del proveedor. Nada en el almacén se escribe a mano.

## Backends

| Backend | Función | Estado |
|---|---|---|
| SQLite (FTS5 + sqlite-vec) | base: un archivo por vault, sin servidor, integrado en el proceso MCP | actual (FTS5), vec pendiente |
| DuckDB | análisis sobre las mismas tablas (informes de coverage, frescura, consultas entre proyectos), exportación a parquet para compartir | adaptador pendiente |
| RocksDB | clave-valor para flujos de sesión con muchas escrituras desde un orquestador (paquetes de relay, aprobaciones) antes de plegarlos en nodos/aristas | adaptador pendiente |

Todos los backends implementan el mismo contrato: `put_nodes`, `put_edges`, `query(sql-like)`, `search_text`, `search_vector`, `rebuild(sources)`. El motor nunca depende de una función específica de un backend fuera de su adaptador.

## Proveedores

| Proveedor | Produce | Contrato |
|---|---|---|
| escáner del vault | nodos doc (cada archivo markdown; los indexados reciben chunks, los espejos generados se marcan), aristas declaradas, aristas `links` del cuerpo | frontmatter + taxonomy |
| registros de decisión | nodos decision, aristas supersedes | salida del decision writer |
| grafo de código — el proveedor propio del kit (`kb/providers/code_graph.py`) | por repositorio: nodos de código de directorio · archivo · símbolo de tipo (solo archivos seguidos por git; Kotlin · Java · TS/JS · Python), `member_of` (extracted), `imports` (extracted; las importaciones con comodín y de paquete son inferred y apuntan al directorio), `tests` (inferred). Resuelve los destinos covers del vault (`code:<p>:paths:<dir>/`, `code:<p>:symbols:<Name>`) | strata DEC-2026-10-28-05. `python3 -m kb code deps · impact · tests-for · symbol · owner-gate`; flow(request) sigue a cargo de un adaptador externo opcional |
| flujo del orquestador (Quilt) | aristas de relay y aprobación entre nodos de sesión | rec.decision.orchestrator-decisions-flow-to-records |
| embedder (local o en la nube con opt-in) | vectores de chunks | consciente del locale; nunca es necesario para que el motor funcione |

## Puertas (gates) que leen el almacén

- puerta de coverage: nodos de código modificados → aristas covers → documento propietario; un nodo modificado sin propietario y sin declaración doc_change es una infracción nueva (rec.kb.covers-owner).
- puerta de enlaces: los wikilinks y enlaces markdown del cuerpo son aristas `links` (source_ref registra cómo se resolvió el destino: file · id · alias · none · md). Los enlaces rotos, los que se resuelven solo por id o solo por alias y los documentos de conocimiento que apuntan a destinos sustituidos son infracciones más allá de la línea base (rec.kb.link-currency). La línea base oficial sigue en `.kb/link-baseline.json`; la tabla baselines del almacén la refleja. Los destinos de enlace que no son markdown y las comprobaciones con `--code-root` se confirman en el sistema de archivos y en git (DEC-2026-10-28-07).
- frescura: nodos doc cuya revisión de código cubierto es más reciente que su campo updated.
- búsqueda: una tabla FTS (bm25) sobre heading·text·title·tags; los vectores densos del proveedor embedder (BAAI/bge-m3, local) se guardan en caché en `embeddings(model, text_hash, dim, vector)` y se adjuntan a los chunks, coseno por fuerza bruta (no hace falta ANN a esta escala); híbrido = reciprocal-rank fusion de ambos. `python3 -m kb search-eval` mide recall@k frente al conjunto de consultas del vault (DEC-2026-10-28-09). El reordenamiento con cross-encoder (BAAI/bge-reranker-v2-m3, `kb/rerank.py`) está desactivado por defecto; se activa con `kb search --rerank`, MCP `search_docs(rerank=true)` o `api.search(rerank=True)`. Vuelve a puntuar los primeros 30 candidatos frente a la consulta (hasta 384 tokens por par), los reordena y luego corta al límite. Medido con el conjunto de consultas del vault el 2026-11-05: el recall@5/@10 de hybrid pasó de .887/.897 a .917/.926, con una mediana de +1,25 s por consulta, +1,1–2,2 GB de memoria GPU y un arranque en frío de 3–4 s. Sin el modelo o sin sentence-transformers el orden se mantiene y el mode del resultado indica que se omitió el reordenamiento. `search-eval --rerank` añade un modo hybrid+rerank para comparar con el mismo conjunto de consultas.
- convergencia: nodo de especificación deseada frente a nodo de documento as-built del mismo asunto (rec.spec.desired-vs-as-built).

## Migración desde strata/scripts

El motor aterrizó en `strata-kit/kb/` con el enfoque shuttle (strata-kit DEC-2026-10-28-01 de este repositorio): cada `strata/scripts/<name>.py` es una llamada fina a `strata-kit/kb`, los hooks siguen funcionando, y los shuttles se eliminan cuando todos los llamantes apuntan al kit.

El primer hito, la paridad, se superó; el siguiente retiró el índice FTS legacy (`.kb/kb.sqlite`, DEC-2026-10-28-13). Ahora el vault tiene un solo almacén.

- `python3 -m kb build-index` es la compilación de fin de sesión: reconstruye todo el almacén y luego deriva del almacén las páginas de nodo (`kb.views.node_pages`), los sortspecs de Obsidian, la bandeja de revisión (`.kb/review-candidates.json`, `_index/review-needed.md`), `manifest.json` y las advertencias de validación de la taxonomy (una infracción block sale con exit 2). `--project` solo acota el informe; el almacén siempre es completo.
- Las reglas de los documentos (descubrimiento, frontmatter, chunks, fusión de taxonomy, validación) viven en un solo lugar, `kb/docrules.py`. El escáner coloca `discovered` (el conjunto descubierto) y `diagnostics` (resultados de validación) en el payload de cada nodo de documento, de modo que la compilación informa de las advertencias sin un índice.
- La frescura es `engine.ensure_fresh_store` (mtime de las fuentes). El antiguo `kb_freshness.py` y la compilación incremental por hash del manifest ya no existen.
- Evidencia: el 2026-10-28 el constructor original (strata@b4b0c86) y `kb build-index` produjeron las mismas páginas de nodo, sortspecs, bandeja de revisión, archivos del manifest, líneas de advertencia y código de salida en dos copias del vault real (760 documentos, 66 páginas de nodo). Los scripts de comparación se eliminaron una vez retirado el índice legacy (orden 2026.10.29-11).
