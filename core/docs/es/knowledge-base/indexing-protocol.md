# Knowledge Base — Protocolo de indexación

> Fuente canónica: strata-kit `core/docs/es/knowledge-base/indexing-protocol.md` (migrado el 2026-10-29 desde strata `docs/07-knowledge-base/indexing-protocol.md`, DEC-2026-10-29-11).

> **Actualizado el 2026-10-29**: este documento describe el motor actual (un único `store.sqlite`, `python3 "$STRATA_KIT/kb"`).
> Se retiraron el antiguo `.kb/kb.sqlite`, la compilación incremental por hash de manifest y el diseño con sqlite-vec (DEC-2026-10-28-13).
> La fuente canónica del esquema de almacenamiento, los backends y las puertas (gate) es `core/docs/es/kb-engine.md`; este documento trata el alcance de la indexación, cómo buscar y las vistas generadas.

## Resumen

Los documentos KB del vault se indexan por fragmentos (chunks) en `store.sqlite`, lo que reduce el consumo de tokens del agente y permite una búsqueda precisa.
El índice es una caché que siempre se puede reconstruir desde sus orígenes (documentos del vault, registros de decisión (decision record), superficie de código), y cada entorno lo construye en local.

## Definición del problema

| Problema | Descripción |
|---|---|
| Recorrido completo forzado | Para llegar a la section deseada, el agente debe leer _index.md y luego el archivo entero |
| Consumo de tokens entre archivos | Explorar 17 archivos (68K chars) desperdicia la ventana de contexto |
| Falta de orden | Las páginas no tienen un orden lógico entre sí, y el agente debe decidir cómo navegar |
| Sin búsqueda semántica | Sin coincidencia de palabras clave no se encuentran documentos relacionados (se complementa con búsqueda por embeddings) |

## Fases

| Fase | Contenido | Estado |
|---|---|---|
| **FTS** | FTS5 (bm25) por chunk + orden por `page_order` del frontmatter | Aplicado — la frescura se comprueba automáticamente al entrar en la búsqueda |
| **Vectorial / híbrida** | Embeddings locales BAAI/bge-m3 + fusión RRF con FTS | Implementado — los vectores solo existen tras ejecutar `python3 "$STRATA_KIT/kb" embed` (DEC-2026-10-28-09). El mode por defecto de MCP `search_docs` es hybrid; el de la CLI `kb search` es FTS (se cambia con `--semantic` o `--hybrid`) |

Se retiró la antigua división en "Phase 1 (FTS5 + hash de manifest) / Phase 2 (sqlite-vec, `--with-vectors`, implementado pero no aplicado)". El índice no se divide en dos; hay un único store y los vectores se adjuntan a los chunks del store.

## Arquitectura

### Disposición de archivos

```
vault/
├── .kb/
│   ├── store.sqlite            # .gitignore — el único índice (artefacto de compilación local)
│   ├── manifest.json           # sin seguimiento — metadatos del índice, se genera en cada máquina (DEC-2026-10-29-04)
│   ├── link-baseline.json      # línea base de la puerta de enlaces (solo se actualiza a la baja)
│   └── review-candidates.json  # .gitignore — candidatos de revisión (generado)
│
├── .gitignore
└── projects/{name}/knowledge-base/
    └── *.md                    # orígenes del índice
```

`.kb/store.sqlite` y sus `-wal` y `-shm` están en el `.gitignore` del vault. Para comprobarlo, véase la sección "KB store" de `.gitignore`.
El esquema lo define el código (`kb/store.py`), no un archivo. No existe `schema.sql` (DEC-2026-10-28-13).

### Disposición del motor de compilación

```
strata-kit/
└── kb/                         # con seguimiento en git — motor de indexación (python3 "$STRATA_KIT/kb" build-index)
```

El motor de compilación está en el repositorio strata-kit. En ejecución localiza el vault mediante la variable de entorno `$STRATA_VAULT`.

### Flujo de datos

```
Editar archivo MD → git commit + push
                    ↓
Otro entorno: git pull
                    ↓
Al entrar en la búsqueda (kb search / MCP), automáticamente:  engine.ensure_fresh_store
  comparar el mtime del origen con el built_at del store (sin hash, bajo coste)
    ├─ fresco → consultar directamente
    ├─ stale → reconstruir todo el store (1-2 s)
    └─ store ausente (máquina nueva) → se genera automáticamente por la misma vía
                    ↓
store.sqlite (nodes · edges · chunks + FTS5 · caché de embeddings)
                    ↓
Agente: kb search / MCP search_docs → devuelve chunk + file:line
```

- No hay reindexación incremental. El store se reconstruye completo cada vez (1-2 s). Se retiró la comparación de hash de manifest que elegía solo los archivos cambiados.
- La ejecución manual (`python3 "$STRATA_KIT/kb" build-index`) y MCP `build_index` son posibles, pero **la vía cotidiana es automática**.
- Un fallo en la comprobación de frescura o en la reconstrucción no bloquea las consultas (avisa y usa el store existente). Vía de escape: `KB_NO_REFRESH=1`.
- Tras reconstruir el store, `build-index` emite las vistas generadas (páginas de nodo, sortspec de Obsidian, Inbox de revisión, `manifest.json`) y las advertencias de validación de taxonomy. Si hay una infracción block, sale con exit 2. Para el comportamiento y los roles, véase `core/docs/es/kb-engine.md`.
- `build-index` no calcula embeddings. `python3 "$STRATA_KIT/kb" embed` calcula solo los chunks que faltan y los guarda en el store; los vectores calculados permanecen en la caché `embeddings` y se reutilizan aunque se reconstruya el store.

### Cobertura del índice (2026.08.19-06 B1)

- **Knowledge**: `projects/*/knowledge-base/` — indexado de texto completo (existente). Desde el 2026-09-08, `patterns/`, `_index/glossary.md` (valor de proyecto `vault`) y `projects/*/overview.md` también se indexan a texto completo — en línea con el alcance de Knowledge de la tabla de tres capas de vault-structure.md.
- **Archive**: archivos `.md` de `projects/*/sessions/` y `tasks/` — solo se indexan **los metadatos (topic · orders · kb_updates · decisions_made · nodes · doc_change) +
  la parte de resumen del cuerpo (primeras 40 líneas)**. `nodes` está en la lista blanca porque sin él no se puede construir la faceta de "historial de trabajo" de la página de nodo. Se distinguen y filtran con las facetas category=`archive`, topic=`sessions|tasks`
  (filtro `category` de MCP). El objetivo es responder con la búsqueda a "¿en qué sesión se trató esto?". **Archive y Planning se excluyen de los valores por defecto de la búsqueda** (DEC-2026-09-30-03) —
  para incluir el historial, use `kb search --include-history`, MCP `search_docs(include_history=true)` o indique `category` explícitamente. `--include-history` también busca registros de decisión y de orden.
- A Archive no se le aplica la validación KB (lifecycle, etc.) — el status del ledger (open/closed) queda fuera del contrato KB.
  **Excepción**: `node_id_check` (¿está el valor de nodes en toc.yaml?) también se aplica a Archive, porque una errata en un nodo hace que la sesión desaparezca de la faceta de historial de trabajo.
- **Planning**: `projects/*/planning/{source}/` — **indexado de texto completo** del texto original de planificación + validación KB (required_fields · lifecycle_override · node_id). Facetas category=`planning`, topic=`{source}`. Es el origen de la faceta "planificación" de la página de nodo. Su status es un estado de planificación (no active), por lo que queda fuera de la política de candidatos de revisión (DEC-2026-09-09-01).
- Las **páginas de nodo** (`projects/*/nodes/`) son `indexed: metadata` — solo la parte de resumen, ya que el texto original de cada faceta ya está indexado.
- Las **notas DEC** (`projects/*/decisions/`) no se indexan como documentos (sin cambios). El provider de registros de decisión mete las decisiones en el store como nodos de decisión, y el generador de páginas de nodo lee `nodes` del registro canónico para saber a qué nodo pertenece una decisión.
- Los enlaces simbólicos (`latest.md`) y los yaml no se indexan.

## KB Result Contract — retirado (DEC-2026-08-19-06)

El contrato común de esquema de resultados fue **retirado**. Desde su establecimiento ningún consumidor (kb-search, strata-mcp) lo implementó,
cada uno funciona de forma estable con su propia forma de resultado, y los múltiples consumidores que el contrato presuponía (strata-kb-server, Hub) no existen.

- **Condición de reactivación**: si aparece realmente una segunda superficie de consumo (como Hub), se rediseña el contrato a partir de los campos en uso real en ese momento.
- El generador de páginas de nodo produce salida dentro del vault, así que no es una "segunda superficie de consumo". Esta decisión de retiro no se revierte.
- Para el texto completo del contrato antes del retiro, consulte el historial de git (este archivo, antes del 2026-08-19).

## Esquema de almacenamiento

La fuente canónica del esquema (`nodes`, `edges`, `chunks`, `baselines`, `revisions`, la tabla virtual FTS5 `chunks_fts` y la caché `embeddings`) es la sección "Esquema" de `core/docs/es/kb-engine.md`. Aquí solo se anota lo que la búsqueda necesita.

- La unidad de búsqueda es `chunks`. Un chunk tiene heading, text, title, tags y `meta_json` (heading_level · line_start · line_end · char_count). Documentos, decisiones y órdenes comparten una tabla FTS y una escala bm25.
- FTS5 indexa con `unicode61` las cuatro columnas heading, text, title y tags.
- Las facetas de taxonomy del documento (category · topic · section_name · page_order, etc.) están en el payload del nodo del documento y las leen los filtros de `kb search` y la ordenación de `--toc`.
- Los enlaces son aristas `links`; las relaciones entre documentos (supersedes, etc.) y `covers` también son aristas. La antigua tabla `document_links` no existe.

El esquema antiguo (las tablas `documents`, `chunks`, `chunks_fts` (columnas doc_title y doc_tags), `document_links` y `coverage`, las columnas `sha256` y `section_name`, y `chunks_vec`) pertenece al índice legacy (`.kb/kb.sqlite`) y fue retirado por DEC-2026-10-28-13. Con él desapareció también la consulta directa con SQL. Las consultas se hacen con `kb search`, MCP y `kb coverage`.

### Nodos temáticos y cobertura

El frontmatter `stable_id`, `nodes`, `covers` y `doc_change` de un documento pasa a ser el payload de nodo del store y las aristas `covers`. Las reglas de consulta inversa de la superficie de código al documento no cambian.

- "¿Qué especificación es dueña de esta ruta?": `python3 "$STRATA_KIT/kb" coverage resolve|nodes|unowned|docs-to-update`
- "¿Qué documento es la forma final de este nodo?": `kb coverage node` (lo usa el generador de páginas de nodo)
- "¿Se actualizó el documento propietario después de que cambiara esta ruta?": la puerta de fin de sesión `kb coverage-gate`
- El árbol de nodos lee directamente `_meta/toc.yaml`. `endpoints` y `tables` no se resuelven como rutas de archivo; sirven para mostrarse en las páginas de nodo.

Validaciones en compilación (todas warn): `node_id_check` (formato, existencia y registro en toc.yaml — también se aplica a Archive), `covers_path_check` (estructura · rutas relativas · prohibidas las entradas a nivel de archivo),
`supersedes_symmetry_check` (A.supersedes=B ⇔ B.status=superseded ∧ B.superseded_by=A), y los valores y motivos de doc_change. Los candidatos de revisión se registran como un artefacto generado (el Inbox de revisión), y la transición solo se hace con un comando explícito (`build-index --apply-review`).

## Detección de cambios y sincronización entre entornos

La detección de cambios compara el mtime del archivo de origen con el `built_at` del store (`engine.ensure_fresh_store`), no un hash de manifest. Por eso no hay un estado de índice que los entornos deban acordar. Lo único que se comparte son los documentos del vault y los registros de decisión; cada entorno construye el store en local.

```
[Entorno A — edición de documentos]
1. Editar archivos MD
2. git commit + push   (al terminar la sesión, handoff sincroniza el vault)

[Entorno B — sincronización]
1. git pull
2. Al entrar en la búsqueda el store se reconstruye automáticamente — a mano: python3 "$STRATA_KIT/kb" build-index
```

**Principio clave:** el store es una caché, así que no se sube a git (`.gitignore`). No hay conflictos binarios, y cualquier máquina vuelve a generar el mismo resultado a partir de los mismos orígenes.

DEC-2026-10-29-04 decide qué artefactos generados tienen seguimiento y quién los escribe.

| Artefacto | Seguimiento | Quién lo escribe |
|---|---|---|
| `.kb/store.sqlite` | No | La entrada de búsqueda de cada máquina y `build-index` |
| `.kb/manifest.json` | No (registro de comparación por máquina) | El `build-index` de cada máquina |
| Notas DEC (`projects/*/decisions/`) | Sí | La CLI de decisiones — la sesión que registró la decisión las confirma junto con el registro |
| Páginas de nodo y `_index/review-needed.md` | Sí | El librarian, una vez al día, con `kb views-publish` (tras build-index, commit-push solo de estos archivos). El `build-index` de una sesión normal solo actualiza el índice local y no confirma estos archivos |
| `.kb/link-baseline.json` | Sí | Se actualiza solo a la baja |

El antiguo método de "compartir `manifest.json` por git para acordar el estado de los archivos e indexar solo los cambios" era un diseño legacy y se retiró (DEC-2026-10-28-13, DEC-2026-10-29-04).

## Protocolo de búsqueda del agente

### Prioridad de búsqueda

```
① Búsqueda FTS5 por palabra clave (cuando se conoce el término exacto)
② Búsqueda FTS5 compuesta (combinaciones AND/OR, filtros --category y --topic)
③ Consulta de metadatos (--toc índice ordenado, --doc chunks dentro de un documento)
④ Búsqueda híbrida / semántica (consultas en lenguaje natural — requiere vectores)
```

Los agentes usan `kb search` o MCP `search_docs` (mode: hybrid por defecto · dense · fts), no SQL. Los resultados devuelven la ubicación `file:Llínea-línea` del chunk y el número de caracteres.

### Ejemplos de uso

**Búsqueda por palabra clave — devuelve los chunks relevantes:**
```bash
python3 "$STRATA_KIT/kb" search "환불수수료" --limit 5
```

**Búsqueda compuesta — AND + filtros:**
```bash
python3 "$STRATA_KIT/kb" search "정산식 AND Payment" --category domain
python3 "$STRATA_KIT/kb" search "정산식" --category domain --topic orders
```

**Consulta del índice ordenado:**
```bash
python3 "$STRATA_KIT/kb" search --toc --category domain
```

**Devolución de ubicación precisa — enlace con la herramienta Read:**
```
kb search "FormulaBaseStructure"
# Resultado: domain/orders/payment-shipping.md  ubicación: L46-101
# → pasar offset=46, limit=55 a la herramienta Read
```

## Referencia de la sintaxis de búsqueda FTS5

`kb search` envuelve entre comillas cada token de la consulta antes de pasarlo a FTS5. Por eso solo funciona la sintaxis siguiente.

| Sintaxis | Ejemplo | Descripción |
|---|---|---|
| Palabra clave única | `환불수수료` | Chunks que contienen ese token |
| Separado por espacios | `Transactional Composite` | Contiene ambos tokens (AND) |
| AND | `Transactional AND Composite` | Contiene ambos tokens |
| OR | `Payment OR Shipping` | Contiene al menos uno |
| NOT | `환불 NOT Coupon` | Condición de exclusión |
| prefix | `Refund*` | Tokens que empiezan por Refund |

Sintaxis que no funciona: especificadores de columna (`doc_tags:orders`, `tags:orders` — sin resultados; use en su lugar los filtros `--category` y `--topic`, y `--tags` para ver solo etiquetas), búsqueda de frase (`"REST Docs"` — se quitan las comillas y se convierte en un AND de dos tokens) y `NEAR`. Los nombres de columna `doc_tags:` y `content:` de documentos anteriores son columnas del índice legacy (las columnas actuales son heading, text, title y tags).

## Extensión del frontmatter — el campo page_order

Se añade un campo de ordenación al frontmatter del document-format.md existente:

```yaml
---
title: "Order Payment & Shipping"
type: concept        # domain es una categoría (directorio), no un tipo de documento
project: shop-api
tags: [orders, payment, shipping]
created: 2026-04-07
updated: 2026-04-07
page_order: 3              # ★ nuevo — orden del documento dentro de la sección
---
```

`--toc` ordena primero por el orden de category y topic de la taxonomy y, dentro de él, por `page_order` (los documentos de directorios con prefijo NN anteriores a la taxonomy usan `section_order`).
`page_order` se indica explícitamente en el frontmatter para definir el orden lógico dentro de la sección.

## Ahorro de tokens (medido)

Las cifras siguientes se midieron en el vault de un proyecto backend en la época del índice FTS5 legacy (2026-04) (15 documentos, 210 chunks, 68K chars). El principio de leer por chunk es el mismo en el store actual, pero las cifras nunca se han vuelto a medir con el motor actual.

| Consulta de búsqueda | Antes (leer todo) | FTS5 (chunk) | Ahorro |
|-----------|-----------------|-------------|--------|
| "환불수수료" | 68,242 chars | 3,473 chars | **95%** |
| "TransactionalExecutor" | 68,242 chars | 1,181 chars | **99%** |
| "정산식 AND Payment" | 13,939 chars (3 archivos) | 6,758 chars | **52%** |

## Búsqueda vectorial (híbrida con bge-m3)

Fuente canónica: la sección de búsqueda de `core/docs/es/kb-engine.md`, DEC-2026-10-28-09.

### Resumen

| Elemento | Actual |
|---|---|
| Modelo | BAAI/bge-m3, ejecución local (sentence-transformers; MPS en Apple Silicon), vectores normalizados de 1024 dimensiones |
| Almacenamiento | `chunks.embedding` en el store + la caché `embeddings(model, text_hash, dim, vector)` que sobrevive a las reconstrucciones |
| Búsqueda vectorial | coseno con numpy por fuerza bruta (unos ms con unos 7 mil chunks — no hace falta ANN) |
| Híbrida | Fusión RRF (k=60) de FTS (bm25) y vectores |
| Juicio de eficacia | `python3 "$STRATA_KIT/kb" search-eval` — recall@k (fts · dense · hybrid) con el conjunto de consultas de `_meta/search-eval.yaml` del vault |
| Cálculo de embeddings | `python3 "$STRATA_KIT/kb" embed` (solo los chunks que faltan. `--model` · `--batch` · `--max-seq` · `--max N`) |

### Alternativas y por qué no se adoptaron

| Alternativa | Decisión |
|---|---|
| sqlite-vec | Se cambia mediante un adaptador cuando los chunks superen los 100 mil (DEC-2026-10-28-09). Ahora no hace falta |
| BD vectoriales externas como LanceDB | Choca con el contrato de un único almacén (DEC-2026-10-28-04) y no aporta ventaja a esta escala — no se adopta |
| khoj | Es una aplicación con su propio host, UI y BD — no se adopta |
| paraphrase-multilingual-MiniLM-L12-v2 (384 dimensiones) | El modelo del diseño legacy. Sustituido por bge-m3 |
| ONNX Runtime · APIs de embeddings en la nube | No se adoptan. El provider de embedder es reemplazable (kb-engine.md), pero la implementación actual es solo bge-m3 local |

El antiguo `build-index --with-vectors`, `apsw` (para cargar sqlite-vec) y la tabla virtual `chunks_vec` eran un diseño legacy y no existen.

## Hoja de referencia de las herramientas de búsqueda

### Compilación

```bash
# Cotidiano: no hace falta — si el store está stale, se reconstruye automáticamente al entrar en la búsqueda

# Compilación manual del store + vistas generadas (páginas de nodo · sortspec · Inbox de revisión · manifest)
python3 "$STRATA_KIT/kb" build-index

# Limitar solo el alcance del informe a un proyecto (el store siempre es completo)
python3 "$STRATA_KIT/kb" build-index --project shop-api

# Reconstruir solo el store / estadísticas
python3 "$STRATA_KIT/kb" build-store
python3 "$STRATA_KIT/kb" store-stats

# Calcular embeddings de los chunks que faltan (antes de la búsqueda semántica / híbrida)
python3 "$STRATA_KIT/kb" embed

# Pasar los candidatos de revisión a status: review-needed y compilar de nuevo
python3 "$STRATA_KIT/kb" build-index --apply-review
```

`--force` es una opción de compatibilidad y no tiene efecto (el store se reconstruye completo cada vez). No existe `--with-vectors`.

### Búsqueda (kb search)

> `kb search` en lo que sigue es una abreviatura de `python3 "$STRATA_KIT/kb" search`.

```bash
# ─── Búsqueda FTS5 por palabra clave ───
kb search "환불수수료"                          # palabra clave única
kb search "Transactional AND Composite"       # AND compuesto
kb search "Payment OR Shipping"                  # OR
kb search "Refund*"                         # prefix
kb search "정산식" --category domain --topic orders   # filtros de categoría y tema (en lugar de la sintaxis de especificador de columna)
kb search "환불수수료" --limit 10 --content      # número de resultados + vista previa del contenido
kb search "jwt" --category architecture       # filtro de categoría (también existen --topic, --status y --project)
kb search "환불수수료" --include-history         # incluye texto de sesiones, tareas y planificación, además de decisiones y órdenes

# ─── Búsqueda semántica / híbrida (tras crear vectores con kb embed) ───
kb search "환불 금액을 계산하는 흐름?" --semantic
kb search "인증 토큰 만료 시 처리" --hybrid --content

# ─── Navegación ───
kb search --toc                               # índice completo (ordenado)
kb search --toc --category domain             # filtro de categoría
kb search --doc "domain/orders/payment-shipping.md"       # índice de chunks dentro de un documento
kb search --tags orders                          # búsqueda por etiqueta (solo etiquetas, sin término de consulta)
kb search --stats                             # estadísticas del índice
```

`--section` es un filtro de compatibilidad para los directorios NN-section anteriores a la taxonomy. Para documentos nuevos, use `--category` y `--topic`.

### FTS5 frente a semántica — cuándo usar cada una

| Situación | Recomendado | Motivo |
|------|------|------|
| Se conoce el nombre exacto de la clase o función | FTS5 | `FormulaBaseStructure` → coincidencia exacta, inmediata |
| Búsqueda de un término concreto | FTS5 | `환불수수료`, `TransactionalExecutor` → rank BM25 |
| Pregunta en lenguaje natural | **Semántica / híbrida** | "환불 금액을 계산하는 흐름?" → supera la falta de coincidencia de palabras clave |
| FTS5 no devuelve nada | **Semántica** | "인증 토큰 만료 처리" → 0 resultados en FTS5, la semántica devuelve resultados |
| Tras acotar por categoría/tema | FTS5 | filtro `--category domain --topic orders` |
| No se sabe por dónde empezar a leer | `--toc` | Índice ordenado → captar la estructura de los documentos |

## Guía de división de palabras clave para FTS5

El tokenizador `unicode61` de FTS5 **separa tokens solo por espacios y signos de puntuación**.
No realiza análisis morfológico del coreano, por lo que al buscar importa la estrategia de división de las palabras clave.

### Problema: por qué hace falta dividir las palabras clave

```
Texto original:  "환불수수료 변경 시 재계산 처리"
              ↓ tokenización unicode61
Tokens:       ["환불수수료", "변경", "시", "재계산", "처리"]
```

| Consulta de búsqueda | Coincide | Motivo |
|-----------|----------|------|
| `환불수수료` | ✅ | Coincidencia exacta de token |
| `환불수수료변경` | ❌ | No existe el token "환불수수료변경" |
| `환불수수료 AND 변경` | ✅ | Existen ambos tokens por separado |
| `환불` | ❌ | Una subcadena de "환불수수료" no coincide |
| `환불*` | ✅ | La búsqueda por prefix coincide con "환불수수료" |

### Reglas de división

**1. Divida con espacios los términos coreanos compuestos y busque con AND**

```bash
# ❌ Juntos: no hay coincidencia
kb search "환불수수료변경"

# ✅ Dividido + AND
kb search "환불수수료 AND 변경"
```

**2. Use prefix (*) cuando necesite coincidencia parcial**

```bash
# ❌ Solo con "환불" no se encuentra "환불수수료"
kb search "환불"

# ✅ El prefix coincide con "환불수수료", "환불금액" y "환불요청"
kb search "환불*"
```

**3. Los nombres de clase en inglés no distinguen mayúsculas y no se dividen en CamelCase**

```bash
# ✅ unicode61 normaliza las mayúsculas
kb search "formulabasestructure"      # coincide con FormulaBaseStructure

# ❌ No se puede dividir dentro de CamelCase
kb search "Formula AND Base"          # ambas palabras deben existir por separado

# ✅ Rodéelo con un prefix
kb search "Formula*"
```

**4. Consultas mixtas en coreano e inglés**

```bash
# ✅ Una los tokens de cada idioma con AND
kb search "Payment AND 정산식"

# ✅ Combine filtros de categoría y tema con búsqueda de contenido
kb search "Payment" --category domain --topic orders
```

**5. Si dividir las palabras clave tampoco funciona → pase a la búsqueda semántica / híbrida**

```bash
# Consulta en lenguaje natural difícil de encontrar con FTS5
kb search "인증 토큰이 만료되면 어떻게 처리하나요?" --hybrid
```

El tramo que FTS pierde por las partículas y palabras compuestas del coreano (4-8 % en el conjunto de evaluación) lo cubren los vectores, y se decidió reforzarlo tras la evaluación con una tabla trigram de FTS5 o con bge-m3 sparse (DEC-2026-10-28-09).

### Árbol de decisión de búsqueda del agente

```
Pregunta recibida
  │
  ├─ ¿Se conoce el término/nombre de clase exacto?
  │   └─ SÍ → FTS5: kb search "término"
  │
  ├─ ¿Término coreano compuesto?
  │   └─ SÍ → FTS5: dividir por espacios + AND
  │            p. ej.: "환불수수료 AND 변경 AND 재계산"
  │
  ├─ ¿Hace falta coincidencia parcial?
  │   └─ SÍ → FTS5: prefix(*)
  │            p. ej.: "Refund*", "환불*"
  │
  ├─ ¿Pregunta en lenguaje natural?
  │   └─ SÍ → híbrida/semántica: kb search "pregunta" --hybrid
  │
  └─ ¿FTS5 devolvió 0 resultados?
      └─ Reintentar con semántica
```

## Decisiones clave de diseño

| Decisión | Fundamento |
|------|------|
| Un único `store.sqlite` es el único índice y no se sube a git | Elimina los conflictos de merge binarios y la duplicación de esquema y de guardas de frescura que producían dos índices (DEC-2026-10-28-13) |
| La frescura es una comparación del mtime del origen, y el store se reconstruye completo cada vez | Con 1-2 s el incremental es innecesario. Una compilación parcial que recortara el store perdería las vistas de otros proyectos (DEC-2026-10-28-13) |
| `manifest.json` no tiene seguimiento | Es un registro de comparación por máquina que nadie lee (DEC-2026-10-29-04) |
| El motor de compilación está en el repositorio strata-kit | Se gestiona como herramienta de la propia metodología, independiente de cualquier proyecto |
| El frontmatter es la single source of truth | Obsidian, FTS5 y Dataview consultan los mismos datos |
| El chunk lleva juntos heading, title, tags y meta | Una tabla FTS y una escala bm25 ordenan documentos, decisiones y órdenes, y muestran la ubicación (DEC-2026-10-28-08) |
| Embeddings bge-m3 + fuerza bruta con numpy + RRF con FTS | Buen rendimiento con coreano e inglés mezclados, y sus 8192 tokens evitan truncar chunks largos. No hace falta ANN a esta escala (DEC-2026-10-28-09) |
| El efecto de los vectores se juzga por recall@k sobre un conjunto de evaluación | `kb search-eval` |

Decisiones legacy retiradas: seguimiento git de manifest.json y `.gitignore` de kb.sqlite, compilación incremental basada en hash SHA256, `paraphrase-multilingual-MiniLM-L12-v2`, `apsw` y sqlite-vec, y la interpretación de cosine distance de 0 a 1 (para MiniLM). Todas desaparecieron junto con el índice legacy mediante DEC-2026-10-28-13 o fueron sustituidas por DEC-2026-10-28-09.

## Resumen de dependencias

| Paquete | Uso | Cuándo se necesita |
|--------|------|-----------|
| Python 3 | Ejecutar `kb` | Siempre |
| SQLite 3 (con FTS5) | store | Siempre (viene con el SO) |
| PyYAML | Analizar frontmatter y taxonomy | Siempre |
| sentence-transformers (con PyTorch, ~500MB) | Calcular embeddings bge-m3 | Solo al usar `kb embed` |
| numpy | Coseno de vectores | En búsqueda semántica / híbrida |

sqlite-vec y apsw ya no se usan. Sin embeddings, la búsqueda FTS y todas las vistas generadas funcionan igualmente. La lista exacta de dependencias se toma de los import de `kb/`.

### Entorno de ejecución

- Sin proceso residente. No hace falta GPU (en Apple Silicon los embeddings son rápidos con MPS).
- Reconstruir el store tarda 1-2 s (unos 760 documentos y 7 mil chunks, medido en DEC-2026-10-28-13 y 09).
- El cálculo de embeddings tarda mucho la primera vez; después solo se calculan los chunks cambiados, gracias a la caché `embeddings`.

## Limitaciones

| Limitación | Descripción | Respuesta |
|---|---|---|
| Morfología coreana (FTS5) | unicode61 solo separa por espacios — "환불수수료변경" no coincide | Seguir la guía de división de palabras clave, usar búsqueda semántica en paralelo |
| Sin división de CamelCase (FTS5) | FormulaBaseStructure → un único token | Búsqueda con prefix (*) o escribir el nombre completo |
| Sin soporte de especificador de columna, frase ni NEAR | Todos los tokens de la consulta van entre comillas, así que la sintaxis avanzada de FTS5 no funciona | Usar los filtros `--category` y `--topic` y AND en su lugar |
| La búsqueda semántica necesita preparación | Primero hay que crear los vectores con `kb embed`, y la primera consulta es lenta por la carga del modelo | FTS5 primero, semántica como fallback |
| Solo rank BM25 (FTS) | Sin ponderación por estructura o importancia del documento | Ordenar el índice con page_order, usar híbrida en paralelo |
| Con Obsidian sin ejecutar | Las consultas Dataview son imposibles | FTS5/semántica funcionan independientemente de Obsidian |
