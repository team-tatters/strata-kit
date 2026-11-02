# KB エンジン: 保存の契約

ナレッジベースは、文書・コード面・決定・セッション・カードのグラフであり、vault の隣にある 1 つのファイルベースのストアに保持されます。ストア内のすべては出典から生成され（rec.kb.generated-views）、ストアはいつでも再構築できるキャッシュです。

## なぜストアを 1 つにするのか

現在の vault には、FTS5 索引、ノードページ、決定ノートのミラー、coverage の対応表、リンクのベースラインがあり、それぞれ別のスクリプトで作られ、それぞれ別のファイルに置かれています。コードグラフの決定（strata DEC-2026-10-28-05）はコードシンボルと影響エッジを加え、埋め込みはベクトルを加えます。それぞれが自分のファイルを持つと、肝心の問い（変更された関数を所有する文書はどれか、このセッションが拠り所にした規則を置き換えた決定はどれか、このノードに触れたセッションはどれか）に答えるのにツール間の結合が必要になります。スキーマが 1 つのストアが 1 つあれば、1 回のクエリで答えられ、バックエンドが変わってもスキーマは変わりません。

## スキーマ

```text
nodes(id, kind, project, path, title, status, updated, revision, payload_json)
  kind ∈ {doc, code, decision, session, order, task, card, node, profile}
edges(src, dst, kind, confidence, source_ref, created)
  kind ∈ {covers, supersedes, kb_updates, orders, decisions_made, relay, calls, imports, tests, member_of, links, implementation}
  confidence ∈ {declared, extracted, inferred}
chunks(node_id, seq, heading, text, title, tags, locale, embedding?, meta_json)
  全文検索とベクトル検索の単位。heading・title・tags を本文の隣に置くので、FTS 索引（unicode61、4 列）は legacy 索引と同じ順位付けになる。meta_json は heading_level・line_start・line_end・char_count を保持する。文書・決定・オーダーは 1 つの FTS テーブルと 1 つの bm25 尺度を共有する。legacy 索引の順位との一致は目標ではない (DEC-2026-10-28-08)
baselines(gate, project, key, recorded)                リンクと coverage のベースライン
revisions(store_rev, kit_rev, built_at, sources_hash)  ストア全体の出自
```

宣言されたエッジは frontmatter（covers, supersedes, orders, kb_updates, decisions_made）と決定レコードから来ます。抽出・推論されたエッジはグラフ provider（imports, calls, tests）から来て、provider の信頼度ラベルをそのまま保ちます。ストアの中に手書きされたものはありません。

## バックエンド

| バックエンド | 役割 | 状態 |
|---|---|---|
| SQLite (FTS5 + sqlite-vec) | 基本: vault ごとに 1 ファイル、サーバーなし、MCP プロセスに組み込み | 現行 (FTS5)、vec は未実装 |
| DuckDB | 同じテーブル上の分析（coverage レポート、鮮度、プロジェクト横断クエリ）、共有用の parquet エクスポート | アダプター未実装 |
| RocksDB | オーケストレーターから来る書き込みの多いセッションストリーム（リレーパケット、承認）を、ノード/エッジに畳み込む前に保持するキーバリューストア | アダプター未実装 |

すべてのバックエンドは同じ契約を実装します: `put_nodes`, `put_edges`, `query(sql-like)`, `search_text`, `search_vector`, `rebuild(sources)`。エンジンは、アダプターの外でバックエンド固有の機能に依存しません。

## provider

| provider | 生成するもの | 契約 |
|---|---|---|
| vault スキャナー | 文書ノード（すべての markdown ファイル。索引対象のものはチャンクを持ち、生成されたミラーにはフラグを付ける）、宣言されたエッジ、本文の `links` エッジ | frontmatter + taxonomy |
| 決定レコード | 決定ノード、supersedes エッジ | decision writer の出力 |
| コードグラフ — キット自前の provider（`kb/providers/code_graph.py`） | リポジトリごとに: ディレクトリ・ファイル・型シンボルのコードノード（git 追跡ファイルのみ。Kotlin · Java · TS/JS · Python）、`member_of`（extracted）、`imports`（extracted。ワイルドカードとパッケージの import は inferred でディレクトリを指す）、`tests`（inferred）。vault の covers 対象（`code:<p>:paths:<dir>/`, `code:<p>:symbols:<Name>`）を解決する | strata DEC-2026-10-28-05。`python3 -m kb code deps · impact · tests-for · symbol · owner-gate`; flow(request) は任意の外部アダプターの担当のまま |
| オーケストレーターストリーム (Quilt) | セッションノード間のリレーと承認のエッジ | rec.decision.orchestrator-decisions-flow-to-records |
| 埋め込み器（ローカル、またはオプトインのクラウド） | チャンクのベクトル | ロケールを認識する。エンジンの動作に必須ではない |

## ストアを読むゲート

- coverage ゲート: 変更されたコードノード → covers エッジ → 所有する文書。所有者も doc_change 宣言もない変更ノードは新たな違反です（rec.kb.covers-owner）。
- リンクゲート: 本文の wikilink と markdown リンクは `links` エッジです（source_ref に対象の解決方法 file · id · alias · none · md を記録する）。壊れたリンク、id だけ・別名だけで解決されるリンク、知識文書が置き換え済みの対象を指しているものは、ベースラインを超えた違反です（rec.kb.link-currency）。記録上のベースラインの正本は `.kb/link-baseline.json` のままで、ストアの baselines テーブルはそのミラーです。markdown 以外のリンク対象と `--code-root` の検査は、ファイルシステムと git で確認します (DEC-2026-10-28-07)。
- 鮮度: covers が担うコードの revision が updated フィールドより新しい文書ノード。
- 検索: heading・text・title・tags に対する 1 つの FTS テーブル (bm25)。埋め込み器 provider（BAAI/bge-m3、ローカル）による密ベクトルは `embeddings(model, text_hash, dim, vector)` にキャッシュしてチャンクに付与し、コサインは総当たりで計算する（この規模では ANN は不要）。ハイブリッド = 両者の reciprocal-rank fusion。`python3 -m kb search-eval` は vault のクエリセットに対して recall@k を測定する (DEC-2026-10-28-09)。
- 収束: 同じ主題についての目標仕様ノードと as-built 文書ノードの対比（rec.spec.desired-vs-as-built）。

## strata/scripts からの移行

エンジンはシャトル方式（このリポジトリの strata-kit DEC-2026-10-28-01）で `strata-kit/kb/` に入りました。各 `strata/scripts/<name>.py` は `strata-kit/kb` への薄い呼び出しであり、フックは動作し続け、すべての呼び出し元がキットを指した時点でシャトルは削除されます。

最初のマイルストーンである同等性は通過し、次のマイルストーンで legacy FTS 索引（`.kb/kb.sqlite`、DEC-2026-10-28-13）を廃止しました。vault が持つストアは 1 つになりました。

- `python3 -m kb build-index` はセッション終了時のビルドです。ストア全体を再構築した後、ノードページ（`kb.views.node_pages`）、Obsidian の sortspec、レビュー受信箱（`.kb/review-candidates.json`, `_index/review-needed.md`）、`manifest.json`、taxonomy 検証の警告（block 違反は exit 2）をストアから導出します。`--project` は報告の範囲を絞るだけで、ストアは常に全体です。
- 文書の規則（発見、frontmatter、チャンク、taxonomy のマージ、検証）は 1 か所、`kb/docrules.py` にあります。スキャナーは各文書ノードの payload に `discovered`（発見集合）と `diagnostics`（検証結果）を載せるので、ビルドは索引なしで警告を報告できます。
- 鮮度は `engine.ensure_fresh_store`（ソースの mtime）が担います。古い `kb_freshness.py` と manifest ハッシュによる増分ビルドはなくなりました。
- 証拠: 2026-10-28 に、元のビルダー（strata@b4b0c86）と `kb build-index` は、実際の vault の 2 つのコピー（文書 760、ノードページ 66）で、同じノードページ、sortspec、レビュー受信箱、manifest のファイル、警告行、終了コードを生成しました。比較スクリプトは legacy 索引を廃止した後に削除されました（オーダー 2026.10.29-11）。
