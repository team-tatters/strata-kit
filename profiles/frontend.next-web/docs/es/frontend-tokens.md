# Convención de Tokens para frontend

> Fuente canónica: strata-kit `profiles/frontend.next-web/docs/es/frontend-tokens.md` — migrado desde strata `docs/05-conventions/frontend-tokens.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Contrato de Core: `core/docs/es/architecture/frontend-design-contract.md`

Este documento es la convención que asigna los tres niveles de tokens (Primitive → Alias → Component) a archivos, compilación y CSS de utilidad.
El proyecto puede cambiar el formato y las herramientas; si lo hace, lo registra en el profile del proyecto, no aquí.

## Archivo canónico

- Ubicación: un único archivo dentro del paquete Foundation (por ejemplo `tokens/tokens.json`).
- Formato: se recomienda JSON de W3C Design Tokens (DTCG): admite `$value`, `$type` y referencias alias (`{color.blue.80}`), y los plugins de sincronización de herramientas de diseño lo leen.
- Se colocan T1 y T2 en un mismo archivo, separados por grupos de nivel superior (`primitive.*`, `alias.*`). T3 es `component.*`, solo cuando hace falta.
- Los modos se expresan en el valor alias con `$extensions.modes` o en un archivo de modo aparte. El nombre es uno solo, independientemente del modo.

```json
{
  "primitive": { "color": { "blue": { "80": { "$type": "color", "$value": "#1b4380" } } } },
  "alias": {
    "color": {
      "action": { "primary": { "bg": { "default": { "$value": "{primitive.color.blue.80}" } } } },
      "surface": { "default": { "$value": "{primitive.color.common.0}" } }
    }
  }
}
```

## Productos generados (se resuelven solo en la etapa de compilación)

| Producto | Consumidor | Notas |
|---|---|---|
| Variables CSS (`--color-action-primary-bg-default`) | CSS de utilidad · tema en tiempo de ejecución | Solo se exponen alias. Las variables T1 se ocultan con un prefijo interno o no se generan |
| Constantes TS (`tokens.color.action.primary.bg.default`) | Donde se necesite un objeto de estilo | Los tipos se derivan de la ruta alias |
| Variables de la herramienta de diseño | Diseñadores | Herramienta de sincronización (por ejemplo Tokens Studio · Variables API); la dirección la decide el profile |
| **Catálogo de alias** (`tokens.md`, generado) | Agentes · revisores | Una línea por nombre, significado y uso. Se mantiene con un tamaño que quepa en el presupuesto de contexto T0 |

El código de los componentes usa solo los **nombres alias** de los productos generados. No importa directamente el archivo de tokens ni calcula valores.

## Asignación de CSS de utilidad

Las clases de utilidad son un medio de entrega de los alias. El nombre de la clase refleja tal cual la ruta alias.

| Permitido | Prohibido |
|---|---|
| `bg-surface-default` · `text-muted` · `border-status-pending` | `bg-blue-80`(T1) · `bg-[#1b4380]`(valor arbitrario) · `text-[13px]` |

La configuración del tema (por ejemplo Tailwind `@theme` o un preset) es un producto generado y no se edita a mano. No generar utilidades T1 (`bg-blue-80`) es la forma más sencilla de hacerlo cumplir.

## Stories (canónicas cuando no hay herramienta de diseño)

- Primitive UI: al menos una story por componente, mostrando en una tabla todas las combinaciones de variant · intent · size.
- Semantic Component: una story para cada eje de estado de datos (default · loading · empty · error).
- Foundation: se incluyen stories del catálogo de alias (color · espaciado · sombra · tipografía): una pantalla para que los diseñadores revisen sin herramienta.

## Comprobaciones

| Comprobación | Método | Ubicación |
|---|---|---|
| Valores raw fuera de Foundation | Comprobación de diff de líneas nuevas — literales hex · rgba · px · valores arbitrarios `[…]` · patrones de clases T1 | `profiles/frontend.next-web/enforcement/diff-rules.json.template` |
| Caducidad de excepciones | Se analiza `@strata:token-exception … until YYYY-MM-DD`; falla si hoy ya pasó esa fecha | El mismo script |
| Aprobación de cambios de tokens | Un PR con diff en el archivo de tokens lleva un DEC id en su cuerpo | Regla de CI o plantilla de PR |

## Prohibiciones

- Usar nombres T1, valores raw o valores arbitrarios en componentes
- Editar a mano un tema eludiendo el archivo de tokens
- Incluir nombres de paleta o de pantalla en los nombres alias (`color.blue.button`, `color.dashboard.header`)
