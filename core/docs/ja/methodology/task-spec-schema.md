# タスク仕様スキーマ (Task Specification Schema)

> 正本: strata-kit `core/docs/ja/methodology/task-spec-schema.md` (2026-10-29 strata `docs/04-agents/task-spec-schema.md` から移行、DEC-2026-10-29-11)。

> Builder が生成し Worker が消費するタスク仕様の構造を定義します。
> タスク仕様は**自己完結**でなければなりません — Worker が仕様だけでコードを完成できる必要があります。

## 保存場所

```
$STRATA_VAULT/projects/{project-name}/tasks/
  {yyyy.mm.dd}/
    {nn}-{short-kebab-title}/      # Work Order フォルダ
      _order.yaml                   # 作業指示書 (Builder が生成)
      task-{nn}-{title}.yaml        # Worker 実行仕様
```

### この場所を選ぶ理由

- `$STRATA_VAULT` — プロジェクトリポジトリに影響しない (別リポジトリ)
- `tasks/` — KB 文書 (knowledge-base/) と分離され、検索インデックスの対象ではない
- `{yyyy.mm.dd}/` — 時間の流れに沿った追跡、認知負荷を最小化
- `{nn}-{title}/` — 同じ日の複数の作業指示を、連番とタイトルで区別

### 命名規則

| 要素 | 形式 | 例 |
| ------------- | ------------------------------ | ------------------------------- |
| 日付フォルダ | `yyyy.mm.dd` | `2026.04.23` |
| Work Order フォルダ | `{nn}-{kebab-title}` | `01-debounce-mongo-sync` |
| 作業指示書 | `_order.yaml` | 常に固定 (アンダースコア = 最上位に並ぶ) |
| タスクファイル | `task-{nn}-{kebab-title}.yaml` | `task-01-redis-dirty-mark.yaml` |

### 連番ルール

- その日付フォルダの既存項目数 + 1
- 複数マシンで同時に作業すると番号が衝突し得る → **title が実際の識別子**となる
- 番号の衝突は並び順にのみ影響し、機能上の問題はない

---

## _order.yaml — 作業指示書

Builder がタスクを分割した後に生成するマニフェスト。

### 必須フィールド

```yaml
order:
  id: "2026.04.23-01"                # {日付}-{連番}
  title: "Redis Debounce による MongoDB 同期の最適化"
  date: "2026-04-23"
  mode: "task"                        # task | verbal (escalated)
  project: "shop-api"

  goal: |
    作業の目的と背景を記述する。
    なぜこの作業が必要か、完了時にどのような状態になっているべきか。

  context:
    prior_session: "session-2026-04-22-01"    # 前回のハンドオフへの参照
    prior_decisions:                           # この作業に影響する既存の決定
      - "PostProcessJob は polling 方式 (@Scheduled fixedDelay=5000)"
    blocker_resolved: "PostProcessJob システムの実装完了 (4/21)"
    kb_references:                             # 関連する KB 文書
      - "$STRATA_VAULT/projects/shop-api/knowledge-base/03-orders/checkout.md"

  tasks:
    - id: "task-01"
      title: "CacheGenericOperator に SET 演算を追加"
      model_tier: "standard"
      layer: "L2_DataLayer"
      depends_on: []

    - id: "task-02"
      title: "DirtyMarkService の実装"
      model_tier: "standard"
      layer: "L3_Composite"
      depends_on: ["task-01"]

    - id: "task-03"
      title: "DataUpsertListener を debounce に切り替え"
      model_tier: "deep"
      layer: "L3_Composite"
      depends_on: ["task-01", "task-02"]

  acceptance:
    - "既存の即時処理フローから dirty mark フローへの切り替えが完了している"
    - "単体テストがすべて合格する"
    - "レイヤー違反が 0 件"

  status: "open"                       # drafting | open | in_progress | completed | cancelled
  completed_tasks: []                  # 完了したタスク id の一覧
```

### 任意フィールド

```yaml
  escalated_from: "verbal"             # verbal → task に切り替えた場合
  completed_before_spec:               # 切り替え前に verbal で完了した項目
    - "CacheGenericOperator に SET 演算を追加"
  
  estimated_sessions: 1                # 想定セッション数
  priority: "high"                     # high | medium | low
  deadline: "2026-04-25"              # 絶対日付

  verification_tier: "self_verified"  # solo | self_verified | cross_verified (enum 値)
                                      #   省略時は verbal = solo。Task Mode では明示を推奨。
                                      #   詳細: core/docs/ja/methodology/verification-tier.md
  entry_point: "change"               # design_first | dev_first | spec_first | change — 成果物 (Spec・Design・Impl) の入口。
                                      #   順序は固定しない。整合性検査がゲート。詳細: core/docs/ja/architecture/frontend-design-contract.md
  design_verified: "self"             # none | self | designer | cross — デザイン整合性検証の独立性 (core/docs/ja/methodology/verification-tier.md)。
                                      #   UI 作業でなければ none。
  methodology_feedback:               # 方法論フィードバックループ (任意)
    enabled: true
    backlog_ref: "$STRATA_VAULT/projects/{name}/backlog/methodology-backlog.yaml"
```

> **ただし Core の source-of-truth を変更する作業** (layer-rules / naming-convention / task-spec-schema / agent-roles)
> では `verification_tier: cross_verified` が**必須**です (`core/docs/ja/methodology/verification-tier.md`)。
> この場合に限り、verification_tier は任意ではなく必須フィールドとして扱います。

### status のライフサイクル

```
drafting → open → in_progress → completed
                              → cancelled
```

| 状態 | 意味 | 遷移条件 |
|------|------|----------|
| `drafting` | Builder がタスクを分割中 | Builder が _order.yaml の作成を開始した |
| `open` | 作業指示が確定し、Worker が実行可能 | すべてのタスク仕様の作成が完了した |
| `in_progress` | 一部のタスクを実行中 | 最初の Worker の実行が始まった |
| `completed` | 全タスクが完了 | すべての acceptance を満たした |
| `cancelled` | 取り消し | 明示的な取り消しの決定 |

`drafting` 状態の作業指示は、次のセッションで Builder が引き継いで完成させるか、破棄します。

---

## _order.md — 作業指示書の新形式 (2026-08-19, DEC-2026-08-19-03)

新規 order は `_order.md` で書く — **YAML frontmatter が order の本体**であり (スキーマは上の `_order.yaml` と同じ)、
本文は Obsidian のリンクグラフに組み込むための最小限の markdown です。

```markdown
---
order:
  id: "2026.08.20-01"
  # ... (_order.yaml スキーマそのまま)
---

# {order title}

- Design: [[design-doc]]
- Decisions: [[DEC-YYYY-MM-DD-NN]]
```

- 機械が解析する対象は frontmatter のみ — order を消費するスクリプトは `_order.yaml` と `_order.md` (frontmatter) の両方に対応します。
- 本文には design 文書と関連 DEC の `[[wikilink]]` を必ず残します (スパイン（ハンドオフのリンク: orders, kb_updates, decisions_made）のエッジ — session→order→design+DEC)。
- 既存の `_order.yaml` は遡って変換しません。`task-{nn}.yaml` は yaml のままです (グラフへの組み込みは order ノートが担います)。

---

## task-{nn}.yaml — Worker 実行仕様

Worker が受け取る自己完結したタスク文書。

### 完全なスキーマ

```yaml
task:
  id: "2026.04.23-01/task-01"          # {order-id}/{task-id}
  title: "CacheGenericOperator に SET 演算を追加"
  order_ref: "_order.yaml"             # 上位の作業指示書への参照

execution:
  model_tier: "standard"               # deep | standard | light (モデル名はツールアダプタがマッピング)
  model_reason: "既存の CacheGenericOperator のパターンを踏襲"
  estimated_turns: 8
  estimated_files: 2

scope:
  layer: "L2_DataLayer"
  module: "domain:common-cache"
  nodes: ["common.cache"]                         # このタスクが属するトピックノード — カバレッジリゾルバが directories から導出
  can_reference: ["L1_Component"]
  cannot_reference: ["L3_Composite", "Route_Controller"]
  constraints:                                    # ADR から抽出したドメイン制約
    - id: "CC-NNN-NN"
      rule: "{この scope に適用される制約の 1 行ルール}"
  docs_to_update:                                 # directories・module を covers で所有する仕様 — カバレッジリゾルバが注入
    - node: "common.cache"
      doc: "[[kb-shop-api-common-cache-spec]]"
      reason: "covers.paths が一致 — SET 演算の追加は仕様の演算一覧の変更"
  directories:
    - "domain/common-cache/src/main/kotlin/com/example/domain/common_cache/components/"

inputs:
  reference_files:
    - path: "domain/common-cache/.../CacheGenericOperator.kt"
      reason: "既存パターンの参照 — ReactiveRedisOperations の使い方"
    - path: "docs/architecture/layer-rules.yaml#L2_DataLayer"
      reason: "レイヤールールの確認"

  requirements: |
    実装すべき内容の詳細仕様。
    - メソッドシグネチャ
    - 動作の説明
    - 制約条件

  conventions: |
    適用するコンベンションの要約 (Worker が別ファイルを読まなくて済むように)。
    - PAL マーカー必須 (@pal-port, @pal-layer, @pal-domain, @Comment)
    - 命名: {Domain}{ServiceType}

  design_ref:                          # UI を作るタスクでは必須。デザイン成果物へのポインタ (core/docs/ja/architecture/frontend-design-contract.md)
    kind: "figma"                      # figma | storybook | claude_design | none
    ref: "file/abc?node-id=12:34"      # ファイル・ノード・ストーリー id・キャンバス URL
    version: "2026-04-23"              # ツールのバージョンまたはスナップショット日 — 整合性検査の基準点
    reason: null                       # kind: none の場合は必須 (例: "テキストのみの管理画面")

deliverables:
  files:
    - path: "domain/common-cache/.../CacheGenericOperator.kt"
      action: "modify"                  # create | modify | create_or_modify
      description: "SET 演算のメソッドを 4 つ追加"
    - path: "domain/common-cache/.../CacheGenericOperatorTest.kt"
      action: "create_or_modify"
      description: "SET 演算の単体テスト"

acceptance_criteria:
  - "addToSet, popFromSet, getSetSize, getSetMembers を実装"
  - "既存メソッドのシグネチャに変更なし"
  - "単体テストが合格"
  - "レイヤー違反なし"

context_budget:
  max_reference_files: 5
  max_loaded_tokens: 20000
  compaction_strategy: "file-based"

status: "pending"                       # pending | in_progress | completed | blocked
completion: null                        # 完了時に Worker が埋める (下記参照)
```

**`scope.nodes` と `scope.docs_to_update`** — タスクが変更するコード領域を所有する仕様 (frontmatter `covers`) と、その仕様のトピックノードを Builder が注入します。`scope.constraints` と同じ原理です。Worker はリゾルバを実行せず、注入された値だけを見ます。
- 所有する仕様がない領域 (新機能) の場合は、仕様の作成を `deliverables.files` に含めるか、`docs_to_update: []` とともに `inputs.requirements` に意図的に空にした理由を書きます。理由のない空配列は検証で警告されます。
- 値の形式の正本は core/docs/ja/knowledge-base/document-format.md の「ノード・カバレッジフィールド」節です。

### completion セクション (Worker が埋める — ただし `triage.review_gate` は例外)

`completion.self_report` と成果物の一覧は Worker が埋めますが、**`triage.review_gate` は
独立した再判定者 (reviewer/relay) が埋めます** — 自己申告検証ゲートの前提 (エージェント ≠ 再判定者、
`core/docs/ja/methodology/agent-operations.md` §4) により、Worker 自身が埋めるとゲートが無力化されるためです。

```yaml
completion:
  status: "completed"                   # completed | blocked | partial
  completed_at: "2026-04-23T14:30:00+09:00"
  files_created:
    - "domain/common-cache/.../CacheGenericOperatorTest.kt"
  files_modified:
    - "domain/common-cache/.../CacheGenericOperator.kt"
  tests:
    total: 4
    passed: 4
    failed: 0
  layer_violations: 0
  naming_violations: 0
  constraint_compliance:                # scope.constraints の各項目の遵守結果
    - id: "CC-NNN-NN"
      met: true
      note: "{遵守の根拠または特記事項}"
  design_sync: "aligned"                # aligned | stale | waived | none — Impl↔Design の整合性 (inputs.design_ref があれば必須)
  design_sync_reason: ""                # waived の場合は必須: 理由 + until YYYY-MM-DD。stale の場合は完了宣言不可
  doc_change: "updated"                 # updated | none — scope.docs_to_update の処理結果 (セッション frontmatter と同じキー)
  doc_change_reason: ""                 # none の場合は必須 (例: "リファクタリングのみ — 外部契約・ポリシーの変化なし")
  docs_updated:                         # updated の場合、更新した文書 (updated スタンプ・sources にこのタスクを追加)
    - "[[kb-shop-api-common-cache-spec]]"
  notes: "特記事項なし"
  methodology_signals:                  # 任意 — 方法論改善のシグナル (リスト。なければ [] または省略)
    - type: "incomplete_spec"           # incomplete_spec | scope_issue | constraint_conflict | rule_gap | drift | design_drift
                                        #   design_drift: alias 外の値・契約 (軸・状態) の不一致を発見 → トークン/デザイン契約の改善候補
      severity: "minor"                 # minor | major | blocking
      scope: "methodology"              # project | methodology
      affected_core:                    # scope: methodology の場合は 1 件以上必須
        - "core/docs/ja/methodology/task-spec-schema.md"
      summary: "タスク仕様にテストコマンドのフィールドがなく、完了検証の基準が揺らいだ"
  triage:                               # 任意 — Agent Operations の出力分類 (Decision Inbox 用)
    self_report:
      status: "completed"               # completed | blocked | needs_decision | rejected
      risk: "low"                       # high | medium | low | unknown
      decisions_needed: []
    review_gate:                        # 自己申告検証ゲート (再判定が必須の場合)
      required: true
      reviewer: "cross_verified"
      result: "agreed"                  # agreed | reclassified | no_reviewer
      final_status: "completed"         # 再判定後に確定した status
      max_review_rounds: 1
```

`methodology_signals` は、Worker が作業中に発見した**方法論そのものの隙間**を報告するチャネルです。
1 つの completion から複数の隙間 (例: incomplete_spec + rule_gap) が同時に出ることがあるため、**リスト**です。
Builder は各項目を個別に分類します。
通常の `scope_issue` (現在のタスクの行き詰まり) と異なり、ルール・スキーマ・コンベンションの改善候補を指します。
Builder はハンドオフ時にこれを backlog に積み、昇格を判定します
(→ 下の「Promotion Gate」節)。

`triage` は、出力を人が見る Decision Inbox に送る前の分類です。`self_report` はエージェントが埋め、
`review_gate` はクロス検証がそのラベルを再判定します (自己申告は信用できないため)。ルール、リスクに基づく分岐、再判定者が
いない場合のフォールバックは → `core/docs/ja/methodology/agent-operations.md` 「Decision Inbox + 自己申告検証ゲート」を参照。

---

## methodology-backlog.yaml — 改善候補の蓄積

方法論の改善候補を積む別ファイル。decisions.yaml (決定記録) とは分離します —
backlog は*候補*であり、ライフサイクル (レビュー→採用/却下) が異なるためです。
この節は backlog の**フィールドスキーマとライフサイクル enum** の source of truth です。
シグナルの流れと Promotion Gate もこのセクションが定義します (下の「Promotion Gate」節、DEC-2026-10-29-12)。

```
project backlog:  $STRATA_VAULT/projects/{name}/backlog/methodology-backlog.yaml  # vault (Tier V)
core backlog:     $STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml  # Strata Core の改善候補
```

```yaml
methodology_backlog:
  - id: "MB-shop-api-2026-001"   # {project} プレフィックスで中央昇格時の衝突を防ぐ
    scope: "methodology"              # project | methodology
    source:
      project: "shop-api"
      type: "worker_rejection"        # worker_rejection | reviewer_finding | repeated_warning
      ref: "tasks/2026.05.31/01-sync/task-02.yaml"
    signal: "incomplete_spec"
    severity: "major"
    affected_core:                    # scope: methodology の場合は 1 件以上必須
      - "core/docs/ja/methodology/task-spec-schema.md"
      - "core/roles/agent-roles.yaml"
    summary: "テストコマンドの欠落により、Worker が完了検証不可と判定した"
    proposed_action: "task スキーマに verification.commands フィールドを追加"
    status: "open"                    # open → triaged → accepted | rejected → applied
    promoted_to: null                 # 昇格時は "$STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml#<id>"
```

### ライフサイクル

```
open → triaged → accepted → applied
              → rejected
```

| 状態 | 意味 |
|------|------|
| `open` | シグナルを蓄積済み、未レビュー |
| `triaged` | Builder が scope・重複・affected_core の確認を完了した |
| `accepted` | Core の改善対象として採用 (昇格済み) |
| `rejected` | 改善不要と判定 (理由を記録) |
| `applied` | Strata Core に反映済み、テンプレート/アダプタを再生成した |

---

### Promotion Gate

backlog 項目は `scope` によって処理経路が分かれる。

- `scope: project` — そのプロジェクトの規則・layer-map・AGENTS.md・KB・決定の改善候補として処理する。
- `scope: methodology` — core backlog (`$STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml`) へ昇格させる。

Builder は `scope: methodology` の項目について次を行う。

1. 重複がないか確認する。
2. `affected_core` が1つ以上あることを確認する。
3. core backlog に昇格項目を追加する。
4. 元のプロジェクト項目に `promoted_to` を記録する。
5. kit に反映されるまで status は `triaged` または `accepted` のままにする。反映されたら `applied` と `applied_in` (コミット・DEC) を書く。

判定 (`accepted`・`rejected`) は人が行う。以前の strata 中央 backlog (`strata/methodology-backlog.yaml`) は kit backlog へ移された (DEC-2026-10-29-12)。

## 自己完結性チェックリスト

Builder がタスク仕様を書いた後、Worker に渡す前に検証します:

```
□ scope.layer は単一のレイヤーか?
□ scope.can_reference は layer-rules.yaml と一致するか?
□ scope.constraints は、そのドメイン/レイヤーに適用可能な制約を含んでいるか?
□ scope.nodes があり、scope.docs_to_update はカバレッジリゾルバの結果と一致するか?
  (所有する仕様がない場合、仕様の作成が deliverables に含まれているか、意図的に空にした理由があるか?)
□ inputs.reference_files に Worker が必要とするすべてのファイルが明記されているか?
□ inputs.requirements は口頭説明なしでも理解できるか?
□ inputs.conventions に当該レイヤーのコンベンションが要約されているか?
□ deliverables.files に作成/変更するすべてのファイルが列挙されているか?
□ acceptance_criteria は検証可能な形か? (テスト合格、違反 0 件など)
□ acceptance_criteria に制約遵守の検証が含まれているか?
□ acceptance_criteria に docs_to_update の処理 (仕様の更新、または doc_change: none + 理由) が含まれているか?
□ context_budget.max_reference_files ≤ 5 か?
```

**1 つでも満たさない場合は Worker に渡しません。**

Worker がタスクを受け取る際の検証:

```
□ scope.layer が明記されているか?
□ scope.docs_to_update が空の場合、意図的に空にした理由が明記されているか?
□ inputs.reference_files のファイルが実際に存在するか?
□ inputs.requirements が空でないか?
□ deliverables.files が空でないか?
□ acceptance_criteria が 1 件以上あるか?
```

**満たさない項目を見つけたら、直ちに Builder に差し戻します (scope_issue を報告)。**

---

## タスク整理ポリシー

| 時点 | 行動 |
|------|------|
| タスク完了 | `status: completed` + completion セクションを埋める |
| 作業指示全体の完了 | `_order.yaml` の `status: completed` |
| スプリント終了 | 完了した日付フォルダは保管 (削除しない) |
| 90 日経過 | 完了した作業指示フォルダはアーカイブ可能 |

完了したタスクの主要な決定事項は、すでにハンドオフと KB に還流されているため、
タスクファイル自体は**監査証跡 (audit trail)** の目的でのみ保管します。
