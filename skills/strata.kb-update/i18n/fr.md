# strata.kb-update

## Aperçu

Maintient la connaissance de forme réalisée égale au code : trouve le document responsable de chaque chemin modifié, le met à jour sur place avec ses sources, ou consigne pourquoi aucun changement n'est nécessaire, puis régénère les vues générées.

## Quand l'utiliser

Après un changement de code couvert ; lorsqu'une porte ou un avis de dette se déclenche ; sur demande. Aussi pour déclarer doc_change: none avec une raison, ce qui est un résultat valide.

## Procédure

1. Listez les fichiers modifiés et résolvez leurs documents responsables via covers. Preuve : la correspondance.
2. Pour chaque responsable : mettez à jour la section concernée sur place ; renseignez updated et sources. Preuve : le diff.
3. Pour les chemins sans responsable : créez un document de forme ou étendez covers. Preuve : la nouvelle correspondance.
4. Là où la forme n'a pas changé : écrivez doc_change: none avec la raison. Preuve : la déclaration.
5. Reconstruisez l'index et lancez la vérification des liens. Preuve : les sorties.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « Le changement de code est interne, la documentation n'est pas touchée. » | Déclarez alors doc_change: none avec cette raison. La porte exige la déclaration, pas la supposition. |
| « Je mettrai la documentation à jour à la prochaine session. » | La session suivante ne sait pas ce qui a changé. Mettez à jour maintenant ou déclarez. |
| « Un horodatage suffit. » | Un horodatage sans vérification du contenu est de la dérive datée. |

## Signaux d'alerte

- Un chemin couvert modifié sans mise à jour ni déclaration.
- Un document mis à jour sans sources.
- Des pages de nœuds régénérées à la main.

## Vérification

- Correspondance complète.
- L'index et la vérification des liens passent.
- Les déclarations ont des raisons.
