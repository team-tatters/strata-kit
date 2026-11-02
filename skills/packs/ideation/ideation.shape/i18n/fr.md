# ideation.shape

## Vue d'ensemble

Une idée est utile bien avant d'être achevée. Cette compétence aide la personne à organiser une idée jusqu'à ce qu'elle soit utilisable — en planification, dans une spécification, une décision ou une rétrospective — sans fabriquer l'idée à sa place. Chaque idée est une note à cinq facettes (origine, problème, méthode, résultat, sens). Les facettes vides sont permises ; ce sont les prochaines questions. L'agent estime combien de conditions et combien d'ordres l'idée demande encore et demande à la personne de confirmer ; le nombre confirmé est le poids de l'idée, et la somme des poids de toutes les idées ouvertes est la charge de réflexion que porte la personne. Les idées peuvent grandir sans limite ; une idée sans croissance depuis plus de 30 jours se voit proposer l'archivage, jamais la suppression.

La méthode de questionnement et la boîte à outils en cas de blocage suivent jwynia/agent-skills `brainstorming` v1.1 (MIT) : des états décrits par signaux, questions et interventions ; son protocole de divergence est ici un outil, pas l'ossature.

## Quand l'utiliser

Quand la personne apporte une idée, un problème qu'elle veut attaquer, une intuition, ou qu'elle est bloquée. Pas pour rédiger des exigences (strata.spec) ni pour consigner une décision déjà prise (strata.decision) : ce sont des candidats du flux suivant. Pas pour générer des idées au nom de la personne. La conversation seule se fait en lecture seule ; écrire ou faire grandir une note d'idée fait passer la session en session unique (DEC-2026-11-01-18).

## Démarche

1. **La faire sortir.** Lance `python3 -m kb ideas list` et cherche les idées ouvertes semblables et les approches existantes (`python3 -m kb search "<les mots de la personne>" --hybrid`). Montre ce qui existe et la charge de réflexion, puis demande : « Sur quoi d'existant cela pourrait-il s'appuyer ? » Propose trois choix : une nouvelle note, compléter une note existante, ou renforcer ce qui est déjà ouvert et seulement noter ceci. Preuve : la liste et le choix de la personne.
2. **Nature.** Demande si l'idée attaque un problème ou un phénomène clair, ou cherche à rendre concrète une intuition floue. Une idée-problème part du problème, puis du résultat et de la méthode ; une intuition part du sens et de l'origine. Preuve : `nature` dans la note.
3. **Cinq facettes.** Une question à la fois : que résout-elle (problème), que veut-elle obtenir (résultat), qu'est-ce qui a du sens pour la personne (sens), que fait-elle pour y arriver (méthode), d'où est-elle partie (origine). Écris les mots de la personne. Une facette à laquelle elle ne peut pas encore répondre s'écrit « 비어 있음 ». Si la méthode est remplie alors que le problème ou le résultat est vide, l'idée est verrouillée sur une forme : demande « Que doit accomplir ceci ? Cette méthode en est-elle une façon ? » Preuve : les sections de facettes de la note.
4. **Conditions et poids.** Estime les conditions qui doivent être vraies pour que l'idée tienne et le nombre d'ordres qu'elle demanderait ; une expérience minimale peut être une condition. Montre l'estimation et demande à la personne de la corriger ou de la confirmer. Seulement ensuite, écris `conditions`, `orders_expected` et `weight_confirmed`. Preuve : la confirmation de la personne.
5. **Élargir, resserrer, éliminer.** Utilise les facettes vides comme termes de recherche de références ; montre chacune avec sa source. Si les candidats s'accumulent, regroupe-les par approche et demande un représentant et une expérience minimale par groupe. La personne choisit d'élargir ou de resserrer la cible et la façon d'éliminer : élimination dure (retirer ce qui est flou et se concentrer sur le reste) ou élimination douce (tout organiser, puis compresser par les liens). N'évalue pas pendant que les facettes se remplissent ; n'élimine que lorsque la personne le choisit. Écris les cas éliminés et leurs raisons dans la note. Entre idées, `python3 -m kb ideas near <note> [--embed]` montre facette par facette la proximité des autres idées, des candidats de relation (alternative, détournement, regroupement, concurrence) avec leurs valeurs, des candidats de lien et une ligne de biais de voisinage ; `python3 -m kb ideas map <note> [--facet F]` écrit un canevas Obsidian centré sur l'idée. Aucun des deux n'écrit la note : n'ajoute que les liens choisis par la personne, chacun avec un événement `link`. Preuve : la section des cas éliminés.
6. **En cas de blocage.** Si toutes les options sont des variantes, diagnostique l'état à partir de ses signaux et n'utilise que l'outil correspondant : cécité de convergence → lister d'abord les options évidentes ; verrouillage de fonction → séparer le quoi (WHAT) du comment (HOW) ; effondrement des axes → faire tourner qui, quand, échelle ou méthode ; enfermement de domaine → tirer du matériau de collision avec `python3 -m kb ideas draw --note <note>` (d'abord des dossiers hors des projets de l'idée, la liste de contraintes quand les dossiers manquent). Demande avec quoi le matériau entre en collision ; la personne écrit ce qu'elle voit. Preuve : le matériau montré et les mots de la personne.
7. **Consigner la croissance et conclure.** Pour chaque facette remplie, lien ajouté, usage dans un autre flux ou condition remplie, lance `python3 -m kb ideas event <note> facet|link|use|condition "<quoi>"` (une note archivée se rouvre). Puis lance `python3 -m kb skills next ideation.shape` et montre les candidats tels quels, « ne rien faire » compris ; la personne choisit. Consigne le choix dans le fichier actif et dans la section de jugement du passage de relais. Preuve : les lignes d'événement et le choix.

## Format de la note

`$STRATA_VAULT/ideas/<YYYY-MM-DD>-<slug>.md`, vérifiée par `python3 -m kb ideas check` :

```markdown
---
title: "<l'idée dans les mots de la personne>"
type: idea
created: YYYY-MM-DD
nature: problem | intuition
status: active | archived
projects: [<projets liés>]
conditions:
  - {text: "<condition>", met: false}
orders_expected: 2
orders_done: 0
weight_confirmed: YYYY-MM-DD
---

# <titre>

## 발단
## 문제
## 방법
## 결과
## 의미
## 소거한 사례
## 발전 기록

- YYYY-MM-DD facet — <ce qui a grandi>
```

L'archivage (`python3 -m kb ideas tidy --apply`, aperçu par défaut) ne pose que `status: archived` et `archived: {date, reason}` ; la note reste à sa place.

## Rationalisations

| Pensée | Réfutation |
|---|---|
| « Quelques idées d'exemple l'aideraient à démarrer. » | Alors la note contient tes idées. Donne du matériau et une question ; la personne écrit ce qu'elle voit. |
| « La facette vide est évidente ; je la remplis. » | Une facette vide est la prochaine question. La remplir cache le manque que la personne devrait regarder. |
| « Le poids n'est qu'une estimation ; je l'écris. » | Seul un poids confirmé compte dans la charge de réflexion. Demande d'abord. |
| « Cette idée doit clairement passer en planification. » | Le flux est une suggestion. Montre les candidats avec « ne rien faire » et laisse choisir la personne. |
| « Cette idée n'a mené nulle part ; supprime-la. » | On archive, on ne supprime jamais. Une intuition à moitié formée peut rencontrer plus tard la pièce qui lui manque. |

## Signaux d'alerte

- Une phrase de facette que la personne n'a ni dite ni approuvée.
- Évaluer des idées pendant que les facettes se remplissent.
- Un poids sans `weight_confirmed`.
- Une nouveauté qui ne sert ni le problème ni le résultat.
- Idéer à partir de zéro sans avoir cherché les approches existantes.
- Prendre « l'inverse » pour de la divergence : on reste sur le même axe.

## Vérification

- La note passe `python3 -m kb ideas check`.
- Chaque phrase de facette et le poids remontent aux mots de la personne dans cette session.
- Des événements de croissance ont été consignés pour ce qui a changé.
- La personne a choisi le flux suivant parmi les candidats.
