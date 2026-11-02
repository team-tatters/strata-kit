# 09 — Context Protocol: Constraint-Aware Context Loading

> 正本: strata-kit `core/docs/ja/methodology/context-protocol.md` (2026-10-29 strata `docs/09-context-protocol.md` から移管、DEC-2026-10-29-11)。

> kit のカード（`rec.context.entry-view-budget`・`rec.session.split-at-task-boundary`・`rec.session.state-in-files`）と `core/docs/ja/methodology/session-splitting.md` の原則に基づき、制約 (Constraint) を認識するコンテキスト読み込みの規則を定義します。

## 1. 問題定義

ADR で決めたドメイン制約 (例: 「hard-delete 禁止」「Bitemporal 必須」) が実装段階で失われる経路:

1. ADR の散文が長すぎて、毎回全文を読めない
2. Compaction のときに ADR の詳細が失われる
3. Worker は独立したコンテキストで動く — Builder セッションでの ADR の議論を知らない
4. タスク仕様にドメイン制約が欠けていると、Worker は検知できない

## 2. 解決: 制約は入口ビューに要約で載せ、レジストリ全文は必要なときに読む

### コンテキスト階層

```
T0 — Universal (常に読み込む、12KB 以内 — rec.context.entry-view-budget)
  ├── AGENTS.md + CLAUDE.md            (生成ガイダンス — must カードの要約、制約の要約 2KB 以内)
  └── active/{session-id}.yaml         (セッションごとの active-task — DEC-2026-08-19-05)

T1 — Session (セッション開始時)
  ├── 最新の handoff ファイル
  ├── decisions.yaml                   (生成インデックス、必要なときに — 正本は decisions/ のレコード)
  └── constraint-registry.yaml         (必要なときに — 入口ビューのリンクから)

T2 — Domain (タスク対象ごと)
  ├── 該当トピックノードのノードページ (最終形状・ポリシー・決定・作業履歴・負債を結合した生成物、エントリポイント)
  ├── 該当ドメインの Constraint Card 全文
  └── 関連 ADR の Decision Outcome セクション

T3 — Implementation (実装時)
  ├── 対象のソースファイル
  ├── テストファイル
  └── layer-rules.yaml (該当レイヤーのセクション)
```

### constraint-registry.yaml の規則

- **場所**: `.strata/constraint-registry.yaml` (プロジェクト内)
- **サイズ上限**: 3KB 以内。生成ガイダンスには 2KB の要約だけを載せ、全文はリンクで置く
- **3KB を超えたら**: `severity: should` の項目を別ファイルに分離する。registry には `must`/`must-not` だけを残す
- **更新時点**: ADR が accepted に遷移するとき + Constraint Card を作るときに同時に更新する
- **形式**: `decisions.yaml` と同じ YAML インデックス

```yaml
constraints:
  - id: CC-NNN-01
    source: ADR-NNN
    severity: must
    scope: {domains: [{domain}], layers: [{layer}]}
    rule: "{1 行の実行可能な規則}"
    status: active
```

### decisions.yaml の規則 (2026-08-19 訂正)

- 必要なときに読む `decisions.yaml` は、**レコード (`.strata/decisions/DEC-*.yaml`) から再生成されるコンパクトなインデックス**である。手での編集は禁止。
- 決定の追加・採番・インデックスの再生成は **decision writer CLI** だけが行う (flock で直列化 — 複数セッションが同時に動いても安全、DEC-2026-08-19-05。役割→実装の対応: `python3 -m kb --help`、`core/docs/ja/kb-engine.md`)。
- 詳細が必要なら、インデックス項目の `record:` パスからレコード全文を読み込む — Registry (1 行) → Card (~50 行) → ADR (~200 行) と段階的に詳細化するのと同じパターン (インデックスの要約 → レコード全文)。
- Tier P の物理的な位置は placement profile に従う (`core/docs/ja/environment/data-placement.md` §1.5 — embedded=repo、detached=vault `projects/{n}/strata/`)。

## 3. Agent Role ごとの Context 読み込み

### Builder

| 状況 | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| タスク作成 | ✓ constraint-registry を絞り込み | ✓ | ノードページ → 該当ドメインの Card | - |
| ADR 作成 | ✓ | ✓ | ノードページ (決定の連鎖を確認) | - |
| Constraint 抽出 | ✓ | - | - | - |

Builder は constraint-registry.yaml を読み、タスクのドメイン/レイヤーで絞り込んで、
該当する constraint をタスク仕様の `scope.constraints` に注入します。
同じ方法で、変更範囲を所有する仕様 (`covers`) をカバレッジリゾルバーで見つけ、`scope.docs_to_update` に注入します。
ノードページはこの二つの注入のエントリポイントです — ノードをひとつ開けば、現行の仕様・有効な制約・現行の決定がひと画面に揃います。

### Worker

| 状況 | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| タスク実行 | CLAUDE.md のみ | - | - | ✓ |

**Worker は constraint-registry.yaml を直接読みません。** ノードページも直接は読みません。

Builder がタスク仕様の `scope.constraints` と `scope.docs_to_update` に注入した内容だけを使います。
これはタスク仕様の**自己完結性**の原則と一致します。

```yaml
# Worker が受け取るタスク仕様
scope:
  layer: "L2_DataLayer"
  constraints:
    - id: "CC-NNN-01"
      rule: "この scope に適用される制約"
    - id: "CC-NNN-02"
      rule: "別の制約"
```

Worker はこの `scope.constraints` を、完了報告の `constraint_compliance` に変換します。

### Supporter

| 状況 | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| Constraint 検索 | ✓ registry 検索 | - | 検索結果のみ | - |

Supporter は Builder の依頼で、特定のドメイン/レイヤーの constraint を検索します。

## 4. Context Budget の規則

```
CB-1: T0 (AGENTS.md + CLAUDE.md) は 12KB、継承ガイダンスを含めて 14KB 以内 (wizard verify)
  → 制約レジストリ・決定インデックスは T0 ではない。制約は生成ガイダンスに 2KB の要約で載せる
  → ガイダンスがあふれたら、目次化 (参照中心) による縮小を優先
  → using-strata が読む入口経路 (スキル本文・コアレジストリ・憲法) は verify が別に報告する (2026-10-29、上限なし)

CB-2: T2 の Constraint Card はドメインあたり 10KB 以内
  → 10KB を超えたら Card 全文の代わりに registry の 1 行要約だけを読み込む

CB-3: .strata/ 全体の読み込み量は 30KB 以内 (T0+T1+T2 の合計)
  → 超えたら T2 を registry の該当行で置き換える

CB-4: ADR 全文は Builder (ADR 作成/Constraint 抽出) だけが読み込む
  → ほかの役割は Constraint Card を通じて ADR の決定にアクセスする
  → これが Constraint Card の存在理由

CB-5: ノードページはノードあたり 8KB 以内 (CB-2 の Card 予算と合わせて T2 上限を維持)
  → 生成器が、作業履歴の面を直近 5 件に、決定の面を現行 + 直前 1 件に切り詰めて予算内に収める
  → それでも超えるなら、最終形状・ポリシーの面だけを残し、残りはリンクで置き換える
```

## 5. Compaction への耐性

```
Compaction 前:  ADR 全文 + 詳細な議論 (コンテキストに存在)
Compaction 後:  要約だけが残る — ADR の詳細が失われる恐れ

Constraint の復元経路:
  constraint-registry.yaml (ファイルにあるので、いつでも読み直せる)
  → 1 行要約で「何を守るべきか」をすぐ確認
  → 詳細が必要なら個別の Constraint Card を参照 (T2)
  → さらに深い文脈が必要なら source_adr を参照

段階的な詳細化 (Layered Detail):
  Registry (1 行)  →  ノードページ (~100 行)  →  Card (~50 行)  →  ADR (~200 行)
  要約は入口ビュー     ドメインに入るとき一度      必要なときに読み込む  ほとんど読み込まない
```

ノードページは Card と ADR の代わりにはならない。どの Card・どの ADR・どの仕様が現行かを教えるエントリポイントであり、本文はリンクの先にある。

## 6. 既存のコンテキスト管理との関係

| 既存 (kit のカード・session-splitting.md) | 本文書 (拡張) |
|---|---|
| CLAUDE.md の階層設計 (§2·§4, `wizard verify`) | 維持 — 制約の要約は生成ガイダンスに、レジストリ全文は必要なときに |
| ハンドオフプロトコル (`strata.handoff`, session-splitting.md §5) | 維持 — ハンドオフに constraint 抽出の状態を追加 |
| Compaction 防御 (execution-modes.md, `kb pre-compact`, SessionStart compact) | 強化 — registry が追加の復元アンカー |
| トークン予算ガイド (session-splitting.md §5.2) | 拡張 — CB-1~5 の規則を追加 |
| Memory vs Handoff vs KB の区別 (§7, rec.session.state-in-files, rec.kb.session-records-in-vault) | 維持 — Constraint Card は KB に置く |
| (新規) トピックノード | T2 のエントリポイント — ノードページは Index 階層の生成物であり、正本ではない (core/docs/ja/knowledge-base/vault-structure.md) |

## 7. メモリ・ハンドオフ・KB の区別

ハーネスのメモリ（Claude Code では `~/.claude/projects/<プロジェクト>/memory/`）は、セッション開始のたびにインデックスが自動で読まれる場所である。だから何を置くかが次のセッションの判断を変える。

| 何を | どこに | 理由 |
|---|---|---|
| 進行状態 — 手元の作業、次にやること、未コミット、行き詰まり | アクティブファイル（`.strata/local/active/`）とハンドオフ | セッションが終われば古くなる。メモリに置くと、次のセッションが過去の状態を今の事実として読む |
| 長く有効な事実 — ユーザーの好み、働き方についての指示、外部資源の場所 | ハーネスのメモリ | 毎セッション自動で読まれるべきもの |
| 決定と方針 | 決定レコード、カード | レビュー済みの正本。メモリのフィードバックが方針になればこちらへ移す |
| 設計・仕様・知識 | vault KB | リンクとカバレッジでコードと結ばれる |

**進行状態はメモリに置かない。** セッションを閉じるとき、そのセッションがメモリに書いた進行状態の項目はハンドオフへ移す（`strata.handoff` のメモリ点検ステップ、DEC-2026-10-31-16）。

**確認日。** メモリ項目の前付けに、最後に正しいと確認した日を `verified: YYYY-MM-DD` として書く（DEC-2026-10-31-14・34）。ハーネスが書く `modified` は変わった日、`verified` は内容がまだ正しいと見た日である。エージェントが項目を書くか直すときに書き、ハンドオフ点検で人が「まだ正しい」と答えた項目も更新する。

**整理。** `python3 -m kb hygiene --memory` が、現在のフォルダーのメモリから整理候補を理由とともに示す。理由は、古い（確認日、なければ更新日が 60 日超 — ユーザー設定 `memory.stale_days`）、日付なし、状態表現の一致、形式不明、反対のフィードバック候補の組、インデックスとファイルの不一致である。ツールは読むだけで本文を出力しない。状態表現は一致であって判定ではない — 状態を名指す規則も引っかかる。移す・まとめる・消すは、人が項目ごとに承認したものだけ行う。消すときは同じディレクトリの `_archive/` へ移し、前付けに `retired`・`retired_reason` を書き、インデックスの行を外す（DEC-2026-10-31-17）。メモリのインデックスの大きさは `wizard verify` が示し、12KB を超えると警告だけする（DEC-2026-10-31-19）。Codex のメモリはまだ範囲外である（DEC-2026-10-31-13）。
