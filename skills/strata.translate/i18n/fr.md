# strata.translate

## Aperçu

Comble les locales manquantes des cartes, corps de skills, rôles et documents à partir du texte canonique, en utilisant le glossaire, sans changer le sens, les identifiants ni la structure.

## Quand l'utiliser

Lorsque la vérification i18n signale des locales en attente, après la rédaction d'un nouveau texte, ou sur demande. Traduisez le sens ; ne traduisez jamais les identifiants.

## Procédure

1. Exécutez tools/i18n_check.py et listez les éléments en attente. Preuve : la sortie.
2. Lisez le glossaire et le texte canonique. Preuve : les chemins.
3. Écrivez chaque locale manquante en gardant identiques les identifiants, énumérations, clés et espaces réservés ; conservez l'ordre des sections dans les corps de skills. Preuve : le diff.
4. Relancez la vérification ; les erreurs doivent être nulles et les avertissements moins nombreux. Preuve : la sortie.
5. Signalez toute phrase où le texte canonique était ambigu, avec la question pour l'auteur.

## Rationalisations

| Pensée | Réponse |
|---|---|
| « Une traduction approximative vaut mieux que rien. » | Une règle approximative est une autre règle. Traduisez avec précision ou signalez. |
| « L'identifiant se lit mal dans la langue cible, je vais le localiser. » | Les identifiants sont en anglais par politique. Localisez l'étiquette, pas l'id. |
| « Les espaces réservés peuvent bouger. » | Les espaces réservés doivent correspondre exactement, sinon le générateur casse. |

## Signaux d'alerte

- Une énumération ou une clé traduite.
- Une locale avec une phrase en trop ou manquante.
- Des avertissements de la vérification qui n'ont pas diminué.

## Vérification

- Identifiants identiques.
- Erreurs de la vérification nulles, avertissements diminués.
- Ambiguïtés signalées.
