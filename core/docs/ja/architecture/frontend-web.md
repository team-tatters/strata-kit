# フロントエンド Web レイヤーアーキテクチャ

> 正本: strata-kit `core/docs/ja/architecture/frontend-web.md` — strata `docs/03-architecture/frontend-web.md` から移管（オーダー 2026.10.29-06、2026-10-29）。ルール YAML は `core/rules/`。

> 機械可読なルール: `core/rules/layer-rules.yaml` → `frontend.variants.web`
> この文書は、フレームワーク非依存の Web フロントエンド variant を人が読むための詳細説明です。
> トークン・バリアント・組み合わせとデザイン成果物の整合は `core/docs/ja/architecture/frontend-design-contract.md` が定義します。

## 境界原則

Strata Core のフロントエンド指針は、特定の UI フレームワーク、ルーター、状態管理ライブラリ、スタイリングツールを定義しません。
Core には、import・パス・静的解析で検証できる責務の境界だけを置きます。

レイヤーの関係は単一の線形ツリーではなく DAG です。
下の表の `can_reference` が source of truth であり、表にないレイヤーの参照と、`cross_reference: false` のレイヤーにおける同レベル間の相互参照は禁止です(Feature Block ではドメインをまたぐ参照を指します。下記参照)。

| Layer | can_reference |
|---|---|
| Foundation | なし |
| Contract | Foundation |
| DataState | Foundation, Contract |
| Primitive UI | Foundation |
| Semantic Component | Foundation, Contract, Primitive UI |
| Feature Block | Foundation, Contract, DataState, Primitive UI, Semantic Component |
| Route Surface | Foundation, Contract, Feature Block, App Shell |
| App Shell | Foundation, Contract, DataState, Primitive UI, Semantic Component |

## Variants

Strata フロントエンドは 3 つの variant をサポートします。

| Variant | 用途 | 状態 |
|---|---|---|
| `atomic` | 既存の L1/LM/L2/Atomic/Molecule/Partial/Page/Layout 構造とレガシープロジェクトとの互換 | 維持 |
| `web` | フレームワーク非依存の Web アプリケーション境界 | デフォルト |
| `mobile` | ネイティブモバイル UI（SwiftUI・Compose）— レイヤーと can_reference は web と同じで、語彙・組み立て・ターゲットのルールが異なる（`core/docs/ja/architecture/frontend-mobile.md`） | 2026-09-11 |

プロジェクトごとの選択は `.strata/layer-map.yaml` の `variant` または `frontend_variant` に置きます。
選択値がなければ、Core のデフォルトは `web` です。

## Foundation

セマンティックトークン、純粋関数、定数、プリミティブ型を置きます。

**許可:** token, const, type, util

**禁止:** UI レンダリング、transport 呼び出し、グローバル状態へのアクセス、フレームワーク依存の実装

## Contract

UI と transport の間の安定した契約です。
DTO、ViewModel、schema、API port/interface、cache key contract を置きます。

**ルール:**
- Foundation のみを参照します。
- UI レイヤーと DataState を参照しません。
- transport の実装を直接呼び出しません。
- コンポーネントファイルに散らばりやすい interface/type は、このレイヤーに集めます。

## DataState

サーバー状態、mutation、クライアント状態の adapter 層です。
具体的なライブラリは convention で決め、Core は UI が transport を直接見られないようにする境界だけを定義します。

**ルール:**
- Foundation と Contract のみを参照します。
- UI コンポーネントをレンダリングしません。
- transport client を UI に直接公開しません。
- cache key と DTO/ViewModel の契約は Contract を参照します。

**2 つの区間:** transport（`{name}.service` — HTTP 呼び出し、DTO を返す）と adapter（`use{Entity}Query` · `use{Entity}{Action}Mutation` · `use{Name}State`）。
transport を import できるのは adapter だけです。上位レイヤーは adapter だけを見ます。

## Primitive UI

セマンティックトークンに結び付いた低レベルの UI です。
ドメインの意味やサーバー状態を知らないものでなければなりません。

**ルール:**
- Foundation のみを参照します。
- Contract のドメインモデル、DataState、transport を参照しません。
- Props と Foundation の token だけで動作します。

## Semantic Component

ユーザーまたはドメインの意味を持つ UI コンポーネントです。
Atomic/Molecule のようなサイズの分類ではなく、「何をするコンポーネントか」を名前と責務で表現します。

**検証可能な中核の境界:** Semantic Component は DataState を直接呼び出しません。
サーバー状態と mutation は props または callback で注入されます。

Feature Block の描画側の半分を切り出したコンポーネントは `{Domain}{Purpose}View` と命名します。データ状態の軸（loading · empty · error）は props で受け取ります。
見た目は、Primitive UI の variant 軸の値と Foundation の alias の組み合わせだけで決めます（Composition Legality — `core/docs/ja/architecture/frontend-design-contract.md`）。

## Feature Block

特定のユースケースの画面断片と、そのデータ・状態を組み立てるレイヤーです。
DataState の呼び出しは、このレイヤーから許可されます。

**ルール:**
- 異なるドメインの Feature Block 間の直接参照は禁止です。同じドメインの中では、Section が別の Section を子として含めてかまいません。異なるドメインの画面を一緒に見せる必要があるときは、Route Surface の `{RouteName}Page` が各ドメインの Section を並べて配置し、props とイベントでつなぎます。
- ドメインは feature ルート直下のディレクトリ 1 つです（layer-map の `feature_root`、なければ layer-rules の `Feature_Block.domain_slice` の接頭辞）。ルートの外にある Feature Block ファイルはドメイン分離の対象外です。この境界はコードのスライスの境界であり、業務ドメインの意味を保証するものではありません。
- Semantic Component、Primitive UI、DataState、Contract を組み立てます。
- ルーティングやアプリレベルの provider の責務を持ちません。

接尾辞は `{UseCase}Section`（ルートを持たない画面断片 — atomic variant の Partial に相当）で、形に応じて `Panel` · `Dialog` · `Table` を使います。接尾辞 `Block`・`Container`・`Partial` は禁止です（`core/rules/naming-convention.yaml` → `Feature_Block.forbidden_suffixes`）。
Section は**その use case の状態の所有者**です（独立した保存単位である子 Section は自分の状態を所有します） — Props を宣言し、ローカル状態・effect・DataState adapter フックを直接持ち、下へ向けてのみ伝播します。描画は `View`（Semantic Component）に任せます:
`Route Surface → Section → View → Primitive UI`。状態の所有は 3 つに分かれます — ローカルの下書きを所有すること、サーバーキャッシュを観察すること、保存コマンドに責任を持つことです。同じドメインの子 Section が下書きと mutation を所有するのは、それが自分の use case であり独立した保存単位であるときだけで、親と共有する状態だけを props で受け取ります。複数の Section が編集する下書きの所有者は 1 つであり、Section をまたぐ submit・cancel・アトミックな保存は 1 つの調整役（親 Section）が受け持ち、内側の入力は View または controlled component にします。アトミック性は複数の mutation の後の invalidation ではなく、1 つの DataState/API コマンドまたはトランザクションから得ます。複数の Section が同じ query key を観察することは重複した所有ではありません。状態ロジックをフックに分離することは義務ではなく、サービス呼び出し（transport）と 2 つ以上の Section が使う共通の加工だけを、参照構造として外に置きます。分離の基準と Props の命名は `profiles/frontend.next-web/docs/ja/frontend-react.md` を参照してください。

## Route Surface

URL の入口、route params、権限の境界、画面の組み立てを担当します。

**ルール:**
- Feature Block を配置します — 原則として Section 1 つ。2 つ以上なら `{RouteName}Page` の組み立てコンポーネントを置きます。この組み立てコンポーネントは、どこに置かれても（routes でも features でも）Route Surface です — layer-map ではそのマッピングを Feature Block のマッピングより前に置きます。
- 再利用可能な UI として export しません。
- transport の直接呼び出しは禁止です。DataState フックの呼び出しも禁止です — `can_reference` に DataState がありません。

ルーターごとのファイルルールは Core ではなく、フレームワークの convention で定義します。

## App Shell

グローバル provider、ナビゲーション、アプリレベルのレイアウトを担当します。

**ルール:**
- Feature Block を直接参照しません。
- ドメインのユースケースロジックを持ちません。
- グローバル provider とシェルレベルのレイアウトだけを扱います。
- 複数のアプリ（ゾーン）が共有するシェルパッケージも App Shell です。アプリの境界をまたぐ移動は URL でのみ行います。

## Core / Convention / Profile の分離

| 性格 | 場所 | 例 |
|---|---|---|
| 検証可能なアーキテクチャ境界 | Core `core/docs/ja/architecture/frontend-web.md`, `core/rules/layer-rules.yaml` | Semantic Component から DataState を参照することの禁止 |
| デザイン契約（トークン・バリアント・組み合わせ・整合） | Core `core/docs/ja/architecture/frontend-design-contract.md` | コンポーネントは alias を参照（コンポーネントトークンは所有者からのみ）、design_ref・整合状態 |
| フレームワーク/ライブラリのバインディング | `profiles/<id>/docs/ja/` | query hook、router、スタイリングツール、トークンファイルのマッピング |
| プロジェクトのレガシー/移行ポリシー | プロジェクトの `.strata/` | legacy/bridge/target zone |

Strata Core が定義するのは「どのライブラリを使うか」ではなく、「どの責務がどのレイヤーを通らなければならないか」です。
