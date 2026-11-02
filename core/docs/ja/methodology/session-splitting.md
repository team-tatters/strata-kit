# 02 — セッション分割ガイド

> 正本: strata-kit `core/docs/ja/methodology/session-splitting.md` (2026-10-29 strata `docs/02-session-splitting.md` から移行、DEC-2026-10-29-11)。

> Builder が作業指示書を書く前に必ず参照する文書です。
> セッション分割は「コンテキスト喪失の防止」に最も効果的な戦略です。

## 1. 分割判断マトリクス

### 1.1 定量基準

| 指標 | 単一セッション | 2-3 セッション | 4+ セッション |
|---|---|---|---|
| 変更ファイル数 | ≤15 | 16-40 | 40+ |
| 影響レイヤー数 | 1-2 | 3 | 4+ |
| 参照ファイル数 | ≤10 | 11-25 | 25+ |
| 想定会話ターン | ≤20 | 21-40 | 40+ |
| 新規ドメイン数 | 1 | 2 | 3+ |
| 必要な探索ステップ | ≤2 | 3-4 | 5+ |

### 1.2 定性基準

**即座に分割が必要な状況:**
- 「まず A を調査し、結果に応じて B の方向を決める」 → 探索セッション + 実装セッション
- 「既存コードをリファクタリングしながら新機能も追加する」 → リファクタリングセッション + 機能追加セッション
- 「フロントエンドとバックエンドを同時に変更する」 → FE セッション + BE セッション
- 「テストを先に書き、実装後に検証する」 → TDD セッション (Writer/Reviewer パターン)

**単一セッションで十分な状況:**
- 単一ファイルのバグ修正
- 既存パターンと同じ CRUD の追加
- テストの補完
- 文書の更新
- 設定の変更

## 2. 分割パターンカタログ

### 2.1 レイヤー順次分割 (Layer-Sequential)

最も一般的なパターン。新機能を土台から積み上げる必要があるとき。

```
依頼: 「注文 (Order) ドメインを新規実装してください」

Session 1: L1 + LM1 (基礎)
├── OrderEntity, OrderStatus enum, OrderType を定義
├── MongoDB Document のマッピング
└── 共通 Audit Entity の継承を設定
    → ハンドオフ: エンティティ/型を確定、次は L2

Session 2: L2 DataLayer (データ)
├── OrderCommandService (create, update, delete)
├── OrderQueryService (findById, findByStatus, search)
├── OrderRepository, OrderTemplate
└── 単体テスト
    → ハンドオフ: L2 完成、次は LM2 または L3

Session 3: L3 Composite (ビジネス)
├── OrderCompositionService
├── 決済連携ロジック (PaymentCoordinator を使用)
├── 在庫引当ロジック (InventoryCoordinator を使用)
└── 結合テスト
    → ハンドオフ: L3 完成、次は Controller

Session 4: Route Controller (API)
├── OrderController (エンドポイント定義)
├── Request/Response DTO
├── Validation 設定
└── API 文書の生成
```

### 2.2 ドメイン並列分割 (Domain-Parallel)

同じレイヤーで複数のドメインを同時に作業するとき。

```
依頼: 「User, Order, Product ドメインの L2 をすべて実装してください」

Session A: L2 — User ドメイン (独立)
Session B: L2 — Order ドメイン (独立)
Session C: L2 — Product ドメイン (独立)

前提: L1 Component が事前に確定していること
前提: 各ドメイン間で L2 の相互参照がないこと (Strata のルールにより保証)
```

### 2.3 探索-実装分割 (Explore-Implement)

方向が不確実な作業で使う。

```
依頼: 「遅い部分を見つけて最適化してください」

Session 1: 探索 (Explore)
├── コード分析とボトルネックの特定
├── プロファイリング結果の解釈
├── 最適化戦略を 3 つ導出
└── 探索結果を $STRATA_VAULT/projects/{name}/sessions/ に記録 (Tier V)
    → ハンドオフ: 最適化戦略を確定、詳細な実装計画

Session 2-N: 実装 (Implement)
├── 確定した戦略に沿ったコード変更
├── 性能テスト
└── 結果の記録
```

### 2.4 TDD 分割 (Writer/Reviewer)

Anthropic が推奨する Writer/Reviewer パターン。

> **検証軸との関係:** この Writer/Reviewer パターンは、`core/docs/ja/methodology/verification-tier.md` の **Verification Tier**
> (Self-Verified / Cross-Verified) をセッション分割で実現した**事例の 1 つ**です。
> Tier の定義は `core/docs/ja/methodology/verification-tier.md` が source of truth であり、ここでは重複して定義しません。
> - Reviewer が同じツール系統なら → **Self-Verified**
> - 別のモデル系統なら → **Cross-Verified** (実装: `skills/strata.review/SKILL.md`)

```
Session 1: テスト作成 (Writer)
├── 要件に基づいてテストケースを作成
├── すべてのテストが失敗することを確認
└── テストファイルを commit

Session 2: 実装 (Writer)
├── Session 1 のテストを通すコードを作成
├── すべてのテストが合格することを確認
└── 実装コードを commit

Session 3 (任意): レビュー (Reviewer)
├── 新しいコンテキストでコードレビュー
├── Session 2 のコードがレイヤールールに従っているか検証
└── リファクタリングを提案
```

### 2.5 フロント-バック分割 (Frontend-Backend)

```
依頼: 「注文機能の UI と API の両方を実装してください」

Session BE: バックエンド
├── L2-L3-Controller を実装
├── API 仕様文書を確定 ($STRATA_VAULT/projects/{name}/tasks/.../api-specs/order.yaml, Tier V)
└── ハンドオフ: API エンドポイント + DTO を確定

Session FE: フロントエンド
├── API 仕様 (Contract) を参照 — 先行条件は BE の完了ではなく **Contract の確定**。mock transport で先に進められる
├── Frontend variant に合わせた Contract/DataState/Feature の順序
├── entry_point (design_first | dev_first | spec_first | change) を宣言 — 順序は固定せず、整合性検査がゲート (core/docs/ja/architecture/frontend-design-contract.md)
└── API 結合テスト + Impl↔Design の整合性確認 (design_sync)
```

BE セッションと FE セッションは、Contract が確定すれば並行できます。FE が先に進む `dev_first` も許可されます — この場合、Contract は FE セッションの成果物となり、BE セッションがそれを検証します。

## 3. 作業指示書 (Task Specification) の形式

Builder が各セッションのために書く文書:

```yaml
# $STRATA_VAULT/projects/{name}/tasks/{date}/{nn}-{title}/task-{id}.yaml
task:
  id: "ORD-L2-001"
  title: "Order L2 DataLayer の実装"
  session_type: "implement"      # explore | implement | review | refactor
  estimated_turns: 15
  estimated_files: 8

scope:
  layer: "L2_DataLayer"
  domain: "order"
  directories:
    - "src/data/order/"
    - "test/data/order/"
  
constraints:
  layer_rule: "@core/rules/layer-rules.yaml#L2_DataLayer"
  naming_rule: "@core/rules/naming-convention.yaml#backend.L2"
  can_reference:
    - "L1_Component"
    - "LM1_Inherite"
  cannot_reference:
    - "L2_DataLayer (他のドメイン)"
    - "LM2_Coordinate"
    - "L3_Composite"

inputs:
  prior_session: "ORD-L1-001"    # 前のセッション ID (なければ null)
  entities:
    - "@src/components/order/OrderEntity.ts"
    - "@src/components/order/OrderStatus.ts"
  reference_implementation:
    - "@src/data/user/UserCommandService.ts"  # パターン参照

deliverables:
  files:
    - path: "src/data/order/OrderCommandService.ts"
      description: "CUD トランザクションサービス"
    - path: "src/data/order/OrderQueryService.ts"
      description: "読み取り専用クエリサービス"
    - path: "src/data/order/OrderRepository.ts"
      description: "MongoDB Repository 実装"
    - path: "test/data/order/OrderCommandService.test.ts"
      description: "CommandService の単体テスト"
    - path: "test/data/order/OrderQueryService.test.ts"
      description: "QueryService の単体テスト"

acceptance_criteria:
  - "すべての単体テストが合格"
  - "レイヤー依存の違反なし (Hook 検証に合格)"
  - "命名コンベンションを遵守"
  - "1 つのメソッドは 1 つのエンティティのみを管理"

context_budget:
  max_reference_files: 5
  max_loaded_tokens: 20000       # 参照ファイルのトークン上限
  compaction_strategy: "file-based"  # 決定事項はファイルに、コンテキストは軽く
```

## 4. Builder の分割提案プロトコル

Builder がユーザーの依頼を受けたときに行う分析手順:

```
ユーザー: 「注文管理機能を全体的に実装して」

Builder の分析:
┌─────────────────────────────────────────┐
│ 📋 作業範囲の分析                        │
│                                          │
│ 影響レイヤー: L1, L2, LM2, L3, Route (5) │
│ 想定変更ファイル: ~35 個                  │
│ 想定参照ファイル: ~15 個                  │
│ 想定会話ターン: ~60 回                    │
│                                          │
│ ⚠ 判定: セッション分割が必要 (4 セッション推奨) │
│                                          │
│ 提案:                                    │
│ Session 1: L1 エンティティ/型 (15 分, ~8 ターン)   │
│ Session 2: L2 DataLayer (30 分, ~15 ターン)        │
│ Session 3: L3 Composite (30 分, ~15 ターン)        │
│ Session 4: Controller + API (20 分, ~12 ターン)    │
│                                          │
│ 並列可能: Session 2 のサブドメイン分離    │
│ 依存チェーン: S1 → S2 → S3 → S4         │
└─────────────────────────────────────────┘
```

Builder はこの分析を**先にユーザーに見せて承認を得た後**、作業指示書を生成します。

## 5. セッション終了シグナル

Builder が現在のセッションを終了してハンドオフすべきタイミング:

| シグナル | 対応 |
|---|---|
| 会話ターンが 15 回を超えた | 現在の作業単位を完了した後にハンドオフ |
| Compaction が発生した | 直ちに状態を保存し、可能なら現在の単位を完了した後にハンドオフ |
| 「先ほどお伝えした…」の再説明が必要になった | コンテキスト喪失の兆候 — 直ちにハンドオフを準備 |
| レイヤー境界をまたぐ作業に入った | 現在のレイヤーを完了して次のセッションへ |
| 探索結果に基づく方向転換 | 探索結果を文書化し、実装は新しいセッションで |
| ユーザーの要件変更 | 変更点を文書化し、再分析して新しい計画を立てる |
| 会話が警告線（既定は約 40 万トークン）を超えた | 進行中の単位を仕上げ、次の作業境界でハンドオフ（事実と仮説の節を含む）して新しいセッションへ。遅くとも限界線（既定は約 60 万）の前に — 5.1 |
| 同じ仮説で試みが二度行き詰まった | 三つ目の回避策を探さず、止まって実測した事実と選択肢を報告 — 5.1 |

### 5.1 再開信号：トークン警告線と同じ仮説での二度の失敗

二つの信号は、作業をその場で打ち切れという基準ではない。進行中の単位を仕上げて次の作業境界で分けよという信号である（カード `rec.session.split-at-task-boundary`）。コンパクションはウィンドウがほぼ満ちたときに起きるので、ウィンドウが大きいほど介入が遅れる。また一つの仮説にこだわる会話は、長さに関係なく判断を曇らせる。二つの信号はこの二つの場合を捉える。

**トークン警告線と限界線。** 会話が約 40 万トークンを超えたら、単位を仕上げ、次の作業境界でハンドオフを書いて新しいセッションへ移る。次の境界が遠くても約 60 万トークンの前には移る。二つの値はウィンドウの比率ではなく固定のトークン数である（DEC-2026-10-31-09、値は DEC-2026-10-31-33）。1M ウィンドウを既定で使うとき、コンパクションよりずっと手前でセッションを整理するための出発値で、私たちの作業での実測の裏付けはまだない。ユーザー設定 `~/.strata/config.yaml` の `session.restart_tokens`・`session.restart_limit` で変え、開始ヘッダーの `restart signal` 行が現在の値を示す。Claude Code では `/context` コマンドかステータスラインで現在の大きさを見る。エージェントが直接読めないときは人が伝える。

**同じ仮説での二度の失敗。** 試みが二度行き詰まったら三つ目の回避策を探さず、止まって実測した事実と選択肢を報告する。同じ仮説とは同じ原因推定である。直した箇所が違っても「原因は X だ」という推定が同じなら同じ仮説である。失敗とは、確かめようとした症状（同じテストの失敗、同じエラー）がそのまま残ることである。報告の後、人が方向を決めるか、ハンドオフに捨てた仮説を書いて新しいセッションで見直す。

**ハンドオフの事実と仮説の節。** 再開信号で終えるセッションは、ハンドオフの「事実と仮説」節に、確認した事実（何で確認したかと共に）、確認できていない推定、捨てた仮説（捨てた理由と共に）を分けて書く（DEC-2026-10-31-11）。次のセッションはこの節を先に読み、捨てた仮説を再び掴まない。台帳で働くセッションは同じ三項目を再開エントリーに書く（agent-operations 5.3）。

### 5.2 会話のトークン予算とコンパクションの時点

| ウィンドウ | 既定の自動コンパクション | `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` のとき | 警告線 40 万・限界線 60 万との関係 |
|---|---|---|---|
| 20 万トークン | 20 万（ウィンドウの上限） | 16 万 | コンパクションが先に来る。このウィンドウではコンパクション発生の信号が警告線の役を果たす |
| 100 万トークン | 約 96 万 7 千 | 約 77 万〜80 万 | 警告線と限界線がコンパクションより先に来る |

固定コストはハーネスのシステムプロンプト、ツール定義、指針、開始ヘッダー、メモリである。strata-kit が加える指針とヘッダーは約 8〜12KB（おおよそ 3 千〜5 千トークン）で（`wizard verify`）、残りはハーネスと接続した MCP サーバーの数によって異なるので `/context` で見る。

既定のコンパクション時点は Claude Code の文書（model-config）の値である。自動コンパクションのウィンドウ（`autoCompactWindow` 設定、`/autocompact` コマンド、`CLAUDE_CODE_AUTO_COMPACT_WINDOW` 環境変数、10 万〜100 万）はそこまで満ちたら圧縮する値で、`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` はこのウィンドウに掛ける比率なのでコンパクションを早めるだけである。環境変数で `500k` のような単位表記を読むのは v2.1.304 以降のみ。大きなウィンドウではコンパクションは警告線よりずっと後に来るので、セッションの整理はコンパクションではなく警告線と限界線が担う。コンパクションの設定を変えるかどうかはユーザーが決める。

## 6. /split-session コマンドの動作フロー

ユーザーが `/split-session` を実行したときに Builder が行う手順:

```
1. 現在の依頼の範囲を分析
2. 分割マトリクスを適用 (セクション 1 を参照)
3. 分割計画をユーザーに提案
4. 承認されたら:
   a. セッションごとに task-{id}.yaml を生成
   b. TASK_TRACKER.md を更新
   c. 依存順序を明記
   d. 最初のセッションをすぐに開始するか、全体計画のみを保存
```
