# strata.build-task

## Aperçu

Exécute une tâche : lit la spécification que la tâche porte, ne modifie que les fichiers nommés au sein d'une seule couche, exécute la commande de vérification, et rapporte l'achèvement avec les preuves et la conformité contrainte par contrainte.

## Quand l'utiliser

Un fichier de tâche issu de strata.order est assigné, ou l'utilisateur demande d'implémenter un changement planifié. Pas sans tâche : une tâche incomplète est rejetée avec la liste des éléments manquants.

## Procédure

1. Lisez la tâche et vérifiez qu'elle est complète (couche, fichiers, contraintes, vérification). Preuve : la liste de contrôle. Rejetez si elle est incomplète, mais lisez d'abord les fichiers nommés et les documents qu'ils désignent, et listez les décisions manquantes comme des choix concrets avec options et recommandation ; lire n'est pas deviner, implémenter l'est. Ensuite, réservez l'ordre (`python3 -m kb order claim <order-id>`) ; si une autre machine ou session le détient, arrêtez-vous et demandez à la personne. Preuve : la sortie de la réservation.
2. Lisez les fichiers nommés et un exemple existant du même motif. Preuve : les chemins.
3. Écrivez d'abord le test qui échoue lorsque la tâche ajoute un comportement, puis le code minimal, puis refactorisez. Preuve : la sortie des tests avant et après.
4. Exécutez la commande de vérification de la tâche et le vérificateur de couches. Preuve : les sorties et les codes de sortie.
5. Rapportez : fichiers modifiés, tableau de conformité aux contraintes, preuves, tout ce qui n'a pas été vérifié.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « La tâche est presque complète, je peux déduire le reste. » | La déduction est la façon dont les couches se font traverser. Rejetez et demandez les éléments manquants. |
| « Écrire les tests après le code, c'est très bien. » | Le test qui échoue prouve que le test teste quelque chose. |
| « L'avertissement du vérificateur est un faux positif. » | Rapportez-le comme avertissement avec votre raisonnement ; ne le faites pas taire. |

## Signaux d'alerte

- Des modifications de fichiers non nommés dans la tâche.
- Un rapport sans sortie de commande.
- Une contrainte marquée respectée sans raison.

## Vérification

- La sortie de la commande de vérification figure dans le rapport.
- Seuls des fichiers de la couche ont changé.
- Le tableau de conformité aux contraintes est complet.
