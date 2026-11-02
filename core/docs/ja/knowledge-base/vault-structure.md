# Knowledge Base — Vault 構造

> 正本: strata-kit `core/docs/ja/knowledge-base/vault-structure.md`（2026-10-29 strata `docs/07-knowledge-base/vault-structure.md` から移行、DEC-2026-10-29-11）。

## 概要

Vault はすべてのプロジェクトが共有する Obsidian 互換のナレッジベースです。
独立した Git リポジトリとして管理され、プロジェクトのコードとは分離されています。

## 3 層モデル（Archive / Knowledge / Index）

vault のあらゆるコンテンツは 3 つの層のいずれかに属し、層ごとに維持の規律が異なります（DEC-2026-08-19-04）。

| 層 | ディレクトリ | 規律 |
|---|---|---|
| **Archive** | `projects/*/sessions/`, `projects/*/tasks/`, `projects/*/relays/` | append-only。write-once が**正常**であり、改訂やリンクの義務はない。KB ではなく証拠の保管庫 |
| **Planning**（Archive の変種） | `projects/*/planning/{source}/` | 外部の企画ツール（Notion など）から取り込んだ企画原文（`type: planning`）。**原文の節は不変**（Archive の規律）で、文書末尾の `## 구현 검토`（実装レビュー）節だけを更新する。方針項目ごとの実装有無・企画との差異・根拠を表に記録し、frontmatter の `implementation.status` で分類する。実体のある方針は Knowledge の仕様に蒸留し、その仕様の `sources:` が原文を指す（DEC-2026-09-09-01） |
| **Knowledge** | `projects/*/knowledge-base/`, `patterns/`, `_index/glossary.md` | **update-in-place の義務** — 更新時に `updated:` が必須、根拠となる Archive 文書への出典リンク（`sources:` frontmatter）が必須 |
| **Index** | `_index/`, 各 `_index.md`, `projects/*/decisions/` の DEC ノート, `projects/*/nodes/` のノードページ | **生成専用 — 手編集禁止。** 正本（レコード・frontmatter・toc.yaml）から再生成する（DEC projection generator、ノードページ生成器 — 実装の対応: `python3 -m kb --help` · `core/docs/ja/kb-engine.md`） |

知識の昇格（Archive → Knowledge）は蒸留セッションが行い、Decision Inbox のゲートを通る。
新規文書の作成より既存 Knowledge 文書の更新を優先する（リビングドキュメントの原則）。

### 3 種類の文書の役割と置き場所（DEC-2026-09-30-03）

| 文書 | 何を載せるか | どこに置くか | 既定の検索 |
|---|---|---|---|
| 仕様（決定） | コード・実装要件について実装時点で下した決定とその理由、対象のコードシンボル、現行か置き換え済みか | decision レコード（Tier P）→ DEC ノートのミラー | 索引化前 — インデックス（`decisions.yaml`）と DEC ノートを直接読む（索引への組み込みは後続） |
| KB（Knowledge） | サービスとドメインを、人が理解できる目次と流れで説明した最終の形 | `knowledge-base/`、目次は `_meta/toc.yaml` | 含む |
| 作業履歴（Archive・Planning） | セッション記録、タスク仕様、日付の付いた診断・報告、外部企画の原文 | `sessions/`, `tasks/`, `relays/`, `planning/` | 除外（明示的に要求したときのみ） |

- **目次の 1 か所に KB 文書は 1 つ。** 同じ主題の新しい文書を作らず、既存の文書を書き直す。やむを得ず新しい文書で置き換える場合は、古い文書を `status: superseded` + `superseded_by` で閉じる。
- **日付の付いた報告書・診断・スナップショットは KB ではない。** ファイル名やタイトルに日付が入る文書（`*-2026-09-16.md` など）はその日の事実を記録したものなので、作業履歴（`tasks/{date}/` または `sessions/`）に置く。KB にはその結果として変わった最終の形だけを反映し、`sources:` で報告書を指す。
- **既定の検索は KB だけを見る。** 作業履歴は、検索ツールに明示的に要求したときだけ含める（`search_docs(include_history=true)` または `category` の指定、CLI の `--include-history`）。履歴が正本を検索結果から押し出さないようにするためである。

3 つの層を横断する鍵が**主題ノード**です。ノードは人が読む目次の単位で、正本はプロジェクトの `_meta/toc.yaml` です。
文書は frontmatter の `nodes:` で所属を宣言し、ノードページはそのノードを指す Knowledge（最終の形・方針）、決定、Archive（作業履歴）を**結合**して生成します。
ノードページは昇格ではありません。何も新しく書かず、すでにあるものを 1 画面に集めるだけで、穴があれば穴が見えるままにします。その穴が欠落の可視化です。

## ディレクトリ構造

```
vault/
├── .obsidian/           Obsidian アプリ設定（共有、git 追跡）
│   └── plugins/         Custom Sort、Dataview などのプラグイン設定
├── .kb/                 ★ KB 索引の管理
│   ├── manifest.json    ファイルごとの SHA256 ハッシュ（git 追跡）
│   ├── schema.sql       DB スキーマ定義（git 追跡）
│   └── store.sqlite     KB store（strata-kit kb、.gitignore — legacy の kb.sqlite は DEC-2026-10-28-13 で削除）
├── .local/              マシンごとの設定（.gitignore）
│   └── resolved-paths.yaml
├── .gitignore
├── env-config.yaml      登録済みマシン alias の一覧（パスなし）
│
├── _index/              MOC (Map of Content)
│   ├── projects.md      プロジェクト一覧 + リンク
│   ├── decisions.md     プロジェクト横断の ADR インデックス
│   ├── patterns.md      パターン/レッスンのインデックス
│   └── glossary.md      ドメイン用語辞書
│
├── _meta/               ★ グローバル設定
│   └── taxonomy.yaml    分類体系の定義（カテゴリ、タイプ、タグ）
│
├── projects/            プロジェクトごとの知識
│   └── {project-name}/
│       ├── overview.md          技術スタック、目的、現在の状態
│       ├── _meta/               プロジェクト設定
│       │   ├── taxonomy.yaml    プロジェクト拡張 taxonomy（グローバルを継承）— ディレクトリ軸
│       │   └── toc.yaml         ★ 主題ノードツリー（人が読む目次の正本）— 主題軸
│       ├── knowledge-base/      ★ プロジェクト KB（索引対象）
│       │   ├── _index.md        MOC（Dataview による動的目次）
│       │   ├── domain/          ドメイン知識（カテゴリ 1）
│       │   │   ├── _index.md    カテゴリ MOC
│       │   │   ├── epics/       エピックごとのドメイン知識
│       │   │   └── {topic}/     トピックディレクトリ（プロジェクト taxonomy で定義）
│       │   │       ├── _index.md
│       │   │       └── *.md     KB 文書
│       │   ├── architecture/    技術アーキテクチャ（カテゴリ 2）
│       │   │   ├── _index.md
│       │   │   ├── decisions/   ADR
│       │   │   ├── constraints/ Constraint Card
│       │   │   ├── api-contracts/
│       │   │   ├── data-models/
│       │   │   ├── infrastructure/
│       │   │   └── *.md
│       │   ├── guides/          ガイド（カテゴリ 3）
│       │   │   ├── _index.md
│       │   │   ├── onboarding/
│       │   │   ├── conventions/
│       │   │   ├── troubleshooting/
│       │   │   └── *.md
│       │   └── references/      リファレンス（カテゴリ 4）
│       │       ├── _index.md
│       │       └── *.md
│       ├── tasks/               ★ タスク仕様（Builder→Worker）
│       │   └── {yyyy.mm.dd}/    日付ごとのグループ
│       │       └── {nn}-{title}/  Work Order フォルダ
│       │           ├── _order.yaml    作業指示書
│       │           └── task-{nn}-*.yaml  Worker 実行仕様
│       ├── strata/              ★ detached profile の Tier P 正本（core/docs/ja/environment/data-placement.md §1.5）
│       │   ├── profile.yaml     placement profile manifest（新しい PC の bootstrap アンカー）
│       │   ├── decisions/       decision レコード（DEC-*.yaml、1 決定 = 1 ファイル）
│       │   ├── decisions.yaml   生成型インデックス（手編集禁止）
│       │   ├── constraint-registry.yaml
│       │   └── layer-map.yaml
│       ├── decisions/           DEC ノート — 生成専用（DEC projection generator、手編集禁止）
│       │   └── DEC-YYYY-MM-DD-NN.md
│       ├── nodes/               ノードページ — 生成専用（ノードページ生成器、手編集禁止）
│       │   └── {node-id}.md     例) orders.checkout-v2.coupon.md
│       ├── planning/            ★ 企画文書（type planning）— 企画文書インポーターが生成、原文不変 + 実装レビュー節
│       │   └── {source-name}/   原典ごと（例: notion-orders-intake）。ファイル名 {元タイトル-slug}--{原典 id の先頭 8 文字}.md — 元タイトルの言語を維持
│       └── sessions/            セッションのハンドオフ・ledger（Archive）
│           └── session-YYYY-MM-DD-{slug}.md
│
├── patterns/            プロジェクト横断のパターン
│   └── {pattern-name}.md
│
├── strata-feedback/     方法論フィードバックの記録
│   └── {topic}.md       適用/未適用のフィードバック
│
├── references/          外部参照、API 要約
│   └── {reference-name}.md
└── assets/              バイナリ資産（画像・Excel など — vault ルートへの配置禁止）
```

## 命名規則

| 対象 | 形式 | 例 |
|---|---|---|
| プロジェクトディレクトリ | kebab-case | `my-api-server` |
| 文書ファイル名 | kebab-case.md | `auth-strategy.md` |
| DEC ノート（生成） | DEC-YYYY-MM-DD-NN.md | `DEC-2026-08-19-01.md` |
| ノードページ（生成） | {node-id}.md — ノード id そのまま、ドット(.)を含む | `orders.checkout-v2.coupon.md` |
| セッション文書 | session-YYYY-MM-DD-{slug}.md | `session-2026-08-19-vault-restructure.md` |
| MOC ファイル | 単数形の名詞 | `projects.md`, `glossary.md` |

セッションのファイル名は上の単一の規格だけを使う — `handoff-*` 接頭辞、接頭辞なしの日付ファイル名、`.yaml` のセッションファイルは廃止（legacy は移行の対象）。連番（NN）ではなく slug が実際の識別子である。

## 安定 ID（frontmatter `id:`）

すべての vault 文書は、移動・改名に対して不変の安定 ID を frontmatter に持ちます。

```yaml
id: "kb-shop-api-order-concepts"   # {接頭辞}-{project}-{slug} — 生成後は不変
aliases: ["旧ファイル名"]               # 移動・改名時に元の識別子を保持（Obsidian の unlinked mentions を吸収）
```

接頭辞は文書クラスのすべてを網羅します（2026-08-19 の cross-review を反映）。

| 接頭辞 | 対象 | 例 |
|---|---|---|
| `kb` | knowledge-base/, patterns/ の文書 | `kb-shop-api-order-concepts` |
| `session` | sessions/（ハンドオフ・ledger） | `session-strata-2026-08-19-vault-restructure` |
| `order` | 作業指示書 `_order.md` | `order-strata-2026.08.19-01` |
| `task` | タスク仕様文書 | `task-strata-2026.08.19-01-task-03` |
| `dec` | DEC ノート（生成） | `dec-strata-2026-08-19-01` |
| `relay` | relays/ の packet・feedback | `relay-strata-2026-08-19-task01-core-spec-review` |
| `moc` | `_index/` および各 `_index.md` の MOC | `moc-shop-api-knowledge-base` |
| `node` | `nodes/` のノードページ（生成） | `node-shop-api-orders.checkout-v2.coupon` |
| `plan` | `planning/` の企画文書（インポート） | `plan-shop-api-0123456789abcdef0123456789abcdef` — slug は原典（Notion）の id で、再インポートでも不変 |
| `doc` | 上のどれにも属さないその他の文書 | `doc-vault-env-config` |

- **{project} の値**: `projects/{name}/` 配下ではそのプロジェクト名。**プロジェクト横断の文書**（`patterns/`, `references/`, `_index/`, vault ルート）は `vault` を使う（例: `kb-vault-{slug}`, `moc-vault-decisions`）。
- パスは探索の手段にすぎず、長期的な同一性ではない。リンクや参照の同一性は `id:` が担う。
- 移行（移動・改名）時は `id:` を維持し、古いファイル名を `aliases:` に追加する。
- **ノード id は文書 id とは別の名前空間である。** `orders.checkout-v2.coupon` のように祖先からドット(.)でつないだパスであり、上の接頭辞体系には従わない。文書は `nodes:` フィールドにノード id を書き、ノードページの**文書** id だけが `node-{project}-{node-id}` として接頭辞体系に組み込まれる。slug にドットが許されるのは `node` 接頭辞のときだけである。

## KB カテゴリ体系

taxonomy.yaml で定義し、4 つのカテゴリで構成します。

| カテゴリ | 目的 | depth 制限 | 主なタイプ |
|----------|------|:---:|-----------|
| `domain` | ビジネスドメインの知識 | 3 | concept, specification, flow |
| `architecture` | 設計判断、API、インフラ、制約 | 2 | specification, decision, overview, constraint |
| `guides` | オンボーディング、規約、トラブルシューティング | 2 | guide, pattern, runbook |
| `references` | 外部標準、規格の参照 | 2 | reference, glossary |

- NN 接頭辞なし — 並び順は taxonomy の `order` フィールドによる
- カテゴリはディレクトリから導く（frontmatter には記録しない）
- `domain` カテゴリの children はプロジェクト taxonomy で定義する
- 詳細な規則: `templates/vault/_meta/taxonomy.yaml`

カテゴリは**ディレクトリ軸**（文書がどこに置かれるか）であり、主題ノードは**主題軸**（文書が何についてのものか）です。両者は別物です。
カテゴリを frontmatter に書かないのはパスと重複するからですが、`nodes:` はパスから導けない情報なので重複ではありません。1 つの文書が複数のノードに属してよく、ノードはディレクトリを作りません。
ノードツリーの正本と規則: プロジェクトの `_meta/toc.yaml`、形式の規則はグローバル taxonomy の `topic_nodes` 節。

## プロジェクトのオンボーディング手順

新しいプロジェクトを vault に登録するとき:

1. `vault/projects/{project-name}/` ディレクトリを作成する
2. `overview.md` を作成する（必須 frontmatter を含む。document-format.md を参照）
3. `_index/projects.md` を更新する（Index 層 — 生成型に移行した後は再生成に置き換わる）
4. `_meta/taxonomy.yaml` を作成する（プロジェクトのドメイントピックを定義）
5. `_meta/toc.yaml` を作成する（主題ノードツリー — 最初のノード 1 つで十分。文書が `nodes:` を持ち始める時点が出発点）
6. `knowledge-base/` 配下にカテゴリのディレクトリを作成する（`domain/`, `architecture/`, `guides/`, `references/`）
7. `sessions/`, `tasks/` ディレクトリを作成する。detached profile のプロジェクトなら `strata/`（Tier P）も含める — `profile.yaml` manifest が必須（core/docs/ja/environment/data-placement.md §1.5）。`decisions/` と `nodes/` は生成器が作る

### overview.md の最小内容

```markdown
---
title: "{プロジェクト名}"
type: overview
project: {project-name}
tags: [{技術スタックのタグ}]
created: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
status: active
---

## 目的
{プロジェクトの目的を 1〜2 文で}

## 技術スタック
- 言語: {language}
- フレームワーク: {framework}
- DB: {database}

## Strata レイヤーの対応
{このプロジェクトのディレクトリ → Strata レイヤーのマッピング}
```

## 決して含めないもの

- ソースコード（コードスニペットは例外的に許可）
- ビルド成果物
- 環境ごとの絶対パス
- シークレット、キー、トークン
- 生のハンドオフ YAML（要約のみ保存）

例外: frontmatter `covers:` のリポジトリ**相対パス・シンボル・エンドポイント・テーブル名**はコードではなくポインターなので許可します。絶対パスとコード本文は引き続き禁止です。
