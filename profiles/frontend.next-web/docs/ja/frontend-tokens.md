# フロントエンド Token Convention

> 正本: strata-kit `profiles/frontend.next-web/docs/ja/frontend-tokens.md` — strata `docs/05-conventions/frontend-tokens.md` から移管 (オーダー 2026.10.29-06, 2026-10-29)。ルール YAML は `core/rules/`。

> Core の契約: `core/docs/ja/architecture/frontend-design-contract.md`

この文書は、トークン 3 層 (Primitive → Alias → Component) をファイル・ビルド・ユーティリティ CSS にマッピングする慣例である。
形式とツールはプロジェクトが変更でき、変更した場合はここではなくプロジェクト profile に記す。

## 正本ファイル

- 位置: Foundation パッケージ内の単一ファイル (例: `tokens/tokens.json`)。
- 形式: W3C Design Tokens (DTCG) JSON を推奨 — `$value`・`$type`・alias 参照 (`{color.blue.80}`) をサポートし、デザインツール同期プラグインが読み取る。
- 1 つのファイルに T1・T2 の両方を置き、最上位のグループで分ける (`primitive.*`, `alias.*`)。T3 は必要なときだけ `component.*`。
- モードは alias 値の `$extensions.modes` または別の mode ファイルで表現する。名前はモードに関係なく 1 つ。

```json
{
  "primitive": { "color": { "blue": { "80": { "$type": "color", "$value": "#1b4380" } } } },
  "alias": {
    "color": {
      "action": { "primary": { "bg": { "default": { "$value": "{primitive.color.blue.80}" } } } },
      "surface": { "default": { "$value": "{primitive.color.common.0}" } }
    }
  }
}
```

## 生成物 (ビルド段階でのみ解決)

| 生成物 | 利用者 | 備考 |
|---|---|---|
| CSS 変数 (`--color-action-primary-bg-default`) | ユーティリティ CSS · ランタイムテーマ | alias だけを公開する。T1 変数は内部用の接頭辞で隠すか、生成しない |
| TS 定数 (`tokens.color.action.primary.bg.default`) | スタイルオブジェクトが必要な場所 | 型は alias パスから導出 |
| デザインツールの変数 | デザイナー | 同期ツール (例: Tokens Studio · Variables API) — 方向は profile が決める |
| **alias カタログ** (`tokens.md`、生成) | エージェント · レビュアー | 名前・意味・用途を 1 行ずつ。T0 コンテキスト予算に収まるサイズを保つ |

コンポーネントコードは生成物の **alias 名**だけを使う。トークンファイルを直接 import したり、値を計算したりしない。

## ユーティリティ CSS のマッピング

ユーティリティクラスは alias の伝達手段である。クラス名は alias パスをそのまま映す。

| 許可 | 禁止 |
|---|---|
| `bg-surface-default` · `text-muted` · `border-status-pending` | `bg-blue-80`(T1) · `bg-[#1b4380]`(任意の値) · `text-[13px]` |

テーマ設定 (例: Tailwind `@theme`・preset) は生成物であり、手で編集しない。T1 ユーティリティ (`bg-blue-80`) を生成しないことが最も単純な強制である。

## ストーリー (デザインツールがない場合の正本)

- Primitive UI: コンポーネントごとにストーリー 1 つ以上、すべての variant·intent·size の組み合わせを表で公開する。
- Semantic Component: データ状態の軸 (default · loading · empty · error) をそれぞれストーリーにする。
- Foundation: alias カタログのストーリー (色·間隔·影·タイポグラフィ) を置く — デザイナーがツールなしでレビューする画面。

## 検査

| 検査 | 方法 | 位置 |
|---|---|---|
| Foundation の外の raw 値 | 新規行の diff 検査 — hex·rgba·px リテラル·`[…]` 任意の値·T1 クラスパターン | `profiles/frontend.next-web/enforcement/diff-rules.json.template` |
| 例外の期限切れ | `@strata:token-exception … until YYYY-MM-DD` を解析し、今日がその日付を過ぎていれば失敗 | 同じスクリプト |
| トークン変更の承認 | トークンファイルの diff がある PR は本文に DEC id | CI ルールまたは PR テンプレート |

## 禁止

- コンポーネントで T1 名·raw 値·任意の値を使うこと
- トークンファイルを迂回するテーマの手編集
- alias 名にパレット名·画面名を含めること (`color.blue.button`, `color.dashboard.header`)
