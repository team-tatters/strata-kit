# Convención de Next.js para frontend

> Fuente canónica: strata-kit `profiles/frontend.next-web/docs/es/frontend-next.md` — migrado desde strata `docs/05-conventions/frontend-next.md` (orden 2026.10.29-06, 2026-10-29). El YAML de reglas está en `core/rules/`.

> Límite de Core: `core/docs/es/architecture/frontend-web.md`

Este documento explica cómo un proyecto Next.js se asigna al Route Surface y al App Shell de Core.
Next.js no es un requisito previo de Core.

## App Router

- Un route file (`page.tsx`) es un Route Surface.
- Los archivos de layout/provider/shell son el App Shell.
- Los fragmentos de pantalla reutilizables se separan como Feature Block (`Section`).
- Los route params, search params, metadata y el authorization boundary se resuelven en el Route Surface.

### Presupuesto de page.tsx

`page.tsx` solo hace **resolver params · guardia de autenticación · metadata · colocar una Section**. Los hooks de estado del servidor (query/mutation) y las llamadas a transport están prohibidos: se bajan a un Feature Block.
Si se necesita más de una Section, se coloca un componente de ensamblaje `{Route}Page` en el área de Feature y page.tsx renderiza solo ese componente.

## Pages Router

El Pages Router se gestiona como variant heredada o como migration zone del proyecto.
Las áreas nuevas priorizan la asignación del App Router. `pages/**` se asigna a Route Surface en el layer-map y su zone se marca como legacy.

## Server / Client Boundary

Usar o no Server Components, Client Components y server actions es una framework convention.
El límite de Core es el mismo. La llamada directa a transport y la ubicación de las llamadas a DataState no deben romper las reglas de capas.

## Multi-zone

En una estructura donde varias apps (zones) se unen bajo un mismo dominio mediante rewrites:

- Un paquete de shell que cruza zones (navegación, provider de sesión) es el **App Shell**. No referencia Feature Blocks.
- Puede que el QueryClient no esté separado por zone, por lo que el primer elemento de la query key es el identificador de la zone (`profiles/frontend.next-web/docs/es/frontend-query-state.md`).
- El desplazamiento entre zones se hace solo mediante enlaces (URL). No se importa el Feature Block de otra zone.
