# strata.retro

## Vue d'ensemble

Une rétrospective sert la compréhension de la personne, pas l'efficacité de l'agent. L'agent prépare le matériau et pose des questions ; la personne explique avec ses propres mots ; ensuite seulement l'agent montre ce que disent les registres et où ils se taisent. Le résultat est une note écrite par la personne et, si quelque chose mérite d'être porté dans la méthode ou les décisions, chaque élément passe à la skill qui en a la charge.

## Quand l'utiliser

Quand la personne veut revenir sur un travail passé : une semaine, un ordre, une phase de projet, ou une décision et sa chaîne de remplacements. Pas pour vérifier qu'un travail est terminé (strata.verify), ni pour une revue indépendante d'un changement (strata.review). Le mode de travail reste en lecture seule jusqu'à ce que la personne accepte d'écrire une note ; l'écrire fait passer la session en session unique.

## Procédure

1. **Convenir du matériau et produire le dossier.** Fixer avec la personne une période et un projet, ou une décision de départ (sa chaîne de remplacements et les revues et sessions qui la nomment — un dossier plus petit quand toute une période est trop), et, au besoin, un nœud ou un terme de recherche. Lancer `python3 -m kb retro-bundle --project P --from D --to D [--node N] [--query Q]` ou `python3 -m kb retro-bundle --project P --decision DEC-id`. Indiquer le dossier et les décomptes de `00-목차.md`, et préciser que le dossier peut être chargé tel quel dans NotebookLM. Preuve : le chemin du dossier et les décomptes.
2. **Laisser la personne choisir quoi regarder.** Montrer telle quelle la liste des éléments de `00-목차.md` : chaque décision, revue et session avec les faits de son registre (date, nœuds, relation de remplacement, revues ou décisions liées). Demander par où commencer. Si la personne demande ce que dit un élément, citer mot pour mot sa section de conclusion depuis le dossier, avec fichier et titre. Ne pas résumer, classer, ni dire lequel a mal tourné. Preuve : le choix de la personne.
3. **Questionner avant de dire quoi que ce soit.** Sur l'élément choisi, une question à la fois : quelle était la prémisse, pourquoi les alternatives ont perdu, ce qu'on sait maintenant qu'on ignorait alors, ce qu'elle choisirait aujourd'hui et pourquoi. Attendre la réponse dans ses propres mots. Preuve : les questions posées.
4. **Montrer les registres une fois que la personne a expliqué.** Là où l'explication et les registres divergent, ou là où ils se taisent (pas d'alternatives, pas de contexte, un jugement renversé dans la section de raisonnement de la session), citer le dossier avec fichier et titre et interroger ce manque. Aucun verdict du type « c'était une bonne décision ». Preuve : chaque renvoi avec sa source.
5. **Écrire la note d'apprentissage, avec accord.** Demander s'il faut garder une note. Si oui, annoncer le passage en session unique et écrire `$STRATA_VAULT/retrospectives/<AAAA-MM-JJ>-<sujet>.md` avec le frontmatter `title`, `type: reference`, `created`, `tags: [retrospective, project/<p>]`, `source` (les conditions du dossier) et trois sections : **Ce qui a été regardé** (conditions du dossier et éléments choisis), **Ma compréhension, dans mes mots** (les mots de la personne, ou un texte qu'elle a approuvé ligne par ligne), **Candidats à transmettre** (chacun avec sa destination et son état). Preuve : le chemin de la note.
6. **Transmettre les candidats que la personne confirme.** Une leçon valable au-delà de ce projet → strata.distill. Une lacune de la méthode → une entrée du backlog. Une décision qu'elle prendrait autrement aujourd'hui → strata.decision avec remplacement. Chacun seulement après son accord. Preuve : la skill appelée par candidat, ou « aucun » avec la raison.

## Rationalisations

| Pensée | Réfutation |
|---|---|
| « Je vois ce qui a mal tourné ; le dire fait gagner du temps. » | Le but ici n'est pas le temps. C'est l'explication de la personne qui construit la compréhension ; votre conclusion la remplace. |
| « Un court résumé des décisions aidera d'abord. » | Un résumé est un verdict sur ce qui comptait. Montrez les éléments avec les faits du registre, citez la conclusion mot pour mot si on vous la demande, et laissez choisir. |
| « Je rédige la section compréhension, elle corrigera. » | La note devient alors la vôtre. Écrivez ses mots, ou ce qu'elle a approuvé ligne par ligne. |
| « Ce candidat va clairement au backlog ; je l'enregistre. » | Enregistrer change l'état. Demandez d'abord, puis passez-le à la skill responsable. |

## Signaux d'alerte

- Une première réponse qui évalue, classe ou résume la période.
- Un renvoi à un registre sans le fichier et le titre du dossier.
- Une note dont la section compréhension se lit comme de la prose d'agent.
- Une entrée de backlog, un motif distillé ou une décision de remplacement que la personne n'a pas confirmé.

## Vérification

- Le dossier a été produit avec les conditions convenues et ses décomptes ont été montrés.
- Les questions sont venues avant tout renvoi, et chaque renvoi citait sa source.
- Si une note a été écrite : la personne a accepté, elle est dans retrospectives/ et ses trois sections suivent le format décrit.
- Chaque candidat transmis a été confirmé et est allé à la skill responsable.
