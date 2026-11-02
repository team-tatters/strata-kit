# Arquitectura de capas del frontend Mobile

> Canónico: strata-kit `core/docs/es/architecture/frontend-mobile.md` — migrado desde strata `docs/03-architecture/frontend-mobile.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Reglas legibles por máquina: `core/rules/layer-rules.yaml` → `frontend.variants.mobile` (DEC-2026-09-11-01)
> Este documento es la descripción detallada, legible por personas, de la variante de UI móvil nativa (SwiftUI, Jetpack Compose).
> Enlaces: `profiles/frontend.swiftui/docs/es/frontend-swiftui.md` (verificado, o-rot) · todavía no hay enlace con Compose (§Android).
> Los tokens, las variantes, la composición y la alineación de los artefactos de diseño los define `core/docs/es/architecture/frontend-design-contract.md`.

## Por qué una variante distinta de web

Las ocho capas y la tabla de `can_reference` son **exactamente las mismas** que en `web`. En la primera adopción de SwiftUI (o-rot, 2026-09-10), las 46 violaciones
fueron todas problemas de límites de archivo y ninguna fue un problema de diseño, así que la semántica de las capas se traslada sin cambios. Cuatro cosas son distintas.

| Eje | web | mobile |
|---|---|---|
| Vocabulario | Puntos de entrada por URL, `use*Query`, `.service.ts`, el `{Name}ViewModel` del Contract = forma de los datos | Puntos de entrada del grafo de navegación, `Store`/`Repository`, el Contract usa `UiState`/`UiModel`. **El nombre ViewModel significa propietario del estado, por lo que no se usa en Contract** |
| Ensamblado de Feature | Se prohíben las referencias entre Feature Blocks | Se permite el ensamblado **padre → hijo** dentro del mismo árbol de dominio (`composition: parent_child`). Se prohíben los hermanos y el sentido inverso |
| Targets | Zonas y paquetes | La app, el widget, el reloj y el intent **meten archivos en varios targets** para compartirlos. Core decide qué capas se pueden compartir |
| Escalera de aplicación | Análisis estático de rutas de import | El compilador (límite de módulo) es el canónico; el comprobador de referencias de tipos es un complemento **dentro** del módulo |

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

## Capas ↔ construcciones móviles

| Layer | SwiftUI | Compose (sin verificar) |
|---|---|---|
| Foundation | `enum` de tokens, `Shape` puro, utilidades de zona horaria | `object` de tokens, extensiones de `MaterialTheme`, utilidades puras |
| Contract | Structs `Codable`, `{Name}UiState`, `enum` de reglas puras + `static func`, parser de deep links | `data class`, `sealed interface UiState`, funciones puras de use case |
| DataState | `@MainActor final class {Name}Store: ObservableObject` + `actor {Name}Repository` | `ViewModel` (propietario del estado) + `Repository` (`suspend` + `Dispatchers.IO`), Room/DataStore |
| Primitive UI | `public struct: View` del paquete del sistema de diseño | Composables sin estado en el módulo `core:designsystem` |
| Semantic Component | Vistas que reciben solo props, `@EnvironmentObject` 0, `{Model}+Style.swift` | Composables que reciben solo `UiState`, `hiltViewModel()` 0 |
| Feature Block | Fragmentos de pantalla que sostienen `@StateObject`/`@EnvironmentObject` | `{UseCase}Screen` + `hiltViewModel()` |
| Route Surface | `TabView`, `NavigationStack`, `navigationDestination`, resolución de deep links | `NavHost`, rutas type-safe, deep links |
| App Shell | `@main App`, creación de Stores globales y la cadena de `.environmentObject`, `WidgetBundle` | `Application`, `MainActivity`, módulos Hilt, `Scaffold` |

## Ensamblado de Feature (composition)

Una pantalla móvil es una jerarquía: la pantalla Hoy presenta una hoja de estado de ánimo, y la pestaña Actividad presenta una hoja de sesión completada. Si se mantuviera tal cual el "sin referencias entre Feature Blocks" de web,
todo este ensamblado sería una violación. Mobile usa el dominio como ruta.

- Un dominio forma un árbol con `/`, como `today` y `today/mood`. Se declara en `domain:` de `.strata/layer-map.yaml`.
- **Un padre puede referenciar a su hijo.** El Feature Block de `today` ensambla la hoja de `today/mood`.
- Hijo → padre y entre hermanos (`today` ↔ `activity`) están prohibidos. Si dos dominios usan el mismo fragmento, ese fragmento baja a Semantic Component.
- El ámbito de reducer padre → reducer hijo de TCA y el de Screen padre → Screen hijo de Compose siguen la misma regla.

## Targets

En las plataformas de Apple, la app, el widget, el reloj, la complicación del reloj y los App Intents son cada uno un target; en Android son los módulos de app, widget y Wear. Es costumbre meter un archivo en varios targets,
y copiar es la semilla de la deriva (drift). Core decide solo **qué se puede compartir**.

| Capa | Compartir | Condición |
|---|---|---|
| Foundation · Contract · Primitive UI · Semantic Component | Libre | No tienen estado |
| DataState | Condicional | `layer-map targets.shared[].stateful: true` + el documento debe indicar que **cada target tiene su propia instancia** (por ejemplo, el HealthStore del reloj lee su propio HealthKit) |
| Feature Block · Route Surface · App Shell | Prohibido | Cada target tiene pantallas, puntos de entrada y shell distintos |

El comprobador lee `targets.shared` de `layer-map.yaml` y lo contrasta con las capas (una violación `target_share`). La fuente canónica es el archivo del proyecto
(`sources` por target en `project.yml`), y el layer-map transcribe esa declaración.

## Escalera de aplicación

| Nivel | Responsable | Fuerza |
|---|---|---|
| Límite de módulo (paquete SPM / módulo Gradle) | Aísla Foundation · Contract · DataState · Primitive UI del target de la app. Un paquete no puede importar la app | **Impuesto por el compilador — canónico** |
| Target | App, widget, reloj, tests. Se comparte añadiendo un target por archivo | Impuesto por el compilador |
| Comprobador de referencias de tipos (`check-swift-layers.py`) / ArchUnit · Konsist | Dirección entre archivos **dentro** de un módulo, aislamiento de dominio, ensamblado, compartición de targets | CI blocking |
| reglas de style | Nueva introducción de valores raw, fuentes del sistema, `Color(hex:)` | CI blocking, solo sobre líneas nuevas |
| Hook de edición | Los mismos comandos anteriores sobre los archivos cambiados — **según el árbol de trabajo de git** (no según eventos de herramientas) | warning → exit 2 como retroalimentación al agente |

Cada vez que se eleva un paquete, la parte del comprobador se reduce. Cuando Contract y DataState pasan a ser paquetes, ese límite aparece en `import`,
y el hook basado en imports de Core también funciona en Swift. Un proyecto brownfield empieza con un paquete del sistema de diseño y eleva Contract y después DataState, en ese orden.

## Android (sin verificar)

El equivalente en Compose es solo la columna derecha de la tabla anterior, y no se ha verificado en un proyecto real. Cosas que confirmar al aplicarlo:

- Las tres capas UI / Domain / Data de la guía oficial de Google se corresponden con (Primitive+Semantic+Feature+Route) / Contract / DataState de mobile. Es un detalle más fino, no un conflicto.
- La aplicación reutiliza Gradle multimódulo más el modo brownfield (layer-map) de `profiles/backend.kotlin-spring-cqrs/enforcement/`. Los imports de Kotlin son explícitos, así que no hace falta un comprobador de referencias de tipos.
- La restauración tras la muerte del proceso (`SavedStateHandle`), la recolección consciente del ciclo de vida, la ubicación de los módulos de DI (App Shell) y el `commonMain` de KMP (compartir Contract + DataState) los decide el documento del enlace con Compose. Backlog de metodología MB-o-rot-2026-004.

## Separación Core / Convention / Profile

- **Core** (este documento + `core/rules/layer-rules.yaml`): reglas de capas, `can_reference`, ensamblado y compartición de targets. Independiente de la plataforma.
- **Convention** (`profiles/frontend.swiftui/docs/es/frontend-swiftui.md`, más adelante `frontend-compose.md`): cómo asociar las capas a las construcciones del lenguaje, concurrencia, nombres, gestión de paquetes.
- **Profile** (`.strata/layer-map.yaml` · `constraint-registry.yaml` del proyecto): mapeo de archivos, árbol de dominios, lista de compartición de targets, excepciones.
