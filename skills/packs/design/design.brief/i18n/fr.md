# design.brief

## Aperçu

C'est l'étape de design de la personne. Quoi que l'on conçoive — un document, un objet physique, une image, une publication, un écran —, le travail part d'un brief : à quoi il sert, qui le voit, sur quel support, sous quelles contraintes, avec quelles références, et ce qui doit être vrai pour qu'il soit terminé. Le brief appartient à la personne ; l'agent pose les questions et note, il ne décide pas des goûts. Un design s'appuie sur le goût de la personne et sur les techniques qui l'expriment (une surface de verre, une ombre douce en relief, un empilement de bordures et de nuances) ; le brief nomme celles que ce travail utilise.

Le contrat de design frontend (core/docs/<locale>/architecture/frontend-design-contract.md) est une chose distincte : le flux technique qui porte un design décidé jusque dans le code. Ce pack ne le suit pas et ne le modifie pas (DEC-2026-11-01-09). Les deux se rencontrent en un seul endroit : quand un livrable entre dans un produit, le contrat le désigne par `design_ref`. Traduire l'expression de la personne en tokens du produit est le travail de l'implémentation.

## Quand l'utiliser

La personne s'apprête à concevoir quelque chose, sur n'importe quel support ; une spécification ou une sortie a besoin de quelque chose de conçu ; la personne veut juger un design au regard de son objectif. Pas pour rédiger la spécification (strata.spec), ni pour implémenter un écran (strata.build-task). Discuter d'un design se fait en lecture seule ; rédiger le brief fait passer la session en session unique (DEC-2026-11-01-18).

## Procédure

1. **Brief.** Posez une question à la fois et rédigez les sept sections : Purpose, Audience, Medium and format, Constraints, References, Acceptance criteria, Deliverable (objectif, public, support et format, contraintes, références, critères d'acceptation, livrable). L'objectif commence par ce que l'on conçoit — une page web, un écran d'application, des diapositives, un rapport, une infographie, une affiche, une image ou une publication, un objet physique, ou autre chose — et se note aussi dans le frontmatter du brief comme `category` (`web`, `app`, `slides`, `report`, `infographic`, `poster`, `image`, `post`, `object`, `other`) ; puis la phrase que cette pièce doit transmettre ; puis le contenu dans l'ordre — ce qui doit y être et ce qui peut sauter. La catégorie décide de l'adaptateur à l'étape 3. Une section sans réponse indique inconnu. Preuve : le brief et sa catégorie.
2. **Références.** Pour chaque référence, demandez ce que la personne a remarqué en premier, ce qui, dans la référence, produit cet effet, et si cela a sa place dans ce travail. Notez sa réponse à côté du lien. Quand le projet ou la marque a une note de goût et une note d'expression (design.taste), nommez les lignes de goût (#tag) et les techniques sur lesquelles ce travail s'appuie. Une réaction ou un refus que la personne approuve tel qu'écrit entre dans la note de goût comme signal venu de ce brief, par design.taste. Preuve : la section References.
3. **Faire ou confier.** La personne conçoit, ou l'agent fait des ébauches dans le cadre du brief. Les options proposées par l'agent sont marquées comme les siennes ; la personne choisit. Lisez l'adaptateur de la catégorie du brief dans `data/adapters.md` : diapositives, rapports et infographies prennent l'adaptateur de document (argumentation, titres d'action, choix du graphique et de la structure) ; web et app prennent un skill de design externe si la personne en choisit un, sinon la courte solution de repli de ce fichier — jamais les deux. Quand le livrable est une page web ou un écran d'application et que la personne le souhaite, utilisez un skill de design qu'elle a déjà installé — par exemple Taste Skill (Leonxlnx/taste-skill, `design-taste-frontend`) ou Impeccable (pbakaus/impeccable) ; demandez lequel et n'en installez aucun vous-même. Transmettez-lui l'objectif, le public et les contraintes du brief, ainsi que les primitives et techniques du projet ou de la marque quand elles existent (Taste Skill : `--keep palette,type` ; Impeccable : son `DESIGN.md`). Ce que ce skill choisit est une option côté agent, pas le goût de la personne ; ce sont toujours les critères d'acceptation du brief et le verdict de la personne qui décident (DEC-2026-11-01-12). Preuve : les ébauches, le skill utilisé le cas échéant et le choix de la personne.
4. **Juger.** Proposez les vérifications communes de `data/adapters.md` comme critères d'acceptation candidats, en suggestions de l'agent ; seuls ceux que la personne retient rejoignent les critères. La personne juge chaque critère d'acceptation ; notez son verdict. Un critère qui échoue renvoie le travail à l'étape qui en est la cause — objectif, ordre du contenu, hiérarchie, mise en page, valeurs ou point focal — et pas seulement à l'endroit où cela se voit. Désignez le résultat dans la section Deliverable avec `design_ref` (`kind`, `ref`, `version`). Quand le résultat entre dans un produit, c'est à ce `design_ref` que le processus propre du produit prend le relais. Preuve : les verdicts et la référence.
5. **Suite.** `python3 -m kb skills next design.brief` : design.taste quand le travail a laissé des réactions ou des refus à consigner, strata.order quand le livrable entre dans un produit, strata.review, ou rien.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « Ce n'est qu'une affiche ; un brief, c'est trop. » | Cinq lignes suffisent. Sans objectif ni public, personne ne peut dire si c'est terminé. |
| « Je sais ce qui rend bien ici. » | C'est la moyenne de ce que le modèle a vu. Le goût, c'est la réaction de la personne à ses références ; demandez-la. |
| « Le lien de référence suffit. » | Un lien ne dit pas ce qui a compté. Notez ce à quoi la personne a réagi. |
| « Les règles de tokens du produit devraient façonner ceci. » | Pas ici. Le contrat reçoit le livrable à design_ref ; l'implémentation traduit. |
| « La section Medium and format dit déjà ce que c'est. » | Cette section contient la taille et le type de fichier. Ce que l'on conçoit décide de l'adaptateur et du skill externe ; demandez-le d'abord. |
| « L'adaptateur a de bonnes valeurs par défaut ; je les applique. » | Ce sont des vérifications de métier et des points de départ, pas le look de la personne. Ses références et son goût passent d'abord. |

## Signaux d'alerte

- Un artefact livré sans brief.
- Un objectif, un public ou un critère d'acceptation que la personne n'a jamais énoncé.
- Des références listées comme de simples liens.
- Le choix d'apparence de l'agent consigné comme le goût de la personne.

## Vérification

- Le brief a sept sections dans les mots de la personne, les inconnues marquées, et une catégorie.
- Chaque critère d'acceptation porte le verdict de la personne.
- La section Deliverable désigne le résultat avec design_ref.
