# Convención de React para frontend

> Fuente canónica: strata-kit `profiles/frontend.next-web/docs/es/frontend-react.md` — migrado desde strata `docs/05-conventions/frontend-react.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Límite de Core: `core/docs/es/architecture/frontend-web.md` · Contrato de diseño: `core/docs/es/architecture/frontend-design-contract.md`

Este documento describe las convenciones con las que un proyecto React implementa las capas web de Core.
React no es un requisito previo de Core.

## Cadena unidireccional — Page → Section → View → Primitive

El flujo va en una sola dirección, de la ruta a la pantalla. **La Section es la propietaria del estado de su caso de uso** (una Section hija que es una unidad de guardado independiente es propietaria del suyo): la Section declara los Props, mantiene el estado y lo propaga solo hacia abajo.

```
route file (Route Surface)
  └─ params · guard · metadata · exactamente un <XxxSection/>. Hooks: solo hooks de enrutamiento
      └─ XxxSection (Feature Block) — propietaria del estado
           │  useState · useEffect · hooks locales · hooks de DataState adapter (use*Query · use*Mutation) se llaman directamente aquí
           ├─ <XxxView/>          Semantic Component — solo recibe props y dibuja
           └─ <XxxSubSection/>    Section hija del mismo dominio si hace falta — propietaria del estado si es una unidad de guardado independiente:
                                  obtiene y guarda directamente los datos de su caso de uso; solo el estado compartido con el padre llega por props.
                                  Un input que se envía o cancela junto con el padre es una View o un controlled component,
                                  no una Section; el padre es dueño del borrador y del submit (guardado atómico: un comando o una transacción)
                └─ Primitive UI + tokens alias
```

## Propiedad del estado en una Section y criterio de separación

Lo que se queda dentro de una Section y lo que se saca se decide por **tipo, no por cantidad**. Separar la lógica de estado en un hook no es una obligación.

| Tipo | Ubicación | Motivo |
|---|---|---|
| Estado local (`useState` · `useReducer`), efectos (`useEffect`), valores derivados (`useMemo`), hooks locales que solo usa esta Section | **Dentro de la Section** | El propietario del estado debe verse en un solo lugar |
| Lectura y escritura del estado del servidor | La Section **llama** a hooks de DataState adapter. La implementación está en `query-hooks/` | El transport no aparece en la Section |
| Llamadas a servicios (HTTP · storage · SDK externo) | **Siempre fuera** — DataState transport | Los componentes no conocen el transport |
| Procesamiento, cálculo o lógica de estado usados por dos o más Sections | **Fuera** — `features/{domain}/hooks/use{Thing}` o una util de Foundation | Las capas comunes usan una estructura de referencia |
| Cuando otra Section debe reutilizar íntegra la lógica de estado de una Section, o debe probarse por separado | Opcional — separar como `use{UseCase}Section` | Se separa solo cuando es necesario. Lo predeterminado es dentro de la Section |

## Significado de los sufijos

| Sufijo | Capa | Llamadas a DataState | Hooks de router | Notas |
|---|---|---|---|---|
| `{Route}Page` / route file | Route Surface | Prohibido | Permitido | El principio es colocar 1 Section. Con 2 o más, un componente de ensamblaje `{Route}Page` — una Route Surface esté donde esté, routes o features (su mapeo en el layer-map va antes del de Feature Block). Aquí se colocan lado a lado las Section de dominios distintos |
| `{UseCase}Section` | Feature Block | Permitido | Prohibido — la Page los inyecta | Propietaria del estado. Fragmento de pantalla sin ruta, reutilizable en varias rutas. Prohibido importar la Section de otro dominio; una Section del mismo dominio puede contenerse como hija |
| `{UseCase}Panel` · `Dialog` · `Table` | Feature Block | Permitido | Prohibido | Una Section con forma de overlay, panel lateral o tabla |
| `{Domain}{Purpose}View` | Semantic Component | Prohibido | Prohibido | Solo props. Solo puede tener estado de UI local (abierto, hover) |
| Componente Primitive | Primitive UI | Prohibido | Prohibido | Solo alias + ejes variant |

Los sufijos `Container`, `Block` y `Partial` están prohibidos: se usa `Section` (o `Panel` · `Dialog` · `Table` según la forma).

## Nombres de props — el propietario y la dirección van en el nombre

Cuando el estado y los hooks que posee una Section bajan a varios hijos, solo con el nombre del prop debe poder saberse **quién es el propietario, en qué dirección fluye y si es un valor o una acción**. Prefijos y sufijos expresan esas tres cosas. Lectura por máquina: `core/rules/naming-convention.yaml` → `frontend.Props`.

| Función | Forma | Ejemplo | Regla |
|---|---|---|---|
| Valor actual del estado propiedad del padre (lectura) | Sustantivo, sin prefijo | `selectedIds` · `filter` · `page` | Sin prefijo = «del padre, el hijo solo lee» |
| Petición de cambio del estado del padre (hijo → padre) | `on{State}Change` | `onSelectedIdsChange` · `onFilterChange` | No se pasa el setter tal cual. Los props `set*` están prohibidos |
| Disparar una acción del padre (evento) | `on{Event}` (verbo) | `onSubmit` · `onRowClick` · `onDelete` | Cuando el hijo no necesita conocer el resultado |
| Un par valor + cambio **compartido por varios hijos** | Paquete `{state}Control` | `selectionControl={{ value, onChange }}` | Marca de referencia múltiple. Tipo `{State}Control`. No se reparte el mismo estado entre varios hijos como dos props, valor y callback |
| Paquete de datos derivados o solo de visualización | `{name}Model` | `orderModel` | El ViewModel de Contract. No se incluyen callbacks |
| Valor inicial (propiedad del hijo) | `default{State}` | `defaultPage` | No controlado. El padre no interviene después |
| Booleano | `is` · `has` · `can` · `should` | `isEditing` · `canDelete` · `shouldAutoFocus` | Forma afirmativa. Los nombres de atributos HTML como `disabled` son una excepción |
| Porción de estado del servidor | Sustantivo de datos + `is{Entity}Loading` + `{entity}Error` | `orders` · `isOrdersLoading` · `ordersError` | No se pasa el objeto de resultado de query completo |
| Delegación de renderizado | `render{Slot}` | `renderRow` | |
| ref | `{name}Ref` | `scrollRef` | |

**Recomendación — las referencias múltiples van en un paquete Control.** Cuando tres hijos leen y escriben un mismo estado del padre, se agrupan `value`, `onChange` y los valores derivados en un único objeto `{state}Control` que se pasa hacia abajo. El sufijo del nombre revela que es un estado propiedad del padre y compartido en varios lugares, y el número de props no crece al añadir hijos. Los prefijos planos como `shared*` o `section*` indican la propiedad pero no la dirección (lectura/escritura), por lo que no se usan.

```tsx
// Section — propietaria del estado
const [selectedIds, setSelectedIds] = useState<number[]>([]);
const selectionControl: SelectionControl = { value: selectedIds, onChange: setSelectedIds, count: selectedIds.length };
const { data: orders = [], isLoading: isOrdersLoading } = useOrderListQuery(filter);

<OrderTableView orders={orders} isOrdersLoading={isOrdersLoading} selectionControl={selectionControl} onRowClick={handleRowClick} />
<OrderBulkActionView selectionControl={selectionControl} onDelete={handleDelete} />
```

Las funciones manejadoras internas se llaman `handle{Event}`, y los nombres de los props que se pasan a los hijos son `on{Event}`. No se usa el mismo nombre para ambos.

## Component Boundary

- Se coloca un componente exportado por archivo.
- Se permiten funciones auxiliares y subcomponentes privados dentro del archivo, pero se separan en otro archivo si se reutilizan.
- DTO, ViewModel, schema e interface se mueven a Contract.
- Un Semantic Component no llama directamente a hooks de DataState; los recibe inyectados mediante props/callbacks.
- Los ejes del estado de los datos (loading · empty · error) se reciben como props de la View y se renderizan. La Section decide los valores.

## State Boundary

- El ensamblaje del use case y las llamadas a DataState comienzan en el Feature Block (Section).
- No se introduce en los shared UI components una dependencia de una biblioteca de estado del servidor.
- El feature-local context se usa de forma limitada, solo cuando el paso de props se vuelve profundo. Si un paquete Control lo resuelve, no se crea un context.
