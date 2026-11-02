# Knowledge Base — インデックスプロトコル

> 正本: strata-kit `core/docs/ja/knowledge-base/indexing-protocol.md`（2026-10-29 strata `docs/07-knowledge-base/indexing-protocol.md` から移行、DEC-2026-10-29-11）。

> **2026-10-29 現行化**: この文書は現行エンジン（`store.sqlite` 1 つ、`python3 "$STRATA_KIT/kb"`）を記述する。
> 以前の `.kb/kb.sqlite`・manifest ハッシュによる増分ビルド・sqlite-vec の設計は廃止された（DEC-2026-10-28-13）。
> ストレージスキーマ・バックエンド・ゲート（gate）の正本は `core/docs/ja/kb-engine.md` であり、この文書はインデックスの範囲・検索の使い方・生成ビューを扱う。

## 概要

vault の KB 文書をチャンク単位で `store.sqlite` にインデックス化し、エージェントのトークン消費を減らして精密な検索を可能にします。
インデックスは、原本（vault 文書・決定レコード（decision record）・コード表面）からいつでも作り直せるキャッシュであり、各環境がローカルで作ります。

## 問題の定義

| 問題 | 説明 |
|---|---|
| 全体走査の強制 | エージェントは _index.md → 該当ファイル全体を読まないと目的の section に到達できない |
| トークンの横断消費 | 17 ファイル（68K chars）を探索してコンテキストウィンドウを浪費する |
| 順序の欠如 | ページ間に論理的な順序がなく、エージェントがナビゲーションを判断する必要がある |
| 意味検索が不可 | キーワードが一致しないと関連文書を見つけられない（埋め込み検索で補う） |

## 段階の区分

| 段階 | 内容 | 状態 |
|---|---|---|
| **FTS** | チャンク単位の FTS5（bm25）+ frontmatter `page_order` による並び替え | 適用済み — 検索に入るとき鮮度を自動確認 |
| **ベクトル・ハイブリッド** | ローカルの BAAI/bge-m3 埋め込み + FTS との RRF 融合 | 実装済み — ベクトルは `python3 "$STRATA_KIT/kb" embed` を実行して初めて作られる（DEC-2026-10-28-09）。MCP `search_docs` の既定 mode は hybrid、`kb search` CLI の既定は FTS（`--semantic`・`--hybrid` で切り替え） |

以前の「Phase 1（FTS5 + manifest ハッシュ）/ Phase 2（sqlite-vec・`--with-vectors`、実装済み・未適用）」という区分は廃止された。インデックスは 2 つに分かれず store 1 つであり、ベクトルは store のチャンクに付く。

## アーキテクチャ

### ファイル配置

```
vault/
├── .kb/
│   ├── store.sqlite            # .gitignore — 唯一のインデックス（ローカルビルドの成果物）
│   ├── manifest.json           # 追跡しない — インデックスのメタ情報、マシンごとに作る (DEC-2026-10-29-04)
│   ├── link-baseline.json      # リンクゲートの基準線（減る方向にのみ更新）
│   └── review-candidates.json  # .gitignore — レビュー候補（生成物）
│
├── .gitignore
└── projects/{name}/knowledge-base/
    └── *.md                    # インデックスの原本
```

`.kb/store.sqlite` とその `-wal`・`-shm` は vault の `.gitignore` に入っている。確認: `.gitignore` の「KB store」節。
スキーマはファイルではなくコード（`kb/store.py`）が定義する。`schema.sql` はない（DEC-2026-10-28-13）。

### ビルドエンジンの配置

```
strata-kit/
└── kb/                         # git 追跡 — インデックスエンジン (python3 "$STRATA_KIT/kb" build-index)
```

ビルドエンジンは strata-kit リポジトリにあります。実行時には `$STRATA_VAULT` 環境変数で vault のパスを参照します。

### データフロー

```
MD ファイルを編集 → git commit + push
                    ↓
別の環境: git pull
                    ↓
検索に入るとき(kb search / MCP)自動で:           engine.ensure_fresh_store
  原本の mtime と store の built_at を比較 (ハッシュなし、低コスト)
    ├─ 新鮮 → そのまま照会
    ├─ stale → store 全体を再生成 (1〜2 秒)
    └─ store がない(新しいマシン) → 同じ経路で自動生成
                    ↓
store.sqlite (nodes · edges · chunks + FTS5 · 埋め込みキャッシュ)
                    ↓
エージェント: kb search / MCP search_docs → chunk + file:line を返す
```

- 増分の再インデックスはない。store は毎回全体を作り直す（1〜2 秒）。変更分だけを選ぶ manifest ハッシュ比較は廃止された。
- 手動実行（`python3 "$STRATA_KIT/kb" build-index`）と MCP `build_index` は可能だが、**日常の経路は自動**である。
- 鮮度確認・再生成の失敗は照会を止めない（警告を出して既存の store を使う）。抜け道: `KB_NO_REFRESH=1`。
- `build-index` は store を再生成した後、生成ビュー（ノードページ・Obsidian sortspec・レビュー Inbox・`manifest.json`）と taxonomy 検証の警告を出します。block 違反なら exit 2。動作と役割は `core/docs/ja/kb-engine.md`。
- 埋め込みは `build-index` では計算しない。`python3 "$STRATA_KIT/kb" embed` が欠けているチャンクだけを計算して store に入れ、計算したベクトルは `embeddings` キャッシュに残るので、store を作り直しても再利用される。

### インデックスのカバレッジ (2026.08.19-06 B1)

- **Knowledge**: `projects/*/knowledge-base/` — 全文インデックス（従来どおり）。2026-09-08 から `patterns/`・`_index/glossary.md`（プロジェクト値 `vault`）・`projects/*/overview.md` も全文インデックス — vault-structure.md の 3 層の表にある Knowledge の範囲と一致。
- **Archive**: `projects/*/sessions/`・`tasks/` の `.md` — **メタ（topic・orders・kb_updates・decisions_made・nodes・doc_change）+
  本文の要約部（先頭 40 行）だけ**をインデックスする。`nodes` が欠けるとノードページの「作業履歴」面を作れないのでホワイトリストに含める。category=`archive`、topic=`sessions|tasks` のファセットで区別・フィルタする
  （MCP の `category` フィルタ）。「どのセッションで扱ったか」を検索で答えるためである。**検索の既定では Archive・Planning を除外する**（DEC-2026-09-30-03） —
  履歴まで見るには `kb search --include-history`、MCP `search_docs(include_history=true)`、または `category` を明示する。`--include-history` は決定・オーダーのレコードも一緒に検索する。
- Archive には KB 検証（lifecycle など）を適用しない — ledger の status（open/closed）は KB 契約の外にある。
  **例外**: `node_id_check`（nodes の値が toc.yaml にあるか）は Archive にも適用する。ノードの誤記は、作業履歴面からセッションを消してしまうからである。
- **Planning**: `projects/*/planning/{source}/` — 企画原文の**全文インデックス** + KB 検証（required_fields・lifecycle_override・node_id）。category=`planning`、topic=`{source}` のファセット。ノードページの「企画」面の原本。status が企画の状態（active ではない）なので、レビュー候補のポリシーの外にある (DEC-2026-09-09-01)。
- **ノードページ**（`projects/*/nodes/`）は `indexed: metadata` — 各面の原文がすでにインデックスされているので、要約部だけ。
- **DEC ノート**（`projects/*/decisions/`）は文書としてはインデックスしない（現行維持）。決定は決定レコードの provider が store の決定ノードとして入れ、決定のノード所属は、レコード正本の `nodes` をノードページ生成器が読む。
- シンボリックリンク（`latest.md`）と yaml はインデックスしない。

## KB Result Contract — 廃止 (DEC-2026-08-19-06)

共通の結果スキーマ契約は**廃止された**。制定後、どの消費者（kb-search、strata-mcp）も実装せず、
それぞれの結果形式で安定して動作しており、契約の前提だった複数の消費者（strata-kb-server、Hub）は存在しない。

- **復活の条件**: 2 つ目の消費面（Hub など）が実際に現れたら、その時点で実際に使われているフィールドから契約を設計し直す。
- ノードページ生成器は vault 内部の生成物なので「2 つ目の消費面」ではない。この廃止決定は覆さない。
- 廃止前の契約の全文は git 履歴（このファイル、2026-08-19 より前）を参照。

## ストレージスキーマ

スキーマ（`nodes`・`edges`・`chunks`・`baselines`・`revisions`、FTS5 仮想テーブル `chunks_fts`、`embeddings` キャッシュ）の正本は `core/docs/ja/kb-engine.md` の「スキーマ」節である。ここでは検索に必要なものだけを書く。

- 検索の単位は `chunks` である。チャンクは heading・text・title・tags と `meta_json`（heading_level・line_start・line_end・char_count）を持つ。文書・決定・オーダーが FTS テーブル 1 つ、bm25 の尺度 1 つを使う。
- FTS5 は heading・text・title・tags の 4 列を `unicode61` でインデックスする。
- 文書の taxonomy ファセット（category・topic・section_name・page_order など）は文書ノードの payload にあり、`kb search` のフィルタと `--toc` の並び替えが読む。
- リンクは `links` エッジ、文書間の関係（supersedes など）と `covers` もエッジである。以前の `document_links` テーブルはない。

以前のスキーマ（`documents`・`chunks`・`chunks_fts`（doc_title・doc_tags 列）・`document_links`・`coverage` テーブル、`sha256`・`section_name` カラム、`chunks_vec`）は legacy インデックス（`.kb/kb.sqlite`）のものであり、DEC-2026-10-28-13 で廃止された。SQL で直接照会する方法も一緒になくなった。照会は `kb search`・MCP・`kb coverage` で行う。

### 主題ノード・カバレッジ

文書の `stable_id`・`nodes`・`covers`・`doc_change` frontmatter は、store のノード payload と `covers` エッジになります。コード表面 → 文書の逆照会の規則は変わらない。

- 「このパスを所有する仕様は何か」: `python3 "$STRATA_KIT/kb" coverage resolve|nodes|unowned|docs-to-update`
- 「このノードの最終形はどの文書か」: `kb coverage node`（ノードページ生成器が使う）
- 「このパスが変わった後、所有する文書は更新されたか」: セッション終了ゲート `kb coverage-gate`
- ノードツリー自体は `_meta/toc.yaml` を直接読む。`endpoints`・`tables` はファイルパスとして解釈せず、ノードページの表示用である。

ビルド時の検証（すべて warn）: `node_id_check`（形式、toc.yaml の存在・登録 — Archive にも適用）、`covers_path_check`（構造・相対パス・ファイル単位の禁止）、
`supersedes_symmetry_check`（A.supersedes=B ⇔ B.status=superseded ∧ B.superseded_by=A）、doc_change の値・理由。レビュー候補は生成物（レビュー Inbox）として記録され、遷移は明示的なコマンド（`build-index --apply-review`）で行う。

## 変更検知と複数環境の同期

変更検知は manifest ハッシュではなく、原本ファイルの mtime と store の `built_at` の比較である（`engine.ensure_fresh_store`）。そのため環境間で合意すべきインデックス状態はない。共有するのは vault 文書と決定レコードだけで、store は環境ごとにローカルで作る。

```
[環境 A — 文書を編集]
1. MD ファイルを編集
2. git commit + push   (セッション終了時に handoff が vault を同期)

[環境 B — 同期]
1. git pull
2. 検索に入るとき store が自動で再生成される — 手動では python3 "$STRATA_KIT/kb" build-index
```

**核心原理:** store はキャッシュなので git に上げない（`.gitignore`）。バイナリの衝突がなく、どのマシンでも同じ原本から同じ結果を作り直せる。

生成物のうち何を追跡し、誰が書くかは DEC-2026-10-29-04 が定める。

| 生成物 | 追跡 | 書き手 |
|---|---|---|
| `.kb/store.sqlite` | しない | 各マシンの検索開始時・`build-index` |
| `.kb/manifest.json` | しない（マシンごとの比較記録） | 各マシンの `build-index` |
| DEC ノート（`projects/*/decisions/`） | する | 決定 CLI — 決定を記録したセッションがレコードと一緒にコミット |
| ノードページ・`_index/review-needed.md` | する | librarian が 1 日 1 回 `kb views-publish`（build-index の後、これらのファイルだけを commit-push）。通常のセッションの `build-index` はローカルのインデックスだけを更新し、これらのファイルをコミットしない |
| `.kb/link-baseline.json` | する | 減る方向にのみ更新 |

以前の「`manifest.json` を git で共有してファイル状態を合意し、変更分だけをインデックスする」方式は legacy 設計であり、廃止された（DEC-2026-10-28-13、DEC-2026-10-29-04）。

## エージェント検索プロトコル

### 検索の優先順位

```
① FTS5 キーワード検索 (正確な用語がわかっているとき)
② FTS5 複合検索 (AND/OR の組み合わせ、--category・--topic フィルタ)
③ メタデータ照会 (--toc 並び替えた目次、--doc 文書内のチャンク)
④ ハイブリッド・セマンティック検索 (自然言語の質問 — ベクトルが必要)
```

エージェントは SQL ではなく `kb search` または MCP `search_docs`（mode: hybrid 既定 · dense · fts）を使う。結果はチャンクの `file:L行-行` の位置と文字数を返す。

### 使用例

**キーワード検索 — 関連 chunk を返す:**
```bash
python3 "$STRATA_KIT/kb" search "환불수수료" --limit 5
```

**複合検索 — AND + フィルタ:**
```bash
python3 "$STRATA_KIT/kb" search "정산식 AND Payment" --category domain
python3 "$STRATA_KIT/kb" search "정산식" --category domain --topic orders
```

**並び替えた目次の照会:**
```bash
python3 "$STRATA_KIT/kb" search --toc --category domain
```

**精密な位置の返却 — Read tool との連携:**
```
kb search "FormulaBaseStructure"
# 結果: domain/orders/payment-shipping.md  位置: L46-101
# → Read tool に offset=46, limit=55 を渡す
```

## FTS5 検索構文リファレンス

`kb search` は質問の各トークンを引用符で囲んで FTS5 に渡す。そのため、次の構文だけが動作する。

| 構文 | 例 | 説明 |
|---|---|---|
| 単一キーワード | `환불수수료` | そのトークンを含む chunk |
| 空白区切り | `Transactional Composite` | 両方のトークンを含む (AND) |
| AND | `Transactional AND Composite` | 両方のトークンを含む |
| OR | `Payment OR Shipping` | 1 つ以上を含む |
| NOT | `환불 NOT Coupon` | 除外条件 |
| prefix | `Refund*` | Refund で始まるトークン |

動作しない構文: 列指定（`doc_tags:orders`・`tags:orders` — 結果なし。代わりに `--category`・`--topic` フィルタを使い、タグだけを見るときは `--tags`）、フレーズ検索（`"REST Docs"` — 引用符が外れて 2 トークンの AND になる）、`NEAR`。以前の文書にある `doc_tags:`・`content:` という列名は legacy インデックスの列である（現行の列は heading・text・title・tags）。

## Frontmatter 拡張 — page_order フィールド

既存の document-format.md の frontmatter に、並び順のフィールドを追加します:

```yaml
---
title: "Order Payment & Shipping"
type: concept        # domain はカテゴリ（ディレクトリ）であり、文書タイプではない
project: shop-api
tags: [orders, payment, shipping]
created: 2026-04-07
updated: 2026-04-07
page_order: 3              # ★ 新規 — セクション内の文書の順序
---
```

`--toc` は taxonomy の category・topic の順を先に、その中で `page_order` により並び替える（taxonomy 以前の NN-prefix ディレクトリの文書は `section_order` を使う）。
`page_order` は frontmatter に明示して、セクション内の論理的な順序を定義します。

## トークン削減効果（実測）

以下は legacy の FTS5 インデックス時代（2026-04）のあるバックエンドプロジェクトの vault での実測である（15 文書、210 chunks、68K chars）。チャンク単位で読むという原理は現行の store も同じだが、数値を現行エンジンで測り直したことはない。

| 検索クエリ | 従来（全体を読む） | FTS5（chunk） | 削減率 |
|-----------|-----------------|-------------|--------|
| "환불수수료" | 68,242 chars | 3,473 chars | **95%** |
| "TransactionalExecutor" | 68,242 chars | 1,181 chars | **99%** |
| "정산식 AND Payment" | 13,939 chars (3 ファイル) | 6,758 chars | **52%** |

## ベクトル検索 (bge-m3 ハイブリッド)

正本: `core/docs/ja/kb-engine.md` の検索の節、DEC-2026-10-28-09。

### 要約

| 項目 | 現行 |
|---|---|
| モデル | BAAI/bge-m3、ローカル実行（sentence-transformers、Apple Silicon は MPS）、1024 次元の正規化ベクトル |
| 保存 | store の `chunks.embedding` + 再生成後も残る `embeddings(model, text_hash, dim, vector)` キャッシュ |
| ベクトル検索 | numpy のコサイン総当たり（チャンク約 7 千個の規模で数 ms — ANN は不要） |
| ハイブリッド | FTS（bm25）とベクトルの RRF（k=60）融合 |
| 効果の判断 | `python3 "$STRATA_KIT/kb" search-eval` — vault `_meta/search-eval.yaml` のクエリセットによる recall@k（fts · dense · hybrid） |
| 埋め込みの計算 | `python3 "$STRATA_KIT/kb" embed`（欠けているチャンクだけ。`--model` · `--batch` · `--max-seq` · `--max N`） |

### 代替案と採用しなかった理由

| 代替案 | 判断 |
|---|---|
| sqlite-vec | チャンクが 10 万個を超えたらアダプターで切り替える（DEC-2026-10-28-09）。今は不要 |
| LanceDB などの外部ベクトル DB | ストレージ 1 つの契約（DEC-2026-10-28-04）と食い違い、この規模では利点がない — 導入しない |
| khoj | 別のホスト・UI・DB を持つアプリなので導入しない |
| paraphrase-multilingual-MiniLM-L12-v2 (384 次元) | legacy 設計のモデル。bge-m3 に置き換え |
| ONNX Runtime · クラウド埋め込み API | 採用しない。embedder provider は差し替え可能だが（kb-engine.md）、現在の実装は bge-m3 ローカルのみ |

以前の `build-index --with-vectors`、`apsw`（sqlite-vec のロード用）、`chunks_vec` 仮想テーブルは legacy 設計であり、存在しない。

## 検索ツールのチートシート

### ビルド

```bash
# 日常: 不要 — 検索に入るとき store が stale なら自動で再生成

# store + 生成ビュー(ノードページ・sortspec・レビュー Inbox・manifest)の手動ビルド
python3 "$STRATA_KIT/kb" build-index

# 報告範囲だけを 1 つのプロジェクトに (store は常に全体)
python3 "$STRATA_KIT/kb" build-index --project shop-api

# store だけ再生成 / 統計
python3 "$STRATA_KIT/kb" build-store
python3 "$STRATA_KIT/kb" store-stats

# 欠けているチャンクの埋め込みを計算 (セマンティック・ハイブリッド検索の前に)
python3 "$STRATA_KIT/kb" embed

# レビュー候補を status: review-needed に遷移させて再びビルド
python3 "$STRATA_KIT/kb" build-index --apply-review
```

`--force` は互換用のフラグで効果がない（store は毎回全体を再生成する）。`--with-vectors` はない。

### 検索 (kb search)

> 以下の `kb search` は `python3 "$STRATA_KIT/kb" search` の略称です。

```bash
# ─── FTS5 キーワード検索 ───
kb search "환불수수료"                          # 単一キーワード
kb search "Transactional AND Composite"       # AND 複合
kb search "Payment OR Shipping"                  # OR
kb search "Refund*"                         # prefix
kb search "정산식" --category domain --topic orders   # カテゴリ・トピックのフィルタ (列指定構文の代わり)
kb search "환불수수료" --limit 10 --content      # 結果数 + 内容プレビュー
kb search "jwt" --category architecture       # カテゴリフィルタ (--topic、--status、--project もある)
kb search "환불수수료" --include-history         # セッション・タスク・企画原文と、決定・オーダーまで

# ─── セマンティック・ハイブリッド検索 (kb embed でベクトルを作った後) ───
kb search "환불 금액을 계산하는 흐름?" --semantic
kb search "인증 토큰 만료 시 처리" --hybrid --content

# ─── ナビゲーション ───
kb search --toc                               # 全体の目次 (並び替え済み)
kb search --toc --category domain             # カテゴリフィルタ
kb search --doc "domain/orders/payment-shipping.md"       # 文書内の chunk 目次
kb search --tags orders                          # タグ検索 (質問語なし、タグだけ)
kb search --stats                             # インデックス統計
```

`--section` は taxonomy 以前の NN-section ディレクトリのための互換フィルタである。新しい文書では `--category`・`--topic` を使う。

### FTS5 とセマンティック — いつどちらを使うか

| 状況 | 推奨 | 理由 |
|------|------|------|
| 正確なクラス名/関数名がわかっているとき | FTS5 | `FormulaBaseStructure` → 正確に一致、即時 |
| 特定の用語の検索 | FTS5 | `환불수수료`、`TransactionalExecutor` → BM25 rank |
| 自然言語の質問 | **セマンティック・ハイブリッド** | "환불 금액을 계산하는 흐름?" → キーワード不一致を克服 |
| FTS5 の結果がないとき | **セマンティック** | "인증 토큰 만료 처리" → FTS5 は 0 件、セマンティックは返す |
| カテゴリ/トピックで範囲を絞った後 | FTS5 | `--category domain --topic orders` フィルタ |
| どこから読めばよいかわからないとき | `--toc` | 並び替えた目次 → 文書構造を把握 |

## FTS5 キーワード分割ガイド

FTS5 の `unicode61` トークナイザーは、**空白と句読点だけを基準にトークンを分離**します。
韓国語の形態素解析は行わないので、検索時にはキーワードの分割戦略が重要です。

### 問題: なぜキーワードの分割が必要か

```
文書の原文:  "환불수수료 변경 시 재계산 처리"
              ↓ unicode61 トークン化
トークン:    ["환불수수료", "변경", "시", "재계산", "처리"]
```

| 検索クエリ | 一致 | 理由 |
|-----------|----------|------|
| `환불수수료` | ✅ | トークンが正確に一致 |
| `환불수수료변경` | ❌ | 「환불수수료변경」というトークンは存在しない |
| `환불수수료 AND 변경` | ✅ | 2 つのトークンがそれぞれ存在 |
| `환불` | ❌ | 「환불수수료」の部分文字列は一致しない |
| `환불*` | ✅ | prefix 検索で「환불수수료」に一致 |

### 分割の規則

**1. 韓国語の複合用語は空白で分けて AND 検索する**

```bash
# ❌ 続けて書くと不一致
kb search "환불수수료변경"

# ✅ 分割 + AND
kb search "환불수수료 AND 변경"
```

**2. 部分一致が必要なら prefix(*) を使う**

```bash
# ❌ "환불" だけでは "환불수수료" を見つけられない
kb search "환불"

# ✅ prefix で "환불수수료"、"환불금액"、"환불요청" すべてに一致
kb search "환불*"
```

**3. 英語のクラス名は大文字小文字を区別せず、CamelCase の分離はない**

```bash
# ✅ unicode61 は大文字小文字を正規化する
kb search "formulabasestructure"      # FormulaBaseStructure に一致

# ❌ CamelCase の内部分離はできない
kb search "Formula AND Base"          # 2 つの単語がそれぞれ存在する必要がある

# ✅ prefix で回避
kb search "Formula*"
```

**4. 韓国語 + 英語の混在クエリ**

```bash
# ✅ 各言語のトークンを AND で連結
kb search "Payment AND 정산식"

# ✅ カテゴリ・トピックのフィルタ + 内容検索の組み合わせ
kb search "Payment" --category domain --topic orders
```

**5. キーワード分割でもだめなら → セマンティック・ハイブリッド検索に切り替える**

```bash
# FTS5 では見つけにくい自然言語のクエリ
kb search "인증 토큰이 만료되면 어떻게 처리하나요?" --hybrid
```

韓国語の助詞・合成語のせいで FTS が取りこぼす区間（評価セット基準で 4〜8%）はベクトルが受け持ち、評価の後に FTS5 trigram テーブルか bge-m3 sparse で補強することにした（DEC-2026-10-28-09）。

### エージェント検索の意思決定ツリー

```
質問を受信
  │
  ├─ 正確な用語/クラス名を知っているか?
  │   └─ YES → FTS5: kb search "用語"
  │
  ├─ 韓国語の複合用語か?
  │   └─ YES → FTS5: 空白 + AND で分割
  │            例: "환불수수료 AND 변경 AND 재계산"
  │
  ├─ 部分一致が必要か?
  │   └─ YES → FTS5: prefix(*)
  │            例: "Refund*", "환불*"
  │
  ├─ 自然言語の質問か?
  │   └─ YES → ハイブリッド/セマンティック: kb search "質問" --hybrid
  │
  └─ FTS5 の結果が 0 件か?
      └─ セマンティックで再試行
```

## 主要な設計決定

| 決定 | 根拠 |
|------|------|
| `store.sqlite` 1 つが唯一のインデックスで、git に上げない | バイナリの merge conflict を除去し、インデックス 2 つが生んでいたスキーマ・鮮度ガードの二重化を除去 (DEC-2026-10-28-13) |
| 鮮度は原本 mtime の比較、store は毎回全体を再生成 | 1〜2 秒なので増分は不要。部分ビルドが store を切ると他のプロジェクトのビューを失う (DEC-2026-10-28-13) |
| `manifest.json` は追跡しない | 読む人がいない、マシンごとの比較記録 (DEC-2026-10-29-04) |
| ビルドエンジンは strata-kit リポジトリにある | 方法論自体のツールとして管理し、プロジェクトから独立 |
| frontmatter が single source of truth | Obsidian + FTS5 + Dataview の双方が同じデータを参照 |
| チャンクに heading・title・tags・meta を一緒に置く | FTS 1 テーブル・bm25 1 尺度で文書・決定・オーダーを順位付けし、位置を出力 (DEC-2026-10-28-08) |
| bge-m3 埋め込み + numpy 総当たり + FTS との RRF | 韓英混在に強く、8192 トークンなので長いチャンクを切らない。この規模では ANN は不要 (DEC-2026-10-28-09) |
| ベクトルの効果は評価セットの recall@k で判断 | `kb search-eval` |

廃止された legacy の決定: manifest.json の git 追跡・kb.sqlite の `.gitignore`、SHA256 ハッシュによる増分ビルド、`paraphrase-multilingual-MiniLM-L12-v2`、`apsw`・sqlite-vec、cosine distance 0〜1 の解釈（MiniLM 用）。いずれも DEC-2026-10-28-13 で legacy インデックスと一緒になくなったか、DEC-2026-10-28-09 で置き換えられた。

## 依存関係の要約

| パッケージ | 用途 | 必要なとき |
|--------|------|-----------|
| Python 3 | `kb` の実行 | 常に |
| SQLite 3 (FTS5 を含む) | store | 常に (OS 標準) |
| PyYAML | frontmatter・taxonomy のパース | 常に |
| sentence-transformers (PyTorch を含む、~500MB) | bge-m3 埋め込みの計算 | `kb embed` を使うときだけ |
| numpy | ベクトルのコサイン | セマンティック・ハイブリッド検索時 |

sqlite-vec・apsw はもう使わない。埋め込みがなくても FTS 検索とすべての生成ビューは動作する。正確な依存の一覧は `kb/` の import を基準にする。

### 実行環境

- 常駐プロセスなし。GPU 不要（Apple Silicon では MPS により埋め込みが速い）。
- store の再生成は 1〜2 秒（文書 760・チャンク約 7 千の規模、DEC-2026-10-28-13・09 で実測）。
- 埋め込みの計算は最初の 1 回は長くかかり、以降は `embeddings` キャッシュのおかげで変わったチャンクだけを計算する。

## 限界

| 限界 | 説明 | 対応 |
|---|---|---|
| 韓国語の形態素 (FTS5) | unicode61 は空白分離だけ — 「환불수수료변경」は不一致 | キーワード分割ガイドを守り、セマンティックを併用 |
| CamelCase の未分離 (FTS5) | FormulaBaseStructure → 単一トークン | prefix(*) 検索、または全体を入力 |
| 列指定・フレーズ・NEAR 未対応 | クエリのトークンがすべて引用符で囲まれるため FTS5 の高度な構文が動作しない | `--category`・`--topic` フィルタ、AND で代替 |
| セマンティック検索の事前準備 | `kb embed` で先にベクトルを作る必要があり、モデルのロードのため最初の質問が遅い | FTS5 を第一に、セマンティックは fallback |
| BM25 rank のみ (FTS) | 文書構造/重要度の重み付けがない | page_order で目次を並び替え、ハイブリッドを併用 |
| Obsidian 非実行時 | Dataview クエリは不可 | FTS5/セマンティックは Obsidian と独立に動作 |
