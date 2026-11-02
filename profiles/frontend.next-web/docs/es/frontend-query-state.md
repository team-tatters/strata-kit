# Convención de Query / State para frontend

> Fuente canónica: strata-kit `profiles/frontend.next-web/docs/es/frontend-query-state.md` — migrado desde strata `docs/05-conventions/frontend-query-state.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Límite de Core: `core/docs/es/architecture/frontend-web.md`

Este documento es la convention que asigna la capa DataState a una biblioteca concreta.
La source of truth de Core es «la UI no llama a transport directamente»; este documento describe las opciones de implementación.

## Dos tramos dentro de DataState

| Tramo | Archivo | Función | Puede referenciar |
|---|---|---|---|
| transport | `{name}.service.ts` | Llamadas al HTTP client, devuelve DTO | Foundation · Contract |
| adapter | `use{Entity}Query.ts` · `use{Entity}{Action}Mutation.ts` · `use{Name}State.ts` | Hooks de estado de servidor/cliente | Foundation · Contract · **transport** |

Solo un adapter puede importar transport. Los componentes (Section), el Route Surface y los hooks comunes ven únicamente adapters.

## Nombres de hooks

| Tipo | Nombre | Ubicación (capa) |
|---|---|---|
| Lectura de estado del servidor | `use{Entity}Query` · `use{Entity}ListQuery` | DataState adapter |
| Escritura de estado del servidor | `use{Entity}{Action}Mutation` (Create · Update · Delete · Submit …) | DataState adapter |
| Separar la lógica de estado de una Section (opcional) | `use{UseCase}Section` — solo cuando otra Section la reutiliza o se prueba por separado. Lo predeterminado es dentro de la Section | Feature Block |
| Procesamiento/cálculo común | `use{Thing}` — lógica usada por dos o más Sections | Feature Block hooks o Foundation |
| Estado del cliente | `use{Name}State` · `use{Name}Store` | DataState adapter |
| Utilidad pura | `use{Thing}` — depende solo de hooks del framework | Foundation |

**Prefijos prohibidos**: `useFetch · useGet · usePost · usePut · usePatch · useDelete`. Los verbos HTTP son vocabulario de transport; los hooks usan vocabulario de dominio.
El código existente no se toca y solo se comprueban las líneas nuevas (`profiles/frontend.next-web/enforcement/`).

## Query Key — forma · propiedad · cumplimiento

Las claves se crean únicamente mediante una fábrica de claves: una por funcionalidad (dominio), guardada en el `{domain}.keys.ts` de esa funcionalidad.

```ts
// features/{domain}/{domain}.keys.ts
export const orderKeys = {
  all:     ['shop', 'order'] as const,                       // [scope, domain]
  lists:   () => [...orderKeys.all, 'list'] as const,
  list:    (p: OrderListRequest) => [...orderKeys.lists(), p] as const,
  details: () => [...orderKeys.all, 'detail'] as const,
  detail:  (id: number) => [...orderKeys.details(), id] as const,
};
```

- **Forma**: `[scope, domain, entity/scope…, params]`. El primer elemento es el identificador de app o zone: varias apps pueden compartir el QueryClient, así que evita colisiones.
- **Jerarquía**: `all → lists → list(p)`, `all → details → detail(id)`. Una clave plana (`['orders']`) no permite invalidación parcial, por lo que no cumple.
- **Propiedad**: la invalidación se hace solo desde un hook de mutation, y solo con las claves que ese hook **declara como afectadas**, mediante una lista de etiquetas en `meta.invalidates` de la mutation o una lista explícita dentro del hook. Las claves declaradas pueden ser un **subárbol** como `keys.lists()`, una clave de detalle exacta como `keys.detail(id)` o claves de otro dominio, siempre construidas con la fábrica de claves de la funcionalidad propietaria. Llamar a `invalidateQueries` directamente en un componente está prohibido.
- **Cumplimiento**: el análisis estático de dependencias no detecta literales en línea; se bloquean solo las líneas nuevas con reglas de diff (`no-inline-query-key`, `no-component-invalidate`).

## Reglas básicas

- El estado del servidor se envuelve en adapters de query/mutation.
- La política de cache invalidation posterior a una mutation se coloca en DataState.
- El estado global no es la opción predeterminada. Se consideran primero URL state, query cache y local state.
- Si el paso de props se vuelve excesivo, se coloca un composition boundary dentro del Feature Block o un feature-local context.

## Prohibiciones

- Llamar al transport client directamente desde un componente de UI
- Que un Route Surface contenga detalles de mutation por use case
- Que un Semantic Component llame directamente a un server-state adapter
- Literales de queryKey fuera de `*.keys.ts`

## Asignación de bibliotecas

En proyectos de la familia React, DataState puede implementarse con query hooks, mutation hooks y client-state hooks.
La biblioteca concreta y su API según la versión se deciden en el profile del proyecto o en la framework convention.
