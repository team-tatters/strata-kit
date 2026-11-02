# strata.signal

## Vue d'ensemble

L'étape d'exploitation montre des indicateurs ; elle ne prend pas en charge les flux du produit. Deux sortes l'alimentent : les mesures de strata lui-même (révision du kit, sessions, vérification, passations, git) et les indicateurs de flux produit qu'un projet lit, en lecture seule, dans des flux qu'il a déjà — un registre QA, les cas de test de couverture. Quand l'un se dégrade, cette skill le garde dans une note avec ses preuves et laisse le choix à la personne : elle montre à quoi le changement pourrait mener et pourquoi, puis enregistre ce que la personne a retenu.

## Quand l'utiliser

Quand le rapport quotidien du librarian liste de nouveaux signaux ouverts, quand le contrôle liste des signaux qui traînent, ou quand la personne voit un indicateur se dégrader et veut le garder. Pas pour un incident du produit, une alerte ou un retour d'utilisateur — cela relève des fonctions propres du produit. Pas non plus pour décider d'une règle (strata.decision). Écrire une note fait passer une session en lecture seule en session unique.

## Procédure

1. **Trouver le changement.** Lancer `python3 -m kb signals candidates --project <p>` et montrer les candidats ; `python3 -m kb indicators show --project <p>` montre les indicateurs de flux produit par rapport à la collecte précédente. Écrire les candidats avec `--write` une fois la personne d'accord (la tâche quotidienne du librarian les écrit d'elle-même, sans destination). Preuve : la liste des candidats ou les chemins des notes.
2. **Vérifier les preuves.** La section des preuves de chaque note contient la valeur mesurée avec sa base — révision ou collecte précédente, et le seuil. Si un candidat repose sur trop peu (une session, une seule collecte), le dire dans la note. Preuve : la section des preuves de la note.
3. **Montrer où il pourrait aller, et demander.** Pour chaque signal ouvert, donner les candidats avec une raison chacun : une entrée du backlog de méthode (une lacune dans notre façon de travailler ou dans le kit), une note d'idée (mérite d'être développée mais pas encore claire, ideation.shape), un document de planification (un travail à planifier, strata.planning), une décision (strata.decision, quand elle fixe une règle), ou l'abandon (du bruit, déjà traité). Améliorer le flux propre du produit est un travail planifié comme un autre — il part du choix de la personne, pas d'une écriture de cette skill dans ce flux. Ne pas choisir. Preuve : les candidats et la question.
4. **Créer l'élément receveur, puis enregistrer le choix.** N'écrire l'élément receveur qu'avec le texte que la personne a approuvé : montrer l'entrée du backlog avant de l'ajouter ; confier une idée à ideation.shape et une planification à strata.planning. Puis lancer `python3 -m kb signals route --project <p> <note> --to <id de l'élément ou chemin du vault> --by <personne>`. Pour un abandon, `--drop "<raison>" --by <personne>`. La commande refuse une cible qui n'existe pas encore. Preuve : la sortie de route.
5. **Contrôler les notes.** Lancer `python3 -m kb signals check --project <p>`. Corriger chaque problème listé ; présenter à la personne les signaux ouverts depuis plus de 14 jours comme une question, pas comme une décision prise à sa place. Preuve : la sortie de la commande et son code de sortie.

## Rationalisations

| Pensée | Réfutation |
|---|---|
| « La tendance est évidente ; j'ajoute directement l'entrée au backlog. » | Alors personne ne l'a choisie, et le lecteur suivant ne peut pas voir d'où elle vient. Écrivez le signal, montrez les candidats, laissez la personne choisir. |
| « La personne est occupée ; je choisis la destination la plus probable. » | La destination appartient à la personne (DEC-2026-11-01-17). Laissez le signal ouvert et demandez ; un signal ouvert ne coûte rien, un élément erroné coûte un nettoyage. |
| « L'indicateur QA s'est dégradé ; j'enregistre le défaut ou je corrige le registre. » | Le registre QA et le stock de défauts sont le flux propre du produit. Le kit les lit ; les modifier est un travail planifié que la personne choisit. |
| « Ce rapport d'incident est important ; je le garde aussi comme signal. » | Les incidents et les retours ont leur place dans les fonctions du produit. Une seconde copie ici divise l'historique. |

## Signaux d'alerte

- Une entrée de backlog, une note d'idée ou une décision créée à partir d'un signal sans l'approbation de la personne.
- Une note routée dont le decided_by est l'agent ou le librarian.
- Une note sans base de comparaison dans ses preuves.
- Toute écriture dans les flux propres du produit (registre, stock de défauts, rapports de couverture) faite depuis cette skill.

## Vérification

- Chaque nouvelle note se trouve dans projects/<p>/signals/ et ses preuves contiennent la valeur et sa base.
- Chaque note routée nomme la personne qui a choisi, et sa cible existe.
- Rien n'a été écrit dans les flux propres du produit.
- `python3 -m kb signals check --project <p>` se termine avec 0, et les signaux qui traînent ont été soumis à la personne.
