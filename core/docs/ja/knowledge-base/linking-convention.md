# Knowledge Base — リンク規則

> 正本: strata-kit `core/docs/ja/knowledge-base/linking-convention.md` (2026-10-29 strata `docs/07-knowledge-base/linking-convention.md` から移行、DEC-2026-10-29-11)。

## 概要

vault 内部のリンクは Obsidian との互換性を最優先する。
vault の外 (strata-kit、projects) への参照は環境変数ベースとする。

## リンクの種類

### 1. vault 内部のリンク — Wikilink を使う

```markdown
<!-- 同じ vault 内の文書を参照 -->
[[overview]]
[[decisions/001-use-jwt-auth]]
[[glossary#JWT]]

<!-- 表示テキストを変更 -->
[[decisions/001-use-jwt-auth|JWT 認証の決定]]
```

**規則:**
- vault 内部は常に `[[wikilink]]` を使う
- パスは vault ルート基準の相対パス
- 拡張子 `.md` は省略する
- Obsidian の Graph View で関係が可視化される

### 2. vault → kit の参照 — 環境変数

```markdown
<!-- vault 文書から kit の方法論を参照するとき -->
レイヤー規則は `$STRATA_KIT/core/rules/layer-rules.yaml` を参照。
```

**規則:**
- 絶対パスの使用を禁止する
- 必ず `$STRATA_KIT` 環境変数を使う
- vault 文書から kit への参照は最小限にする (vault は知識、kit は方法論)

### 3. vault → project の参照 — 環境変数

```markdown
<!-- vault 文書からプロジェクトコードを参照するとき -->
実装: `$STRATA_PROJECTS/{project-name}/src/auth/AuthService.ts`
```

**規則:**
- `$STRATA_PROJECTS` 環境変数を使う
- コードの参照にはパスだけを記録する (コードのコピー禁止)

### 4. project CLAUDE.md → vault の参照 — @ 構文

```markdown
<!-- プロジェクトの CLAUDE.md から vault を参照するとき -->
プロジェクト知識: @$STRATA_VAULT/projects/my-api/
```

**規則:**
- Claude Code の `@` 遅延読み込み構文を使う
- パスは環境変数で解決する

### 5. project CLAUDE.md → kit の参照 — @ 構文

```markdown
<!-- プロジェクトの CLAUDE.md から kit を参照するとき -->
レイヤー規則: @$STRATA_KIT/core/rules/layer-rules.yaml
```

### 6. typed frontmatter link — 関係の種類をデータで

本文の wikilink は「関連がある」としか言わない。関係の**種類**は frontmatter のフィールドで書く (DEC-2026-08-19-03)。生成器・検証・ノードページはこのフィールドだけを読み、本文のリンクは読まない。

| フィールド | 方向 | 使う type | 意味 |
|---|---|---|---|
| `sources` | Knowledge → Archive | KB・pattern | この文書の根拠となったセッションとタスク。Knowledge の更新時に必須 |
| `up` | 子 → 親 | すべての文書 | この文書を含む上位の概念・MOC |
| `decisions` | 文書 → 決定 | KB・session・task | この文書が従う、または作った決定 |
| `supersedes` / `superseded_by` | 新しい決定 → 古い決定 / 古い → 新しい | decision | 置き換え関係の両端。検証が対称性を確認する |
| `nodes` | 文書 → トピックノード | decision・session・task・specification・concept・constraint | この文書が属する目次の単位 |
| `covers` | 仕様 → コードの面 | specification・concept | この文書が**正本**であるコードのパス・シンボル・エンドポイント・テーブル |
| `related` | 文書 ↔ 文書 | すべての文書 | 言及・参考の関係。所有ではない |

**規則:**
- `sources`・`up`・`decisions`・`supersedes`・`related` の値は `[[wikilink]]` である。`nodes` の値は toc.yaml のノード id、`covers` の値は repo 相対のポインタである。この二つは wikilink ではない。
- 関係フィールドは値がなければ省略する。空の配列を置くと、検証が「意図的な空か」を尋ねる。
- 同じ関係を本文の wikilink でも書くことは許される (Obsidian のグラフ用)。ただし正本は frontmatter である。
- 値の形式の正本: `nodes`・`covers`・`doc_change`・`supersedes` は document-format.md の「ノード・カバレッジフィールド」節、`sources` は同じ文書の frontmatter スキーマ。

### 7. リンクが常に現行を指すようにする規則 (DEC-2026-09-30-03)

- **wikilink の対象は、ファイル名 (または vault 相対パス) で解決できなければならない。** frontmatter の `id:` や `aliases` (タスク id など) でしか解決できないリンクは Obsidian で壊れるので使わない。ファイルを移動または改名したら、古い名前を `aliases:` に残す (検索・unlinked mention 用) が、リンク自体は検査器が示す通りに新しいファイル名へ直す。
- **自由テキストをリンクで包まない。** `[[restdocs 양식 정렬]]` のように対象文書のないリンクは禁止する。説明が必要なら表示テキストを使う (`[[session-2026-09-02-x|task05 후속]]`)。
- **置き換えられた文書を指す本文のリンクは、現行の文書に変える。** 置き換え関係のフィールド (`supersedes`・`superseded_by`) と、履歴を説明する文は例外である。検査器は両者を区別できないので、この項目は参考 (警告) としてだけ報告する。
- **コードはパスよりシンボルで指す。** `covers.symbols` にクラス・関数の名前を書き、本文でも `CollaboratorCommandService.invite` のようにシンボルで書く。パスはモジュール・パッケージの水準までしか書かない。ファイルは移動してもシンボル名はあまり変わらないからである。
- **検査:** `python3 "$STRATA_KIT/kb" link-check` が、壊れた wikilink、自由テキストのリンク、id でしか解決できないリンク、置き換えられた文書への本文リンクを見つける。生成・インポートされた文書 (DEC ノート、ノードページ、企画原文、`_index/`) の違反は手で直せないので、報告するだけでブロックしない (直す場所は生成器)。セッション終了ゲートは、そのセッションのプロジェクトの文書だけを見る。既存の違反はベースライン (`$STRATA_VAULT/.kb/link-baseline.json`) にまとめ、**ベースライン外に新しい違反があるときだけ失敗**する。セッション終了 (`python3 "$STRATA_KIT/kb" ledger close`) はこの検査で vault 同期を止め、ハンドオフ生成 (`python3 "$STRATA_KIT/kb" handoff`) は警告だけを出す。急ぐときに限り `STRATA_LINK_CHECK=warn` で警告に降格する。ベースラインは直した分だけ `--shrink-baseline` で縮める。
- **コードとの突き合わせ:** `--code-root {project}=<repo>` を渡すと、KB の `covers.paths` がリポジトリに存在するか、`covers.symbols` の名前がコードで検索できるかも確認する (コードのリポジトリがあるマシンでのみ)。

## 禁止事項

| 禁止パターン | 理由 | 代替 |
|---|---|---|
| vault 内の絶対パス (`/home/alice/...`) | マシン間で互換性がない | `$STRATA_KIT`、`$STRATA_VAULT` を使う |
| vault 内のマークダウンリンク `[text](path)` | Obsidian Graph に表示されない | `[[wikilink]]` を使う |
| コードブロックのコピー | コードの腐敗 | パス参照だけを記録する |
| プロジェクト間の直接参照 | 依存関係が生まれる | vault/patterns/ に共通パターンとして抽出する |
| 関係の種類を本文リンクだけに頼る | 生成器・検証が読めない | §6 typed frontmatter link |

`covers` のコードポインタは wikilink でなくてよい。frontmatter 内の repo 相対パスは「vault 内のマークダウンリンク禁止」の対象ではない。

## 埋め込み

Obsidian の埋め込み構文も使える:

```markdown
<!-- 別の文書の特定の節を埋め込む -->
![[decisions/001-use-jwt-auth#결정]]

<!-- 画像を埋め込む -->
![[architecture-diagram.png]]
```

埋め込みは参照先の文書の内容が変わると自動で反映されるので、重複して書くより埋め込みを推奨する。
