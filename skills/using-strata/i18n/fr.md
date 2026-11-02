# using-strata

## Aperçu

`using-strata` est le point d'entrée. Il fait deux choses et rien d'autre : il affiche où en est la session (pour que l'utilisateur et l'agent partagent les mêmes faits) et il route la tâche vers le skill qui en est responsable. Il ne fait jamais le travail lui-même et il ne change jamais ; les extensions viennent du registre en couches, pas de ce fichier.

## Quand l'utiliser

- Au début de chaque session, avant toute réponse, y compris une question de clarification, une recherche dans le code ou la lecture d'un fichier. Les questions sont des tâches.
- Chaque fois que la tâche change de forme : un rapport de bogue en plein milieu d'une fonctionnalité, une demande de déploiement, une demande de mise à jour de la documentation.
- Pas lorsque vous avez été dépêché comme sous-agent pour exécuter une tâche précise : suivez alors la tâche et ignorez ce skill.

## Procédure

1. **Lire le manifeste du projet.** Ouvrez `.strata/profile.yaml` à la racine du projet. S'il est absent, arrêtez-vous et invoquez `strata.init-wizard`. Preuve : le chemin du manifeste et sa valeur `project`.
2. **Charger le registre en couches seulement en l'absence d'en-tête.** Si le hook de démarrage a affiché un en-tête strata, cet en-tête montre déjà les cartes must en vigueur et l'état de chaque couche du registre. Utilisez-le et ne rouvrez ni la constitution ni les registres en entier. Faites la correspondance des routes de l'étape 5 avec les descriptions de skills que le harnais affiche, et n'ouvrez le fichier de registre d'une couche de profil ou de projet que lorsque l'en-tête montre que cette couche a ses propres routes. Sans en-tête, faites ce qui suit. Lisez `skills/registry.yaml` de strata-kit, puis le registre du profil, puis le registre du projet (`.strata/kit/registry.yaml`, écrit par l'assistant, et le `skills/registry.yaml` du Tier P quand le projet a des packs de skills). Ouvrez chaque fichier ; lorsqu'un fichier de couche n'existe pas, dites « absent » pour cette couche au lieu de la sauter. Les couches suivantes ajoutent des routes et écrasent les précédentes selon `skill`. Ouvrez aussi chaque fichier du `required_context` de ce skill (la constitution) plutôt que de vous fier à un résumé. Preuve : la liste des routes, avec la couche d'où provient chacune, et les chemins du required_context ouverts. La couche utilisateur (`~/.strata/skills` : les paquets du kit sous `packs/`, les compétences de la personne sous `local/`) se lit après le profil et avant le projet ; elle ne fait qu'ajouter des routes — un nom qu'une autre couche possède est refusé, sauf une compétence locale qui nomme avec `overrides:` la compétence du noyau qu'elle remplace, et l'en-tête le montre (`python3 -m kb skills check`, DEC-2026-10-31-36).
3. **Afficher l'en-tête de contexte.** Domaine (travail ou personnel), identifiant du projet et alias, identifiant du profil, les cartes must en vigueur (ids uniquement), les cartes should levées avec leurs raisons, et la prochaine action tirée de la dernière passation ou du fichier active-task. Si le hook de démarrage a affiché l'en-tête, réaffichez cet en-tête et ajoutez-y le mode de travail ; ne le reconstruisez pas à partir des fichiers. Si ni fichier actif ni passation ne peuvent être lus (variable non définie, outil refusé, fichier absent), dites-le et lisez les traces du dépôt lui-même — notes comme NOTES ou HANDOFF, `git log`, branches — avant de demander où en est le travail ; l'en-tête indique où il a cherché. Preuve : l'en-tête dans la réponse, avant toute autre chose.
4. **Fixer le mode de travail.** Si le harnais en a attribué un (une pièce Quilt indique son mode dans ses instructions), utilisez-le. Sinon, choisissez : lecture seule (investigation, questions, revue ; aucun changement de fichier ni d'état externe), session unique (un changement qui se termine dans cette session), multisession (un travail qui traverse les sessions : un ordre existe ou existera), orchestration (plusieurs sessions ou rôles travaillant en parallèle). Obligations : lecture seule, l'en-tête et la route seulement, ni fichier actif ni passation ; session unique, un fichier actif avec `mode` et `harness_session_id` (l'identifiant de session du harnais, `CLAUDE_CODE_SESSION_ID` dans Claude Code, pour que l'en-tête et la restauration après compaction trouvent le fichier de cette session), les preuves de vérification, les enregistrements de décision et une passation seulement s'il reste des éléments en attente ; multisession, en plus l'ordre et une passation à chaque fin de session ; orchestration, en plus les politiques de permissions par rôle, les contraintes injectées dans les fichiers de tâche et les paquets de revue. Une session en lecture seule qui s'apprête à changer un état passe d'abord en session unique. Les enregistrements de décision et la confirmation avant un changement d'état s'appliquent dans tous les modes. Preuve : le mode dans l'en-tête.
5. **Faire correspondre la tâche à une route.** Comparez la demande aux déclencheurs dans la locale demandée, avec repli sur `en`. Si une route peut s'appliquer, nommez-la. Si plusieurs s'appliquent, les skills de processus (`strata.spec`, `strata.order`) passent avant les skills d'implémentation (`strata.build-task`). Preuve : la route et la raison en une ligne.
6. **Invoquer le skill.** Annoncez « j'utilise <skill> parce que <raison> » et suivez-le à la lettre. Créez une tâche à faire par élément de la liste de contrôle de ce skill. Si, après lecture, le skill ne convient pas, dites-le et revenez à l'étape 5.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « Ce n'est qu'une question simple. » | Les questions sont des tâches. Affichez l'en-tête et routez. Cela coûte une lecture. |
| « Il me faut plus de contexte avant de vérifier les skills. » | La vérification des skills précède la collecte de contexte ; un skill vous dit quel contexte collecter. |
| « Je me souviens de ce que dit ce skill. » | Les skills changent avec la révision du noyau. Lisez la version actuelle. |
| « Le skill est excessif pour ce changement. » | Les petits changements deviennent grands. Le routage est bon marché ; sauter un point de contrôle ne l'est pas. |
| « C'est en lecture seule, donc l'en-tête peut sauter. » | La lecture seule supprime les fichiers, pas l'en-tête. C'est l'en-tête qui montre les cartes must. |
| « L'utilisateur est pressé. » | L'en-tête fait cinq lignes. Une mauvaise route coûte plus de temps que son affichage. |

## Signaux d'alerte

- Une réponse qui commence par une réponse ou une action, sans en-tête de contexte.
- Un travail qui avance sans skill nommé et sans raison énoncée.
- Une session qui modifie des fichiers dans un projet sans `.strata/profile.yaml`.
- Une carte must listée dans l'en-tête que les étapes suivantes contournent ensuite par l'argumentation.
- Une session en lecture seule qui modifie un fichier sans être d'abord passée en session unique.

## Vérification

Avant de passer au skill routé, confirmez tous les points suivants et énoncez-les en une ligne :

- L'en-tête a été affiché en premier et nomme l'identifiant du projet et le profil.
- Les couches du registre ont été lues ou l'en-tête du hook de démarrage les a indiquées, et la route (ou « aucune, parce que … ») est nommée.
- Le mode de travail est énoncé.
- La liste `required_context` du skill routé est chargée.
