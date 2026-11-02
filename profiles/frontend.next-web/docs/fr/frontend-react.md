# Convention React pour le frontend

> Source canonique : strata-kit `profiles/frontend.next-web/docs/fr/frontend-react.md` — migré depuis strata `docs/05-conventions/frontend-react.md` (ordre 2026.10.29-06, 2026-10-29). Le YAML des règles se trouve dans `core/rules/`.

> Frontière de Core : `core/docs/fr/architecture/frontend-web.md` · Contrat de design : `core/docs/fr/architecture/frontend-design-contract.md`

Ce document décrit les conventions suivies par un projet React pour implémenter les couches web de Core.
React n'est pas un prérequis de Core.

## Chaîne à sens unique — Page → Section → View → Primitive

Le flux va dans un seul sens, de la route à l'écran. **La Section est le propriétaire de l'état de son cas d'usage** (une Section enfant qui est une unité d'enregistrement indépendante possède le sien) — la Section déclare les Props, détient l'état et ne le propage que vers le bas.

```
route file (Route Surface)
  └─ params · guard · metadata · exactement un <XxxSection/>. Hooks : hooks de routage uniquement
      └─ XxxSection (Feature Block) — propriétaire de l'état
           │  useState · useEffect · hooks locaux · hooks DataState adapter (use*Query · use*Mutation) sont appelés directement ici
           ├─ <XxxView/>          Semantic Component — reçoit uniquement des props et dessine
           └─ <XxxSubSection/>    Section enfant du même domaine si nécessaire — propriétaire de l'état si c'est une unité d'enregistrement indépendante :
                                  récupère et enregistre directement les données de son cas d'usage ; seul l'état partagé avec le parent arrive en props.
                                  Un input soumis ou annulé avec le parent est une View ou un controlled component,
                                  pas une Section ; le parent possède le brouillon et le submit (enregistrement atomique : une commande ou une transaction)
                └─ Primitive UI + tokens alias
```

## Propriété de l'état dans une Section et critère de séparation

Ce qui reste dans une Section et ce qui en sort se décide par **type, pas par nombre**. Séparer la logique d'état dans un hook n'est pas une obligation.

| Type | Emplacement | Raison |
|---|---|---|
| État local (`useState` · `useReducer`), effets (`useEffect`), valeurs dérivées (`useMemo`), hooks locaux utilisés uniquement par cette Section | **Dans la Section** | Le propriétaire de l'état doit être visible en un seul endroit |
| Lecture et écriture de l'état serveur | La Section **appelle** les hooks DataState adapter. L'implémentation est dans `query-hooks/` | transport n'apparaît pas dans la Section |
| Appels de service (HTTP · storage · SDK externe) | **Toujours à l'extérieur** — DataState transport | Les composants ne connaissent pas transport |
| Traitement, calcul ou logique d'état utilisés par au moins deux Sections | **À l'extérieur** — `features/{domain}/hooks/use{Thing}` ou une util de Foundation | Les couches communes adoptent une structure de référence |
| Quand une autre Section doit réutiliser en bloc la logique d'état d'une Section, ou qu'elle doit être testée seule | Facultatif — séparer en `use{UseCase}Section` | On ne sépare que si nécessaire. Par défaut, dans la Section |

## Sens des suffixes

| Suffixe | Couche | Appels DataState | Hooks de routeur | Remarques |
|---|---|---|---|---|
| `{Route}Page` / route file | Route Surface | Interdit | Autorisé | Le principe est de placer 1 Section. À partir de 2, un composant d'assemblage `{Route}Page` — une Route Surface où qu'il se trouve, routes ou features (son mapping dans le layer-map passe avant celui de Feature Block). Les Section de domaines différents y sont placées côte à côte |
| `{UseCase}Section` | Feature Block | Autorisé | Interdit — la Page les injecte | Propriétaire de l'état. Fragment d'écran sans route, réutilisable dans plusieurs routes. Importer la Section d'un autre domaine est interdit ; une Section du même domaine peut être contenue comme enfant |
| `{UseCase}Panel` · `Dialog` · `Table` | Feature Block | Autorisé | Interdit | Une Section sous forme d'overlay, de panneau latéral ou de tableau |
| `{Domain}{Purpose}View` | Semantic Component | Interdit | Interdit | Props uniquement. Ne peut avoir qu'un état d'UI local (ouverture, survol) |
| Composant Primitive | Primitive UI | Interdit | Interdit | Uniquement alias + axes variant |

Les suffixes `Container`, `Block` et `Partial` sont interdits — utilisez `Section` (ou `Panel` · `Dialog` · `Table` selon la forme).

## Nommage des props — le propriétaire et la direction dans le nom

Quand l'état et les hooks détenus par une Section descendent vers plusieurs enfants, le seul nom du prop doit permettre de savoir **qui en est propriétaire, dans quel sens il circule, et s'il s'agit d'une valeur ou d'une action**. Préfixes et suffixes expriment ces trois points. Lisible par machine : `core/rules/naming-convention.yaml` → `frontend.Props`.

| Rôle | Forme | Exemple | Règle |
|---|---|---|---|
| Valeur courante d'un état détenu par le parent (lecture) | Nom, sans préfixe | `selectedIds` · `filter` · `page` | Sans préfixe = « détenu par le parent, l'enfant ne fait que lire » |
| Demande de modification de l'état du parent (enfant → parent) | `on{State}Change` | `onSelectedIdsChange` · `onFilterChange` | On ne passe pas le setter tel quel. Les props `set*` sont interdits |
| Déclencher une action du parent (événement) | `on{Event}` (verbe) | `onSubmit` · `onRowClick` · `onDelete` | Quand l'enfant n'a pas besoin de connaître le résultat |
| Une paire valeur + modification **partagée par plusieurs enfants** | Regroupement `{state}Control` | `selectionControl={{ value, onChange }}` | Marqueur de référence multiple. Type `{State}Control`. On ne disperse pas le même état entre plusieurs enfants sous forme de deux props, valeur et callback |
| Regroupement de données dérivées ou d'affichage uniquement | `{name}Model` | `orderModel` | Le ViewModel de Contract. On n'y met pas de callbacks |
| Valeur initiale (détenue par l'enfant) | `default{State}` | `defaultPage` | Non contrôlé. Le parent n'intervient plus ensuite |
| Booléen | `is` · `has` · `can` · `should` | `isEditing` · `canDelete` · `shouldAutoFocus` | Forme affirmative. Les noms d'attributs HTML comme `disabled` font exception |
| Tranche d'état serveur | Nom de donnée + `is{Entity}Loading` + `{entity}Error` | `orders` · `isOrdersLoading` · `ordersError` | On ne passe pas l'objet de résultat de query en entier |
| Délégation de rendu | `render{Slot}` | `renderRow` | |
| ref | `{name}Ref` | `scrollRef` | |

**Recommandation — les références multiples passent par un regroupement Control.** Quand trois enfants lisent et écrivent un même état du parent, on regroupe `value`, `onChange` et les valeurs dérivées dans un seul objet `{state}Control` que l'on transmet vers le bas. Le suffixe du nom révèle qu'il s'agit d'un état détenu par le parent et partagé à plusieurs endroits, et le nombre de props n'augmente pas quand on ajoute des enfants. Les préfixes plats comme `shared*` ou `section*` indiquent la propriété mais pas la direction (lecture/écriture) ; on ne les utilise donc pas.

```tsx
// Section — propriétaire de l'état
const [selectedIds, setSelectedIds] = useState<number[]>([]);
const selectionControl: SelectionControl = { value: selectedIds, onChange: setSelectedIds, count: selectedIds.length };
const { data: orders = [], isLoading: isOrdersLoading } = useOrderListQuery(filter);

<OrderTableView orders={orders} isOrdersLoading={isOrdersLoading} selectionControl={selectionControl} onRowClick={handleRowClick} />
<OrderBulkActionView selectionControl={selectionControl} onDelete={handleDelete} />
```

Les fonctions gestionnaires internes se nomment `handle{Event}`, et les noms des props passés aux enfants sont `on{Event}`. On n'utilise pas le même nom pour les deux.

## Component Boundary

- On place un seul composant exporté par fichier.
- Les fonctions auxiliaires et les sous-composants privés à l'intérieur d'un fichier sont autorisés, mais on les sépare dans un autre fichier dès qu'ils sont réutilisés.
- Les DTO, ViewModel, schema et interface sont déplacés vers Contract.
- Un Semantic Component n'appelle pas directement les hooks DataState ; il les reçoit injectés par props/callbacks.
- Les axes d'état des données (loading · empty · error) sont reçus comme props de la View et rendus. C'est la Section qui décide des valeurs.

## State Boundary

- L'assemblage du use case et les appels DataState commencent dans le Feature Block (Section).
- On n'introduit pas de dépendance à une bibliothèque d'état serveur dans les shared UI components.
- Le feature-local context n'est utilisé que de façon limitée, lorsque le passage de props devient profond. Si un regroupement Control suffit, on ne crée pas de context.
