# Knowledge Base — ドキュメント形式

> 正本: strata-kit `core/docs/ja/knowledge-base/document-format.md`（2026-10-29 strata `docs/07-knowledge-base/document-format.md` から移行、DEC-2026-10-29-11）。

## 概要

vault 内のすべての `.md` ファイルは YAML frontmatter を含まなければなりません。
Obsidian と MCP サーバー（Phase 3）の両方で解析できる形式を使います。

## Frontmatter スキーマ

```yaml
---
# === 必須フィールド ===
title: "ドキュメントのタイトル"
id: "{接頭辞}-{project}-{slug}"  # 安定 ID — 移動・改名で不変（接頭辞体系: core/docs/ja/knowledge-base/vault-structure.md の安定 ID の節）
type: overview | decision | session | pattern | reference | glossary
      | concept | specification | flow | guide | runbook | constraint | epic | moc | node
created: YYYY-MM-DD

# === 条件付き必須 ===
project: {project-name}       # 特定プロジェクトのドキュメントの場合（横断ドキュメントは id の project の位置に vault）
status: draft | active | review-needed | superseded | archived
sources: ["[[出典セッション/タスク]]"]  # Knowledge 層のドキュメント（KB・pattern）の更新時に必須 — 根拠となる Archive へのリンク（DEC-2026-08-19-03）
nodes: ["{node-id}"]          # 主題ノードへの所属 — decision・session・specification・concept・constraint で必須（「ノード・カバレッジのフィールド」の節）

# === 任意フィールド ===
tags: [namespace/value, ...]  # 名前空間付きタグを推奨
updated: YYYY-MM-DD           # 最終更新日
updated_by: {git user}@{machine}  # 最終更新者 — 書き込みフックが git identity とマシン alias でスタンプ（DEC-2026-09-09-05）
page_order: 1                 # カテゴリ内のドキュメント順（KB 索引用）
author: builder | worker | manual  # 作成主体
machine: {alias}              # 作成マシン — このマシンの alias（STRATA_ENV、env-config.yaml）。別マシンを記したセッション記録は vault-git が拒否する
superseded_by: "[[新しいドキュメント]]"   # status: superseded のとき（置き換えられた側 → 置き換えた側）
supersedes: ["[[以前の決定]]"]   # decision — この決定が置き換える以前の決定（superseded_by の逆方向）
covers: {paths, symbols, endpoints, tables}  # specification・concept — このドキュメントが正本となるコード面
doc_change: none              # session・task — コードは変更したが形状は更新していないことを宣言（doc_change_reason 必須）
aliases: ["旧ファイル名"]         # 移動・改名時に元の識別子を保持
related: ["[[関連ドキュメント1]]"]     # Obsidian wikilink — 言及関係（所有関係は covers）
---
```

## type 別の必須フィールド

| type | 追加の必須フィールド | 説明 |
|---|---|---|
| `overview` | `project` | プロジェクトまたはカテゴリの概要 |
| `decision` | `project`, `status`, `nodes` | ADR。決定の文脈と根拠を含む。任意で `supersedes` |
| `session` | `project`, `machine`, `nodes` | セッションのハンドオフ・ledger。**メタ情報と要約部のみ索引化**（Archive — 2026.08.19-06）。任意で `doc_change` |
| `pattern` | — | プロジェクト横断で再利用するパターン |
| `reference` | — | 外部ドキュメント、標準、仕様の要約参照 |
| `glossary` | — | ドメインまたは技術用語の定義 |
| `concept` | `nodes` | ドメイン概念、ビジネスルール、原理の説明。任意で `covers` |
| `specification` | `status`, `nodes` | 機能仕様、要件、制約条件、受け入れ基準。ノードの最終形状。`covers` を推奨 |
| `flow` | — | ビジネスプロセス、データフロー、シーケンス |
| `guide` | — | 手順の案内、How-to ドキュメント |
| `runbook` | `status` | 運用・障害対応の手順書 |
| `constraint` | `source_adr`, `severity`, `scope`, `rule`, `verification`, `status`, `nodes` | ADR から抽出された、実行可能な単一の制約 |
| `epic` | `constraints`, `domains`, `layers`, `personas`, `status` | PRD の機能単位。constraint へのリンクが必須 |
| `planning` | `project`, `status`, `nodes`, `source`, `implementation` | 外部の企画ツールから取り込んだ企画原文（PRD・ポリシー・Epic/Story）。原文は不変 + `## 実装レビュー` の節。`implementation.status` がレビュー結果を分類する。status は企画の状態（lifecycle_override） |
| `moc` | — | 目次（Map of Content）。`_index/` と各 `_index.md`、生成される静的索引。**生成専用** |
| `node` | `project`, `node` | 主題ノードのページ。最終形状・ポリシー・決定・企画・作業履歴・負債を結合する。**生成専用** |

`moc` と `node` は Index 層です。手で書かず、正本（frontmatter・レコード・toc.yaml）から再生成します。

## ノード・カバレッジのフィールド

主題ノード（node）は、人が読む目次の単位です。1 つのノードが、最終形状（仕様）、ポリシー（制約）、決定、作業履歴を 1 画面に集めるための鍵になります。ノードツリーの正本はプロジェクトの `_meta/toc.yaml` で、ドキュメントは以下の 4 つのフィールドで自分をノードとコードに結び付けます。**この節が値の形式の正本です。** taxonomy は必須かどうかだけを定めます。

### `nodes` — このドキュメントが属する主題ノード

```yaml
nodes: ["orders.checkout-v2.coupon"]   # toc.yaml に定義されたノード id、複数可
```

- ノード id はドキュメント id（`{接頭辞}-{project}-{slug}`）とは**別の名前空間**です。祖先から順にドット（.）でつないだパスで、各要素は kebab-case です。
- decision・session・specification・concept・constraint で必須です。タスク仕様も同じフィールドを使います（`core/docs/ja/methodology/task-spec-schema.md` を参照）。
- セッションとタスクのノードは、カバレッジリゾルバ（変更ファイル → そのファイルを所有する仕様 → その仕様のノード）が導出します。人が選ぶのは、コード変更のないセッションだけです。
- 空配列は許容しますが、検証が警告します。ノードなしが意図なら、本文に理由を残します。

### `covers` — このドキュメントが正本となるコード面

```yaml
covers:
  paths: ["service/order-api/src/main/kotlin/com/example/order/refund/"]   # リポジトリ相対パス、部分文字列マッチ
  symbols: ["RefundCalculationService"]                              # クラス・関数の名前
  endpoints: ["POST /v1/orders/{id}/refunds"]                    # METHOD + パスの接頭辞
  tables: ["refund_items"]                                      # テーブル名
```

- specification・concept でのみ使います。セッション・決定・制約は `covers` を持ちません。それらは `nodes` でノードを指すだけです。
- ファイル単位のパスは使いません。モジュール・パッケージ・コントローラー・ルートの接頭辞のように、移動に対して安定した識別子だけを使います。マッチング規則は layer-map のパスマッチングと同じです（部分文字列、上から順）。
- 1 つの面は、ちょうど 1 つのドキュメントが所有します。重複すると検証が警告します。上位の概念ドキュメントは `up` でつなぎます。
- `covers` は**所有**関係であり、言及ではありません。言及は `related` に置きます。この区別が曖昧になると、1 つのファイルを 5 つのドキュメントが所有することになり、カバレッジゲートがノイズとなって無視されます。
- コードパスのポインタは、vault にソースコードを置かないという原則と衝突しません。コードではなくリポジトリ相対パスだけを記録します（`core/docs/ja/knowledge-base/vault-structure.md`「絶対に含めないもの」）。

### `doc_change` — コードは変更したが形状を更新しないとき

```yaml
doc_change: none
doc_change_reason: "リファクタリングのみ実施 — 外部契約・ポリシーに変化なし"
```

- session・task で使います。`covers` のパスが変更されたのに、その面を所有するドキュメントが更新されておらず、このフィールドもない場合、セッション終了ゲートが該当ノードの**負債**として記録し、警告します。
- 空の値は禁止です。`none` なら必ず理由を付けます。ledger が `next: "none"` に reason を要求するのと同じ原則です。

### `supersedes` — この決定が置き換える以前の決定

```yaml
supersedes: ["[[DEC-2026-08-13-05]]"]
```

- decision で使います。**置き換えられた側の状態は保存せず、導出します**（DEC-2026-09-30-03）。あるレコードの `supersedes` に現れた決定は、索引と DEC ノートで自動的に `status: superseded` と `superseded_by` を持ちます。置き換えられた側のレコードファイルは修正しません。
- すでに記録された決定に置き換え関係を後から追加するときは `python3 "$STRATA_KIT/kb" decision supersede --id 新 --target 旧` を、置き換える決定なしに取り下げるときは `python3 "$STRATA_KIT/kb" decision withdraw --id X --reason ...` を使います。本文に「置き換え」「撤回」と書くだけでは、状態として認識されません。
- KB ドキュメント（decision 以外）は、これまでどおり置き換えられた側に `status: superseded` と `superseded_by` を直接書きます。
- `superseded_by` は逆方向（置き換えられた側 → 置き換えた側）の既存フィールドです。両者は同じ事実の両端です。
- ノードページの「決定」面は、この鎖の末端を現行の決定として、残りを履歴として示します。

## ドキュメントのライフサイクル

```
draft → active → review-needed → superseded → archived
                      ↓                ↓
                   active           archived
```

| 状態 | 意味 | 遷移可能先 |
|------|------|-----------|
| `draft` | 作成中、レビュー前 | active, archived |
| `active` | 有効な現行ドキュメント | review-needed, superseded, archived |
| `review-needed` | 更新が必要（90 日経過で自動フラグ付け） | active, superseded, archived |
| `superseded` | 新しいドキュメントに置き換え済み。`superseded_by` フィールド必須。置き換えた決定が `supersedes` を宣言する場合は対称性検証の対象 | archived |
| `archived` | 無効。検索の重みを下げる | — |

**type ごとの例外**: `constraint` は専用のライフサイクルを使います —
`active → superseded → retired`（taxonomy.yaml `lifecycle_override`）。
制約は draft 状態を持たず、ADR が accepted になった時点で active として作成され、廃止は `retired` と表記します。

## 本文のルール

### 一般ルール

- Markdown 形式（CommonMark + Obsidian 拡張）
- 見出しは `##` から始める（`#` は frontmatter の title との重複を避けるため）
- 1 つのドキュメントは 1 つの主題に集中する（MECE 原則）
- 最大の長さ: 概要/パターン/概念 500 行、ADR 200 行、セッション要約 100 行、仕様 1000 行、目次・ノードページ 300 行
- 本文セクション見出しの正本は taxonomy の `document_types.{type}.body_sections` です。以下の構造ブロックはその描画であり、生成器は taxonomy から見出しを作ります

### 可読性ルール（必須）

- **自己完結した用語**: ドキュメントは、そのドキュメントだけを読んで理解できなければなりません。外部の技術的背景がないと意味が分からない用語 — 英語の専門用語、実装内部の概念、書き手が独自に作った合成語 — をそのまま使いません。どうしても必要なら、**初出のときに 1 行で説明して定義**します。（例: 「materialize」「resolve」「single-flight」「degraded」のような語の代わりに、「最初のリクエスト時に作っておく」「照会して組み立てる」のように**動作を言い換えて**書きます。）
- **本文と締めくくりの流れの一致**: ドキュメント末尾の「未決/要確認/依頼への回答」項目は、本文で実際に定義し展開した内容からのみ引き出します。本文にない新しい概念を、締めくくりの節で初めて持ち出しません。読者が、各未決項目が本文のどの部分につながるのかを 1 対 1 で見つけられなければなりません。
- **判定基準**: 「このドキュメントを初めて見る同じチームの同僚が、外部検索なしで、本文だけを読んですべての用語と未決項目を理解できるか？」 そうでなければ、言い換えるか、本文に根拠を追加します。

### 人が読むドキュメントのルール（必須 — DEC-2026-09-10-01）

読者は人です。エージェントが解析しやすい形では書きません。KB ドキュメント・セッションのハンドオフ・決定レコード・チャットでの報告に同じく適用します。

- **認識できる整理だけを使う。** 一度読んで意味が分からない段落や表は書きません。コードのシンボル・パス・決定 ID を並べて説明の代わりにしません。表は 1 つのセルに 1 つの事実だけを入れ、表の中に表を入れません。
- **重複と冗長を禁止し、1 つの文脈で書く。** 同じ事実を複数の節で繰り返しません。節が変わるときに視点が変わらないよう、1 つの流れでつなぎます。
- **要約が先、根拠は後。** 記述が長くなるときは、冒頭に結論の要約を置き、コードの位置・実測値・引用は後ろの根拠の節に付けます。要約だけを読んで判断できなければなりません。
- **コード形式の順序ラベルを使わない。** `A1·A2·B3` のように、文字と数字を組み合わせたコードでタスク・ドキュメントの順序・項目を分類しません。順序と項目は、意味が分かる短い文で書きます。（「A3 hub プルーニング」ではなく「hub で使わない画面を削除する」。）すでにラベルが付いた既存のドキュメントを引用するときに限り、原文のラベルを括弧で添えます。

### Decision（ADR）本文の構造

```markdown
## 맥락
{決定が必要になった背景}

## 결정
{選んだ方向とその理由}

## 대안
{検討したが選ばなかった方向とその理由}

## 결과
{この決定による影響、トレードオフ}
```

`supersedes` を宣言した決定は、`## 結果` に何をなぜ置き換えるのかを 1 行残します。ノードページが決定の鎖を示すとき、その行が説明になります。

### Session 要約本文の構造

```markdown
## 완료
- {完了した項目}

## 진행 중
- {未完了の項目と現在の状態}

## 결정 사항
- {このセッションで下した決定}

## 주의 사항
- {次のセッションで知っておくべき警告/課題}
```

- 上の 4 つの節は、ハンドオフ**要約部**の構造です。ledger の actor エントリと `next_session` ブロックの形式は `core/docs/ja/methodology/agent-operations.md` §5.3 が正本であり、この構造と共存します。
- コードを変更したのに最終形状を更新していない場合は、frontmatter に `doc_change: none` と理由を宣言し、`## 注意事項` に同じ理由を書きます。

### Pattern 本文の構造

```markdown
## 문제
{このパターンが解決する問題}

## 해결
{パターンの説明}

## 적용 예시
{コードスニペットまたは構造の例}

## 적용 프로젝트
- [[project-a]] — {どのように適用したか}
```

### Constraint Card 本文の構造

ADR から抽出された、実行可能な単一の制約。50 行以内で簡潔に書きます。

```yaml
---
title: "{制約のタイトル — 1 行の名詞形}"
type: constraint
created: YYYY-MM-DD
status: active
source_adr: "[[NNN-adr-slug|ADR-NNN]]"
severity: must-not        # must | must-not | should
scope:
  domains: [{ドメイン}]     # この制約が適用されるビジネスドメイン
  layers: [{レイヤー}]      # この制約が適用される Strata レイヤー
rule: "{1 行の実行可能なルール — MUST/MUST NOT の文}"
verification: code-review  # code-review | unit-test | integration-test | static-analysis
tags: [constraint, severity/{level}, layer/{layer}, domain/{domain}]
aliases: [CC-NNN-NN]       # 固有 ID（ADR 番号-連番）
---
```

```markdown
## 근거
{ADR のどの節から導かれたか、なぜこの制約が必要かを 1-3 行で}

## 위반 시 영향
{この制約が破られるとどんな問題が起きるかを 1-3 行で}

## 검증 방법
{コードレビュー、テスト、静的解析など具体的な確認方法}
```

**Constraint Card の作成ルール:**
- ADR が accepted に遷移したとき、同じセッション内で抽出する（Builder の義務）
- 1 ADR → N 個の Card（通常 3-10 個）
- severity は ADR 原文の言葉から決める: 「必ず/必須/MUST」→ must、「禁止/NEVER」→ must-not、「推奨/SHOULD」→ should
- scope は、この制約が適用されるドメインとレイヤーの範囲
- constraint-registry.yaml に 1 行の要約を同時に登録する

### Epic 本文の構造

PRD の機能単位。constraints フィールドで ADR の制約とつなぐ。

```yaml
---
title: "{機能単位のタイトル}"
type: epic
project: {project-name}
created: YYYY-MM-DD
status: draft
constraints:                # ★ 必須 — この Epic が遵守すべき Constraint Card
  - "[[CC-NNN-01]]"
  - "[[CC-NNN-02]]"
domains: [{ドメイン}]
layers: [{影響を受けるレイヤー}]
personas: [{対象ペルソナ}]  # プロジェクトで定義したペルソナ ID
tags: [epic, domain/{domain}]
---
```

```markdown
## 目標
{この Epic が解決するユーザーの問題を 1-3 行で}

## 受け入れ基準
- {検証可能な完了条件}

## 制約の要約
{constraints フィールドの各 Constraint Card がこの Epic にどう適用されるかの要約}
```

**Epic の作成ルール:**
- constraints フィールドは必須。空配列はレビューのシグナル（意図的な空か漏れかの判別が必要）
- タスクに分割するとき、Builder は Epic の constraints を各タスクの scope.constraints に振り分ける

### Planning 本文の構造

外部の企画ツール（Notion など）から取り込んだ企画原文。多くは依頼がすでに終わっているか、決定が反映済みのドキュメントなので、「依頼」ではなく**企画**として扱います（DEC-2026-09-09-01）。
原文は as-intended、Knowledge の仕様は as-built です。この 2 つを 1 つのドキュメントに混ぜません — 原文の節は修正せず、ドキュメント末尾の `## 実装レビュー` の節だけを更新します。

```yaml
---
title: "{原題}"
id: plan-{project}-{原典の id}          # 再インポートで不変
type: planning
project: {project-name}
status: realized                      # 企画の状態 — requested | planned | in-progress | realized | on-hold | archived
nodes: ["orders.payments-v2"]           # Inbox 承認後に記録（インポーターは候補を出すだけ）
source: "notion:{32hex}"              # 原典の識別子（必須）
source_name: notion-orders-intake        # planning/ 配下のディレクトリ
source_path: "{原典エクスポートの相対パス}"  # 版の追跡
up: "[[plan-{project}-{上位 id}]]"    # Epic/Story のように上位ドキュメントがあるとき
topic: "分類: … · 業務グループ化: … · スプリント: …"   # 原典プロパティの 1 行 — ノードバックフィルプランナーの検索対象
owner: "{名前}"                       # 任意 — 企画の所有者。企画漏れの判定はこの人に尋ねる（なければユーザー、DEC-2026-10-31-35）
implementation:                       # ★ 必須 — 実装レビュー結果の分類
  status: unreviewed                  # unreviewed | implemented | partial | diverged | not-implemented | superseded
  reviewed: YYYY-MM-DD                # unreviewed なら省略
  spec: "[[kb-…]]"                    # 蒸留された最終形状のドキュメント（あれば）
created: YYYY-MM-DD
---
```

```markdown
# {原題}
{原文 — 修正しない}

## 구현 검토

| 項目 | 企画 | 実装 | 差異 | 根拠 |
|---|---|---|---|---|
| {ポリシー項目} | {企画が述べていること} | {コードがしていること} | {なし · 異なる · 未実装} | {コードパス・シンボル・仕様へのリンク} |
```

**Planning の作成ルール:**
- `## 実装レビュー` は項目（ポリシーの文・チェックボックス・Story）単位で書きます。ドキュメントの 1 行要約は `implementation.status` が担います — diverged・partial なら、表に差異の行がなければなりません。
- レビューが仕様の更新につながるなら、その仕様の `sources:` にこのドキュメントを入れ、`implementation.spec` で逆向きに指します。
- `status`（企画の状態）と `implementation.status`（実装レビュー）は別の軸です。「リリース済み」の企画がコードと異なることはあり得ます — それが diverged です。
- ノードページの「企画」面はこの type だけを結合し、バッジ（未レビュー・実装済み・一部実装・企画と異なる・未実装・置き換え済み）で示します。unreviewed の件数と diverged・partial のドキュメントは負債として計上されます。
- 企画と実装が食い違ったら、`## 実装レビュー` の差分行で終わらせず判定依頼として残す（`python3 -m kb divergence add`、ゲートの再照合行は `kb coverage-gate --divergence-inbox`）。判定は人だけが行い、四つのうち一つである: 整合（差分なし）、文書が古い（企画・仕様を実装に合わせる）、企画漏れ（`owner` に補完を依頼）、実装の欠陥（バグタスク）。判定を記録すると（`kb divergence judge`）`implementation.reviewed` がその日になり、同じ変更で再照合を求められなくなる。`implementation.status` は判定に応じて直す（DEC-2026-10-31-35）。

### 企画バンドル (strata.planning)

外部の企画の原典を整理するときは、原本ドキュメント一つではなくバンドルを使います(DEC-2026-11-01-04·05)。`audit/` フォルダを持つ `planning/<bundle>/` フォルダがバンドルです。バンドルの外にある企画ドキュメント(上の形式)は原本のままです。

| 場所 | 中身 | 注入・共有 |
|---|---|---|
| `source/`(または `category: source`) | 原典そのもの、編集しない | しない — 根拠 |
| `audit/facts*.md` | 事実リスト `# \| source location \| type \| content \| role \| axes \| subtopic` | しない — 根拠 |
| `audit/coverage*.md` | 対照表 `# \| source location \| destination \| note` — 七つの行き先 | しない — 根拠 |
| `audit/defects*.md`、`audit/isolated*.md` | 欠陥(`# \| kind \| content \| handling`)、隔離した規則 | しない — 根拠 |
| バンドル直下の `*.md` | 整理版: `planning_doc: prd \| tech-spec \| terms \| tree` | する |

- 整理版にはコードもアーキテクチャも書きません(テーブル、カラム、スキーマ。クラス、モジュール、サービス名。API パス、HTTP コード。フレームワーク、ライブラリ、ベンダー)。そうした事実は対照表の `code` の行き先に送ります。
- 表は列の位置で読むので、見出しはどの言語でもかまいません。行き先は英語(`isolated:` `defect:` `code` `background` `duplicate:#n` `out of scope:`)か韓国語(`격리:` `결함:` `코드` `배경` `중복:#n` `범위 밖:`)で書きます。それ以外の値は `<refined document> R<n>` として読まれます。
- 知識検索が見つけるのは整理版だけです。`python3 -m kb planning check <bundle>` は対照表と整理版をチェックし、`python3 -m kb planning boundary [--list]` は注入の境界を出力します。

## タグ名前空間

すべてのタグは `namespace/value` 形式を推奨します。taxonomy.yaml に定義された名前空間:

| 名前空間 | パターン | 説明 | 値の制限 |
|-------------|------|------|---------|
| `project` | `project/{name}` | プロジェクトのスコープ | 自由 |
| `layer` | `layer/{name}` | Strata アーキテクチャのレイヤー | L1, LM1, L2, LM2, L3, Route, Atomic, Molecule, Partial, Page, Layout, Foundation, Contract, DataState, Primitive_UI, Semantic_Component, Feature_Block, Route_Surface, App_Shell |
| `domain` | `domain/{domain}` | ビジネスドメイン | 自由 |
| `tech` | `tech/{technology}` | 技術またはフレームワーク | 自由 |
| `audience` | `audience/{role}` | 対象読者 | developer, planner, devops, all |

例: `tags: [project/my-api, layer/L2, domain/auth, tech/jwt]`

名前空間のないタグも許容されますが、ビルド時に警告が出ます。
詳細な検証ルール: `core/templates/vault/_meta/taxonomy.yaml` → `tag_namespaces`, `validation`
