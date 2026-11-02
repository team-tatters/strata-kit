# フロントエンド Query / State Convention

> 正本: strata-kit `profiles/frontend.next-web/docs/ja/frontend-query-state.md` — strata `docs/05-conventions/frontend-query-state.md` から移管 (オーダー 2026.10.29-06, 2026-10-29)。ルール YAML は `core/rules/`。

> Core の境界: `core/docs/ja/architecture/frontend-web.md`

この文書は、DataState レイヤーを特定のライブラリにマッピングする convention です。
Core の source of truth は「UI は transport を直接呼び出さない」であり、この文書は実装上の選択を説明します。

## DataState 内の 2 区間

| 区間 | ファイル | 役割 | 参照可能 |
|---|---|---|---|
| transport | `{name}.service.ts` | HTTP client 呼び出し、DTO を返す | Foundation · Contract |
| adapter | `use{Entity}Query.ts` · `use{Entity}{Action}Mutation.ts` · `use{Name}State.ts` | サーバー/クライアント状態フック | Foundation · Contract · **transport** |

transport を import できるのは adapter だけである。コンポーネント (Section)・Route Surface・共通フックは adapter だけを見る。

## フックの命名

| 種類 | 名前 | 位置 (レイヤー) |
|---|---|---|
| サーバー状態の読み取り | `use{Entity}Query` · `use{Entity}ListQuery` | DataState adapter |
| サーバー状態の書き込み | `use{Entity}{Action}Mutation` (Create · Update · Delete · Submit …) | DataState adapter |
| Section の状態ロジックの分離 (任意) | `use{UseCase}Section` — 別の Section が再利用する場合、または単独でテストする場合のみ。デフォルトは Section の中 | Feature Block |
| 共通の加工・計算 | `use{Thing}` — 2 つ以上の Section が使うロジック | Feature Block hooks または Foundation |
| クライアント状態 | `use{Name}State` · `use{Name}Store` | DataState adapter |
| 純粋なユーティリティ | `use{Thing}` — フレームワークのフックだけに依存 | Foundation |

**禁止接頭辞**: `useFetch · useGet · usePost · usePut · usePatch · useDelete`。HTTP 動詞は transport の語彙であり、フックはドメインの語彙である。
既存コードには手を付けず、新規行だけを検査する (`profiles/frontend.next-web/enforcement/`)。

## Query Key — 形 · 所有 · 強制

キーはキーファクトリを通してのみ作る — 機能(ドメイン)ごとに 1 つ、その機能の `{domain}.keys.ts` に置く。

```ts
// features/{domain}/{domain}.keys.ts
export const orderKeys = {
  all:     ['shop', 'order'] as const,                       // [scope, domain]
  lists:   () => [...orderKeys.all, 'list'] as const,
  list:    (p: OrderListRequest) => [...orderKeys.lists(), p] as const,
  details: () => [...orderKeys.all, 'detail'] as const,
  detail:  (id: number) => [...orderKeys.details(), id] as const,
};
```

- **形**: `[scope, domain, entity/scope…, params]`。最初の要素はアプリ・zone 識別子 — 複数のアプリが QueryClient を共有することがあるため、衝突を防ぐ。
- **階層**: `all → lists → list(p)`、`all → details → detail(id)`。フラットなキー (`['orders']`) は部分的な無効化ができないため不適合。
- **所有**: 無効化は mutation フックからのみ、そのフックが**影響を受けると宣言した**キーだけに行う — mutation の `meta.invalidates` のタグリスト、またはフック内の明示的なリストで宣言する。宣言するキーは `keys.lists()` のような部分ツリー、`keys.detail(id)` のような正確な詳細キー、または別ドメインのキーでもよく、いずれも所有する機能のキーファクトリで作る。コンポーネントから `invalidateQueries` を直接呼ぶことは禁止。
- **強制**: 静的な依存解析ではインラインリテラルを捕捉できない — diff ルール (`no-inline-query-key`, `no-component-invalidate`) で新規行だけをブロックする。

## 基本ルール

- サーバー状態は query/mutation adapter で包みます。
- mutation 後の cache invalidation ポリシーは DataState に置きます。
- グローバル状態はデフォルトの選択肢ではありません。URL state、query cache、local state をまず検討します。
- props の受け渡しが過剰になる場合は、Feature Block 内部の composition boundary または feature-local context を置きます。

## 禁止

- UI コンポーネントから transport client を直接呼び出すこと
- Route Surface が use case ごとの mutation の詳細ロジックを持つこと
- Semantic Component から server-state adapter を直接呼び出すこと
- `*.keys.ts` の外にある queryKey リテラル

## ライブラリのマッピング

React 系のプロジェクトでは、DataState を query hook、mutation hook、client-state hook として実装できます。
具体的なライブラリとバージョン別の API は、プロジェクト profile または framework convention で決めます。
