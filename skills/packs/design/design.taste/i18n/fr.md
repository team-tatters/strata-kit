# design.taste

## Aperçu

Le goût est un registre de jugements, pas un style que choisit l'agent. Cette compétence tient ce registre pour un projet ou une marque — jamais pour une personne dans son ensemble, car le goût se juge dans le contexte où se situe le travail (DEC-2026-11-01-10). La note de goût a quatre sections : goût (les lignes que la personne a promues), signaux (réactions et choix), inférences (ce que l'agent a supposé, marqué), rejets (ce que la personne a refusé et pourquoi). Une étiquette qui apparaît dans trois briefs différents devient une candidate à la promotion ; la personne décide. La note d'expression écrit à quoi ressemble ce goût : les primitives (couleur, flou, opacité, espacement, rayon, typographie) une seule fois, et chaque technique comme un paragraphe lisible avec un bloc YAML de couches et de relations — éclaircir et assombrir en luminosité OKLCH, opacité, contraste WCAG — que `kb taste expression` calcule (DEC-2026-11-01-11).

La procédure tire sa forme de skeltonmedia/design-taste-skills (MIT ; voir le NOTICE du pack — ce n’est pas Taste Skill, c’est un autre dépôt) : entretien autour des références, journal des rejets, promotion des seuls signaux récurrents, inférences marquées. Le texte et les vérifications d'ici sont propres à strata.

## Quand l'utiliser

Pendant que la personne conçoit et réagit à quelque chose ; quand un projet ou une marque a besoin que son goût soit écrit ou revu ; quand une technique doit être écrite de façon à pouvoir être vérifiée. Pas pour le brief lui-même (design.brief), ni pour les tokens ou le contrat de composants d'un produit — c'est la traduction de l'implémentation. Lire une note de goût se fait en lecture seule ; écrire un signal, une inférence ou une technique fait passer la session en session unique (DEC-2026-11-01-18).

## Procédure

1. **Trouver la note.** Demandez pour quel projet ou quelle marque c'est. Ouvrez sa note de goût et sa note d'expression, ou proposez de les créer à partir de l'exemple du pack ; exécutez `python3 -m kb taste check <taste.md>` et montrez les candidates. Preuve : les chemins et la sortie de la vérification.
2. **Entretien, une question à la fois.** Pour chaque référence : qu'avez-vous remarqué en premier, qu'est-ce qui, dedans, produit cet effet, est-ce que cela a sa place ici. Notez la réponse comme un signal : `- YYYY-MM-DD 반응|고름 #tag [[brief]] — "ses mots"`. Quand la personne part d'une valeur plutôt que d'une référence (une valeur centrale d'une marque, un mot comme « confiance »), prenez cinq axes comme cadre — forme, couleur, sentiment, texture, objet — et demandez pour chacun une association et un indice visible ; les indices de la personne sont des signaux, toute association ajoutée par l'agent est une inférence. Réduire à environ trois mots-clés qui ne se heurtent pas se fait avec la personne seule ; quand deux se heurtent, demandez lequel mène et lequel reste dans la petite part d'accent (DEC-2026-11-01-13). Preuve : les nouvelles lignes de signal, relues à la personne.
3. **Rejets.** Quand la personne refuse quelque chose, demandez pourquoi et écrivez `- YYYY-MM-DD #tag [[brief]] — "ses mots" — 이유: …`. Un rejet sans raison est une question encore ouverte. Preuve : les lignes de rejet.
4. **Inférences.** Tout ce que l'agent conclut des signaux — « semble préférer les couleurs calmes » — va dans la section des inférences sous la forme `- [추론] #tag … — YYYY-MM-DD`, et est montré à la personne comme la lecture de l'agent. Preuve : les lignes marquées.
5. **Promotion.** Pour chaque candidate que la vérification montre (trois briefs différents ; les répétitions au sein d'un même brief comptent une fois), montrez ses signaux et demandez : promouvoir, garder en attente ou abandonner. Seulement en cas de promotion, écrivez `- #tag <la phrase de la personne> — 승격 YYYY-MM-DD · 근거 [[a]] [[b]] [[c]]`. Ne promouvez jamais à partir d'une seule réaction marquante. Preuve : le choix de la personne et la vérification réussie.
6. **Expression.** Quand la personne dit comment quelque chose devrait paraître, écrivez ou mettez à jour les primitives, puis la technique : un paragraphe dans ses mots, un bloc YAML qui référence les primitives par leur seul nom, les couches, et les relations qui portent le jugement (le bord est plus clair que la page ; le texte se lit à 4,5:1 sur le verre, le grand texte à 3:1). Pour un travail sans contrat produit (diapositives, affiches, rapports), une technique peut nommer des rôles comme valeurs dérivées — `text.primary: color.ink`, `accent: color.accent` — afin qu'un brief puisse viser des rôles ; les valeurs de composant restent dans le contrat du produit. Exécutez `python3 -m kb taste expression <expression.md> --show` et relisez les valeurs calculées. Preuve : 0 problème et les valeurs.
7. **Suite.** `python3 -m kb skills next design.taste` : design.brief pour démarrer un travail qui s'appuie sur ces lignes, ou rien.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « Elle adore clairement ceci ; je l'écris comme son goût. » | Une réaction est un signal. Le goût, c'est ce qui tient à travers trois travaux différents, et c'est la personne qui le promeut. |
| « Je devine son style à partir des références. » | C'est une inférence. Écrivez-la marquée, montrez-la, laissez la personne la corriger. |
| « Une valeur hexadécimale est plus claire qu'un nom. » | Une valeur brute cache le jugement. Nommez la primitive et écrivez la relation qui la rend juste. |
| « Gardons un seul fichier de goût pour la personne ; c'est plus simple. » | Le goût se juge dans le contexte d'un projet ou d'une marque. Une note partagée mélange des jugements portés sur des choses différentes. |
| « Elle l'a refusé ; la raison est évidente. » | Demandez. La raison est ce qui rend un rejet réutilisable. |

## Signaux d'alerte

- Une ligne de goût sans date de promotion ou avec moins de trois briefs derrière elle.
- Une inférence de l'agent écrite hors de la section des inférences ou sans sa marque.
- Un signal paraphrasé au lieu d'être cité.
- Une technique avec des valeurs de couleur brutes ou sans aucune relation.
- Une note de goût pour une personne plutôt que pour un projet ou une marque.

## Vérification

- `python3 -m kb taste check <taste.md>` indique 0 ; les candidates ont été montrées et la personne a choisi pour chacune.
- `python3 -m kb taste expression <expression.md>` indique 0 pour chaque technique touchée.
- Chaque nouvelle ligne est faite des mots de la personne ou d'un texte qu'elle a approuvé, relu devant elle.
