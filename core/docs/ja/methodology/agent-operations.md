# Agent Operations（エージェント運用軸）

> 正本: strata-kit `core/docs/ja/methodology/agent-operations.md`（2026-10-29 に strata `docs/04-agents/agent-operations.md` から移行、DEC-2026-10-29-11）。

> Strata の**3番目の直交軸**。Execution Mode（どう作業するか）→ Verification Tier（誰が検証するか）→ **Agent Operations（いつ・どれだけ・どう消化するか）**。
> Verification Tier の定義は `core/docs/ja/methodology/verification-tier.md` が source of truth である。
> 扱うもの: 運用時間帯（夜間バッチ）、予算（budget envelope）、マルチセッション構造、そして急増する成果物を人が消化する方法（Decision Inbox + 自己申告検証ゲート）。
> 状態: `draft`（設計合意済み。§1 packet と §5 ledger CLI（`kb ledger`）は実装済み。§2–4 の成果物検証と Decision Inbox gate には自動化されたツールがない — 旧 strata の agent-ops.py は 2026-06 以降使われていない（DEC-2026-10-29-12）。実際の agent runner は未実装）

## 0. なぜ必要か

Execution Mode と Verification Tier は「1つの作業をいかにうまくやるか」を扱う。
Agent Operations はその上の問題、つまり **エージェントを多数・長時間動かすときに、人がボトルネックにも溺れもしないための運用規律**を扱う。

核となる前提（この軸全体を貫く）:

> エージェントを多く動かすことが目的ではない。**引き渡しの単位・役割・成果物・人が見る表面積を強く制限する**ことが目的である。
> 産出量を増やす装置（マルチセッション・夜間バッチ）はすべて、産出を消化する装置（Decision Inbox・検証ゲート）がなければ人を溺れさせる。

原則の要約:

1. リレーは会話全体ではなく**構造化された packet**を送る。
2. マルチセッションは N:N の会話ではなく **Coordinator 中心（hub-and-spoke）** で運用する。
3. 夜間作業は自律ではなく **budgeted batch** に限定する。
4. 人は raw output ではなく **Decision Inbox** だけを見る。
5. 人が見るラベルは自己申告ではなく、**クロス検証で再判定されたもの**である。

この文書は、runtime 系の方法論 primitive である **Relay Packet、Decision Inbox、review_gate、Shared Session Ledger** の source of truth である。
Quilt ハブのような adapter/runtime は、この primitive を再定義せず、routing・projection・execution surface として消費する。

---

## 1. Relay Packet 階層（トークン削減 + 誤り最小化）

会話全体の送信は禁止。目標はトークン量を減らすことではなく、**トークンあたりの情報密度を高める**ことである。
（交差検討の手順: `skills/strata.review/SKILL.md`、送達は Quilt ハブの `hub_send`）

```text
Level 0: 質問のみ
Level 1: 質問 + 現在の結論 + 論点            ← デフォルト
Level 2: Level 1 + 根拠ファイル/行 + diff 要約  ← デフォルト
Level 3: 必要な抜粋の全文
Level 4: transcript 全体（例外的にのみ）
```

基本は Level 1〜2。散文の会話をそのまま投げると、相手が何を判断すべきかがぼやける。
推奨する packet の形:

```yaml
intent: "review"
decision_so_far: "Verification Tier の正本は verification-tier.md に分離された"
open_questions:
  - "Promotion Gate のフローと backlog スキーマの境界は合っているか?"
evidence:
  - file: "core/docs/ja/methodology/verification-tier.md"
  - file: "core/docs/ja/methodology/task-spec-schema.md"
constraints:
  - "Core 文書にはツール名を入れない"
request:
  - "抜けを1〜2個だけ指摘"
```

- **アンカーを同梱する**: 複数回の往復で相手が合意を忘れて漂流しないよう、毎回 `decision_so_far`（固定要約）を同梱する。
- **薄い packet を遮断する**: `evidence`/`request` が空なら送信前に警告する。空の packet が送られると、検証が行われていないのに Cross-Verified に見える危険がある。（実際の事例: 空の packet を受け取った Reviewer が「検討不可」を正しく返した）

## 2. マルチセッション（Model-A n · Model-B n）

可能だが、N:N で互いに会話させると、トークンの爆発・重複レビュー・責任の不明確化に行き着く。
基本は **hub-and-spoke**。

```text
Coordinator
  ├─ ModelA-Review-1
  ├─ ModelA-Research-1
  ├─ ModelB-CodeReview-1
  ├─ ModelB-Impl-1
  └─ ModelB-Contrarian-1
```

セッション同士を直接話させない。すべて relay queue に成果物を出し、**Coordinator が取りまとめる**。

禁止構造:
```text
Model A1 ↔ Model B1 ↔ Model A2 ↔ Model B2 ...   (ファンアウトは容易で、ファンインが難しい)
```

役割分離:

| 役割 | 責務 | 権限の境界 |
|------|------|----------|
| Primary | 作業を主導 | — |
| Reviewer | 欠陥を探す | 判定ではなく指摘のみ |
| Contrarian | 反対の論理を探す | adversarial verify と連結 |
| Summarizer | 成果物を圧縮 | 内容の変更禁止 |
| Archivist | decision/backlog を整理 | **`open→triaged` まで。`accepted/rejected` は人** |

> **要点**: ファンアウト（マルチセッション）は容易で、ファンイン（統合）が難しい。収束点（Coordinator または人）がなければ、§4 の問題を自ら悪化させる。

作業ツリー（git worktree）規則（DEC-2026-09-17-01）: 並列 Worker・並列セッションであっても、作業ツリーは**ユーザーがその提案を受諾した場合にのみ**作る。自動モードも同じ。デフォルトは、ユーザーが見ているチェックアウトの単一ブランチでの逐次実行であり、作業ツリーが本当に必要なら、必要性・ブランチ名・片付け計画を1項目で提案して返答を待つ。終わったらブランチを残し、作業ツリーを片付けて報告する。正本の規則は `core/docs/ja/methodology/execution-modes.md` § 絶対規則 7。

### 2.1 実行成果物スキーマ

マルチセッション自体を実行する runner はまだない。Coordinator が受け取る plan 成果物は以下のスキーマに従い、レビューの際に **N:N リンク禁止**、役割 enum、Archivist の権限境界を確認する（自動検査ツールは今はない）。

```yaml
multi_session:
  coordinator: "human"        # human | agent
  sessions:
    - id: "review-1"
      role: "reviewer"        # primary | reviewer | contrarian | summarizer | archivist
      tool: "codex"           # adapter label、Core enum ではない
      packet_ref: "$STRATA_VAULT/projects/{n}/relays/..."
      allowed_transitions: [] # archivist は ["open->triaged"] のみ許可
```

禁止:
- `direct_peer_links`: セッション同士が直接会話するリンク。発見したら差し戻す。
- Archivist が `accepted/rejected/applied` まで判定する遷移。

## 3. 夜間バッチプロトコル（22:00–08:00）

自律作業ではなく **budgeted batch**。「決定は人」という原則を破らないために、**夜間=生成、昼間=判定**に分離する。

### 22時前 — 人が準備
```text
1. 今夜処理する work packet を 3〜5 個選ぶ
2. 各 packet に範囲/禁止事項/予算/完了条件を明記する
3. 書き込み許可範囲を制限する (write_scope)
4. 中断条件を定義する
```

### 夜間エージェントの規則
```text
- 新しいアーキテクチャ決定の禁止
- 本番に影響する作業の禁止
- コミット/デプロイ/削除の禁止（または別途承認）
- 曖昧なら中断して質問として残す
- 各 agent は最終1ページの要約のみ提出する
- 成果物はすべて needs_decision で待機（cross_verified まで採用禁止）
```

### budget envelope + ハードリミット
```yaml
agent_budget:
  max_turns: 8
  max_files_read: 12
  max_output_lines: 80
  write_scope: ["assigned/paths/only"]
  stop_if:
    - "architecture decision required"
    - "test cannot run"
    - "scope expands beyond assigned files"
```

> **安全装置の優先順位**: ハードリミット（`max_turns`/`max_files`/`write_scope`）が**第1次**。自己判断による中断（`stop_if: 曖昧なら`）は**第2次** — エージェントが曖昧さを認識できなければ止まらないからである。第1次が常に作動しなければならない。

### 08時 — 人が見るもの
```text
- 決定が必要な項目 / 実際に変更されたファイル / テスト結果 / リスク / 捨てる成果物 / 次の指示候補
```

トークン/時間は正確な数字よりも、**セッションごとの budget envelope + 時間あたりのペーシング**で管理する（上限を明け方に使い果たして空白が生じないように）。

### 3.1 バッチ成果物スキーマ

夜間バッチは runner ではなく **batch spec** でまず固定する。開始前に packet の存在と
hard budget フィールドを確認する（自動検査ツールは今はない）。実行ツールが何であっても、この spec なしに夜間バッチを開始しない。

```yaml
night_batch:
  window: "22:00-08:00"
  packets:
    - id: "nb-001"
      packet_ref: "$STRATA_VAULT/projects/{n}/relays/..."
      owner: "primary"
  budget:
    max_turns: 8
    max_files_read: 12
    max_output_lines: 80
    write_scope:
      - "assigned/paths/only"
    stop_if:
      - "architecture decision required"
      - "test cannot run"
```

夜間の成果物はすべて、§4 の gate で `review_gate.required: true` として扱う。

## 4. Decision Inbox + 自己申告検証ゲート（この軸の核心）

人のボトルネックは「読むこと」ではなく「**判定**」である。エージェントの出力を、情報ではなく**判定可能な単位**に加工する。
人が見る表面は **Decision Inbox ただ1つ**。raw output は保存するだけにする。

### 4.1 出力の強制フォーマット (self-report)
```yaml
result:
  status: completed | blocked | needs_decision | rejected
  one_line: "何をしたか"
  changed_files: []
  evidence: []          # pointer 必須（decision のない長文説明は禁止）
  tests: []
  risks:
    - severity: high | medium | low
      summary: ""
      action_needed: ""
  decisions_needed: []
  discardable_notes_ref: "..."   # raw output はここに保存するだけ
```

### 4.2 自己申告検証ゲート (Self-Report Validation Gate)

**問題**: 上の `status`/`risks` は、エージェントが**自分で**分類する。自分のリスクを過小評価すると（high→low）、人が Inbox だけを見る瞬間に、誤分類された項目が埋もれて通過する。
**実測の根拠**: 自己申告は信用できない — モデルは根拠のない自己主張を事実として登録せず、根拠+コードを渡すと検証したうえで受け入れる。

**解決策**: Decision Inbox に入る**前に**、リレー（クロス検証）が **triage ラベルだけ**を再判定する。

```text
検証対象:
  raw output 全体の再レビュー ❌          (これをやると §1 のトークン削減が崩れる)
  status / risk / decisions_needed / evidence pointer の再判定 ✅
```

フロー:
```text
Agent self-report
  → Relay reclassifies (ラベルのみ)
  → agree    → Decision Inbox に入る
  → disagree → "needs_human_decision" に昇格 (人へ)
```

無限ループの防止:
```yaml
review_gate:
  required: true
  reviewer: cross_verified
  max_review_rounds: 1            # Reviewer が Reviewer を再度呼ぶことを禁止
  disagreement_policy: human_decision   # 不一致 = すぐ Inbox に昇格
```

### 4.3 リスクベースの分岐（すべてを再判定しない）

すべてを再判定するのは高くつく。リスクで分ける。

**再判定必須:**
```text
- status: completed なのにファイル変更がある
- risk: high または unknown
- decisions_needed が存在する
- architecture / schema / migration / deletion / security 関連
- 夜間バッチの成果物（すべて）
- methodology_backlog / decisions の変更
```

**サンプリング（または省略）:**
```text
- low risk / 文書要約 / 探索結果 / テストのみ実行した作業
```

### 4.4 再判定者不在時のフォールバック（安全なデフォルト）

`reviewer: cross_verified` は、別のモデル系列の再判定者を前提とする。
**再判定者がいなければ**（例: 夜間に cross セッションが未稼働）検証できなかったことになるので、
該当項目は自動的に **`needs_human_decision`** に分類する — 検証できていないので通さず、人に上げる。

### 4.5 人が毎日やること (Agent Output Triage)
```text
1. 承認するもの  2. 差し戻すもの  3. 追加で質問するもの  4. 捨てるもの
```
規則: raw output は保存するだけ、人は digest だけを見る、digest には evidence pointer 必須、decision のない長文は禁止。

### 4.6 スキーマ例（task completion 拡張）
```yaml
triage:
  self_report:
    status: completed
    risk: low
    decisions_needed: []
  review_gate:
    required: true
    reviewer: cross_verified
    result: reclassified            # agreed | reclassified | no_reviewer
    final_status: needs_decision
    reason: "low に分類されたが schema 変更を含む"
    max_review_rounds: 1
```

### 4.7 Gate 判定規則

自動検証ツールは今はない（旧 strata の agent-ops.py は 2026-06 以降使われていない、DEC-2026-10-29-12）。以下の判定規則は、レビューと Decision Inbox を整えるときに人・Builder が適用する。

Gate の判定:
- `completed` + 変更ファイル、`risk: high|unknown`、`decisions_needed`、architecture/schema/migration/security/decision のシグナル、夜間バッチの成果物は `review_gate.required: true`。
- reviewer がいなければ `result: no_reviewer`、`final_status: needs_decision`。
- `max_review_rounds` は常に 1。
- `changed_files` があれば `evidence` pointer が必須である。

Decision Inbox の item は `approve | reject | question | discard` のいずれか1つの action としてのみ公開する。raw output は
`discardable_notes_ref` に保存し、Inbox には pointer だけを置く。

---

## 5. Shared Session Ledger（共有セッション台帳）

> 3者の作業者（**user / primary / reviewer**）が1つの要請フローを共有して協業するための**単一の真実の源 (source of truth)**。
> ツールごとの adapter が `primary`/`reviewer` の役割を実際のツールセッションに対応づける。Core スキーマはツール名を enum として持たない。
> reviewer セッションの記憶ではなく、このファイルが文脈を保持する — Strata の第1原則（「セッションは消耗品、文書が永続」）をリレーに適用したもの。

### 5.1 なぜ ledger か（reviewer セッション管理の上位の解法）

リレーを長く回すと「reviewer セッションをどう維持するか」が問題になる。しかし **真実の単位を reviewer セッションではなく共有 ledger に置けば**この問題は解消する:

- reviewer セッションは**揮発してもよい** — 文脈は reviewer の記憶ではなく ledger に残る。
- 次の relay packet の `decision_so_far` / `evidence` / `open_questions` は、reviewer の記憶ではなく **ledger から生成**する（§1 packet）。
- ユーザーはどのツールで始めても、同じ ledger を読んで続きを進める（ツール・開始点を問わない）。

> **ただし、reviewer リセット規則（§1 周辺）は廃止しない。** ledger は*文脈維持*の問題を解くが、
> reviewer が packet にない**古い合意を自分の判断に混ぜる汚染**は別の問題である。リセットは「文脈維持用」ではなく
> **「汚染防止の hygiene」** に格下げして維持する（目的が違うので、ledger ができても消えない）。

### 5.2 位置 · フォーマット

```text
位置: $STRATA_VAULT/projects/{project}/sessions/session-{date}-{slug}.md
      (Core の外、永続・共有・索引に適する。.strata/local はマシンローカルの状態なので不適)
フォーマット: Markdown ファイル + actor ごとの YAML block entry (人の可読性と機械索引を両立)
frontmatter 必須: session_id · project · status · actors · topic · created · next_session · nodes
      (nodes = このセッションが属する主題ノード — §5.7 カバレッジゲートが変更ファイルから導出して突き合わせる)
actor: user | primary | reviewer | coordinator | archivist
tool: optional adapter label    (例: claude | codex — Core enum ではない)
```

### 5.3 エントリスキーマ

各エントリは `## [actor] {ISO8601 timestamp}` ヘッダ + YAML ブロック。append-only、時系列順。

```markdown
## [user] 2026-06-01T12:34:00+09:00
​```yaml
intent: "define shared ledger"
request: "Claude/Codex/User が同じ要請フローを共有できるようにしよう"
decision: null            # ユーザーの決定/中断判断 (あれば)
​```

## [primary] 2026-06-01T12:40:00+09:00
​```yaml
tool: "claude"                         # optional adapter label
from_user: "shared ledger の提案"     # どんな問題を受けたか
action: "上位のフレームで分析"        # どう処理したか
to_reviewer:                        # reviewer に送った packet の要約 (なければ null)
  intent: "review"
  decision_so_far: "ledger is source of truth"
  questions: []
outcome: "受容 | 反論 | 保留"         # reviewer の応答に対する処理 (あれば)
​```

## [reviewer] 2026-06-01T12:45:00+09:00
​```yaml
tool: "codex"                          # optional adapter label
reviewed: "ledger proposal"          # 何を検討したか
verdict: "agree | agree_with_caveat | disagree"
risks:
  - "single writer required"
returned: "返してもらった核心的な意見"
​```

## [primary] 2026-06-01T15:10:00+09:00
​```yaml
action: "再開信号 — 警告線超過 | 同じ仮説で二度失敗"
confirmed: ["確認した事実（何で確認したか）"]
assumed: ["確認できていない推定"]
discarded: ["捨てた仮説（捨てた理由）"]
​```

## next_session
​```yaml
next: "session-2026-06-01-qwer.md"   # close 時に強制 (null 禁止 — チェーン断絶の防止)
reason: "次のフローへ引き継ぐ理由"
​```
```

上の例の `[primary] 2026-06-01T15:10` エントリーは再開エントリーである。再開信号（session-splitting 5.1）で作業を新しいセッションに移すとき、ハンドオフの事実と仮説の節と同じ三項目（confirmed・assumed・discarded）を書く。

### 5.4 単一 writer + ファイルロック (B3 — 同時書き込み汚染の防止)

先ほど実測したセッションファイルの汚染（2つのプロセスが1つのファイルへ同時に append）を ledger で繰り返さないために:

- ツールごとのエージェントプロセスは **ledger ファイルを直接書かない。** 単一の入口 CLI（`python3 "$STRATA_KIT/kb" ledger`）だけを使って書く。
- **単一 CLI ≠ 単一の同時実行**: CLI の内部に**ファイルロック (flock)** がなければならない。複数の adapter がほぼ同時に `append` を呼んでも直列化される。
- ledger は生きている TUI セッションファイル（`~/.claude/...`、`~/.codex/...`）とは**別のファイル**である — TUI の占有とは無関係なので、lsof ガードの対象ではない。

### 5.5 append トリガー (B1 — 誰がいつ残すか)

エントリは自動ではなく**明示的なトリガー**で残す:

```text
- リレーの前後: packet 送信時に primary entry (to_reviewer)、応答の回収時に reviewer entry (verdict)
- ユーザーの決定: user が採用/差し戻し/中断を判断するとき user entry (decision)
- 作業終了: close 時に next_session ポインタを書く (§5.6)
```

### 5.6 セッションチェーニング (B2 — next_session の強制)

ledger を閉じるとき、`next_session.next` を**必ず**埋める。`null` で閉じない —
途切れると次の作業者がフローを引き継げない（ハンドオフの「pending には blocker 必須」と同じパターン）。
続ける作業がなければ `next: "none"` + `reason` を明記して、*意図的な終了*であることを残す。

### 5.7 カバレッジゲート（セッション終了時 — コードは変わったのに形状は変わっていないか）

セッションが閉じるとき、セッション終了ゲート（handoff generator・ledger CLI の validate/close）が、未コミットの decision レコード警告と**同じ場所で**次を検査する:

```text
入力: このセッションが変更したコードファイルの一覧 (タスク completion.files_modified/created、なければリポジトリの diff)
① 変更ファイルごとに、その表面を covers で所有する明細を探す (カバレッジリゾルバ)
② 所有する明細の nodes を集めて、ledger・ハンドオフ frontmatter の nodes と突き合わせる — 漏れていれば埋めるよう警告
③ 所有する明細のうち、このセッションで更新されていないもの (updated がセッション開始より前) があり、
   frontmatter に doc_change: none + doc_change_reason がなければ → 警告 + 該当ノードの負債として記録
④ 所有する明細のない変更ファイルがあれば → 「未所有の表面」警告 (明細の作成または covers の拡張が必要)
```

- **警告であって遮断ではない。** 未コミットレコードの警告と同じ等級である。ただし無視すると、ノードページの「負債」面に残って次の人が目にする。
- `doc_change: none` は §5.6 の `next: "none"` と同じ原則である — 空値禁止、明示的な none + 理由。
- 負債の正本はページではなく、「セッションに doc_change の宣言がない」という事実そのものである。負債を返す方法は2つだけ: 明細を更新する (updated·sources を更新) か、そのセッション文書に doc_change の理由を遡って記載する。
- 値の形式: `core/docs/ja/knowledge-base/document-format.md` の「ノード·カバレッジフィールド」節。レビューポリシー (90日) とは別のシグナルである。

ledger frontmatter の必須フィールドに `nodes` が含まれる (§5.2)。値は ② でリゾルバが導出し、コード変更のないセッションだけ人が直接選ぶ。

---

## 6. 他の軸との関係

```text
②マルチセッション(ファンアウト) ┐
③夜間バッチ(生成)               ├→ ④Decision Inbox + 検証ゲート(ファンイン) ← なければ ①②③ が人を溺れさせる
①リレー(密度↑)                  ┘
⑤ledger ← ①~④ のあらゆる行為が残る共有の真実の源 (ツール・開始点を問わない)
```

- **Execution Mode**: Agent Operations を参照するのみ。（モードの判定/遷移は `core/docs/ja/methodology/execution-modes.md`）
- **Verification Tier**: 検証ゲートの `reviewer: cross_verified` は、`core/docs/ja/methodology/verification-tier.md` の Cross-Verified Tier をそのまま使う。
- **Methodology Feedback Loop**: Archivist の `open→triaged` の境界は、`core/docs/ja/methodology/task-spec-schema.md` の Promotion Gate と backlog lifecycle に従う。判定 (accepted) は人。
- **交差検討**: §1 packet は `skills/strata.review/SKILL.md` が作り、新しいコンテキストのレビュアーに送る（Quilt `hub_send`）。以前の Claude↔Codex リレーツール（strata bridge）は過去の実装であり、使わない。

## 7. 導入の優先順位

```text
①リレー packet の構造化  → 即時可能 (利得が明確、リスクが低い)
④Decision Inbox + ゲート → マスターキー (②③の安全装置、先に設計)
⑤Shared Session Ledger   → リレーを何往復も回す前 (単一 writer+ロックが前提)
②マルチセッション / ③夜間バッチ → ④⑤の設計後 (先にやると人がボトルネック/溺れる)
```

部品はすでにある: 交差検討 (strata.review、クロス検証フィルタ) + backlog lifecycle (判定キュー) + Verification Tier (信頼度ゲート)。fan-in guardrail (成果物の自動検証) はまだない — 旧 agent-ops.py は使われていない。発明ではなく**組み立て**である。

## 8. 未決事項

- `review_gate` 再判定の実際のトークンコストの測定 (薄いゲートという仮定の検証)。
- Coordinator をエージェントにするか、人が兼ねるか (マルチセッションの規模による)。
- マルチセッション runner と夜間 batch runner は未実装。現在の実装は plan/batch/self-report/Inbox 成果物の検証と gate の正規化まで。
- `discardable_notes_ref` (raw output) の保管場所 — vault の relays/ を再利用できる可能性。
- `kb ledger` (旧 session-ledger.py) は実装完了 (append/read/close/validate + flock)。残りの精緻化はクロス検証キューを参照。
- §5.7 カバレッジゲートは実装済み — handoff generator (生成前の検査 + 導出ノードの prefill) と ledger CLI の validate/close (警告) に配線し、close・handoff の後にノードページを再生成する。ledger 必須フィールド `nodes` は導入期なので**警告等級** (エラーへの昇格は遡及の後)。既存文書の遡及 (nodes/covers)・プロジェクトごとの toc.yaml は未着手 (methodology-backlog MB-strata-2026-007)。
- reviewer リセットのトリガー (topic_change / max_rounds 3〜5 / decision_accepted / packet_drift / high_risk) を ledger entry とどう連動させるか。
