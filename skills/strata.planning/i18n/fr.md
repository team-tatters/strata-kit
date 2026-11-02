# strata.planning

## Aperçu

L'étape de planification est un filtre (DEC-2026-11-01-04). Un plan brut mélange des discussions non tranchées, du code et des règles ; injecté tel quel, chaque lecteur ultérieur (une recherche, un outil d'injection comme Onyx, un collègue) lit des déchets. La source n'est donc jamais résumée d'emblée. Elle est découpée en faits, un par ligne, et chaque ligne reçoit une destination. Seuls les documents épurés — le PRD (règles qu'une personne peut observer) et la Logical Tech Spec (garanties qui survivent à un changement d'implémentation) — et les enregistrements de décision sont injectés et partagés. La source et les tableaux de travail restent comme pièces justificatives. **Les documents de planification ne contiennent ni code ni architecture** : tables, colonnes, classes, services, chemins d'API, codes HTTP, frameworks et fournisseurs vont à la destination 'code' et deviennent la matière d'une spécification, d'un ordre ou d'une décision.

## Quand l'utiliser

Une source de planification externe arrive ; une note d'idée (ideation.shape) est prête à devenir un plan ; un dossier existant doit faire vérifier sa table de correspondance. Pas pour rédiger les critères d'acceptation d'un plan déjà épuré (strata.spec), ni pour les choix d'architecture (strata.decision). Le mode de travail est en lecture seule tant que la source est seulement lue ; écrire le dossier le fait passer en session unique, et un dossier qui prend plus d'une session passe en plusieurs sessions — avec une passation à la fin de chaque session (DEC-2026-11-01-18).

## Procédure

1. **De la source à la liste de faits.** Placez la source intacte sous `source/` (ou marquez-la `category: source`). Dans `audit/facts.md`, écrivez un fait par ligne — règles, permissions, transitions d'état, exceptions, données, écrans, critères d'acceptation, décisions, hypothèses, dépendances, historique des révisions. Colonnes, dans cet ordre : `# | emplacement dans la source | type | contenu (une phrase qui garde le sens de la source) | rôle (planification · spécification · code · contexte · doublon) | axes | sous-thème`. Les axes sont les cinq questions auxquelles une règle doit répondre : identity, time, derivation, expiry, conflict (identité, temps, dérivation, expiration, conflit) ; écrivez `n/a` quand aucun ne s'applique. Preuve : la liste de faits.
2. **Arbre et décisions.** Regroupez les sous-thèmes en un projet d'arbre et obtenez la confirmation de la personne avant d'écrire le moindre corps de texte. Les conflits entre sources, ou avec des décisions ultérieures, deviennent des questions ; une réponse qui engage l'architecture est enregistrée avec strata.decision. Preuve : l'arbre confirmé, les questions et leurs réponses.
3. **Rédigez les documents épurés et donnez une destination à chaque ligne.** Dans `audit/coverage.md` (`# | emplacement dans la source | destination | remarque`), chaque fait reçoit exactement une des sept destinations : `<document> R<n>`, `isolated:<group>`, `defect:<what>`, `code`, `background`, `duplicate:#<n>`, `out of scope:<bundle>` (dans l'ordre : reporté dans un document épuré, isolé, défaut, code, contexte, doublon, hors périmètre ; pour ce dernier, la table de correspondance du dossier destinataire contient la même ligne). Les contradictions et les lacunes vont dans `audit/defects.md`, avec la façon dont les documents épurés les ont traitées. Marquez le PRD et la Tech Spec avec `planning_doc: prd` / `tech-spec`. Preuve : la table de correspondance.
4. **Revue de complexité.** Quand la politique d'une fonctionnalité dépasse ce qu'une personne peut retenir (la vérification signale un PRD de plus de 800 mots ou 10 règles, une Tech Spec de plus de 1 200 mots), construisez une table de politique par état et proposez d'isoler des étapes ou des états. Isoler change la politique, c'est donc la personne qui décide ; les règles déplacées vont dans `audit/isolated.md`. Preuve : la proposition et la décision.
5. **Vérifiez, dans un contexte neuf.** Lancez `python3 -m kb planning check <dossier>` : lignes sans destination, doubles comptes, transferts absents chez le destinataire, lignes de règle sans axe, limites, expressions de code dans les documents épurés (là seulement — la source et audit peuvent tout nommer). Corrigez et relancez. Envoyez ensuite le dossier à strata.review pour une passe de vérification seule ; le contexte qui a écrit le dossier est indulgent envers lui. Preuve : la sortie de la vérification et la réponse de la revue.
6. **Impact.** Lancer `python3 -m kb planning impact <lot>`. À partir des nœuds de sujet du frontmatter des documents affinés, il écrit `audit/impact.md` (fichier généré, preuve seulement) : les spécifications de ces nœuds, le code qu'elles couvrent, le code à un saut et ses tests (`--depth` pour plus), les décisions sur les nœuds et les autres planifications sur les mêmes nœuds. Montrer à la personne la ligne de résumé et ce qui se heurte — une décision en vigueur que le plan contredit, un autre plan sur le même nœud. Modifier une spécification ou remplacer une décision revient à la personne. Sans nœud, demander à quels nœuds de sujet le plan appartient. Preuve : la ligne de résumé.
7. **Suite.** `python3 -m kb skills next strata.planning` : strata.spec pour les critères d'acceptation, strata.decision, ou rien. **Raccourci de décision :** quand la source n'est que l'ordre du jour d'une décision, sautez les documents épurés et passez de la liste de faits directement à strata.spec ou strata.decision.

## Frontière d'injection

Injectés et partagés : les documents épurés et les décisions. Pièces justificatives seulement : `source/`, `audit/` et tout ce qui est marqué `category: source` ou `audit`. La frontière tient par le chemin et par la catégorie (DEC-2026-11-01-05) : la recherche de connaissances ignore les pièces justificatives ; `python3 -m kb planning boundary` affiche les chemins d'exclusion pour un connecteur GitHub et les lignes `never` de share.yaml ; `--list` affiche les documents épurés qu'un outil d'injection peut lire. Notion est hors du kit : séparez la page des documents épurés de celle des sources, et pointez le connecteur vers le côté épuré.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « La source est courte ; un résumé suffit. » | Un résumé décide en silence de ce qu'il laisse tomber. La liste de faits montre chaque abandon comme une ligne avec une destination. |
| « Le nom de la table rend la règle plus claire. » | Il lie le plan à une implémentation et fuit dans l'injection. Déplacez-le vers une ligne 'code'. |
| « Je l'ai écrit, je peux le vérifier. » | Le contexte qui écrit est indulgent. Vérifiez dans un contexte neuf. |
| « Le conflit est évident ; je prends la source la plus récente. » | C'est un choix de politique. Notez-le comme défaut et posez la question. |

## Signaux d'alerte

- Un document épuré écrit avant que la personne ait confirmé l'arbre.
- Une liste de faits qui a moins de lignes que la source n'a de règles.
- Une ligne de la table de correspondance sans destination, ou la même ligne comptée deux fois.
- Un document épuré qui nomme une table, une classe, un chemin d'API ou un fournisseur.
- La source modifiée sur place.

## Vérification

- `kb planning check` ne montre ni destination manquante, ni double compte, ni transfert rompu, ni expression de code.
- L'arbre, les isolements et le traitement des défauts citent la réponse de la personne.
- Une revue en contexte neuf a été faite sur le dossier.
- La source se trouve sous `source/`, intacte.
