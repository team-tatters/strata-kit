# Convention Token pour le frontend

> Source canonique : strata-kit `profiles/frontend.next-web/docs/fr/frontend-tokens.md` — migré depuis strata `docs/05-conventions/frontend-tokens.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles se trouve dans `core/rules/`.

> Contrat de Core : `core/docs/fr/architecture/frontend-design-contract.md`

Ce document est la convention qui associe les trois niveaux de tokens (Primitive → Alias → Component) aux fichiers, au build et au CSS utilitaire.
Un projet peut changer le format et les outils ; dans ce cas, il le consigne dans le profile du projet, pas ici.

## Fichier canonique

- Emplacement : un fichier unique dans le paquet Foundation (par exemple `tokens/tokens.json`).
- Format : le JSON W3C Design Tokens (DTCG) est recommandé — il prend en charge `$value`, `$type` et les références alias (`{color.blue.80}`), et les plugins de synchronisation des outils de design le lisent.
- On place T1 et T2 dans un même fichier, séparés par des groupes de premier niveau (`primitive.*`, `alias.*`). T3 est `component.*`, seulement si nécessaire.
- Les modes s'expriment sur la valeur alias par `$extensions.modes` ou dans un fichier de mode distinct. Le nom est unique, quel que soit le mode.

```json
{
  "primitive": { "color": { "blue": { "80": { "$type": "color", "$value": "#1b4380" } } } },
  "alias": {
    "color": {
      "action": { "primary": { "bg": { "default": { "$value": "{primitive.color.blue.80}" } } } },
      "surface": { "default": { "$value": "{primitive.color.common.0}" } }
    }
  }
}
```

## Produits générés (résolus uniquement à l'étape de build)

| Produit | Consommateur | Remarques |
|---|---|---|
| Variables CSS (`--color-action-primary-bg-default`) | CSS utilitaire · thème à l'exécution | On n'expose que les alias. Les variables T1 sont masquées par un préfixe interne ou ne sont pas générées |
| Constantes TS (`tokens.color.action.primary.bg.default`) | Là où un objet de style est nécessaire | Les types sont dérivés du chemin alias |
| Variables de l'outil de design | Designers | Outil de synchronisation (par exemple Tokens Studio · Variables API) — la direction est décidée par le profile |
| **Catalogue d'alias** (`tokens.md`, généré) | Agents · relecteurs | Une ligne par nom, sens et usage. Il reste d'une taille qui tient dans le budget de contexte T0 |

Le code des composants n'utilise que les **noms alias** des produits générés. Il n'importe pas directement le fichier de tokens et ne calcule pas de valeurs.

## Association du CSS utilitaire

Les classes utilitaires sont un vecteur de transmission des alias. Le nom de la classe reflète tel quel le chemin alias.

| Autorisé | Interdit |
|---|---|
| `bg-surface-default` · `text-muted` · `border-status-pending` | `bg-blue-80`(T1) · `bg-[#1b4380]`(valeur arbitraire) · `text-[13px]` |

La configuration du thème (par exemple Tailwind `@theme` ou un preset) est un produit généré et ne s'édite pas à la main. Ne pas générer d'utilitaires T1 (`bg-blue-80`) est la façon la plus simple de l'appliquer.

## Stories (canoniques en l'absence d'outil de design)

- Primitive UI : au moins une story par composant, exposant dans un tableau toutes les combinaisons variant · intent · size.
- Semantic Component : une story pour chaque axe d'état des données (default · loading · empty · error).
- Foundation : on prévoit des stories du catalogue d'alias (couleur · espacement · ombre · typographie) — un écran que les designers utilisent pour relire sans outil.

## Contrôles

| Contrôle | Méthode | Emplacement |
|---|---|---|
| Valeurs raw hors de Foundation | Contrôle de diff des nouvelles lignes — littéraux hex · rgba · px · valeurs arbitraires `[…]` · motifs de classes T1 | `profiles/frontend.next-web/enforcement/diff-rules.json.template` |
| Expiration des exceptions | On analyse `@strata:token-exception … until YYYY-MM-DD` ; échec si aujourd'hui dépasse cette date | Le même script |
| Approbation des changements de tokens | Une PR avec un diff du fichier de tokens porte un DEC id dans son corps | Règle de CI ou modèle de PR |

## Interdictions

- Utiliser des noms T1, des valeurs raw ou des valeurs arbitraires dans les composants
- Éditer à la main un thème en contournant le fichier de tokens
- Inclure des noms de palette ou d'écran dans les noms alias (`color.blue.button`, `color.dashboard.header`)
