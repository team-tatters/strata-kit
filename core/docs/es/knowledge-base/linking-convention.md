# Knowledge Base — Convención de enlaces

> Fuente canónica: strata-kit `core/docs/es/knowledge-base/linking-convention.md` (migrado el 2026-10-29 desde strata `docs/07-knowledge-base/linking-convention.md`, DEC-2026-10-29-11).

## Resumen

Los enlaces dentro del vault ponen la compatibilidad con Obsidian en primer lugar.
Las referencias a lo que está fuera del vault (strata-kit, projects) se basan en variables de entorno.

## Tipos de enlace

### 1. Enlaces dentro del vault — usar wikilinks

```markdown
<!-- Referenciar un documento del mismo vault -->
[[overview]]
[[decisions/001-use-jwt-auth]]
[[glossary#JWT]]

<!-- Cambiar el texto mostrado -->
[[decisions/001-use-jwt-auth|decisión de autenticación JWT]]
```

**Reglas:**
- Dentro del vault, usa siempre `[[wikilink]]`
- La ruta es relativa a la raíz del vault
- Omite la extensión `.md`
- Las relaciones se visualizan en el Graph View de Obsidian

### 2. Referencias vault → kit — variable de entorno

```markdown
<!-- Cuando un documento del vault referencia la metodología del kit -->
Consulta las reglas de capas en `$STRATA_KIT/core/rules/layer-rules.yaml`.
```

**Reglas:**
- Se prohíben las rutas absolutas
- Usa siempre la variable de entorno `$STRATA_KIT`
- Mantén al mínimo las referencias al kit desde documentos del vault (el vault es conocimiento, el kit es metodología)

### 3. Referencias vault → project — variable de entorno

```markdown
<!-- Cuando un documento del vault referencia código del proyecto -->
Implementación: `$STRATA_PROJECTS/{project-name}/src/auth/AuthService.ts`
```

**Reglas:**
- Usa la variable de entorno `$STRATA_PROJECTS`
- En las referencias a código, registra solo la ruta (prohibido copiar código)

### 4. CLAUDE.md del proyecto → referencias al vault — sintaxis @

```markdown
<!-- Cuando el CLAUDE.md de un proyecto referencia el vault -->
Conocimiento del proyecto: @$STRATA_VAULT/projects/my-api/
```

**Reglas:**
- Usa la sintaxis de carga diferida `@` de Claude Code
- La ruta se resuelve mediante la variable de entorno

### 5. CLAUDE.md del proyecto → referencias al kit — sintaxis @

```markdown
<!-- Cuando el CLAUDE.md de un proyecto referencia el kit -->
Reglas de capas: @$STRATA_KIT/core/rules/layer-rules.yaml
```

### 6. typed frontmatter link — el tipo de relación como dato

Un wikilink en el cuerpo solo dice "relacionado". El **tipo** de relación se escribe en un campo del frontmatter (DEC-2026-08-19-03). Los generadores, la validación y las páginas de nodo leen solo estos campos y no leen los enlaces del cuerpo.

| Campo | Dirección | Tipos que lo usan | Significado |
|---|---|---|---|
| `sources` | Knowledge → Archive | KB, pattern | Las sesiones y tareas en que se basa este documento. Obligatorio al actualizar Knowledge |
| `up` | hijo → padre | Todos los documentos | El concepto superior o MOC que contiene este documento |
| `decisions` | documento → decisión | KB, session, task | Las decisiones que este documento sigue o produjo |
| `supersedes` / `superseded_by` | decisión nueva → decisión antigua / antigua → nueva | decision | Los dos extremos de la relación de sustitución. La validación comprueba la simetría |
| `nodes` | documento → nodo temático | decision, session, task, specification, concept, constraint | La unidad del índice a la que pertenece este documento |
| `covers` | especificación → superficie de código | specification, concept | Las rutas de código, símbolos, endpoints y tablas de los que este documento es la **fuente de verdad** |
| `related` | documento ↔ documento | Todos los documentos | Relación de mención o referencia. No es propiedad |

**Reglas:**
- Los valores de `sources`, `up`, `decisions`, `supersedes` y `related` son `[[wikilink]]`. Los valores de `nodes` son ids de nodo de toc.yaml y los de `covers` son punteros relativos al repositorio. Ninguno de los dos es un wikilink.
- Omite un campo de relación cuando no tiene valor. Si dejas un array vacío, la validación pregunta si el vacío es intencionado.
- Escribir la misma relación también como wikilink en el cuerpo está permitido (para el grafo de Obsidian). Pero la fuente de verdad es el frontmatter.
- Fuentes de verdad de los formatos de valor: para `nodes`, `covers`, `doc_change` y `supersedes`, la sección "campos de nodo y cobertura" de document-format.md; para `sources`, el esquema de frontmatter del mismo documento.

### 7. Reglas para que los enlaces apunten siempre al documento vigente (DEC-2026-09-30-03)

- **El destino de un wikilink debe resolverse por nombre de archivo (o ruta relativa al vault).** No uses enlaces que solo se resuelvan mediante el `id:` del frontmatter o `aliases` (como ids de tarea), porque se rompen en Obsidian. Al mover o renombrar un archivo, deja el nombre antiguo en `aliases:` (para búsqueda y unlinked mentions), pero corrige el enlace en sí al nuevo nombre de archivo tal como lo indique el verificador.
- **No envuelvas texto libre en un enlace.** Está prohibido un enlace cuyo documento de destino no existe, como `[[restdocs 양식 정렬]]`. Si hace falta una explicación, usa texto mostrado (`[[session-2026-09-02-x|task05 후속]]`).
- **Cambia los enlaces del cuerpo que apuntan a un documento sustituido para que apunten al documento vigente.** Los campos de relación de sustitución (`supersedes`, `superseded_by`) y las frases que explican la historia son excepciones. El verificador no puede distinguirlos, así que este punto se informa solo como nota (aviso).
- **Señala el código por símbolo en lugar de por ruta.** Escribe nombres de clases y funciones en `covers.symbols`, y en el cuerpo también escribe símbolos como `CollaboratorCommandService.invite`. Escribe rutas solo hasta el nivel de módulo o paquete. Esto se debe a que los nombres de símbolos rara vez cambian aunque se muevan los archivos.
- **Verificación:** `python3 "$STRATA_KIT/kb" link-check` encuentra wikilinks rotos, enlaces de texto libre, enlaces que se resuelven solo por id y enlaces del cuerpo a documentos sustituidos. Las infracciones en documentos generados o importados (notas DEC, páginas de nodo, documentos originales de planificación, `_index/`) no se pueden corregir a mano, así que solo se informan y no bloquean (el lugar para corregirlas es el generador). La puerta de fin de sesión mira solo los documentos del proyecto de esa sesión. Las infracciones existentes se agrupan en una línea base (`$STRATA_VAULT/.kb/link-baseline.json`) y la verificación **falla solo cuando hay una infracción nueva fuera de la línea base**. El fin de sesión (`python3 "$STRATA_KIT/kb" ledger close`) detiene la sincronización del vault por esta verificación, mientras que la generación del traspaso (`python3 "$STRATA_KIT/kb" handoff`) solo avisa. Solo en una urgencia, degrádalo a aviso con `STRATA_LINK_CHECK=warn`. Reduce la línea base con `--shrink-baseline` tanto como hayas corregido.
- **Contraste con el código:** si pasas `--code-root {project}=<repo>`, también comprueba si los `covers.paths` del KB existen en el repositorio y si los nombres de `covers.symbols` se encuentran en el código (solo en una máquina que tenga el repositorio de código).

## Prohibiciones

| Patrón prohibido | Motivo | Alternativa |
|---|---|---|
| Rutas absolutas en el vault (`/home/alice/...`) | No son compatibles entre máquinas | Usar `$STRATA_KIT`, `$STRATA_VAULT` |
| Enlaces Markdown `[text](path)` en el vault | No aparecen en el Obsidian Graph | Usar `[[wikilink]]` |
| Copiar bloques de código | Se pudre el código | Registrar solo referencias de ruta |
| Referencias directas entre proyectos | Crean una dependencia | Extraer como patrón común a vault/patterns/ |
| Depender solo de enlaces del cuerpo para el tipo de relación | Los generadores y la validación no pueden leerlo | §6 typed frontmatter link |

Los punteros de código de `covers` no tienen por qué ser wikilinks. Una ruta relativa al repositorio dentro del frontmatter no está sujeta a la prohibición de "enlaces Markdown en el vault".

## Incrustaciones

También se puede usar la sintaxis de incrustación de Obsidian:

```markdown
<!-- Incrustar una sección concreta de otro documento -->
![[decisions/001-use-jwt-auth#결정]]

<!-- Incrustar una imagen -->
![[architecture-diagram.png]]
```

Una incrustación refleja automáticamente los cambios del documento referenciado, por lo que se recomienda incrustar en lugar de escribir duplicados.
