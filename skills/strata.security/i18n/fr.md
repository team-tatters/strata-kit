# strata.security

## Aperçu

Le noyau donne à l'exploitant une note par jour : ce qui est nouveau, ce qui reste ouvert, ce qui s'est fermé et quelles cibles personne ne surveille. Cette compétence est le côté humain de cette note. Elle lit ce que le travail quotidien a écrit, reporte le jugement de la personne dans les fichiers (un ordre, un risque accepté, un seuil, un lien) et refait les listes de cibles quand la personne apporte de nouvelles mesures. Elle ne collecte, ne note ni ne corrige d'elle-même : le travail quotidien collecte et note selon les règles enregistrées, et le correctif ne passe que par `patch plan` et `patch run` avec une condition remplie.

## Quand l'utiliser

Lire la note est le déclencheur quotidien. Aussi quand il faut surveiller quelque chose de nouveau (un serveur, un poste, un fichier de dépendances), quand la personne demande si une vulnérabilité nous touche, ou quand un seuil ou un risque accepté doit être fixé. Pas pour la réponse à incident (flux de l'operator) ni pour le magasin de défauts du produit.

## Procédure

1. **Lire la note du jour.** Ouvrir `security/notes/<day>.md`. D'abord les lignes urgentes, puis les éléments ouverts avec leur premier jour, puis les cibles aveugles. Si l'en-tête dit qu'une couche n'a pas été vue, le dire avant tout. Preuve : le chemin de la note et sa ligne counts.
2. **Suivre les liens avant de juger.** Pour chaque élément, ouvrir l'enregistrement et la correspondance dans `security/matches/<day>.yaml` : quel identifiant a correspondu, quelle plage, quel score et de quelle source (NVD, CNA, éditeur), si une valeur a été complétée depuis une autre source. Preuve : l'id de l'enregistrement et celui de la correspondance.
3. **Classer avec la personne.** Les urgents ont déjà un ordre (créé par le travail quotidien, attribué à infra par défaut) : le montrer et ne demander que l'attribution (`assign`). Pour les avis, demander : promouvoir en ordre (`promote <match> --by`), accepter comme risque avec raison et échéance (`accept ... --until --by`) ou laisser dans la note. Ne jamais décider seul. Preuve : la sortie de la commande.
4. **Donner des yeux aux cibles aveugles.** Demander à la personne le lieu d'avis (un dépôt GitHub, une page éditeur) et l'écrire comme lien manuel dans `security/sources.yaml` ; pour un dépôt sans lockfile, nommer le SBOM nécessaire. Preuve : la ligne manual_links.
5. **Refaire les listes depuis des mesures, jamais depuis le serveur.** Quand la personne colle `docker ps`, un compose, `dpkg-query` ou des versions d'OS, ne garder que images, versions et noms de paquets (retirer variables, mots de passe, hachages), les placer où pointe `security/registry.yaml`, lancer `python3 -m kb security inventory --project <p> --env <e> --write` et montrer la différence. Preuve : la sortie du diff.
6. **Changer un seuil seulement par la commande.** `python3 -m kb security grading set --project <p> [--env <e>] threshold <valeur> --by <personne>` : la ligne history est l'enregistrement. Preuve : l'entrée history.
7. **Corriger seulement sous une condition remplie.** `patch plan <order>` nomme la condition (niveau code · sans interruption · remplacement en minutes · acceptation enregistrée). `patch run` refuse sans l'une d'elles ; l'acceptation de la personne doit figurer dans l'ordre avant une exécution qui l'exige. Preuve : le plan et l'enregistrement d'exécution dans l'ordre.

## Rationalisations

| Pensée | Réplique |
|---|---|
| « Le titre dit exécution de code à distance ; je le marque urgent. » | Les notes viennent des scores et du seuil enregistré. Sans score c'est un avis avec raison no-score : montrer, ne pas relever. |
| « KEV le liste, donc c'est urgent. » | KEV ordonne la note ; il ne note jamais (DEC-02). Sous le seuil c'est un avis. |
| « Je me connecte en ssh et vérifie la version moi-même. » | L'agent n'entre pas dans les serveurs. Demander à la personne la sortie de la commande. |
| « Le compose contient les versions ; je l'enregistre tel quel. » | Il contient aussi des mots de passe. Garder images et versions ; dire ce qui a été omis. |
| « La personne est occupée ; j'accepte ce risque pour l'instant. » | Un risque accepté appartient à la personne, avec raison et échéance. Le laisser dans la note. |

## Signaux d'alerte

- Une note ou un seuil modifié à la main dans un fichier.
- Un risque accepté sans échéance, ou enregistré par l'agent.
- Une commande serveur lancée depuis la session.
- Un compose ou un fichier d'environnement copié dans le vault avec des secrets.
- Une cible aveugle transformée en correspondance CVE par le seul nom.

## Vérification

- Chaque action nomme une ligne de la note ou un id de correspondance du jour.
- `python3 -m kb security inventory --all` sort avec 0 après un changement de liste.
- Le history de grading.yaml a crû exactement des changements faits ; les lignes d'accepted-risks.yaml ont reason, until et by.
- Aucun serveur ni flux propre au produit n'a été touché.
