<div align="center">
    <img src="./media/strata-kit-symbol.svg" alt="strata-kit symbol: layers stitched across a fault" width="160" height="160"/>
    <h1>strata-kit</h1>
    <h3><em>Work in layers. Keep the thread.</em></h3>
    <p align="center">Travailler par couches. Ne pas perdre le fil.</p>
</div>

<p align="center">
    <a href="https://github.com/team-tatters/strata-kit/stargazers"><img src="https://img.shields.io/github/stars/team-tatters/strata-kit?style=social" alt="GitHub stars"/></a>
    <a href="https://github.com/team-tatters/strata-kit/blob/main/LICENSE"><img src="https://img.shields.io/github/license/team-tatters/strata-kit" alt="License: MIT"/></a>
    <img src="https://img.shields.io/badge/python-3.11%2B-3776AB" alt="Python 3.11+"/>
    <img src="https://img.shields.io/badge/agents-Claude_Code_%C2%B7_Codex_%C2%B7_AGENTS.md-263D3A" alt="Agents: Claude Code, Codex, AGENTS.md"/>
    <img src="https://img.shields.io/badge/locales-6-C86646" alt="6 locales"/>
</p>

<p align="center">
    <a href="./README.md">English</a> ·
    <a href="./README.ko.md">한국어</a> ·
    <a href="./README.ja.md">日本語</a> ·
    <a href="./README.zh-CN.md">简体中文</a> ·
    <a href="./README.es.md">Español</a> ·
    <strong>Français</strong>
</p>

strata-kit est une méthodologie de travail avec des agents de programmation IA, présentée sous forme de kit. Son centre
est la trace écrite : chaque étape du travail est consignée dans un simple dossier Markdown (le vault), chaque sujet
garde un seul document mis à jour sur place, et chaque nouvelle session, chaque agent ou chaque personne part de ces
mêmes documents. C'est ce qui garde le travail cohérent et lui permet de se poursuivre d'une session à l'autre, au lieu
de repartir de zéro à chaque conversation.

Il fonctionne d'abord avec Claude Code, et aussi avec Codex et tout autre agent qui lit `AGENTS.md` et `SKILL.md`, y
compris les agents que vous exécutez vous-même avec une clé d'API.

Auteur : n0roo · Licence : [MIT](LICENSE)

## Par où commencer

| Vous voulez | Commencez par | Vous obtenez |
|---|---|---|
| L'essayer sur un projet | [Démarrage rapide](#démarrage-rapide) | un vault, le plugin, des consignes générées et une première session |
| Comprendre l'idée | [Ce qu'il apporte](#ce-quil-apporte) | traces, spécifications, cartes, skills et contrôles sur une seule page |
| Choisir les règles pour votre stack | [Profils](#profils) | les profils éprouvés sur un projet réel et ceux qui sont encore des brouillons |
| Consulter une référence | [Documentation](#documentation) | les tables générées des cartes, skills, commandes et profils |
| Connaître d'abord les limites | [État et limites](#état-et-limites) | ce qui a été mesuré et ce qui ne l'a pas été |

## À qui il s'adresse

Surtout aux développeurs qui travaillent avec un agent de programmation, et en premier lieu aux ingénieurs qui mènent
seuls un projet du plan jusqu'à la production. Les personnes qui planifient, conçoivent ou exploitent y participent par
les mêmes traces : documents de planification et spécifications, décisions et signaux d'exploitation. Le kit n'a pas
encore de flux de travail complet propre à ces rôles, et il n'a pas encore été utilisé par toute une équipe.

## Ce qu'il apporte

- **Des traces qui restent à jour.** Le vault tient trois sortes de traces. Le journal de travail (sessions, tâches,
  preuves de test) ne fait que s'allonger. Les documents vivants décrivent l'état actuel des choses, un par sujet, sont
  mis à jour sur place et citent le journal de travail dont ils proviennent. L'index (listes de décisions, pages de
  sujet) est généré à partir des deux autres et n'est jamais modifié à la main. Les décisions sont écrites par une CLI,
  un fichier chacune, et ne changent que par un enregistrement qui les remplace. Chaque session se termine par une
  passation qui indique ce qui reste ouvert et ce qui le bloque.
- **Des spécifications qui convergent.** Les documents de planification renvoient aux spécifications de la forme
  réalisée ; les spécifications possèdent le code via `covers` ; une porte de couverture signale le code modifié sans
  propriétaire et les plans implémentés dont le code a bougé, avec un niveau par projet (`advisory` · `default` ·
  `block`) et une base de référence pour les écarts antérieurs à l'adoption.
- **Une méthode qui s'apprend sans agent.** Les conventions (couches selon le rôle et noms selon le langage, le plan
  avant la spécification et la spécification avant le code, décisions et passations dans des fichiers) sont écrites pour
  les agents, mais les personnes peuvent les apprendre et les appliquer de la même façon.
- **Des cartes de recommandation, pas des règles en prose.** Chaque carte comporte une affirmation, une force (`must` ·
  `should` · `may`), les cas où elle s'applique et ceux où elle ne s'applique pas, des preuves, des contre-exemples et
  la manière de la vérifier. `must` ne se négocie pas ; `should` peut être désactivé en consignant la raison. Huit
  règles de base s'appliquent à tous les projets.
- **Des skills qui se terminent par une preuve.** 16 skills de base (entrée et routage, assistant de guidage,
  planification, spécification, ordre, tâche de construction, vérification, revue, décision, mise à jour des
  connaissances, passation, distillation, traduction, rétrospective, signal d'exploitation, sécurité), en six langues,
  plus des packs optionnels (idéation, design). Chaque skill dit quand l'utiliser, quelle preuve la clôt et les excuses
  qu'un agent invoque quand il veut sauter une étape, avec la réponse à chacune. Six rôles (builder, worker, reviewer,
  supporter, operator, librarian) ont chacun ce qu'ils peuvent et ne peuvent pas faire.
- **Des hooks là où l'application en a, de simples fichiers ailleurs.** Dans Claude Code, les hooks et les cartes
  guident le déroulement : un en-tête au démarrage de la session montre le projet, ses cartes `must` et la prochaine
  action lue dans les fichiers, et un hook enregistre l'état avant que le contexte soit compacté. Là où il n'y a pas de
  hooks, les mêmes consignes et skills sont de simples fichiers `AGENTS.md` et `SKILL.md`, et le moteur de base de
  connaissances est un outil en ligne de commande et un serveur MCP.
- **Des contrôles gradués autour des vérificateurs que vous avez déjà.** `kb enforce run` enveloppe un vérificateur
  existant (un test de couches, dependency-cruiser, un lint) et enregistre chaque exécution, de sorte qu'une famille de
  règles peut monter de niveau une fois ses chiffres connus.

## Documentation

Tables de référence générées à partir des sources : [cartes](docs/reference/cards.md) ·
[skills](docs/reference/skills.md) · [commandes](docs/reference/cli.md) · [profils](docs/reference/profiles.md)
(coréen : `docs/ko/reference/`). Les guides et les pages de concepts sont en cours de rédaction. La référence complète
de la méthodologie pour les agents se trouve dans `core/docs/en/`.

## Organisation

```text
core/       règles de base (constitution/), cartes de recommandation, rôles, schémas, règles de couches et de nommage, docs (six langues)
profiles/   ensembles par stack : sélection de cartes, modèles de layer-map et de vérificateurs, conventions
skills/     procédures SKILL.md et registry.yaml (la table de routage que lit la skill d'entrée) ; packs/
kb/         moteur de base de connaissances : stockage, recherche, portes, CLI de décisions, serveur MCP
tools/      assistant, générateurs de plugin et de bundle, validateurs, doctor, métriques, exécuteur d'evals
adapters/   entrées du plugin Claude Code et du bundle Codex
i18n/       glossaire et marqueurs de traduction en attente
```

## Profils

| Profil | État |
|---|---|
| `core.generic` | active |
| `frontend.next-web` (Next.js / React) | active |
| `backend.kotlin-spring-cqrs` | active |
| `backend.go-service`, `backend.typescript-nest`, `cli.go`, `frontend.swiftui`, `service.rust` | draft |

*active* signifie que le profil est utilisé sur un projet réel et qu'un vérificateur de ses règles de couches y a été
exécuté et a laissé une trace. Un profil draft a ses documents et ses règles, mais ses vérificateurs n'ont pas encore
été éprouvés sur un projet.

## Démarrage rapide

Prérequis : Python 3.11+, git, [uv](https://docs.astral.sh/uv/) pour le serveur MCP, Claude Code pour le plugin.

1. Mettez en place le kit et un vault. Le vault est un simple dossier Markdown (un dépôt git est recommandé) où vivent
   les passations, les tâches, les documents de connaissance et les mesures. `kb vault-init` en crée un à partir des
   modèles de `core/templates/vault/` ; il n'écrase jamais un fichier.

   ```sh
   git clone https://github.com/team-tatters/strata-kit.git ~/workspace/strata-kit
   export STRATA_KIT=~/workspace/strata-kit
   cd "$STRATA_KIT" && uv sync
   python3 "$STRATA_KIT/kb" vault-init ~/workspace/vault --project my-app   # add --detached to keep Tier P in the vault
   export STRATA_VAULT=~/workspace/vault        # required: the engine never guesses a vault path
   ```

2. Construisez et installez le plugin Claude Code.

   ```sh
   python3 "$STRATA_KIT/tools/gen_claude_plugin.py" --locale en
   claude plugin marketplace add "$STRATA_KIT/dist/claude"
   claude plugin install strata-kit@strata-kit
   ```

   Il enregistre le hook d'en-tête de début de session, un hook d'instantané avant compactage, les skills, six agents de
   rôle et le serveur MCP de la base de connaissances. Pour Codex, `tools/gen_codex_bundle.py` écrit les skills et les
   instructions des rôles.

3. Générez les consignes d'un projet, ou demandez à l'agent « configure les consignes strata pour ce projet ».

   ```sh
   python3 "$STRATA_KIT/tools/wizard.py" diagnose  <project>
   python3 "$STRATA_KIT/tools/wizard.py" recommend <project> --profile <id> --uses-vault yes
   python3 "$STRATA_KIT/tools/wizard.py" generate  <project> --apply
   python3 "$STRATA_KIT/tools/wizard.py" verify    <project>
   ```

4. Ouvrez une session dans le projet. L'en-tête montre le projet, ses cartes must et la prochaine action lue dans les
   fichiers ; dites ce que vous voulez faire et la skill d'entrée l'oriente. Dites « handoff » pour clore.

Un projet peut tenir strata entièrement à l'écart d'un dépôt partagé (`detached`) : les consignes et les traces vivent
alors dans le vault, et le dépôt ne reçoit que ce que sa CI exécute.

## État et limites

- Chaque skill de base a des scénarios de pression qui échouent sans la skill et réussissent avec elle
  (`skills/*/evals/`).
- Les preuves que la méthode améliore le travail viennent d'une seule personne sur un petit nombre de projets. Elles
  n'ont pas été reproduites ailleurs, et aucune mesure ne montre encore qu'elle fait mieux que d'autres façons de
  travailler.
- L'arborescence de documentation sous `core/docs/en/` ainsi que les fichiers de règles, les modèles et les README des
  vérificateurs sont en anglais. Beaucoup de commentaires du code de `kb` et certains messages en ligne de commande sont
  encore en coréen.
- Quilt, l'orchestrateur aux côtés duquel le kit a été construit, est un adaptateur optionnel (`--harness quilt`) ;
  son adaptateur n'est pas encore dans ce dépôt. Rien d'autre n'en dépend.
- Les nouvelles équipes devraient commencer avec tous les contrôles en `advisory` et ne faire monter une famille de
  niveau qu'après avoir regardé ses chiffres.

## Contribuer

Les issues et les pull requests sont les bienvenues — voir [CONTRIBUTING.md](CONTRIBUTING.md). Signalez les problèmes
de sécurité comme indiqué dans [SECURITY.md](SECURITY.md).

Les éléments tiers sont listés dans les fichiers `NOTICE.md` placés à côté d'eux (`skills/packs/*/`).
