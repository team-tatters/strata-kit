# フロントエンド Styling Convention

> 正本: strata-kit `profiles/frontend.next-web/docs/ja/frontend-styling.md` — strata `docs/05-conventions/frontend-styling.md` から移管 (オーダー 2026.10.29-06, 2026-10-29)。ルール YAML は `core/rules/`。

> Core の境界: `core/docs/ja/architecture/frontend-web.md` · デザイン契約: `core/docs/ja/architecture/frontend-design-contract.md` · トークンバインディング: `profiles/frontend.next-web/docs/ja/frontend-tokens.md`

この文書は、スタイリングツールを Core のレイヤーにマッピングする convention です。
Core は特定の UI ライブラリや CSS ツールを要求しません。

## Layer Mapping

- Primitive UI は alias トークンと variant 軸 (`variant · intent · size · state`) だけで見た目を決める。
- Semantic Component は Primitive の軸の値と alias トークンの組み合わせだけで見た目を決める (Composition Legality)。
- Feature Block は特定の use case の画面の断片であり、レイアウトも alias (space·radius) で表現する。

## 軸の値の規則

- 色の軸の値は意図 (`intent`) である。パレット名 (`green · red · blue`) を軸の値として使わない。
- ドメインの状態 (例: `pending · completed`) が必要なら、`intent` に混ぜず別の `status` 軸として置く。
- デザインツールのコンポーネントプロパティ名とコードの props 名を同じに保つ — 整合性検査の前提。

## Project-Specific Mapping

MUI、Tailwind、CSS-in-JS、design-system package といった選択は、project profile またはこの convention のプロジェクト別拡張に置きます。
どのツールを使っても規則は同じである: ユーティリティクラス・スタイルオブジェクトは alias 名を映し、raw 値と T1 名は Foundation の外に出ない。
その選択は Core の規則ではなく、プロジェクトの constraint です。
