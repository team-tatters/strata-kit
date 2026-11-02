# Arquitectura de capas del frontend Web

> Fuente canónica: strata-kit `core/docs/es/architecture/frontend-web.md` — migrado desde strata `docs/03-architecture/frontend-web.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Reglas legibles por máquina: `core/rules/layer-rules.yaml` → `frontend.variants.web`
> Este documento es el detalle legible por personas de la variante (variant) de frontend web independiente del framework.
> La coherencia entre tokens, variantes, composiciones y entregables de diseño la define `core/docs/es/architecture/frontend-design-contract.md`.

## Principios de frontera

La guía de frontend de Strata Core no define un framework de UI, un router, una biblioteca de gestión de estado ni una herramienta de estilos concretos.
Core solo fija fronteras de responsabilidad que se pueden verificar mediante import, rutas y análisis estático.

La relación entre capas es un DAG, no un único árbol lineal.
`can_reference` de la tabla siguiente es la source of truth; las referencias a capas que no figuran en la tabla, y las referencias cruzadas de un mismo nivel entre capas con `cross_reference: false`, están prohibidas (en Feature Block esto significa entre dominios; véase más abajo).

| Layer | can_reference |
|---|---|
| Foundation | ninguna |
| Contract | Foundation |
| DataState | Foundation, Contract |
| Primitive UI | Foundation |
| Semantic Component | Foundation, Contract, Primitive UI |
| Feature Block | Foundation, Contract, DataState, Primitive UI, Semantic Component |
| Route Surface | Foundation, Contract, Feature Block, App Shell |
| App Shell | Foundation, Contract, DataState, Primitive UI, Semantic Component |

## Variants

El frontend de Strata admite tres variants.

| Variant | Uso | Estado |
|---|---|---|
| `atomic` | La estructura existente L1/LM/L2/Atomic/Molecule/Partial/Page/Layout y la compatibilidad con proyectos heredados | Se mantiene |
| `web` | Fronteras de aplicación web independientes del framework | Por defecto |
| `mobile` | UI móvil nativa (SwiftUI, Compose) — las capas y can_reference son los mismos que en web, pero el vocabulario, la composición y las reglas de destino son distintos (`core/docs/es/architecture/frontend-mobile.md`) | 2026-09-11 |

La elección de cada proyecto se pone en `variant` o `frontend_variant` de `.strata/layer-map.yaml`.
Si no hay valor elegido, el valor por defecto de Core es `web`.

## Foundation

Contiene tokens semánticos, funciones puras, constantes y tipos primitivos.

**Permitido:** token, const, type, util

**Prohibido:** renderizado de UI, llamadas a transport, acceso a estado global, implementaciones dependientes del framework

## Contract

El contrato estable entre la UI y transport.
Contiene DTO, ViewModel, schema, API port/interface y cache key contract.

**Reglas:**
- Referencia solo a Foundation.
- No referencia las capas de UI ni DataState.
- No llama directamente a implementaciones de transport.
- Las interface/type que tienden a quedar dispersas en los archivos de componentes se reúnen en esta capa.

## DataState

La capa de adapter para el estado del servidor, las mutation y el estado del cliente.
La biblioteca concreta se decide en la convention; Core solo define la frontera que impide que la UI vea transport directamente.

**Reglas:**
- Referencia solo a Foundation y Contract.
- No renderiza componentes de UI.
- No expone el transport client directamente a la UI.
- Los cache key y los contratos DTO/ViewModel se refieren a Contract.

**Dos tramos:** transport (`{name}.service` — llamadas HTTP, devuelve DTO) y adapter (`use{Entity}Query` · `use{Entity}{Action}Mutation` · `use{Name}State`).
Solo el adapter puede importar transport. Las capas superiores ven únicamente el adapter.

## Primitive UI

UI de bajo nivel ligada a tokens semánticos.
No debe conocer el significado del dominio ni el estado del servidor.

**Reglas:**
- Referencia solo a Foundation.
- No referencia los modelos de dominio de Contract, DataState ni transport.
- Funciona solo con Props y tokens de Foundation.

## Semantic Component

Un componente de UI con significado de usuario o de dominio.
En lugar de una clasificación por tamaño como Atomic/Molecule, expresa «qué hace el componente» mediante su nombre y su responsabilidad.

**Frontera central verificable:** un Semantic Component no llama directamente a DataState.
El estado del servidor y las mutation se inyectan mediante props o callback.

El componente que se separa como la mitad de renderizado de un Feature Block se nombra `{Domain}{Purpose}View`. El eje de estado de los datos (loading · empty · error) se recibe por props.
La apariencia se decide solo mediante la combinación de valores del eje variant de Primitive UI y alias de Foundation (Composition Legality — `core/docs/es/architecture/frontend-design-contract.md`).

## Feature Block

La capa que ensambla un fragmento de pantalla de un caso de uso concreto junto con sus datos y su estado.
Las llamadas a DataState se permiten desde esta capa.

**Reglas:**
- Las referencias directas entre Feature Block de dominios distintos están prohibidas. Dentro de un mismo dominio, una Section puede contener otra Section como hija. Cuando pantallas de dominios distintos deben mostrarse juntas, el `{RouteName}Page` de la Route Surface coloca lado a lado la Section de cada dominio y las conecta mediante props y eventos.
- Un dominio es un directorio situado directamente bajo la raíz de features (`feature_root` del layer-map o, si no existe, el prefijo de `Feature_Block.domain_slice` en layer-rules). Los archivos de Feature Block fuera de la raíz no tienen aislamiento de dominio. Esta frontera es una frontera de porciones de código y no garantiza el significado de un dominio de negocio.
- Ensambla Semantic Component, Primitive UI, DataState y Contract.
- No asume responsabilidades de enrutamiento ni de provider a nivel de app.

El sufijo es `{UseCase}Section` (un fragmento de pantalla sin ruta — equivale al Partial de la variant atomic); según la forma se usan `Panel` · `Dialog` · `Table`. Los sufijos `Block`, `Container` y `Partial` están prohibidos (`core/rules/naming-convention.yaml` → `Feature_Block.forbidden_suffixes`).
La Section es el **propietario del estado de su caso de uso** (una Section hija que es una unidad de guardado independiente es propietaria del suyo): declara los Props, mantiene directamente el estado local, los efectos y los hooks de adapter de DataState, y propaga hacia abajo únicamente. El renderizado se delega en una `View` (Semantic Component):
`Route Surface → Section → View → Primitive UI`. La propiedad del estado se divide en tres — ser dueña de un borrador local, observar la caché del servidor y ser responsable del comando de guardado. Una Section hija del mismo dominio es dueña del borrador y de las mutations solo cuando es su propio caso de uso y una unidad de guardado independiente; solo el estado compartido con el padre llega por props. Un borrador editado por varias Section tiene un solo propietario, y el submit, el cancel o el guardado atómico entre Section corresponden a un único coordinador (la Section padre), con los inputs internos como View o controlled components. La atomicidad proviene de un único comando o transacción de DataState/API, no de la invalidation tras varias mutations. Que varias Section observen la misma query key no es una propiedad duplicada. Separar la lógica de estado en hooks no es una obligación; solo la llamada al servicio (transport) y el procesamiento común que usan dos o más Section se dejan fuera, como estructura de referencia. El criterio de separación y el nombrado de Props están en `profiles/frontend.next-web/docs/es/frontend-react.md`.

## Route Surface

Se encarga del punto de entrada por URL, los route params, la frontera de permisos y el ensamblado de pantallas.

**Reglas:**
- Coloca Feature Block — en principio una sola Section. Si hay dos o más, se añade un componente de ensamblado `{RouteName}Page`. Ese componente de ensamblado es una Route Surface esté donde esté (routes o features); en el layer-map, su mapeo va antes del mapeo de Feature Block.
- No se exporta como UI reutilizable.
- Las llamadas directas a transport están prohibidas. Las llamadas a hooks de DataState también — DataState no figura en `can_reference`.

Las reglas de archivos de cada router se definen en la convention del framework, no en Core.

## App Shell

Se encarga de los provider globales, la navigation y el layout a nivel de app.

**Reglas:**
- No referencia directamente a Feature Block.
- No contiene lógica de casos de uso del dominio.
- Solo trata los provider globales y el layout a nivel de shell.
- Un paquete de shell compartido por varias apps (zonas) también es App Shell. El paso de una app a otra se hace solo por URL.

## Separación Core / Convention / Profile

| Naturaleza | Ubicación | Ejemplo |
|---|---|---|
| Frontera de arquitectura verificable | Core `core/docs/es/architecture/frontend-web.md`, `core/rules/layer-rules.yaml` | Prohibido referenciar DataState desde Semantic Component |
| Contrato de diseño (tokens · variantes · composición · coherencia) | Core `core/docs/es/architecture/frontend-design-contract.md` | El componente referencia alias (los tokens de componente solo desde su propietario), design_ref y estado de alineación |
| Enlace con framework/biblioteca | `profiles/<id>/docs/es/` | query hook, router, herramienta de estilos, mapeo de archivos de tokens |
| Política heredada/de transición del proyecto | `.strata/` del proyecto | legacy/bridge/target zone |

Strata Core no define «qué biblioteca se usa», sino «qué responsabilidad debe pasar por qué capa».
