# strata.order

## Aperçu

Transforme une spécification approuvée en un ordre et en tâches autonomes qu'un worker peut exécuter sans la conversation : une couche chacune, des fichiers explicites, les contraintes du registre, et la commande qui prouve l'achèvement.

## Quand l'utiliser

Après strata.spec, lorsque le travail doit être découpé. Aussi lorsque l'utilisateur demande un plan. Les petits ordres (deux ou trois tâches, une seule préoccupation) utilisent le mode inline : l'ordre est écrit, et le cérémonial des tâches se réduit à une liste de contrôle dans le même fichier.

## Procédure

1. Lisez la spécification et la layer-map. Preuve : les chemins.
2. Rédigez l'ordre : objectif, critères d'acceptation copiés de la spécification, liste des tâches avec dépendances. Preuve : _order.yaml.
3. Rédigez chaque tâche : couche, fichiers à toucher, contraintes filtrées du registre par périmètre, commande de vérification, critères d'achèvement. Preuve : les fichiers de tâche.
4. Choisissez le mode inline si l'ordre est petit et dites pourquoi. Preuve : la note dans l'ordre.
5. Vérifiez l'absence de cycles et de tâches couvrant deux couches. Preuve : le résultat de la vérification.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « Le worker trouvera les fichiers. » | Un plan s'écrit pour un lecteur sans contexte. Nommez les fichiers. |
| « Les contraintes sont de toute façon dans le registre. » | Filtrez-les dans la tâche. Les workers lisent la tâche, pas le registre. |
| « Petit changement, sautons l'ordre. » | Utilisez le mode inline. Sauter l'ordre fait perdre les critères d'acceptation. |

## Signaux d'alerte

- Une tâche qui ne nomme aucune commande de vérification.
- Une tâche touchant deux couches.
- Un ordre sans critères d'acceptation.

## Vérification

- Chaque tâche a couche, fichiers, contraintes, vérification.
- Aucun cycle de dépendances.
- Le mode inline, s'il est utilisé, est énoncé avec sa raison.
