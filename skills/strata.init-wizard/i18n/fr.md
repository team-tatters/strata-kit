# strata.init-wizard

## Aperçu

L'assistant assemble le guidage d'un projet à partir de cartes de recommandation. Il n'interroge que sur ce que le code ne peut pas révéler, diagnostique la pile technique selon les règles de détection du profil, propose des cartes avec leurs preuves, génère les adaptateurs une fois l'utilisateur d'accord, et vérifie le résultat. C'est aussi la voie de régénération lorsque la révision du noyau avance. Il n'écrit jamais en dehors des chemins listés dans la proposition approuvée.

## Quand l'utiliser

- Un projet n'a pas de `.strata/profile.yaml` (using-strata vous envoie ici).
- L'utilisateur demande que le guidage soit mis en place, modifié ou régénéré.
- Un profil, une carte ou une dérogation doit changer.
- Pas pour le travail quotidien : celui-ci est routé par using-strata vers le skill responsable.

## Procédure

1. **Diagnostiquer d'abord à partir du code.** Exécutez `python3 tools/wizard.py diagnose <project> --apply`. Il lit les fichiers de build et les manifestes, applique les règles de détection des profils, mesure le budget toujours chargé et liste ce qu'il n'a pas pu décider. Preuve : `.strata/kit/diagnosis.yaml`.
2. **Interroger une question à la fois.** Ne posez que les questions ouvertes du diagnostic (taille de l'équipe, durée de vie attendue, nombre de domaines avec écritures inter-domaines, environnements partagés, harnais utilisés). Ne demandez jamais ce que le diagnostic a déjà établi. Enregistrez chaque réponse sur recommend avec `--answer <clé>=<valeur> --because <clé>=<raison>` (clés `team_size`, `lifetime`, `cross_domain_writes`, `shared_envs`, `runtime`, `strata_python`) ; la proposition les garde sous `answers` et le recommend suivant les reprend. **Environnement d'exécution.** Montrez la partie `runtime` du diagnostic — le python que lance chaque chemin d'exécution (shell interactif, hooks Claude Code, MCP, launchd, sh non interactif), les dépendances du kit manquantes, les gestionnaires et fichiers de version trouvés — puis demandez sur quel python le kit tourne. Présentez les options avec leurs avantages et inconvénients tels que recommend les affiche (`asdf` : plusieurs langages dans un seul fichier, mais ses shims ne sont pas dans le PATH de launchd ni d'un shell non interactif, donc il faut le chemin absolu ; `uv-venv` : isolé, reproductible depuis le lockfile, installe python, un seul langage ; `mise` : compatible asdf, plus env et tâches ; `pyenv` ; `brew`·`system` : faciles, épinglage et isolation faibles) et le défaut `uv-venv` avec sa raison (le kit dans un venv uv, le gestionnaire de runtimes de la personne conservé). Enregistrez le choix avec `--answer runtime=<choix>` ; generate écrit alors un seul STRATA_PYTHON dans des fichiers d'extraits sous `.strata/kit/runtime/` (hooks et env des settings, commande MCP, EnvironmentVariables launchd, lignes `~/.zshenv`) et la personne les applique — ne modifiez jamais vous-même les fichiers du home. Preuve : `answers` et `runtime` de la proposition, et `tools/doctor.py` sans éléments runtime une fois appliqués.
3. **Proposer des cartes.** Exécutez `python3 tools/wizard.py recommend <project> --profile <id> [--locale ko] --apply`. Présentez chaque carte ainsi : id, force, claim, références de preuves et contre-exemples. Les cartes must sont expliquées, pas négociées. Pour chaque carte should que l'utilisateur refuse, consignez `waived_reason`. Pour chaque objection à une carte must, consignez un candidat counter_example (il va au backlog, pas dans le projet). Les cartes must à adopter (`adoption: opt_in`, hors constitution) sont posées en questions : la proposition montre chacune avec sa valeur par défaut (le `wizard.adopt_cards` de l'utilisateur dans `~/.strata/config.yaml`, puis le `cards_default` du profil) ; enregistrez la réponse avec `--adopt <id>` ou `--decline <id>=<raison>` (un refus garde sa raison dans la proposition et le registre). Les cartes must conditionnelles (`adoption: conditional`) ne sont pas posées : elles se chargent dès que leur fait vaut pour le projet — `uses_vault` (`--uses-vault yes|no`), `uses_quilt` (`--harness …,quilt`), `domain_work` (le domaine) ; dites lesquelles ont été chargées et pourquoi. Demandez le niveau d'application par famille de règles (`layers`, `naming`, `rules`) : advisory enregistre seulement les violations, default échoue sauf dérogation motivée et datée, block échoue ; les familles non déclarées restent en block. Enregistrez-le avec `--enforce <famille>=<niveau>` ; il va dans le manifeste et les vérificateurs passent par `kb enforce run`. Un vérificateur en mode avertissement qui affiche des violations et sort avec 0 s'enveloppe avec `--violation-exit 0,1 --violation-pattern <sa marque de violation>` ; une entrée erronée du registre ne se modifie pas : on ajoute une correction avec `kb enforce correct`. Preuve : `.strata/kit/proposal.yaml` avec `approved: true` posé par l'utilisateur.
4. **Générer.** Exécutez `python3 tools/wizard.py generate <project> --apply`. Il n'écrit que les chemins listés dans la proposition et appose `core_revision` et `adapter_revision`. Un fichier existant écrit à la main (sans marque de génération en tête) est conservé sauf si la proposition le nomme dans `overwrite_handwritten` ; déplacez d'abord son texte vers `.strata/kit/notes.<locale>.md`. Preuve : la liste des fichiers écrits dans la sortie de la commande.
5. **Vérifier.** Exécutez `python3 tools/wizard.py verify <project>`. Il contrôle le budget (octets toujours chargés), les en-têtes de révision, le registre, et fait passer cinq requêtes d'exemple par les déclencheurs du registre. Preuve : code de sortie 0 et le rapport.
6. **Consigner.** Si le choix du profil ou une dérogation est une décision d'architecture pour ce projet, enregistrez-la avec l'outil d'écriture de décisions. Preuve : l'id DEC dans la réponse.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « La pile est évidente, sautons le diagnostic. » | Le diagnostic mesure aussi le budget et détecte la dérive. Lancez-le ; c'est une seule commande. |
| « L'utilisateur connaît les règles, sautons les preuves. » | Une carte sans preuve est une opinion. Montrez les références ; c'est tout l'intérêt. |
| « Cette carte must ne convient pas ici, levons-la. » | Une carte must ne se lève pas. Expliquez-la et consignez l'objection comme candidat counter_example. |
| « Générons tout, ils supprimeront ce qu'ils ne veulent pas. » | N'écrivez que les chemins approuvés. Les fichiers non demandés sont de la dérive. |
| « La vérification est passée la dernière fois. » | La révision du noyau a pu avancer. Vérifiez après chaque génération. |

## Signaux d'alerte

- Des questions d'entretien dont les réponses se trouvent dans `package.json`, `build.gradle`, `go.mod` ou `Cargo.toml`.
- Une proposition contenant une carte sans entrée `evidence`.
- Un AGENTS.md généré sans `core_revision` dans son en-tête.
- Des fichiers écrits en dehors de la liste de chemins de la proposition.

## Vérification

- `.strata/kit/proposal.yaml` existe avec `approved: true` et chaque carte a une preuve.
- Chaque carte should levée a un `waived_reason`.
- `tools/wizard.py verify <project>` se termine avec le code 0 et son rapport figure dans la réponse.
- Toute décision prise est enregistrée et son id figure dans la réponse.
