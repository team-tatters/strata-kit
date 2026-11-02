# strata.review

## Aperçu

Obtient un contrôle indépendant depuis un contexte neuf, sans partager toute la conversation : un paquet structuré contenant la décision, des preuves sous forme de pointeurs d'abord et une demande bornée, un seul aller-retour, et un tri consigné de la réponse.

## Quand l'utiliser

Pour les décisions non triviales, les changements touchant un contrat, ou sur demande. Pas pour chaque modification ; le paquet coûte du contexte à un relecteur.

## Procédure

1. Choisissez le niveau (0 pointeur, 1 résumé, 2 décision + preuves, 3 diff, 4 complet) selon ce dont le relecteur a besoin. Preuve : le niveau et la raison.
2. Rédigez le paquet : ancrage de la décision, preuves sous forme chemin:lignes, demande limitée à une ou deux lacunes, questions ouvertes. Preuve : le fichier du paquet.
3. Envoyez à une session de relecture qui n'est pas la session de travail ; un seul aller-retour. Preuve : l'enregistrement du relais.
4. Joignez la réponse telle quelle et triez : accepter, réviser, escalader. Si la revue vient de l'extérieur de la session de travail (un autre modèle, une personne, une revue croisée), écrivez aussi un compte rendu de revue dans le vault, projects/<project>/reviews/<date>-<slug>.md, de type review, avec review_of (la révision examinée), received et source : une section « résumé de la réponse » (accepté, réfuté, constats absents du rapport, décisions de l'utilisateur, décisions et ordres qui en découlent) et la section « original » telle quelle (DEC-2026-10-30-03). Preuve : le tri avec ses raisons et le chemin du compte rendu.
5. Si la réponse a changé une décision, consignez-la avec strata.decision.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « Je vais simplement demander dans mon propre contexte. » | Votre contexte porte vos hypothèses. Tout l'intérêt est d'en avoir un neuf. |
| « Envoyons toute la conversation pour ne rien rater. » | Les conversations entières enterrent la question. Preuves sous forme de pointeurs d'abord, demande bornée. |
| « Le relecteur était d'accord, c'est fini. » | Consignez le tri. Un accord sans enregistrement n'est pas une preuve. |

## Signaux d'alerte

- Un paquet sans demande.
- Plusieurs tours automatiques.
- Une sortie du relecteur modifiée avant d'être jointe.

## Vérification

- Paquet complet.
- Un seul aller-retour.
- Tri consigné.
