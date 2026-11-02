# Convention Next.js pour le frontend

> Source canonique : strata-kit `profiles/frontend.next-web/docs/fr/frontend-next.md` — migré depuis strata `docs/05-conventions/frontend-next.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles se trouve dans `core/rules/`.

> Frontière de Core : `core/docs/fr/architecture/frontend-web.md`

Ce document explique comment un projet Next.js s'associe au Route Surface et à l'App Shell de Core.
Next.js n'est pas un prérequis de Core.

## App Router

- Un route file (`page.tsx`) est un Route Surface.
- Les fichiers layout/provider/shell sont l'App Shell.
- Les fragments d'écran réutilisables sont séparés en Feature Block (`Section`).
- Les route params, search params, metadata et l'authorization boundary sont résolus dans le Route Surface.

### Budget de page.tsx

`page.tsx` ne fait que **résoudre les params · garde d'authentification · metadata · placer une seule Section**. Les hooks d'état serveur (query/mutation) et les appels transport sont interdits : on les descend dans un Feature Block.
Si plusieurs Sections sont nécessaires, on place un composant d'assemblage `{Route}Page` dans la zone Feature, et page.tsx ne rend que ce composant.

## Pages Router

Le Pages Router est géré comme variant hérité ou comme migration zone du projet.
Les nouvelles zones cibles privilégient l'association App Router. `pages/**` est associé à Route Surface dans le layer-map, et sa zone est mise à legacy.

## Server / Client Boundary

L'usage de Server Components, de Client Components et de server actions relève de la framework convention.
La frontière de Core est la même. L'appel direct à transport et l'emplacement des appels DataState ne doivent pas enfreindre les règles de couches.

## Multi-zone

Dans une structure où plusieurs applications (zones) sont réunies sous un même domaine par des rewrites :

- Un paquet de shell qui traverse les zones (navigation, provider de session) est l'**App Shell**. Il ne référence pas de Feature Block.
- Le QueryClient pouvant ne pas être séparé par zone, le premier élément de la query key est l'identifiant de zone (`profiles/frontend.next-web/docs/fr/frontend-query-state.md`).
- Le passage d'une zone à l'autre se fait uniquement par lien (URL). On n'importe pas le Feature Block d'une autre zone.
