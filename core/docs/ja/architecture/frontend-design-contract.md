# フロントエンド デザインコントラクト (Design Contract)

> 正本: strata-kit `core/docs/ja/architecture/frontend-design-contract.md` — strata `docs/03-architecture/frontend-design-contract.md` から移管 (オーダー 2026.10.29-06, 2026-10-29)。ルール YAML は `core/rules/`。

> 機械可読ルール: `core/rules/layer-rules.yaml` → `frontend.variants.web` (Foundation · Primitive_UI · Semantic_Component)、
> `core/rules/naming-convention.yaml` → `frontend.Foundation.token_alias` · `markers.token_exception`
> この文書は、デザイン(トークン・バリアント・コンポジション)と実装の間の**検証可能なコントラクト**を定義する。
> 特定のデザインツール、CSS ツール、UI ライブラリを前提としない。ツールのバインディングは `profiles/frontend.next-web/docs/ja/frontend-tokens.md`。

## 境界原則

Core が答えるのは 2 つの問いだけである。「このコンポーネントは何をするか」と「このコンポーネントの見た目はどこで決まるか」。
「どう見えるか」はトークンとバリアント軸の組み合わせから導出されなければならず、コンポーネントコードの中で直接決めてはならない。

「トークン」という一語に混ざっている 3 つの概念を分離する。

| 概念 | 定義 | 置き場所 |
|---|---|---|
| Token | 値の体系。原値(primitive)と意図(alias) | Foundation |
| Variant | コンポーネントが公開する軸 (variant · intent · size · state) | Primitive UI |
| Composition | コンポーネントの組み合わせ。大きさではなく**コントラクト**(名前 = 意味、props = 意図、slots)で表現する | Semantic Component · Feature Block |

## トークン 3 段

| 段 | 役割 | 命名例 | 参照を許可する先 | デザインツール |
|---|---|---|---|---|
| T1 Primitive | パレットスケール・間隔・タイポグラフィの原値 | `cool-neutral-30` · `blue-80` · `space-4` | T2 のみ。コンポーネントからの参照は禁止 | 変数コレクション "Primitive" |
| T2 Alias | 意図。**エージェント・デザイナー・コードが共有する唯一の語彙** | `color.surface.default` · `color.text.muted` · `color.action.primary.bg.hover` · `color.status.pending.fg` | Primitive UI · Semantic · Feature | 変数コレクション "Semantic" (モード: light/dark/density) |
| T3 Component | コンポーネントごとの override。生成物であり任意。T2 alias を指し、raw 値は指さない | `button.solid.primary.bg` | それを所有するコンポーネント(とその内部)のみ | 置かないのが既定 |

**Alias の命名**: `{category}.{object}.{role}.{state?}` — category (color · space · radius · shadow · typography)、object (surface · text · border · action · status · …)、role (default · muted · bg · fg · …)、state (hover · active · disabled · …)。
モード(ライト・ダーク・密度)は alias の**値の層**で分かれ、名前は一つのままである。

**ルール**
- T1 は T2 からのみ参照される。コンポーネントコードに T1 の名前が現れたら違反。
- T3 のコンポーネントトークンは、それを所有するコンポーネント(とその内部)からのみ参照され、alias を指し、raw 値は指さない。別のコンポーネントや画面が同じ値を必要とするときは alias に昇格する。
- Foundation の外で raw 値 (hex · px · rgba · パレットスケール名) は禁止であり、デザインプロパティごとに適用する: 色、余白、フォントサイズと行の高さ、radius、shadow、z-index。実行時に計算・測定される値(仮想スクロールのオフセット、測定した基準幅、データ列の幅などの連続的な寸法)は、`@strata:computed <reason>` を付けた例外として許可する(期限なし。理由が空なら認めない)。alias 変数を参照する任意値は raw 値ではない。ユーティリティ CSS のクラス名は alias の名前をそのまま映さなければならない。
- 新しい alias の追加はアーキテクチャ上の決定である — 決定レコードが必須 (`@strata:token-exception` は期限付きの一時的な逃げ道、下の §例外ポリシー を参照)。

## Variant 軸

Primitive UI が公開する軸は 4 つである。軸の**値にパレット名を使わない** — 「どう見えるか」ではなく「何を意味するか」で値を決める。

| 軸 | 値 (既定の語彙) | 備考 |
|---|---|---|
| `variant` | solid · outline · subtle · clean | 形態 |
| `intent` | primary · neutral · danger · success · warning · info | 意図。プロジェクトはドメインの状態軸(例: `status: pending · completed`)を**別の軸**として拡張できる。同じ軸に混ぜない |
| `size` | sm · md · lg | プロジェクトが値を再定義できる |
| `state` | default · hover · focus · active · disabled | インタラクション状態。**データ状態**(loading · empty · error)は Semantic Component から持つ |

デザインツールのコンポーネントプロパティ名とコードの props 名は**同一**でなければならない。これが整合検査の前提である。

## Composition Legality — 組み合わせの正当性

> Semantic Component と Feature Block の見た目は、**(下位の Primitive UI の variant 軸の値) × (Alias トークン)の純粋関数**でなければならない。

ここでいう「見た目」は、コンポーネント自身の視覚プロパティ — 色、タイポグラフィ、内側の余白(padding)、ボーダー、各状態の見た目 — を指す。コンポーネント間の配置、外側の margin、ビューポートとレスポンシブの振る舞い、コンテンツとアセットはこのルールの外にあり、親が配置するレイアウト要素(grid、stack など)に属する。raw 値とパレットの検査が測るのはこの範囲である。

この一行が Atomic Design の Molecule/Organism(大きさによる分類)を置き換える。組み合わせは大きさではなく正当性で判定する。

| 判定 | 例 |
|---|---|
| 正当 | `<Button intent="danger" variant="outline">` + `color.text.muted` · alias 変数を参照する任意値 · 理由コメント付きの実行時測定幅 |
| 違反 | `bg-blue-80` (T1 の直接参照) · `style={{color:'#303140'}}` (raw 値) · `className="bg-[#fff]"` (任意値) |

Atomic variant との対応は `core/docs/ja/architecture/frontend-atomic.md` の §マッピングに従う。要点: Atom → Primitive UI、Molecule → Semantic Component (データ非依存) または Feature Block (DataState を呼ぶ)、Organism 廃止、Partial → Feature Block (Section)。

## デザイン成果物と整合

機能一つに成果物が 3 つある。それぞれがバージョンを持ち、**どれでも入口**になり得る。ゲートは順序ではなく、組の間の整合検査である。

| 成果物 | 担うもの | 形 |
|---|---|---|
| Spec | 何をするか — 要求・振る舞い・状態 | タスク仕様 · KB specification |
| Design | どう見えるか | `design_ref` (下記) |
| Impl | コード | リポジトリ |

**design_ref** (`core/docs/ja/methodology/task-spec-schema.md` → `inputs.design_ref`)

| kind | 意味 |
|---|---|
| `figma` | デザインツールのファイル・ノードへの参照 |
| `storybook` | ストーリーがデザイン成果物 (デザインツールがない場合の正本) |
| `claude_design` | 下書きキャンバス。`spec_first` 入口の成果物で、確定時に `storybook` または `figma` へ昇格 |
| `none` | デザイン成果物がないことを**明示** — `reason` 必須 (例: 内部ツール、テキストのみ) |

**整合 (aligned) の定義**: コンポーネントのコントラクト — 名前、variant 軸とその値、使用する alias、状態軸 — が Design と Impl で同一である。
ツールはこの定義の上で比較する(プロパティ名の照合、ストーリーのレンダリングとフレームの照合)。人間によるレビューも同じ定義を使う。

**整合状態** (`completion.design_sync`)

```text
aligned   Design ↔ Impl コントラクト一致
stale     片方が変わり再検査が必要 — この状態で完了宣言は不可
waived    意図的な不一致。reason + until(期限日) 必須
none      design_ref.kind: none の作業
```

**入口** (`_order.entry_point`)

```text
design_first   Design → (Design↔Spec) → Impl → (Impl↔Design)
dev_first      Impl → (Impl↔Spec) → Design(retrofit) → (Impl↔Design)
spec_first     Spec → Design·Impl 並行 → 二つの整合検査
change         どの成果物でも変更 → 残りは stale → 整合が回復するまで未完了   (既定値)
```

レビューは独立した段階ではなく、**すべての成果物の遷移が引き起こすもの**である。順序は固定しない。
検証の独立性は `core/docs/ja/methodology/verification-tier.md` の `design_verified` 軸が定義する。

## デザインツールの正本範囲

デザインツール(例: Figma)に置くものは狭く定める。

| 正本の候補 | 参照(正本ではない) | 置かないもの |
|---|---|---|
| T1·T2 トークン変数(モード含む) | Feature レベルの画面フレーム | コンポジションロジック · データフロー · フック境界 |
| Primitive UI コンポーネントと variant プロパティ | | i18n 文言 (キーはコード、ツールにはキーの注釈) |
| Semantic Component の状態軸 (loading · empty · error) | | ルーティング · 権限境界 · レイアウトの原値 |

**トークンの正本はコードリポジトリのトークンファイル**(推奨)。理由: エージェントと CI が安定して読め、コンテキスト予算(`core/docs/ja/methodology/context-protocol.md` CB-1)に合う alias カタログを生成でき、デザインツールへのアクセス可否に依存しない。
デザインツール → コード方向の同期は許可するが、衝突は決定レコードで解決する。逆の選択(ツールを正本とする)は、プロジェクトの profile における決定として可能である。

**トークンの解決地点は一つ** — Foundation のビルド段階(トークンファイル → CSS 変数 · TS 定数 · ツール変数)。コンポーネントは alias の名前を参照し、コンポーネントトークンはそれを所有するコンポーネントだけが参照する。

## デザインツールがないとき

ルールは一つ — **Primitive UI と Semantic Component はストーリーを持つ。** デザインツールがなければストーリーが `design_ref` であり、ツールができればストーリー↔ツールの整合検査につながる。
下書きツール(Claude Design など)の成果物は、確定までの間だけ `design_ref` となり、確定時に昇格する。

## 例外ポリシー

デザイナーが持ち込んだ一回限りの値が alias で表現できないとき:

1. **昇格** — 新しい alias を決定レコードとともに追加する。トークンファイルを変更する PR は DEC id を参照する。
2. **例外タグ** — `@strata:token-exception {reason} until {YYYY-MM-DD}`。期限が過ぎると検査は失敗する。文法は `core/docs/ja/conventions/strata-markers.md`。
3. **計測** — Foundation の外の raw 値の数を、デザインプロパティごとに数えて diff 基準で 0 に保つ (`profiles/frontend.next-web/enforcement/`)。

実行時に計算・測定される値(仮想スクロールのオフセット、測定した基準幅、データ列の幅などの連続的な寸法)は、一回限りのデザイン値ではない。それぞれ `@strata:computed <reason>` を付けた例外としてコードに残り、raw 値としては数えない。一回限りのデザイン値には期限のある `@strata:token-exception` を使う。

## Core / Convention / Profile の分離

| 性格 | 場所 | 例 |
|---|---|---|
| 検証可能なコントラクト | この文書 · `core/rules/layer-rules.yaml` · `core/rules/naming-convention.yaml` | コンポーネントは alias を参照(コンポーネントトークンは所有者からのみ)、整合の定義、入口の enum |
| ツールバインディング | `profiles/frontend.next-web/docs/ja/frontend-tokens.md` · `profiles/frontend.next-web/docs/ja/frontend-styling.md` | トークンファイル形式、ジェネレーター、ユーティリティ CSS クラスのマッピング、ストーリーツール |
| プロジェクトポリシー | プロジェクト Tier P (`layer-map.yaml` · decisions) | トークンファイルのパス、intent の拡張軸、正本の方向、zone ごとの執行強度 |
