# strata.handoff

## Aperçu

Rédige la passation qui permet à la session suivante de continuer sans cette conversation : ce qui a été fait avec les preuves, ce qui est en attente et pourquoi, quelles décisions ont été enregistrées, ce qu'il faut surveiller, et ce qu'il faut distiller dans le noyau personnel. Puis enregistre, vérifie et publie en trois étapes distinctes.

## Quand l'utiliser

À la fin d'une session, à une frontière de tâche, avant une scission ou un compactage, ou sur demande. La quantité à écrire dépend du mode de travail (using-strata) : la lecture seule n'écrit pas de passation ; la session unique n'en écrit que s'il reste des éléments en attente ; la multisession et l'orchestration en écrivent une à chaque fin de session.

## Procédure

1. Enregistrer : écrivez completed (avec fichiers et preuves), in_progress (blocker et unblocked_by pour chacun), decisions_made (ids DEC), la trace des jugements (ce qui a été demandé à la personne et sa réponse, les jugements renversés et pourquoi, en quelques lignes, dans la section de ce nom — DEC-2026-10-30-03), faits et hypothèses (faits confirmés et ce qui les a confirmés, suppositions non encore confirmées, hypothèses écartées et pourquoi ; à remplir chaque fois que la session se termine sur un signal de redémarrage : la conversation a dépassé la ligne d'alerte de jetons, ou les tentatives sur une hypothèse ont été bloquées deux fois ; DEC-2026-10-31-11, session-splitting 5.1), warnings, next_session. Preuve : le fichier de passation.
2. Colonne vertébrale : renseignez les liens orders et kb_updates. Preuve : le frontmatter.
3. Distiller : listez les candidats de distillation pour le noyau personnel, ou « aucun » avec la raison. Preuve : la section des candidats.
4. Mémoire : lancez `python3 -m kb hygiene --memory` et regardez les faits que cette session a écrits ou modifiés. Proposez de déplacer chaque fait d'état d'avancement (le travail en cours, la suite, les changements non commités, les blocages) dans in_progress ou warnings de cette passation, et mettez `verified` à la date du jour sur les faits que la personne confirme encore justes. Retirer un fait de la mémoire est une question à part, posée après le déplacement : seulement pour les faits que la personne approuve un par un, en déplaçant le fichier dans `_archive/` avec `retired` et `retired_reason` et en retirant sa ligne d'index — jamais une simple suppression (context-protocol §7, DEC-2026-10-31-16·17). Preuve : la proposition et les réponses de la personne, ou « aucune mémoire écrite dans cette session ».
5. Vérifier : exécutez la porte de couverture, la vérification des liens, la vérification des enregistrements non commités. Preuve : les sorties. La ligne de la porte « code modifié sans spécification N · candidats M · nouvelle spécification nécessaire K » (avec les modules qui ont besoin de leur propre spécification) va dans la passation ; ses candidats covers attendent dans projects/<project>/_meta/covers-candidates.yaml (source: impact) jusqu'à ce que quelqu'un les approuve et lance `python3 -m kb hygiene --covers-apply`. Si la session a changé de la connaissance plutôt que du code (un concept, une politique ou une décision), la porte liste aussi « code à revérifier (advisory) » : les covers des spécifications des mêmes nœuds thématiques et les affects des décisions remplacées ; notez dans la passation ce qui a été revérifié ou pourquoi non. Si le grade de la porte reste non résolu (une ligne FAIL ou BLOCK ; le script place une ligne « no-go » en tête du passage de relais et sur stderr), la session ne se clôt pas comme terminée : écrivez la spécification (strata.kb-update) ou laissez une dérogation avec motif et date dans le gate-overrides.yaml de Tier P, et indiquez laquelle dans le passage de relais (DEC-2026-10-29-08).
6. Publier : indexez (stage) uniquement les chemins listés (passation, ledger, miroirs) et commitez par le canal de fin de session ; rapportez fidèlement le succès ou l'échec du push. Si le distant a avancé, ne faites jamais de rebase ni d'autostash sur des fichiers que cette session n'a pas écrits : publiez les commits de cette session au-dessus du distant depuis un clone temporaire, ou arrêtez-vous et signalez le chevauchement. Avant de commiter, lisez les règles de commit du projet : listez la racine du projet et lisez AGENTS.md, CLAUDE.md et tout fichier de règles ou de notes qui s'y trouve (README, CONTRIBUTING, fichiers nommés comme *NOTES* ou *RULES*) ; si une règle du projet ou de l'utilisateur diffère d'une consigne par défaut du harness, comme un trailer d'attribution, suivez la règle du projet ou de l'utilisateur.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « "En attente de l'utilisateur" suffit pour l'élément en attente. » | En attente de quoi, et qu'est-ce qui le débloque ? Écrivez les deux, sinon l'élément est reporté indéfiniment. |
| « Je vais tout commiter dans le vault. » | Seulement les chemins de cette session. Les changements des autres sessions ne sont pas à vous de les publier. |
| « Rien à distiller cette fois. » | Dites « aucun » et pourquoi. L'absence est aussi une information. |

## Signaux d'alerte

- Un élément en attente sans blocker.
- Une publication qui a indexé des fichiers que vous n'avez pas écrits.
- Une passation sans valeur next_session.

## Vérification

- Éléments en attente complets.
- Sorties des portes dans la réponse.
- Chemins publiés listés ; statut du push véridique.
