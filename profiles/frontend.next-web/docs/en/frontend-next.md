# Frontend Next.js Convention

> Canonical source: strata-kit `profiles/frontend.next-web/docs/en/frontend-next.md` — migrated from strata `docs/05-conventions/frontend-next.md` (order 2026.10.29-06, 2026-10-29). Rule YAML lives in `core/rules/`.

> Core boundary: `core/docs/en/architecture/frontend-web.md`

This document explains how a Next.js project maps onto Core's Route Surface and App Shell.
Next.js is not a required prerequisite of Core.

## App Router

- A route file (`page.tsx`) is a Route Surface.
- Layout, provider and shell files are the App Shell.
- Reusable screen fragments are split out as Feature Blocks (`Section`).
- Route params, search params, metadata and the authorization boundary are resolved in the Route Surface.

### page.tsx budget

`page.tsx` does only **params resolution, auth guard, metadata, and placing one Section**. Server-state hooks (query/mutation) and transport calls are forbidden — push them down into a Feature Block.
If more than one Section is needed, put a `{Route}Page` assembly component in the Feature area, and page.tsx renders only that one component.

## Pages Router

The Pages Router is managed as a legacy variant or a project migration zone.
New target areas prefer the App Router mapping. `pages/**` is mapped to Route Surface in the layer-map, and its zone is set to legacy.

## Server / Client Boundary

Whether to use Server Components, Client Components and server actions is a framework convention.
The Core boundary is the same either way. Calling transport directly and the location of DataState calls must not break the layer rules.

## Multi-zone

In a structure where several apps (zones) are merged under one domain through rewrites:

- A shell package that spans zones (navigation, session provider) is the **App Shell**. It does not reference Feature Blocks.
- The QueryClient may not be separated per zone, so the first element of a query key is the zone identifier (`profiles/frontend.next-web/docs/en/frontend-query-state.md`).
- Moving between zones is done only through links (URLs). Never import another zone's Feature Block.
