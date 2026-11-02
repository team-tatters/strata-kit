# Arquitectura de capas de la variante Atomic del frontend

> Canónico: strata-kit `core/docs/es/architecture/frontend-atomic.md` — migrado desde strata `docs/03-architecture/frontend-atomic.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Reglas legibles por máquina: `core/rules/layer-rules.yaml` → `frontend.variants.atomic`
> La variante por defecto para proyectos web nuevos es `frontend.variants.web`; los detalles están en `core/docs/es/architecture/frontend-web.md`.
> **Estado: mantenida (compatibilidad heredada)** — no se recomienda adoptarla en trabajo nuevo. La clasificación por tamaño en Molecule/Organism ha sido sustituida por la Composition Legality de la variante web (`core/docs/es/architecture/frontend-design-contract.md`).

## Mapeo a la variante web

| Atomic | Variante web | Criterio |
|---|---|---|
| Atom | Primitive UI | Agnóstico al dominio, solo tokens alias + ejes de variante |
| Molecule | Semantic Component **o** Feature Block | Feature Block si llama a DataState; si no, Semantic Component. **No se juzga por tamaño** |
| Organism | (retirado) | Absorbido por Feature Block |
| Partial | Feature Block (`{UseCase}Section`) | Un fragmento de pantalla sin ruta |
| Page · Layout | Route Surface · App Shell | Igual |
| L2 Hook | DataState adapter | `useQuery{Name}` → `use{Entity}Query` |
| LM | Contract + DataState transport | ViewModel y DTO van a Contract, el API Client va a `{name}.service` |

## Estructura de capas

```
Page / Layout
    ↓
Partial (conjunto de UI común a nivel de página)
    ↓
Molecule (componente específico de un comportamiento)
    ↓
Atomic (componente de UI puro)
    ↓
L2 (Hook de gestión de estado)
    ↓
LM (ViewModel, DTO, API Client)
    ↓
L1 (funciones puras, tipos, constantes)
```

## L1 — capa de funciones puras

El mismo principio que el L1 del backend. Lógica pura que no depende de un framework de UI.
Se permiten Hooks de gestión de estado puros, pero se prohíben las llamadas a API.

**Ejemplos:** useDebounce, useLocalStorage, formatDate, validateEmail

## LM — capa de modelo de datos

La capa intermedia que se encarga de la comunicación con el servidor.

**Composición:** ViewModel (estructura de datos solo para mostrar), DTO (mapeo de petición/respuesta del servidor), 
API Port/Client Interface (el límite de la llamada de transporte), Interface (definición del contrato)

**Reglas:** Sin lógica de renderizado de UI. Se encarga solo de la transformación de datos y la comunicación.

## L2 — capa de gestión de estado

Hooks adapter para el estado de servidor/cliente.

**Reglas:** Usar el API Client de LM para sincronizar el estado del servidor.
No renderizar componentes de UI directamente. Exportar solo Hooks.

## Atomic — UI de unidad mínima

Un componente de UI puro al que se le han quitado todas las dependencias de L2 y de las capas inferiores.
Funciona solo con props, y se prohíbe el acceso al estado global.

**Ejemplos:** Button, Input, Badge, Avatar, Tooltip, Card

## Molecule — UI específica de un comportamiento

Un componente que combina Atomics y enlaza un Hook de L2.
Está especializado en un comportamiento concreto del dominio.

**Ejemplos:** SearchBar (Input + Button + useSearchStore),
OrderCard (Card + Badge + useOrderQuery)

## Partial — conjunto común a nivel de página

Un bloque de UI compartido entre varias páginas.
Una combinación de Molecules y Atomics.

**Ejemplos:** OrderListPartial, UserProfilePartial, NotificationPanel

## Page — destino de ruta

El componente de nivel superior asignado a una URL real.
Combina Layout, Partial, Molecule y Atomic para formar una pantalla completa.

## Layout — envoltorio estructural

Define la estructura de la página: navegación, barra lateral, pie de página, etc.
Recibe el componente Page como children.
