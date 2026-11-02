# strata.distill

## Aperçu

Fait passer ce qui a été appris, et non ce qui a été écrit, du vault de travail vers le noyau personnel : un enregistrement candidat côté travail, et un motif ou un guide réécrit côté personnel, qui tient sans le contexte d'origine.

## Quand l'utiliser

À la clôture d'une session ou sur demande, lorsque quelque chose de réutilisable est apparu. Toutes les sessions n'ont pas de candidat ; « aucun » avec une raison est un résultat valide.

## Procédure

1. Nommez la leçon comme un problème et un jugement, indépendamment du projet. Preuve : une phrase.
2. Écrivez l'enregistrement candidat dans le vault de travail : id, révision source, id de la note cible, statut. Preuve : l'enregistrement.
3. Écrivez ou mettez à jour le document du noyau personnel : problème, options et compromis, conditions, contre-cas, vérification, un exemple synthétique. Preuve : le document.
4. Exécutez le garde-fou (noms, domaines, chemins, pièces jointes) et lisez vous-même le résultat. Preuve : la sortie du garde-fou.
5. Marquez le candidat comme appliqué ; une relance avec le même id doit mettre à jour, pas dupliquer.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « Copions simplement le document, il est déjà écrit. » | Les copies portent le contexte de l'entreprise. Réécrivez uniquement la partie générale. |
| « Le garde-fou est passé, donc c'est propre. » | Les contrôles de chaînes détectent les noms, pas les formes. Relisez-le comme un étranger. |
| « Je distillerai à la fin du projet. » | Les leçons s'estompent. Distillez dans la session qui les a apprises. |

## Signaux d'alerte

- Un document du noyau personnel qui cite un chemin d'entreprise comme seule source.
- Deux documents pour un même id de candidat.
- Un candidat sans id cible.

## Vérification

- Enregistrement candidat complet.
- Le document tient seul ; le garde-fou est passé et son résultat a été lu.
- La relance est idempotente.
