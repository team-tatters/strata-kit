# Convención de frontend Swift/SwiftUI

> Fuente canónica: strata-kit `profiles/frontend.swiftui/docs/es/frontend-swiftui.md` — migrado desde strata `docs/05-conventions/frontend-swiftui.md` (orden 2026.10.29-06, 2026-10-29). Las reglas en YAML están en `core/rules/`.

> Frontera con Core: `core/docs/es/architecture/frontend-mobile.md` (`core/rules/layer-rules.yaml` → `frontend.variants.mobile`) · contrato de diseño: `core/docs/es/architecture/frontend-design-contract.md` · cumplimiento: `profiles/frontend.swiftui/enforcement/`
> v1 2026-09-10 (enlace con la variante web, primera aplicación en o-rot) → **v2 2026-09-11** (variante mobile — vocabulario, ensamblaje de Feature, targets, escalera de cumplimiento, hooks, DEC-2026-09-11-01)

Este documento es la convención para una app SwiftUI que implementa la variante mobile de Core (Foundation → … → App Shell).
SwiftUI no es un requisito previo de Core. Core solo decide "por qué capas debe pasar cada responsabilidad" y las reglas de ensamblaje y de compartición entre targets; este documento las aplica a las construcciones de Swift.

## Resumen

- La clave de primer nivel para identificar una capa es **el rol del tipo que contiene un archivo**, no el directorio. `.strata/layer-map.yaml` reclasifica por rol, y los archivos no se mueven.
- **La fuente canónica del cumplimiento es el compilador.** Cuantas más capas se suben a paquetes SPM locales, más se hacen visibles los límites en `import`. El verificador de referencias de tipos (`check-swift-layers.py`) es un apoyo que revisa la dirección entre archivos dentro de un mismo módulo.
- El propietario del estado es el Feature Block: una vista que crea su estado con `@StateObject` o lo recibe con `@EnvironmentObject`. Una vista que recibe solo `props` es un Semantic Component. La **creación** de los Store y la cadena de inyección por entorno están en un único lugar, el App Shell.
- Un Feature ensambla solo **padre → hijo** dentro del mismo árbol de dominio (`today` → `today/mood`). Una pieza compartida entre hermanos baja a un Semantic Component.
- Compartir entre targets significa añadir el target, no copiar. Foundation, Contract, Primitive y Semantic son libres; DataState exige `stateful: true` y separar explícitamente las instancias; Feature, Route y Shell están prohibidos.
- Para los tokens, la fuente canónica es `tokens.json` del repositorio de código, y el archivo de tokens de Swift es un artefacto generado. En las vistas están prohibidos el hex, las fuentes del sistema y los valores numéricos sin procesar.

## Capa ↔ construcciones de Swift

| Capa | Qué es en Swift | Marcador | Prohibido |
|---|---|---|---|
| Foundation | Enums de tokens (`Color`, `Font`, spacing), `Shape` puros, enums de constantes, utilidades puras como las zonas horarias | `enum {Name}Tokens` · solo `static let` | `ObservableObject`, I/O, `UserDefaults`, vistas |
| Contract | Modelos `Codable` y DTO, valores de estado de pantalla `{Name}UiState`, reglas de cálculo puras (`enum` + `static func`), analizadores de deep links, protocolos de puerto | tipos de valor · solo `import Foundation` | Importar SwiftUI, **propiedades de presentación** como color o icono, **el nombre `ViewModel`** (en móvil significa propietario de estado) |
| DataState | `Store` (propietario de estado en el actor principal) + `Repository`/`Service`/`Session` (I/O aislada) | `@MainActor final class {Name}Store: ObservableObject` · `actor {Name}Repository` | Renderizar vistas, referenciar directamente el Store de otro dominio |
| Primitive UI | Vistas del paquete del sistema de diseño, ajenas al dominio (Button, Chip, Row, TabBar) | `public struct {Name}: View` · props de eje (variant, intent, size) · **debe ser un paquete aparte** | Modelos de dominio, Store |
| Semantic Component | Vistas con significado que dibujan solo a partir de props/UiState — gráficos, escenarios, cabeceras, estados vacíos, extensiones de presentación de los modelos | `struct {Domain}{Purpose}View: View` · `{Model}+Style.swift` · `@EnvironmentObject` 0 | Acceso a Store, `@StateObject` |
| Feature Block | Propietario del estado de un fragmento de pantalla — sostiene un Store con `@StateObject`/`@EnvironmentObject` y propaga props hacia abajo | `struct {UseCase}View` · `{UseCase}Sheet` · árbol de dominio `today/mood` | Referenciar el Feature de un dominio hermano, poseer el grafo de navegación |
| Route Surface | Puntos de entrada de `TabView` y `NavigationStack`, `navigationDestination`, selección de pestaña, resolución de deep links | `MainTabView` · `{Flow}Flow` | **Crear o referenciar** Store (la inyección corresponde al App Shell), exportar UI reutilizable |
| App Shell | `@main struct App`, creación de los Store globales y cadena `.environmentObject`, `WidgetBundle`, cromo del shell (barra de pestañas) | `{Name}App` · `{Name}Shell` · `{Name}Bundle` | Lógica de casos de uso del dominio, referenciar directamente un Feature |

`can_reference` es exactamente la tabla de Core. Solo se añaden tres puntos propios de SwiftUI.

- **La inyección por entorno es una referencia.** `@EnvironmentObject var store: TodoStore` significa que ese archivo referencia `TodoStore`. Un Semantic Component no debe tener `@EnvironmentObject`.
- **Crear con `@StateObject` es poseer.** Los Store se crean en el App Shell, y el estado propio de una pantalla solo en un Feature Block. Que un Route Surface cree un Store es una violación (la forma en que `MainTabView` de o-rot creaba ocho stores dio origen a esta regla).
- **`@main` es el App Shell.** Si una decisión de punto de entrada, como la bifurcación entre onboarding y principal, está en `@main`, baja esa bifurcación a una vista `{Name}Shell` y deja en `@main` solo la creación e inyección de los Store. Hasta que se separe, se mantiene en `exceptions` del layer-map junto con un DEC.

## Ensamblaje de Feature

```
Features/Today/TodayView.swift          domain: today        ← sostiene el Store mediante @EnvironmentObject
Features/Today/Mood/MoodSheetView.swift domain: today/mood   ← el padre (today) la presenta con .sheet
Features/Activity/ActivityView.swift    domain: activity     ← hermano de today. Usar MoodSheetView es una violación
```

- El dominio se escribe en el campo `domain:` de `layer-map.yaml` como una ruta con `/`. El verificador solo deja pasar las referencias padre → hijo.
- Si dos hermanos presentan la misma hoja (sheet), la parte de renderizado de esa hoja baja a un Semantic Component (`MoodPickerView`), y cada Feature lo envuelve con su propio Store.
- Si se usa TCA, el `Scope` del reducer padre es exactamente esta arista. No se fija el nombre del patrón — solo se respeta la dirección de la arista.

## Targets

- Teléfono, widget, reloj, complicación e intent son, cada uno, un target. Compartir consiste en **añadir el archivo** a los `sources` de cada target en `project.yml`; no se hacen copias.
- La lista de lo compartido se transcribe a `targets.shared` de `layer-map.yaml`. El verificador contrasta las capas (`target_share`).
- Si dos targets comparten un DataState (por ejemplo, el reloj usa el archivo `HealthStore` del teléfono), se declara `stateful: true` y se documenta que cada target tiene su propia instancia y qué lee cada uno.
- El intercambio de datos entre targets (`UserDefaults` de App Group, `WatchConnectivity`) lo asume un único archivo `{Name}Session`/`{Name}Bridge` de DataState. Una vista que abre directamente `UserDefaults(suiteName:)` es una violación.

## Propiedad del estado y modelo de observación

- Lo predeterminado es `ObservableObject` + `@Published` + `@MainActor`. Los Store son clases y los modelos son estructuras.
- `@Observable` (el framework Observation) se usa **solo cuando el target de despliegue es iOS 17 / watchOS 10 o posterior**. Los dos modelos difieren en los property wrappers (`@StateObject` ↔ `@State`) y en la granularidad de actualización, por lo que mezclarlos desajusta el momento de inicialización — un proyecto usa un solo modelo. ([Apple: Observation](https://developer.apple.com/documentation/observation), [Squires: not a drop-in replacement](https://www.jessesquires.com/blog/2024/09/09/swift-observable-macro/))
- Un Store conoce solo su propio dominio. El ensamblaje que une dos Store lo hace un Feature Block. Si un Store referencia a otro Store, es una violación de referencia cruzada entre dominios de DataState.
- La persistencia termina dentro del Store/Repository. Si `UserDefaults.standard` o la I/O de archivos aparecen en una vista o en Contract, es una violación.

## Concurrencia

- El modo de lenguaje Swift 6 convierte las carreras de datos en errores de compilación. Se adopta de forma **gradual**: `SWIFT_STRICT_CONCURRENCY = targeted` → `complete` → modo de lenguaje 6. No se activa todo de una vez. ([Apple: Adopting strict concurrency](https://developer.apple.com/documentation/swift/adoptingswift6))
- Todos los Store que tocan las vistas son `@MainActor`. La I/O vuelve al Store mediante `actor {Name}Repository` o `nonisolated` + `Task { @MainActor in … }`. Los callbacks de delegados (`WCSessionDelegate` y similares) siguen la misma convención.
- Los modelos (estructuras) se ajustan a `Sendable` por defecto. Si el paquete Contract exporta solo `Sendable`, los límites de actor encajan por sí solos.

## Nomenclatura — las Swift API Design Guidelines tal cual

La fuente canónica son las [swift.org API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/). Donde chocan con `common.case_styles` de `core/rules/naming-convention.yaml` de Core, **gana la convención de Swift** (tabla siguiente). El nombre del archivo es igual al del tipo de nivel superior que contiene.

| Elemento | Swift | Diferencia con lo predeterminado de Core |
|---|---|---|
| Tipos, protocolos | `UpperCamelCase` | Igual |
| Funciones, variables, propiedades, case | `lowerCamelCase` | **Los case de enum van en lowerCamelCase** — no se usa el `UPPER_SNAKE` de Core |
| Constantes | `lowerCamelCase` (`static let graceDays`) | No se usa el `UPPER_SNAKE` de Core |
| Booleanos | Se leen como afirmaciones — `isEmpty` · `hasWatch` · `canDelete` | Igual que la regla Props de Core |
| Valor de estado de pantalla | `{Name}UiState` (Contract) | No se usa el `{Name}ViewModel` de Core web — en móvil, ViewModel es un propietario de estado |
| Propietario de estado | `{Name}Store` (DataState) | Equivale al `use{Name}State` de Core web |
| Fábrica | `make…` | |
| Par mutante/no mutante | `sort()` / `sorted()`, `append` / `appending` | |
| Protocolo | Lo que es → sustantivo, capacidad → `-able` `-ible` `-ing` | |
| Siglas | Mayúsculas/minúsculas uniformes — `hrvSeries` · `isHRV` (todo en mayúsculas solo donde empieza en mayúscula) | |
| Etiquetas de argumento | Que se lean como una oración. Si el primer argumento es una frase preposicional, la etiqueta es obligatoria | |
| Sufijos prohibidos | `Manager` · `Helper` · `Impl` | Igual que Core. `Handler` solo en métodos de delegado |

Lo que corresponde a Props son los argumentos de `init` de la vista y sus propiedades almacenadas. Se aplica la regla `Props` de Core: el estado del padre es un sustantivo sin prefijo, la solicitud de cambio es `on{State}Change`, el evento es `on{Event}` y el manejador interno es `handle{Event}`. En SwiftUI, `Binding<T>` es un "par valor + cambio", por lo que equivale al paquete `{state}Control` de Core — si varios hijos usan el mismo estado, se pasa un único `Binding` hacia abajo.

El bloque `naming:` de `layer-map.yaml` no lo hace cumplir el verificador. Nombre de archivo = nombre del tipo de nivel superior es una convención que se revisa en la revisión de código.

## Escalera de cumplimiento — el compilador es la fuente canónica

| Nivel | Responsable de | Fuerza |
|---|---|---|
| Paquete SPM local (`Package.swift`) | Aísla Foundation, Contract, DataState y Primitive UI del target de la app. Un paquete no puede importar la app, y las dependencias entre paquetes van solo en la dirección declarada en `dependencies:` | **Impuesto por el compilador — fuente canónica** |
| Target (`project.yml` / target de Xcode) | App, widget, reloj, pruebas. Los fuentes compartidos se añaden al target archivo por archivo | Impuesto por el compilador |
| `check-swift-layers.py` | Dirección de capas entre archivos **dentro** de un módulo, aislamiento de dominio, ensamblaje de Feature, compartición entre targets | CI blocking |
| Regla `--style` / SwiftLint custom_rules | Nueva entrada de valores sin procesar, fuentes del sistema, `Color(hex:)` y similares | CI blocking, se recomienda sobre líneas nuevas |
| Hook de edición | El mismo verificador sobre los **archivos cambiados en el árbol de trabajo de git** (`--changed`) | exit 2 → retroalimentación al agente |

- **Etapas de paquetes.** Un proyecto brownfield empieza con un paquete de sistema de diseño (Foundation + Primitive UI). Después viene Contract (modelos, reglas, valores `Sendable`) y luego DataState. Cada vez que se sube una etapa, ese límite se hace visible en `import`, de modo que el hook de Core basado en imports también funciona en Swift, y la parte del verificador de referencias de tipos se reduce al interior del target de la app (Semantic → Feature → Route → Shell). Esqueleto: `profiles/frontend.swiftui/enforcement/Package.swift.template`.
- **La gestión de paquetes se hace solo con SPM.** No se adoptan CocoaPods ni Carthage en proyectos nuevos. ([DECODE: modularize with SPM](https://decode.agency/article/project-modularization-swift-package-manager/), [Nimble](https://nimblehq.co/blog/modern-approach-modularize-ios-swiftui-spm))
- **El proyecto se genera de forma declarativa.** No se edita `.xcodeproj` a mano; se genera desde el `project.yml` de XcodeGen (o Tuist). El grafo de targets debe revisarse como texto para que las decisiones de capas y targets aparezcan en el PR. ([XcodeGen vs Tuist](https://medium.com/@sayefeddineh/xcodegen-vs-tuist-choosing-the-right-tool-for-xcode-project-generation-bea093c6e105))
- Los paquetes externos se **fijan por versión** (`exact` o `upToNextMinor`) y se confirma `Package.resolved`.
- **El hook de edición se engancha por git, no por evento de herramienta.** Si el PostToolUse de Claude Code se engancha solo a `Write|Edit`, las ediciones por Bash (sed, heredoc) se saltan la verificación. Se fija el matcher en `Write|Edit|Bash`, y ante un evento de Bash el verificador recurre a `--changed` (basado en git status). Plantilla de configuración: `profiles/frontend.swiftui/enforcement/settings.json.template`.

## Tokens y tipografía (enlace con el contrato de diseño)

- La fuente canónica es `tokens.json` del repositorio. El archivo de tokens de Swift (`{Name}Tokens.swift`) es su artefacto generado, y la inicialización con `Color(hex:)` aparece **solo dentro de este archivo**.
- Las vistas usan solo nombres de alias: `OrotColor.sage700` ○ / `Color(hex: "507663")` ✗ / `.font(.system(size: 13))` ✗ / `.padding(14)` debe usar un token de spacing.
- Un alias nuevo es una decisión de arquitectura — registro de decisión + `tokens.json` → Swift, en ese orden. Un valor temporal se escribe `/// @strata:token-exception … until YYYY-MM-DD`.
- Los tokens tipográficos tienen tres ejes: escala de texto (título, cuerpo, pie), **tamaño de icono** (`icon.sm/md/lg` — sustituye a `.font(.system(size:))` en los SF Symbol) y **escala de plataforma** (el reloj no es una reducción del teléfono, sino una escala aparte). Si queda un `.font(.system` por falta de un eje, primero va el DEC que añade el token.
- La accesibilidad la contienen los tokens: solo se usan en texto los alias con un contraste de texto de 4.5:1 o más, y los que quedan por debajo se marcan en el nombre como solo para no texto. Dynamic Type lo absorbe el token mediante `Font.custom(_:size:relativeTo:)`.

## Formato y lint

- Como formateador se usa **swift-format** (`swift format`, `xcrun --find swift-format`), incluido en la toolchain de Xcode 16+. La configuración es un único archivo `.swift-format` (plantilla: `profiles/frontend.swiftui/enforcement/swift-format.json.template`). ([Xcode 16 swift-format](https://mjtsai.com/blog/2024/11/06/swift-format-in-xcode-16/))
- El lint con SwiftLint es **opcional**. Strata solo exige unas pocas `custom_rules`, así que incluso sin SwiftLint, `check-swift-layers.py --style` ejecuta las mismas expresiones regulares. Si se usa SwiftLint, se fusiona `profiles/frontend.swiftui/enforcement/swiftlint-strata.yml.template` en `.swiftlint.yml`. ([SwiftLint custom rules](https://github.com/realm/SwiftLint#defining-custom-rules))

## Marcadores

Se colocan en comentarios de documentación `///` (`core/docs/es/conventions/strata-markers.md`):

```swift
/// Reglas de traducción del estado de hoy — solo funciones puras.
/// @strata:layer Contract
/// @strata:domain today
enum StateEngine { … }
```

## Pruebas

- El target de pruebas unitarias verifica Contract y DataState directamente con `@testable import {App}`. Una capa convertida en paquete se prueba en el target de pruebas del propio paquete. Las pruebas de vistas no son capturas (snapshots): verifican la ruta **Store → estado → texto de la pantalla**.
- Las pruebas de Store se aíslan con `UserDefaults(suiteName: UUID)` o con un directorio temporal. Las pruebas no tocan `.standard`.
- Los archivos se llaman `{Type}Tests.swift`, y el directorio del target de pruebas se excluye en el layer-map con `_test`. El verificador omite en silencio los archivos fuera de `swift.sources`.

## Procedimiento de adopción en brownfield

1. Crea `.strata/layer-map.yaml` a partir de `profiles/frontend.swiftui/enforcement/layer-map.yaml.template` (`variant: mobile`). Clasifica **por rol** y no muevas archivos. Escribe los dominios de Feature como un árbol con `/`.
2. Lleva los no mapeados a 0 con `check-swift-layers.py --summary`.
3. Transcribe a `targets.shared` los fuentes compartidos por target de `project.yml`. Para compartir DataState, `stateful: true` + documentación.
4. Mira las violaciones con `--all`. Sepáralas en tres — lo que se corrige ahora / lo que se registra en `exceptions` junto con un DEC / lo que se congela con `--write-baseline` y solo se bloquea lo nuevo.
5. Activa `--style` y repite el mismo procedimiento.
6. Pon `--all --style --ignore-known` en CI. El hook de edición es `profiles/frontend.swiftui/enforcement/settings.json.template` (Write|Edit|Bash → stdin, `--changed` para Bash).
7. Sube la escalera de paquetes: sistema de diseño → Contract → DataState. En cada etapa, actualiza `swift.sources` y el mapeo del layer-map y regenera el baseline.

## Lo que este documento no decide

No decide el nombre de un patrón de arquitectura (MVVM, TCA, Clean). Se use el nombre que se use, basta con que se cumpla que "el Store es DataState, la propiedad del estado es del Feature Block, las vistas de props son Semantic, el ensamblaje es padre → hijo". La capa de red y las herramientas de caché de estado del servidor también se dejan como constraint del proyecto — pero la regla de Core es la misma: el transport solo es visible dentro de DataState y no se expone a las vistas. Para el enlace con Compose/Android solo existe la tabla de correspondencias de `core/docs/es/architecture/frontend-mobile.md` §Android, y todavía no hay un documento aparte.
