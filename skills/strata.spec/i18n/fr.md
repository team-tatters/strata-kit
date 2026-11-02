# strata.spec

## Aperçu

Produit la spécification visée d'un changement : ce qui doit être vrai une fois le travail terminé, énoncé de sorte que chaque critère soit vérifiable, et en quoi cela diffère de ce que fait le système aujourd'hui.

## Quand l'utiliser

Un changement est demandé et aucune spécification visée n'existe ; un document de planification n'a pas de critères d'acceptation ; l'utilisateur demande si le plan et le comportement actuel concordent. Pas pour les refactorisations pures sans changement de comportement. Répondre à la question de savoir si le plan et le comportement concordent se fait en lecture seule ; rédiger ou réviser une spécification fait passer la session en session unique (DEC-2026-11-01-18).

## Procédure

1. Lisez la source de planification et les documents de forme réalisée que le changement touche. Preuve : la liste des documents lus.
2. Rédigez les objectifs, le périmètre (inclus et exclus), les critères d'acceptation (chacun avec la preuve qui l'établira), les contraintes issues des cartes applicables, les questions ouvertes avec la personne qui répond à chacune. Preuve : la section du document de planification.
3. Listez les différences entre le visé et le réalisé, une ligne chacune. Preuve : la liste des différences.
4. Signalez tout critère qui nécessiterait une nouvelle décision d'architecture ; ne la tranchez pas ici. Preuve : les éléments signalés.
5. Terminer par la revue d'implémentation de chaque document de planification écrit ou modifié dans cette session. Renseigner `implementation.status` d'après ce qu'ont établi les étapes 1 et 3 (implemented, partial, diverged, not-implemented ou superseded ; jamais laissé à unreviewed), `reviewed` à la date du jour et `spec` avec la spécification as-built dont les covers possèdent le code qui réalise le plan. Si aucune spécification ne possède ce code, l'écrire comme une ligne de différence (« aucune spécification ne possède <chemin> ») au lieu d'omettre `spec` en silence. Le coverage gate remonte `spec` depuis le code modifié jusqu'au plan ; un plan sans lui est invisible pour le gate. Preuve : le bloc implementation. Quand la revue trouve que le plan et le code divergent, déposez une demande de jugement (`python3 -m kb divergence add`, ou les lignes de revérification de la porte avec `kb coverage-gate --divergence-inbox`) et demandez à la personne ; ne choisissez jamais le jugement vous-même (règles de planification de document-format, DEC-2026-10-31-35).

## Rationalisations

| Pensée | Réponse |
|---|---|
| « L'utilisateur l'a déjà expliqué dans le chat. » | Le chat n'est pas un artefact durable. Écrivez-le dans le document de planification, sinon la session suivante ne l'aura pas. |
| « Les critères d'acceptation peuvent venir après l'implémentation. » | Ils décrivent alors ce qui a été construit, pas ce qui était voulu. Écrivez-les d'abord. |
| « La liste des différences est évidente. » | Écrivez-la quand même ; la porte de convergence la lit, pas votre mémoire. |
| « La revue d'implémentation peut attendre. » | Ce plus tard vient rarement : la plupart des plans importés restent non revus. Revoir maintenant ceux que cette session a touchés, pendant que le code est ouvert. |

## Signaux d'alerte

- Un critère sans preuve nommée.
- Une spécification qui modifie directement un document de forme réalisée.
- « Implémenter comme discuté » sans document.
- Un document de planification clos comme unreviewed, ou sans `spec` ni ligne de différence expliquant pourquoi.

## Vérification

- Chaque critère nomme sa preuve.
- La liste des différences existe.
- Les questions ouvertes nomment leur responsable.
- Chaque document de planification touché a son bloc implementation (status, reviewed, spec ou la ligne de différence pour la spécification manquante).
