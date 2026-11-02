# フロントエンド Atomic Variant レイヤーアーキテクチャ

> 正本: strata-kit `core/docs/ja/architecture/frontend-atomic.md` — strata `docs/03-architecture/frontend-atomic.md` から移管 (オーダー 2026.10.29-06, 2026-10-29)。ルール YAML は `core/rules/`。

> 機械可読ルール: `core/rules/layer-rules.yaml` → `frontend.variants.atomic`
> 新規 Web プロジェクトの既定 variant は `frontend.variants.web` であり、詳細は `core/docs/ja/architecture/frontend-web.md` を参照する。
> **状態: 維持(レガシー互換)** — 新規採用は非推奨。Molecule/Organism の大きさによる分類は、web variant の Composition Legality (`core/docs/ja/architecture/frontend-design-contract.md`) に置き換えられた。

## web variant へのマッピング

| Atomic | web variant | 判定基準 |
|---|---|---|
| Atom | Primitive UI | ドメイン非依存、alias トークン + variant 軸のみ |
| Molecule | Semantic Component **または** Feature Block | DataState を呼ぶなら Feature Block、そうでなければ Semantic Component。**大きさでは判定しない** |
| Organism | (廃止) | Feature Block に吸収 |
| Partial | Feature Block (`{UseCase}Section`) | ルートを持たない画面の断片 |
| Page · Layout | Route Surface · App Shell | そのまま |
| L2 Hook | DataState adapter | `useQuery{Name}` → `use{Entity}Query` |
| LM | Contract + DataState transport | ViewModel・DTO は Contract、API Client は `{name}.service` |

## レイヤー構造

```
Page / Layout
    ↓
Partial (ページ水準の共通 UI の集合)
    ↓
Molecule (振る舞い特化コンポーネント)
    ↓
Atomic (純粋な UI コンポーネント)
    ↓
L2 (状態管理 Hook)
    ↓
LM (ViewModel, DTO, API Client)
    ↓
L1 (純粋関数, 型, 定数)
```

## L1 — 純粋関数層

バックエンドの L1 と同じ原則。UI フレームワークに依存しない純粋なロジック。
純粋な状態管理 Hook は許可するが、API 呼び出しは禁止する。

**例:** useDebounce, useLocalStorage, formatDate, validateEmail

## LM — データモデル層

サーバーとの通信を担う中間層。

**構成:** ViewModel (表示専用のデータ構造), DTO (サーバーのリクエスト/レスポンスのマッピング), 
API Port/Client Interface (transport 呼び出しの境界), Interface (コントラクト定義)

**ルール:** UI レンダリングロジック禁止。データ変換と通信だけを担う。

## L2 — 状態管理層

サーバー/クライアント状態の adapter Hook。

**ルール:** LM の API Client を使ってサーバー状態を同期する。
UI コンポーネントを直接レンダリングしない。Hook のみを export する。

## Atomic — 最小単位の UI

L2 以下のすべての依存を取り除いた純粋な UI コンポーネント。
Props だけで動作し、グローバル状態へのアクセスは禁止。

**例:** Button, Input, Badge, Avatar, Tooltip, Card

## Molecule — 振る舞い特化 UI

Atomic を組み合わせ、L2 Hook をバインドしたコンポーネント。
特定のドメイン上の振る舞いに特化している。

**例:** SearchBar (Input + Button + useSearchStore),
OrderCard (Card + Badge + useOrderQuery)

## Partial — ページ水準の共通集合

複数のページで共有される UI ブロック。
Molecule と Atomic の組み合わせ。

**例:** OrderListPartial, UserProfilePartial, NotificationPanel

## Page — ルート対象

実際の URL に対応する最上位コンポーネント。
Layout、Partial、Molecule、Atomic を組み合わせて完全な画面を構成する。

## Layout — 構造的ラッパー

ナビゲーション、サイドバー、フッターなどページの構造を定義する。
Page コンポーネントを children として受け取る。
