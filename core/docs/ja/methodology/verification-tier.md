# 検証ティア (Verification Tier)

> 正本: strata-kit `core/docs/ja/methodology/verification-tier.md` (2026-10-29 strata `docs/04-agents/verification-tier.md` から移管、DEC-2026-10-29-11)。

> 実行モード (Verbal/Task) と直交する、検証の独立性の軸。
> 実行モードが*どう作業するか*なら、検証ティアは*結果を誰が検証するか*を定義する。
> `verification_tier` enum の source of truth はこの文書である。

## Tier 定義

| Tier | enum 値 | 定義 | 検証の独立性 |
|------|---------|------|--------------|
| **Solo** | `solo` | 実行主体が自前のチェックリストで検証する | なし |
| **Self-Verified** | `self_verified` | 同じ実行環境/ツール系統内の独立した Reviewer が検証する | 中 |
| **Cross-Verified** | `cross_verified` | 異なる実行環境・ツール系統・モデル系統の Reviewer が検証する | 高 |

- ツール名は Core に書かない。「X が実行 → Y が検証」のような対応づけは、ツールごとのアダプター (AGENTS.md、settings) に置く。
- Reviewer が見るのは会話全体ではなく、**依頼 + diff + 規則 + テスト結果 + チェックリスト**だけである。
- 表示名は `Cross-Verified`、`_order.yaml` に書く enum 値は `cross_verified` である。

## 既定値と必須範囲

```text
Verbal Mode: verification_tier を省略した場合 → solo
Task Mode:   _order.yaml に verification_tier を明記することを推奨
Core の source-of-truth の変更 (layer-rules / naming-convention / task-spec-schema / agent-roles):
             → cross_verified 必須
その他の Core 文書・アダプターの変更 (core/docs/、core/templates/ など):
             → cross_verified 推奨
```

小さな修正のたびに Tier を宣言させない。宣言のコストが検証の利得を上回ると、Strata が重くなる。

## 実装パターン

TDD Writer/Reviewer (`core/docs/ja/methodology/session-splitting.md` §2.4) は、Self/Cross-Verified Tier の実装パターンのひとつである。
セッションをどう分けるかは session-splitting 文書が扱い、検証の独立性の意味と enum はこの文書が持つ。

Cross-Verified の具体的なツール実装は `skills/strata.review/SKILL.md` が扱う。
そのスキルがこの文書の `cross_verified` を実際に行う手順であり、この文書はその手順を定義しない。

## 他の軸との関係

- **Execution Mode**: Verbal/Task の選択と切り替えは `core/docs/ja/methodology/execution-modes.md` が定義する。
- **Agent Operations**: Decision Inbox の `reviewer: cross_verified` はこの Tier を使う。運用規律は `core/docs/ja/methodology/agent-operations.md` が定義する。
- **Methodology Feedback Loop**: Reviewer が見つけた方法論の隙間は、`core/docs/ja/methodology/task-spec-schema.md` の Promotion Gate のフローで backlog に積んで昇格させる。

## デザイン検証軸 (design_verified)

実行モード・検証ティアと直交する三つ目の軸。**デザイン成果物と実装の整合** (`core/docs/ja/architecture/frontend-design-contract.md` §デザイン成果物と整合) を誰が確認したかを定義する。
`_order.yaml` の `design_verified` enum は、この文書が source of truth である。

| 値 | 定義 |
|---|---|
| `none` | UI 成果物なし (`design_ref.kind: none`)、または未検証 |
| `self` | 実装者が整合の定義 (名前・軸・alias・状態軸) で自ら照合した |
| `designer` | デザイン成果物の所有者 (デザイナーまたはデザインツール担当) が確認した |
| `cross` | 異なる実行環境・モデルの Reviewer が、ストーリーレンダー/フレームの照合で確認した |

既定値と必須範囲:

```text
design_ref なし、または kind: none → none
Primitive UI · Semantic Component の新規/変更 (共有 UI パッケージ) → designer 以上を推奨
Feature Block · Route Surface → self 以上
```

`completion.design_sync` が `stale` なら、この軸の値に関係なく完了ではない。`waived` は理由と有効期限を持つ。
