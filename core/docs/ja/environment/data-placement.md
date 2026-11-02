# データ配置の境界 (Data Placement)

> 正本: strata-kit `core/docs/ja/environment/data-placement.md` (2026-10-29 strata `docs/06-environment/data-placement.md` から移行、DEC-2026-10-29-11)。

> Strata の成果物が**どこに置かれ、誰が追跡するか**を定める唯一の正本 (source of truth)。
> 散在していた規則 (cross-model-bridge のデータ表、CLAUDE.md、task-spec-schema、01-context の local/shared の区別) をここに集約する。
> 核心原則: **「セッションは消耗品、データは Core の外、作業履歴はプロジェクト repo の外。」**

## 0. なぜ必要か (解決する問題)

初期設計では、**セッション間で共有するために `.strata/handoffs/`・`.strata/tasks/` をプロジェクト repo で git 追跡**していた。その結果:

- **コミットの churn**: ハンドオフとタスクはセッションごとに作られ変更される*作業履歴*なのに、共有のためにコード repo へコミットされ、コミット頻度が異常に高くなった。
- **二重保存**: ハンドオフを `.strata/handoffs/*.yaml` (repo) に書き、vault の `sessions/*.md` へ同期しつつ原本を repo にそのまま残したため、同じ情報が二か所に重複した。
- **位置のドリフト**: 新しいモデル (shared session ledger、task-spec) はすでに vault を正本としているのに、古いテンプレート/スクリプトは `.strata/` を指しており、一つの成果物に正本が二つできた。

解決策は、**作業履歴をプロジェクト repo の外 (vault) に出し、repo にはプロジェクト固有の指針だけを残すこと**である。これは、ledger/relay を vault へ移した決定の未完部分を仕上げるものである。

## 1. 3-Tier の境界

```text
Tier L · local      {project}/.strata/local/        git 除外   マシン固有・揮発性のランタイム状態
Tier P · project    {project}/.strata/              git 追跡   プロジェクト固有の「指針」(コードと一緒)
Tier V · vault      $STRATA_VAULT/projects/{n}/     vault git  作業「履歴」・協業成果物
```

分類基準を一行で:

> **揮発性なら L、プロジェクト固有の指針なら P、作業履歴・協業成果物なら V。**

| Tier | 場所 | git | 性質 | 変更頻度 |
|---|---|---|---|---|
| **L · local** | `{project}/.strata/local/` | 除外 (.gitignore) | マシン依存、他のマシンでは壊れる、再生成可能 | 高い (追跡しないので無関係) |
| **P · project SoT** | `{project}/.strata/` (ルート) | 追跡 | このプロジェクトのアーキテクチャと制約。コードと一緒に PR レビューされるべき | 低い (アーキテクチャ変更時のみ) |
| **V · vault/shared** | `$STRATA_VAULT/projects/{n}/` | vault git (別) | セッション間・人間同士で共有される履歴と成果物。repo のコミットとは無関係 | 高い (repo の外なので churn なし) |

## 1.5 Placement Profile (embedded | detached)

Tier P の**物理的な位置**は、プロジェクトの repo ポリシーに応じて二つのうち一つを選ぶ。
Tier の意味 (プロジェクト固有の指針) とレビュー義務は同じで、位置だけが変わる。(DEC-2026-08-19-01)

| Profile | Tier P の正本の位置 | repo に残る痕跡 | 適用基準 |
|---|---|---|---|
| **embedded** (既定) | `{project}/.strata/` — git 追跡 | `.strata/local/` の ignore 一行 | 個人/統制された repo — Tier P をコードと一緒に PR レビューできる |
| **detached** | `$STRATA_VAULT/projects/{n}/strata/` — vault git | git 除外の `.strata/local/` のみ (コミット 0 件) | チーム repo など `.strata` のコミットが規約違反となる場合 |

profile の**正本は manifest ファイル**である — ポインタをマシンローカルにだけ置くと、新しい PC では復元されない (cross-review 2026-08-19 反映):

| Profile | manifest の場所 | 保存媒体 |
|---|---|---|
| embedded | `{project}/.strata/profile.yaml` (git 追跡) | プロジェクト repo — **まだ決定のない新規プロジェクトでも判別できる** |
| detached | `$STRATA_VAULT/projects/{n}/strata/profile.yaml` | vault — **新しい PC は vault を pull するだけで profile が復元される** |

```yaml
# profile.yaml — placement profile manifest
profile: detached        # embedded | detached (repo 側の manifest は embedded のみ許可)
project: "{project-name}"
```

`.strata/local/vault-link.yaml` (Tier L、git 除外) は**任意のローカルキャッシュ**である — SoT ではなく、なくても動作する。

- **Tier P resolver の規則** (Tier P を読むすべての利用者に共通 — 実装の対応: `python3 -m kb --help`、`core/docs/ja/kb-engine.md`):
  ① repo の `.strata/profile.yaml` (embedded 宣言) → embedded
  ② repo に `.strata/decisions.yaml`・`.strata/decisions/` が存在 (legacy 検出) → embedded
  ③ `.strata/local/vault-link.yaml` (ローカルキャッシュ) → detached
  ④ `$STRATA_VAULT/projects/{ディレクトリ basename}/strata/profile.yaml` → detached (新 PC の bootstrap)
  ⑤ すべてなければ Strata 未適用のプロジェクト
- detached の Tier P ツリー: `strata/{profile.yaml, decisions/, decisions.yaml, constraint-registry.yaml, layer-map.yaml}`
- repo に完全に触れたくない場合は、チーム repo の `.gitignore` ではなく **global gitignore** (`~/.config/git/ignore`) に `.strata/` を登録する。
- detached では PC 間のセッション引き継ぎが **vault の pull 一回で完結**する (同期フック: DEC-2026-08-19-02)。
- チームと共有すべき決定は、vault での保管とは別に repo の `docs/` へ昇格する (§2 の API 契約の昇格規則と同じパターン)。

## 2. 成果物ごとの配置 (正本表)

| 成果物 | Tier | パス | 備考 |
|---|---|---|---|
| active-task (セッション別) | L | `.strata/local/active/{session-id}.yaml` | セッション中断時の現在状態 (絶対規則)。同時の複数セッションが互いに上書きしないようセッション別ファイル (DEC-2026-08-19-05) |
| session-plan.yaml | L | `.strata/local/session-plan.yaml` | |
| session-log.txt | L | `.strata/local/session-log.txt` | SessionEnd hook が記録 |
| last-compaction.yaml | L | `.strata/local/last-compaction.yaml` | PreCompact のスナップショット |
| agent-sessions.yaml (セッション対応表) | L | `.strata/local/agent-sessions.yaml` | claude_id ↔ codex_id、マシン依存 |
| **profile manifest** | **P** | `.strata/profile.yaml` (embedded) / vault `strata/profile.yaml` (detached) | placement profile の正本 (§1.5) |
| **decision レコード** | **P** | `.strata/decisions/DEC-{date}-{NN}-{slug}.yaml` | 決定の**正本** — 1 決定 = 1 ファイル。採番と記録は decision writer CLI 経由 (同時セッションでも安全、DEC-2026-08-19-05) |
| **decisions.yaml (インデックス)** | **P** | `.strata/decisions.yaml` | レコードから**再生成される T0 インデックス**。手で編集しない |
| **constraint-registry.yaml** | **P** | `.strata/constraint-registry.yaml` | コンテキスト制約レジストリ |
| **layer-map.yaml** | **P** | `.strata/layer-map.yaml` | レイヤー違反検査用のマッピング |
| cowork DB | L | `.strata/cowork/cowork.sqlite*` | CoWorking の揮発性状態 (WAL を含む)。永続化への昇格物は tasks(V)・decision レコード(P) へ |
| ~~shared/~~ | — | `.strata/shared/` | **deprecated** — 作業履歴は Tier V への移行が完了すべき対象。新規作成は禁止 |
| **handoffs (ハンドオフ)** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` | shared session ledger と同じ場所。**vault に直接書く** |
| **shared session ledger** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` | コンテキストの source of truth |
| **tasks (タスク仕様)** | **V** | `$STRATA_VAULT/projects/{n}/tasks/{date}/{nn}-{title}/` | `_order.yaml` + `task-{nn}.yaml` |
| **relay 記録** | **V** | `$STRATA_VAULT/projects/{n}/relays/` | request/feedback のやり取り |
| **Hub delivery state** | **L** | `.strata/local/` またはローカルの Hub DB | hub_id、inbox cursor、pull/ack の状態。マシン・セッション依存 |
| **Hub audit projection** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` または `relays/` | 人が引き継ぐべき packet/review/decision の要約 |
| **methodology-backlog (project)** | **V** | `$STRATA_VAULT/projects/{n}/backlog/methodology-backlog.yaml` | 運用キュー = 作業履歴の性格 |
| **exploration-report / draft api-specs** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` (または tasks の隣) | セッション間の引き継ぎの中間成果物 (accepted API は昇格 — 下の注記) |
| **DEC ノートミラー** (人間向け ADR ミラー) | V | `$STRATA_VAULT/projects/{n}/decisions/DEC-{date}-{NN}.md` + `_generated-index.md` | レコードから生成される**人間の閲覧・バックリンク用ミラー**。正本は Tier P。**生成時点**: decision writer CLI の `add`・`regen-index`・`migrate` がレコードとインデックスを書いた**直後に同じ実行の中で** DEC projection generator を呼び、当該プロジェクト分を**全量再生成**する (冪等、正本のないノートは削除)。コミットはセッション終了チャネル (handoff/ledger close → vault commit+push) が担当し、即時反映は `--sync` (DEC-2026-08-21-01) |

| **トピックノードツリー (toc.yaml)** | **V** | `$STRATA_VAULT/projects/{n}/_meta/toc.yaml` | 人が読む目次の**正本**。性格は指針だが、利用者 (ノードページ生成器・KB 索引・カバレッジリゾルバ) がすべて vault 側にあり、detached プロジェクトは repo に置く場所がないので V。コードと一緒にレビューされるべき変更ではない |
| **ノードページ** | V | `$STRATA_VAULT/projects/{n}/nodes/{node-id}.md` | toc.yaml と 4 面 frontmatter (仕様・制約・決定・セッション) から生成される**結合ビュー** (Index 層、手で編集しない)。**生成時点**: KB 索引ビルドとセッション終了チャネル (handoff/ledger close) が同じ実行の中で当該プロジェクト分を全量再生成する (冪等、正本のないページは削除)。別の手動実行には任せない — DEC ノートミラーの教訓 |

> **ノードページは正本ではない** — 4 面の正本はそれぞれ、仕様(V)・Constraint Card(V) と registry(P)・decision レコード(P)・セッション(V) であり、ノードページはこれらを読み取り専用で集める。「負債」の面も表示にすぎず、正本はセッション文書に `doc_change` の宣言がないという事実そのものである。
>
> **decisions の正本は Tier P である** — 物理的な位置は profile に従う (embedded = repo `.strata/`、detached = vault `projects/{n}/strata/`、§1.5)。vault の `projects/{n}/decisions/` はレコードから生成される **DEC ノート** (人間の閲覧・バックリンク用、手で編集しない) であり、機械可読の SoT ではない。
>
> **DEC ノートミラーの役割と限界** (DEC-2026-08-21-01): embedded プロジェクトのレコード正本は、**プロジェクト repo にコミット・push するまで他のマシンから読めない**。ミラーはこの空白を vault チャネルで埋める環境横断の補完装置であり、正本の代替ではない — したがって ① ミラーはレコードの記録と**同じ実行**で生成されなければならず (別の手動実行に任せると空になる — 2026-08-21 にあるバックエンドプロジェクトでミラー 0 件だった実例)、② セッション終了ゲート (handoff generator・ledger CLI の `validate`/`close`) は repo の `.strata/decisions*` の**未コミットのレコードを警告**する (ブロックはしない)。detached プロジェクトはレコード自体が vault にあり、セッション終了チャネルが一緒にコミットするのでゲートの対象ではない。
>
> **API 契約の昇格規則**: `draft api-specs` は Tier V (セッション引き継ぎの中間物) だが、**accepted API contract** (コード・クライアント・ドキュメントの基準になった時点) は作業履歴ではなく project artifact である → **Tier P または repo の `docs/openapi` へ昇格**する。
>
> **backlog の可視性への注意**: project の `methodology-backlog` 自体は運用キューなので Tier V だが、**accepted 項目が Tier P (`decisions`/`constraint-registry`/`layer-map`) を変更する場合、その Tier P の変更は同じ PR に現れなければならない** (コードレビューの可視性 — backlog が vault に出ても、*決定のコードへの反映*は repo でレビューする)。

## 3. .gitignore 規則 (プロジェクト)

Tier L は除外し、Tier P だけを追跡する。Tier V はそもそもプロジェクト repo の外なので無関係。

```gitignore
# Strata — Tier L(local・cowork) を除外し、Tier P(指針) だけを追跡  [embedded profile]
.strata/local/
.strata/cowork/
.strata/**/*.tmp

# Tier P は明示的に追跡する (除外しない):
#   .strata/decisions/  .strata/decisions.yaml
#   .strata/constraint-registry.yaml
#   .strata/layer-map.yaml
```

**detached profile** では repo の `.gitignore` に触れないのが原則である — global gitignore (`~/.config/git/ignore`) に `.strata/` を登録して repo の痕跡を 0 に保つ (§1.5)。

> ⚠️ 旧規則 (`handoffs/`・`tasks/` を追跡) から**反転**した。以前は「共有のために追跡」だったが、今は共有を **vault (Tier V)** が担い、repo は追跡しない。

## 4. なぜこの境界か (根拠)

- **マシン依存 (L) を git に載せると壊れる。** セッション ID やローカルパスは他のマシンでは無意味 (カード `rec.session.state-in-files` の local/shared 原則と同じ)。
- **指針 (P) はコードと運命を共にする。** アーキテクチャの決定と制約は、そのコードをレビュー・ロールバックするときに一緒に見る必要があるので、同じ repo・同じ PR にあるのが基本である (embedded)。ただしチーム repo の規約が `.strata` のコミットを許さない場合は、**位置だけ**を vault に移す (detached、§1.5) — 指針の性格とレビュー義務は同じである。変更頻度が低く churn を生まない。
- **履歴 (V) には専用の共有チャネルがある。** ハンドオフ・ledger・relay は、セッションと人をつなぐ履歴である。この共有は **vault (独自の git/Obsidian 同期)** が専任するので、コード repo に載せる理由がない。コード repo はコードや指針が変わるときだけコミットされる。

## 5. 他の文書との関係

- **vault 同期**: ハンドオフは vault に直接書く (旧「repo 原本 → vault 変換」という二重保存のフローは廃止)。vault の生成物ごとに誰が書くかは DEC-2026-10-29-04 が定める — DEC ノートは decision writer CLI の実行に組み込まれ (§2 の表)、ノードページは librarian (`kb views-publish`)、索引メタはマシンごと。
- **task-spec-schema.md** (`core/docs/ja/methodology/task-spec-schema.md`): タスクと backlog は Tier V。パスはこの表が正本。
