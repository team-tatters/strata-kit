# フロントエンド Next.js Convention

> 正本: strata-kit `profiles/frontend.next-web/docs/ja/frontend-next.md` — strata `docs/05-conventions/frontend-next.md` から移管 (オーダー 2026.10.29-06, 2026-10-29)。ルール YAML は `core/rules/`。

> Core の境界: `core/docs/ja/architecture/frontend-web.md`

この文書は、Next.js プロジェクトが Core の Route Surface と App Shell をどのようにマッピングするかを説明します。
Next.js は Core の必須の前提ではありません。

## App Router

- route file (`page.tsx`) は Route Surface です。
- layout/provider/shell file は App Shell です。
- 再利用可能な画面の断片は Feature Block (`Section`) として分離します。
- route params、search params、metadata、authorization boundary は Route Surface で解決します。

### page.tsx の予算

`page.tsx` が行うのは **params の解決 · 認証ガード · metadata · Section を 1 つ配置すること**だけである。サーバー状態フック (query/mutation) と transport 呼び出しは禁止 — Feature Block に下ろす。
Section が 2 つ以上必要なら、`{Route}Page` 組み立てコンポーネントを Feature 領域に置き、page.tsx はそれ 1 つだけをレンダリングする。

## Pages Router

Pages Router はレガシー variant またはプロジェクトの migration zone として管理します。
新規の対象領域では App Router のマッピングを優先します。`pages/**` は layer-map で Route Surface にマッピングし、zone を legacy にする。

## Server / Client Boundary

Server Component、Client Component、server action を使うかどうかは framework convention です。
Core の境界は同じです。transport の直接呼び出しと DataState の呼び出し位置がレイヤー規則を破ってはいけません。

## Multi-zone

複数のアプリ (zone) が rewrite によって 1 つのドメインの下に統合される構造では:

- zone をまたぐシェルパッケージ (ナビゲーション・セッション provider) は **App Shell** である。Feature Block を参照しない。
- zone ごとに QueryClient が分離されない場合があるため、query key の最初の要素は zone 識別子である (`profiles/frontend.next-web/docs/ja/frontend-query-state.md`)。
- zone 間の移動はリンク (URL) だけで行う。他の zone の Feature Block を import しない。
