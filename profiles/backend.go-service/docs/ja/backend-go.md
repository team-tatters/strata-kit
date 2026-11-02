# バックエンド Go — 概念モデルの投影

> 正本: strata-kit `profiles/backend.go-service/docs/ja/backend-go.md` (2026-10-29, DEC-2026-10-29-06)
> 概念モデル: `core/docs/ja/architecture/backend-cqrs.md` — レイヤーの意味・依存方向・同一段の参照禁止はそちらが正本である。この文書は、Go でそれをどう表すかだけを定める。

## 要約

- Go のカプセル化の単位は**パッケージ**である。そのため、レイヤーをディレクトリ(`internal/component/`・`internal/data/` …)に展開せず、**機能(ドメイン)パッケージが先**に来て、レイヤーはその中の**役割ファイル**として現れる。Go コミュニティが避けているのは CQRS ではなく、「レイヤーごとのディレクトリと構造体ごとのインターフェース」である。
- 基準スタック: 標準 `net/http`(Go 1.22 のパターンルーティング)・`pgx`・`sqlc`(SQL から型付きクエリ関数を生成)・`log/slog`。フレームワーク(gin・echo)は任意で、投影は同じである。
- インターフェースは**使う側で**小さく定義する("accept interfaces, return structs")。これはヘキサゴナルのポート所有の原則と同じである。
- 境界はコンパイラ(循環 import 禁止)・`internal/` ディレクトリ・`depguard`(golangci-lint)が守る。

## 配置

```
cmd/api/main.go                 Route の組み立て — サーバー起動、依存の接続(手書きの DI)
internal/
  platform/                     LM1 — db プール・トランザクションヘルパー・設定 (pgxpool, slog)
  kit/                          L1 — 純粋関数・エラーコード・ページ型 (フレームワークの import なし)
  order/                        機能パッケージ 1 つ = ドメイン 1 つ
    order.go                    L1(ドメイン) — エンティティ型・値オブジェクト・純粋な計算
    store.go                    L2 下段 — sqlc 生成 Queries をラップした照会・保存 (Repository・Template の役割)
    command.go                  L2 上段 — CommandService: トランザクション内での作成・更新・削除
    query.go                    L2 上段 — QueryService: 読み取り専用、DTO をそのまま返す
    coordinate.go               LM2 — 同じ関心事の L2 の組み合わせ (必要なときだけ)
    usecase.go                  L3 — CompositeService: ユースケース
    http.go                     Route — ハンドラー: 検証・認証コンテキスト・レスポンス変換、usecase だけを呼ぶ
    queries.sql / db/           sqlc の入力・生成物
  payment/ …
```

| 概念レイヤー | Go では | 名前 |
|---|---|---|
| L1 | `internal/kit` パッケージ、機能パッケージの型・純粋関数 | `PageRequest`, `func Convert(...)` |
| LM1 | `internal/platform` | `NewPool`, `WithTx` |
| L2 下段 | `store.go` — sqlc `Queries` のラッパー | `type store struct{ q *db.Queries }` (小文字: パッケージ外から隠す) |
| L2 上段 | `command.go` · `query.go` | `type CommandService struct`, `type QueryService struct` |
| LM2 | `coordinate.go` または `internal/<関心事>` パッケージ | `type PaymentCoordinator struct` |
| L3 | `usecase.go` | `type CommandCompositeService struct` (パッケージがドメインなので `order.CommandCompositeService`) |
| Route | `http.go`, `cmd/api` | `func (h *Handler) CreateOrder(w, r)` |

- 同じパッケージ内なので、Go コンパイラはファイル間の参照を防げない。**同一段の参照禁止はレビューとリンター**で守る: L2 上段の型同士をフィールドとして持たない、`store` はサービス型を知らない。
- 下段(`store`)と生成された sqlc コードは**小文字の型**にして、パッケージ外(他のドメイン・ハンドラー)から直接使えないようにする。他のパッケージが使ってよいのはサービス型・ユースケース型だけである。
- 名前の重複(stutter)を避ける: `order.OrderService` ではなく `order.CommandService`。

## 依存とインターフェース

```go
// internal/order/usecase.go — L3
type CommandCompositeService struct {
    cmd      *CommandService
    payments PaymentAuthorizer          // 他のドメインは使う側で定義した小さなインターフェースとして受ける
}

type PaymentAuthorizer interface {     // ポート: 利用側(order)が所有
    Authorize(ctx context.Context, orderID int64, amount Money) error
}

func (s *CommandCompositeService) PlaceOrder(ctx context.Context, in PlaceOrderInput) (OrderID, error) {
    id, err := s.cmd.Create(ctx, in.toNew())
    if err != nil { return 0, err }
    return id, s.payments.Authorize(ctx, int64(id), in.Total)
}
```

- ドメインパッケージ同士は互いを import しない(L3 ↔ L3 禁止)。必要なものは使う側のインターフェースで受け、`cmd/api/main.go` が実装を接続する。
- 構造体ごとに先回りしてインターフェースを作らない。インターフェースは、置き換え(テストダブル・別実装)が必要な境界にだけ置く。

## コマンドとクエリ

- 書き込み: `CommandService` のメソッドは `platform.WithTx(ctx, pool, func(q *db.Queries) error {...})` の中で実行される。トランザクションは L2 上段だけに置く。
- 読み取り: `QueryService` は sqlc が生成した照会関数(結合を含む)をそのまま DTO として返す。ドメイン型を経由しなくてよい。

## 強制

| 対象 | ツール |
|---|---|
| ドメインパッケージ間の import 禁止、`kit` は何も import しない | `golangci-lint` の `depguard` ルール(パッケージパス基準)または `go-arch-lint` |
| パッケージ外への露出の遮断 | 小文字の識別子、`internal/` |
| 循環依存 | コンパイラ |
| フォーマット・静的検査 | `gofmt`, `go vet`, `staticcheck` |
| テスト | `go test ./...` (store は testcontainers の実際の PG で) |

## マーカー

Go では godoc コメントに `@` なしで置く(`core/rules/naming-convention.yaml` markers.language_format.go、`core/docs/ja/conventions/strata-markers.md`):

```go
// strata:layer L2-QueryService
type QueryService struct{ … }
```
