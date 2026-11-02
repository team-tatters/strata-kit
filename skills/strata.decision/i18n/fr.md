# strata.decision

## Aperçu

Consigne une décision d'architecture sous forme d'enregistrement durable avec l'outil d'écriture de décisions, dans la session même où elle a été prise, et en extrait un candidat de carte de recommandation lorsque la décision se généralise au-delà de ce projet.

## Quand l'utiliser

Dès qu'un choix durable est fait ou découvert. Pas pour les choix d'implémentation locaux qu'un changement ultérieur peut inverser sans toucher à un contrat.

## Procédure

1. Énoncez la décision en une phrase, la raison et les alternatives envisagées. Preuve : le texte.
2. Exécutez l'outil d'écriture de décisions avec topic, decision, reason, affects. Passez chaque alternative envisagée avec --alternative 'option : pourquoi elle a été écartée' et les concepts ou sources consultés avec --background, pour qu'une rétrospective ultérieure voie ce qui n'a pas été choisi (DEC-2026-10-30-03). Preuve : l'id DEC et le chemin de l'index régénéré.
3. Si un enregistrement antérieur est remplacé, exécutez supersede ; s'il est retiré, exécutez withdraw. Preuve : la sortie de la CLI.
4. Si la décision se généralise, rédigez un candidat de carte (claim, force, evidence = ce DEC) dans le backlog. Preuve : le chemin du candidat.
5. Placez l'id DEC dans le decisions_made de la passation.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « Je l'enregistrerai à la fin de la session. » | Les sessions s'arrêtent brusquement. Enregistrez-la maintenant ; c'est une seule commande. |
| « C'est évident, personne n'a besoin d'un enregistrement. » | La session suivante, ce n'est pas vous. L'enregistrement est pour elle. |
| « Je peux modifier l'index directement. » | L'index est généré. Les modifications manuelles sont écrasées et l'enregistrement est perdu. |

## Signaux d'alerte

- Une décision énoncée dans le chat sans id DEC.
- Un index modifié à la main.
- Une règle remplacée (superseded) toujours citée comme en vigueur.

## Vérification

- Id DEC dans la réponse.
- Index régénéré par la CLI.
- decisions_made de la passation mis à jour.
