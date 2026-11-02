# フロントエンド React Convention

> 正本: strata-kit `profiles/frontend.next-web/docs/ja/frontend-react.md` — strata `docs/05-conventions/frontend-react.md` から移管 (オーダー 2026.10.29-06, 2026-10-29)。ルール YAML は `core/rules/`。

> Core の境界: `core/docs/ja/architecture/frontend-web.md` · デザイン契約: `core/docs/ja/architecture/frontend-design-contract.md`

この文書は、React プロジェクトが Core の Web レイヤーを実装する際の慣例を説明します。
React は Core の必須の前提ではありません。

## 一方向の連鎖 — Page → Section → View → Primitive

ルートから画面まで、一方向にのみ流れる。**Section がその use case の状態の所有者**である(独立した保存単位である子 Section は自分の状態を所有する) — Section が Props を宣言し、状態を保持し、下方向にのみ伝播する。

```
route file (Route Surface)
  └─ params · guard · metadata · <XxxSection/> を 1 つだけ。フックはルーティングフックのみ
      └─ XxxSection (Feature Block) — 状態の所有者
           │  useState · useEffect · ローカルフック · DataState adapter フック(use*Query · use*Mutation)をここで直接呼び出す
           ├─ <XxxView/>          Semantic Component — props だけを受け取って描画する
           └─ <XxxSubSection/>    必要なら同じドメインの下位 Section — 独立した保存単位なら状態の所有者:
                                  自分の use case のデータを直接取得・保存する。親と共有する状態だけを props で受け取る。
                                  親と一緒に submit・cancel される入力は Section ではなく View または controlled component で、
                                  下書きと submit は親が所有する(アトミックな保存: 1 つのコマンドまたはトランザクション)
                └─ Primitive UI + alias トークン
```

## Section の状態所有と分離基準

Section の中に置くものと外に出すものは、**数ではなく種類**で分ける。状態ロジックをフックに分離することは義務ではない。

| 種類 | 位置 | 理由 |
|---|---|---|
| ローカル状態 (`useState` · `useReducer`)、エフェクト (`useEffect`)、派生値 (`useMemo`)、この Section だけが使うローカルフック | **Section の中** | 状態の所有者が 1 か所に見えなければならない |
| サーバー状態の読み取り・書き込み | Section が DataState adapter フックを**呼び出す**。実装は `query-hooks/` | transport は Section に現れない |
| サービス呼び出し (HTTP · storage · 外部 SDK) | **常に外** — DataState transport | コンポーネントは transport を知らない |
| 2 つ以上の Section が使う加工・計算・状態ロジック | **外** — `features/{domain}/hooks/use{Thing}` または Foundation util | 共通層は参照構造で |
| ある Section の状態ロジックを別の Section がまるごと再利用する場合、または単独でテストしなければならない場合 | 任意 — `use{UseCase}Section` として分離 | 分離は必要なときだけ。デフォルトは Section の中 |

## 接尾辞の意味

| 接尾辞 | レイヤー | DataState 呼び出し | ルーターフック | 備考 |
|---|---|---|---|---|
| `{Route}Page` / route file | Route Surface | 禁止 | 許可 | Section を 1 つ配置するのが原則。2 つ以上なら `{Route}Page` 組み立てコンポーネント — どこに置かれても(routes でも features でも)Route Surface(layer-map のマッピングは Feature Block より前)。異なるドメインの Section はここで並べて配置する |
| `{UseCase}Section` | Feature Block | 許可 | 禁止 — Page が注入 | 状態の所有者。ルートのない画面の断片で、複数のルートで再利用可能。他のドメインの Section の import は禁止。同じドメインの Section は子として含めてよい |
| `{UseCase}Panel` · `Dialog` · `Table` | Feature Block | 許可 | 禁止 | オーバーレイ・サイド・表の形をした Section |
| `{Domain}{Purpose}View` | Semantic Component | 禁止 | 禁止 | props のみ。ローカルな UI 状態 (開閉・ホバー) だけを持てる |
| Primitive コンポーネント | Primitive UI | 禁止 | 禁止 | alias + variant 軸のみ |

接尾辞 `Container`・`Block`・`Partial` は禁止 — `Section`(形に応じて `Panel` · `Dialog` · `Table`)を使う。

## Props の命名 — 所有者と方向を名前に込める

Section が所有する状態やフックが複数の子に下りていくとき、prop 名だけを見て**誰が所有するか · どちらの方向に流れるか · 値か動作か**が分からなければならない。接頭辞・接尾辞はその 3 つを語る。機械可読: `core/rules/naming-convention.yaml` → `frontend.Props`。

| 役割 | 形 | 例 | 規則 |
|---|---|---|---|
| 親が所有する状態の現在値 (読み取り) | 名詞、接頭辞なし | `selectedIds` · `filter` · `page` | 接頭辞なし = 「親が所有、子は読むだけ」 |
| 親の状態の変更要求 (子 → 親) | `on{State}Change` | `onSelectedIdsChange` · `onFilterChange` | setter をそのまま渡さない。`set*` prop は禁止 |
| 親の動作のトリガー (イベント) | `on{Event}` (動詞) | `onSubmit` · `onRowClick` · `onDelete` | 結果を子が知る必要がないとき |
| 値 + 変更のペアを**複数の子が共有**する | `{state}Control` の束 | `selectionControl={{ value, onChange }}` | 多重参照の標識。型は `{State}Control`。同じ状態を値とコールバックの 2 つの prop として複数の子に散らさない |
| 派生・表示専用データの束 | `{name}Model` | `orderModel` | Contract の ViewModel。コールバックを入れない |
| 初期値 (子が所有) | `default{State}` | `defaultPage` | 非制御。親はその後関与しない |
| 真偽値 | `is` · `has` · `can` · `should` | `isEditing` · `canDelete` · `shouldAutoFocus` | 肯定形。`disabled` のような HTML 属性名は例外 |
| サーバー状態のスライス | データ名詞 + `is{Entity}Loading` + `{entity}Error` | `orders` · `isOrdersLoading` · `ordersError` | query の結果オブジェクトをそのまま渡さない |
| レンダリングの委譲 | `render{Slot}` | `renderRow` | |
| ref | `{name}Ref` | `scrollRef` | |

**推奨 — 多重参照は Control の束で。** 親の状態 1 つを 3 つの子が読み書きするなら、`value`・`onChange`・派生値を `{state}Control` オブジェクト 1 つにまとめて下ろす。名前の接尾辞が「親が所有し複数の場所が共有する状態」であることを示し、子が増えても prop の数は増えない。`shared*`・`section*` のようなフラットな接頭辞は所有を語っても方向 (読み取り/書き込み) を語れないので使わない。

```tsx
// Section — 状態の所有者
const [selectedIds, setSelectedIds] = useState<number[]>([]);
const selectionControl: SelectionControl = { value: selectedIds, onChange: setSelectedIds, count: selectedIds.length };
const { data: orders = [], isLoading: isOrdersLoading } = useOrderListQuery(filter);

<OrderTableView orders={orders} isOrdersLoading={isOrdersLoading} selectionControl={selectionControl} onRowClick={handleRowClick} />
<OrderBulkActionView selectionControl={selectionControl} onDelete={handleDelete} />
```

内部のハンドラ関数の名前は `handle{Event}`、子に渡す prop の名前は `on{Event}` である。両者に同じ名前を使わない。

## Component Boundary

- 1 つのファイルには exported component を 1 つ置きます。
- ファイル内部の補助関数と private subcomponent は許可しますが、再利用されるなら別ファイルに分離します。
- DTO、ViewModel、schema、interface は Contract に移します。
- Semantic Component は DataState hook を直接呼び出さず、props/callback で注入されます。
- データ状態の軸 (loading · empty · error) は View の props として受け取って描画する。値は Section が決める。

## State Boundary

- use case の組み立てと DataState の呼び出しは Feature Block (Section) から始めます。
- shared UI component にサーバー状態ライブラリへの依存を入れません。
- feature-local context は、props の受け渡しが深くなるときにだけ限定的に使います。Control の束で解決できるなら context を作りません。
