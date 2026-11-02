# strata.verify

## Aperçu

Remplace l'impression d'avoir terminé par des preuves. La preuve est consignée au moment où un test, un vérificateur ou une compilation s'exécute, et comparée au moment où l'achèvement est affirmé : si un fichier de la tâche a changé entre-temps, la preuve est périmée et la commande est relancée. Dresse un tableau de ce qu'exigeait la compétence responsable, de ce qui prouve chaque point et de ce qui n'a pas pu être vérifié, puis déclare go ou no-go.

## Quand l'utiliser

Avant tout rapport d'achèvement, toute demande de fusion ou toute affirmation « terminé » ; lorsqu'on demande si quelque chose fonctionne ; dès que « devrait marcher » ou « semble correct » apparaît. Jamais sauté parce que le changement est petit.

## Procédure

1. Rassembler les points de validation de la compétence responsable et de la tâche. Preuve : la liste.
2. Exécuter chaque commande qui produit une preuve (tests, vérificateurs, compilation) via l'enregistreur, en nommant les fichiers modifiés par la tâche : `python3 "$STRATA_KIT/tools/verify_evidence.py" record --files <fichiers ou répertoires de la tâche> -- <commande>`. L'enregistreur affiche la sortie, renvoie le code de sortie de la commande et ajoute une entrée (commande, code de sortie, heure, fin de la sortie, empreinte du contenu des fichiers nommés) à `.strata/local/verify/<session>.yaml` ; la session est le fichier actif par session le plus récent, sauf si `--session` est donné. Ne nommer que les fichiers de cette tâche : d'autres sessions peuvent modifier la même copie de travail. Preuve : les sorties avec leurs codes de sortie et le chemin du fichier de preuve.
3. Avant le compte rendu, exécuter `python3 "$STRATA_KIT/tools/verify_evidence.py" check`. La dernière entrée de chaque commande apparaît réussie ou échouée, à jour ou périmée (avec les fichiers modifiés). Relancer une commande périmée ; une commande échouée est un point no-go. Preuve : la sortie de check.
4. Remplir le tableau : point, preuve (la ligne de check, ou l'exécution externe pour la CI), vérifié ou non vérifié avec la raison.
5. Déclarer go ou no-go. No-go si un point must n'est pas vérifié ou si sa preuve est périmée. Une passation qui indique `tests_passed: true` nomme le fichier de preuve. Un comportement que la modification ajoute ou change doit être exercé par un test commité ; une commande ponctuelle est une vérification manuelle, pas une preuve d'achèvement — marquez l'élément non vérifié et déclarez no-go jusqu'à ce que ce test existe.

Quand la question porte sur le projet entier et non sur une tâche — strata tourne-t-il vraiment ici : vérificateurs installés et exécutés, consignes à jour, décisions commitées, décisions solo sur les sources du noyau, dernière exécution du librarian —, lancez `python3 "$STRATA_KIT/tools/doctor.py" <projet>` (lecture seule ; `--json` donne les mêmes éléments). Ses éléments default et block comptent comme les éléments must ci-dessus ; les éléments de référence sont rapportés, pas notés (DEC-2026-10-31-22·28).

## Rationalisations

| Pensée | Réfutation |
|---|---|
| « J'ai lancé les tests tout à l'heure. » | `check` dit si « tout à l'heure » vaut encore. Si c'est périmé, relancez-les maintenant. |
| « Enregistrer est une charge ; je lance juste la commande. » | L'enregistrement permet de vérifier l'affirmation plus tard : vous-même après une compaction, ou la session suivante. |
| « C'est une modification d'une ligne. » | Les modifications d'une ligne cassent les compilations. Le tableau tient en trois lignes. |
| « Je ne peux pas l'exécuter ici. » | Alors écrivez « non vérifié » et ce qui le vérifierait. Ne l'affirmez pas. |

## Signaux d'alerte

- Un compte rendu d'achèvement sans tableau.
- « Ça devrait marcher » dans un message d'achèvement.
- Des tests décrits sans sortie affichée.
- `tests_passed: true` sans fichier de preuve, ou un tableau citant une preuve que `check` déclare périmée.

## Vérification

- Le tableau est complet.
- `check` renvoie 0 pour les commandes citées (à jour et réussies), ou le point cite une exécution externe.
- Go ou no-go est déclaré.
