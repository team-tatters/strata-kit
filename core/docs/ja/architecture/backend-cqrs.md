# バックエンドアーキテクチャ — 概念モデル

> 正本: strata-kit `core/docs/ja/architecture/backend-cqrs.md`。機械可読ルールは `core/rules/layer-rules.yaml`、構造を最初から備える理由は `core/docs/ja/architecture/prepaid-structure.md`。
> 2026-10-29 改訂 — 言語非依存の概念モデルと言語別の射影を分けた(DEC-2026-10-29-06)、同一レイヤー参照の意味を反映した(DEC-2026-09-30-04, strata)、L3 の接尾辞を CompositeService に揃えた(DEC-2026-10-29-05)。

## 要約

- この文書が定めるのは **どの言語でも同じもの** だけである: レイヤーの役割、依存方向、同一段の参照禁止、コマンドとクエリの分離。ディレクトリ・パッケージ・モジュールの配置と名前、強制ツールは **言語別射影文書** が定める(末尾の表)。
- レイヤーは下から上へのみ参照する: L1 → LM1 → L2 → LM2 → L3 → Route。ロジックレイヤー(L2 のサービス段・LM2・L3)は **同じ段の要素どうし** を参照しない。
- L2 は二段である。下の段はデータアクセス(Repository・DSL Template)、上の段はサービス(Command・Query)。サービスは下の段を使い、同じ段どうしは使わない。
- 再利用が必要なら LM2 Coordinator を置く。まとめる基準は「再利用されるか」ではなく **「同じドメイン関心事か」** である。注入を必要としない純粋な計算は、段の外の純粋オブジェクトに切り出す。
- 射影は、その陣営で最も支持されているフレームワークとイディオムに従う。レイヤーをディレクトリ名で強制しない。レイヤーは **役割** であり、どの物理構造で表すかは言語が決める。

## レイヤー

| レイヤー | 役割 | 参照可能 | 同一レイヤー内の参照 |
|---|---|---|---|
| L1 Component | フレームワークに依存しない純粋関数・定数・型。共通・ドメイン・ユーティリティ | なし | 許可(共通ユーティリティ) |
| LM1 Inherite | L2 に注入される共通基盤 — 監査フィールドの Base Entity、DB・キャッシュ接続設定、共通 Repository インターフェース、トランザクション基盤 | L1 | 許可 |
| L2 DataLayer | ドメイン別のデータアクセス。**下の段** Repository・DSL Template、**上の段** CommandService・QueryService | L1, LM1 | 下の段は上の段を知らない。同じ段どうしは禁止 |
| LM2 Coordinate | 同じドメイン関心事の L2 の組み合わせをまとめた、再利用可能なビジネスフロー | L2 | 禁止 |
| L3 Composite | ユースケース一つ。CompositeService・Listener(イベント)・Task(スケジュール) | LM2, L2 | 禁止 |
| Route Controller | HTTP の受信・検証・認証コンテキストの注入・レスポンス変換・エラーのマッピング | L3 | 許可(共通ミドルウェア) |

### L1 Component

フレームワークに依存しない純粋関数、定数、型である。例: 日付ユーティリティ、検証ルール、エラーコード、ページ型、ソート方向。共通(すべてのドメイン)、ドメイン専用、汎用ユーティリティに分かれる。

### LM1 Inherite

L2 が継承または注入を受ける基盤である。Base Entity(createdAt・updatedAt・createdBy などの監査フィールド)、DB・キャッシュ接続設定、共通 Repository インターフェース、トランザクション管理基盤。

### L2 DataLayer — 二段

| 段 | 要素 | ルール |
|---|---|---|
| 下の段 — データアクセス | `Repository`(ORM・ODM インターフェースの実装)、`Template`(DSL ベースの複雑なクエリ) | 上の段を参照しない。Repository ↔ Template どうしも参照しない |
| 上の段 — サービス | `CommandService`(作成・更新・削除、トランザクション)、`QueryService`(読み取り専用) | 下の段を使う。サービス ↔ サービスの参照は禁止 |

- 一つの関数は一つのエンティティだけを扱う。複数のエンティティを組み合わせる仕事は LM2・L3 の責務である。
- クエリ側は複数のテーブルを結合して DTO をそのまま返してよい。読み取りモデルはドメインモデルを経由しなくてもよい。

### LM2 Coordinate

同じドメイン関心事に属する L2 呼び出しの組み合わせが複数の L3 で使われるときに置く。まとめる基準は再利用の回数ではなく **ドメイン関心事が同じか** である — 異なる関心事を「一緒に呼ばれるから」といって一つの Coordinator に入れない。例: `PaymentCoordinator`(決済処理の共通フロー)、`ReviewCoordinator`(レビュードメインの承認ラインのフロー)。

### L3 Composite

一つのユースケースを実行する。

- `{Domain}CommandCompositeService` · `{Domain}QueryCompositeService` — 振る舞いを明示する必要があれば `{Domain}{Action}CompositeService`(例: `EmissionManageCompositeService`)
- `{Domain}Listener` — イベント駆動のバックグラウンド処理
- `{Domain}Task` — スケジュール駆動のバックグラウンド処理

「注文作成」 = `OrderCommandCompositeService.createOrder()`。一つの CompositeService は一つのユースケース群に対応する。

### Route Controller

URI のマッピング、リクエストパラメータ・本文の検証、認証・認可コンテキストの注入、レスポンス DTO への変換、エラーの HTTP ステータスへのマッピングを行う。**Controller から L2 を直接呼ばない** — どんなに単純な CRUD でも L3 を経由する。リスナーやスケジュール Task も同じ L3 を呼ぶ入口なので、入口アダプターを増やしてもユースケースのコードは変わらない。

## 純粋な計算

単位換算や算式評価のように注入を必要としない計算は、どの段にも入れず **注入のない純粋オブジェクト**(Kotlin `object`、Go のパッケージ関数、Rust の自由関数、TS のモジュール関数)に切り出す。そうすれば、同じ段の参照禁止のために計算を複製したり、無理に Coordinator を作ったりする必要がなくなる。

## 依存方向

```
Route_Controller
    ↓ (L3 のみ)
L3_Composite
    ↓ (LM2 または L2)
LM2_Coordinate
    ↓ (L2 のみ)
L2_DataLayer   上の段 Command·Query → 下の段 Repository·Template
    ↓ (L1, LM1)
LM1_Inherite
    ↓ (L1)
L1_Component
```

矢印と逆方向の参照は禁止である。ロジックレイヤーの同じ段の参照も禁止である。

## コマンドとクエリ

コマンドとクエリの分離は **マイクロサービスの分離ではなく、同一プロセス内の経路の分離** である。

- クエリ経路は副作用がないため、別のストア(レプリカ・キャッシュ・外部テーブル・ビュー)へ移したり差し替えたりするコストが低い。
- コマンド経路のトランザクション境界は、サービスを分けるときの自然な分割線になる。
- 最初から二つを分けておけば、モノリスから複数のデプロイ単位へ移るときにレイヤーはほとんど変わらない(prepaid-structure)。

## Variants

二つの variant はどちらもレイヤー方向が同じで、L2 の書き込み側の処理だけが異なる。プロジェクトは `layer-map.yaml` の `variant` で選ぶ(なければ `cqrs`)。

| | CQRS (デフォルト) | ES-CQRS |
|---|---|---|
| 真実の源 | DB の現在の行 | イベントログ |
| L2 書き込み側 | CommandService | Aggregate → EventStore (ES Track) |
| L2 読み取り側 | QueryService | QueryService (同じ) |
| 追加の構成要素 | なし | Aggregate, EventStore, Projection |
| 向いている場合 | 一般的な CRUD、単純なドメイン | 監査証跡、二重の時間軸、イベント駆動のドメイン |

### ES-CQRS

ES-CQRS は L2 の書き込み側を ES Track に置き換える。コマンドは L3 → Aggregate(イベント発行) → EventStore(保存) → Projection(読み取りモデル更新) → L2 QueryService の順に流れ、クエリは L3 → L2 QueryService と流れる。

| 構成要素 | ルール |
|---|---|
| Aggregate | イベントを発行するドメインモデル。L1 だけを参照し、他の Aggregate を直接参照しない(Saga・ProcessManager で通信)。不変条件を検証した後にイベントを生成する |
| EventStore | L1・LM1 だけを参照する。Aggregate・Projection を直接参照しない。PG + JSONB が基本、必要ならスナップショット |
| Projection | ES Track とレイヤーをつなぐ唯一の橋。同期(inline)または非同期(outbox) |

| ルール | 内容 | 範囲 |
|---|---|---|
| R1 | コマンドの入口は必ず L3 CompositeService を経由する | 両方 |
| R2 | Aggregate は L1 以外のレイヤーを import しない | es-cqrs |
| R3 | L2 DataLayer は読み取り専用(CommandService なし) | es-cqrs |
| R4 | Projection が ES → 読み取りモデルの唯一の橋 | es-cqrs |
| R5 | Aggregate 間の直接参照禁止(Saga で通信) | es-cqrs |
| R6 | Rebase ポリシーは Projection の水準(Aggregate はポリシーを知らない) | es-cqrs |

インフラの水準は段階的に選ぶ: PG だけを使う inline projection(追加コストなし、即時の一貫性) → PG outbox + プロセス内 worker → メッセージブローカー → サービス別 EventStore + ブローカー。

## 言語別の射影

同じレイヤーの意味を、各言語で支持されている構造に移す。共通の原則は三つである — **デプロイ・モジュール単位が先** に来て(機能・ドメイン別のモジュール)、レイヤーはその中で **役割(ファイル・型・接尾辞)** として現れ、境界は **その言語のコンパイラ・パッケージシステム・リンター** が止める。

| 言語 | 代表的なスタック | モジュール単位 | レイヤーの表現 | 境界の強制 | 文書 |
|---|---|---|---|---|---|
| Kotlin·Java | Spring Boot · Spring Data JPA · jOOQ | Gradle モジュール(entity・service) | パッケージ + 接尾辞(CommandService・CompositeService) | ArchUnit(このルール YAML を実行時に読む)、Kotlin `internal` | `profiles/backend.kotlin-spring-cqrs/docs/ja/backend-kotlin-spring.md` |
| Go | 標準 `net/http`(1.22 ルーティング) · `pgx` · `sqlc` | 機能パッケージ(`internal/<domain>/`) | パッケージ内の役割ファイル(`command.go`・`query.go`・`store.go`・`http.go`) | 循環 import 禁止(コンパイラ)、`internal/`、`depguard`・`go-arch-lint` | `profiles/backend.go-service/docs/ja/backend-go.md` |
| Rust | `axum` · `tokio` · `sqlx` | Cargo ワークスペースのクレート | クレート(domain・app・infra・api)とモジュール、`pub(crate)` | `Cargo.toml` の依存方向(コンパイル時)、可視性 | `profiles/service.rust/docs/ja/backend-rust-layers.md` |
| TypeScript | NestJS · (Prisma または TypeORM) | Nest モジュール(ドメイン別) | provider 接尾辞とモジュールの `exports` | Nest DI(エクスポートしていない provider は注入不可)、`dependency-cruiser` | `profiles/backend.typescript-nest/docs/ja/backend-nest.md` |

機械可読ルール(`core/rules/layer-rules.yaml`)の `language_patterns` は kotlin・go・rust・typescript の四つの射影を持ち、L2 は `tiers`(lower・upper)で二つの段を宣言する(オーダー 2026.10.29-07 task-04、相互検証 2026-10-29)。現在、強制ツールが読むのは kotlin 射影(ArchUnit テンプレート)とレイヤー水準の `can_reference`・`cross_reference` だけなので、`tiers` と同じドメイン内の同じ段の参照禁止はまだ宣言である — 強制は別の変更で、実測の後に入れる。

## 決定前の拡張 (分析段階)

2026-10-29 の分析で出た次の三つは、まだ決定ではない。決定されたらこの文書と射影文書に反映する。

- **モジュールの公開契約** — 他のモジュールは契約(インターフェース・専用型・イベント)だけを見る。現在は利用側にあるリモート呼び出しインターフェースを提供側へ移し、伝送方式から切り離すこと。
- **書き込み単位をアグリゲートに** — L2 の書き込み側を「エンティティ一つ」から「アグリゲート一つ」に変え、エンティティ単位の書き込みはモジュールの可視性で隠す。上の L2 二段と合わせて扱う。
- **マイグレーション履歴のモジュール所有** — スキーマと履歴テーブルをモジュールが所有し、モジュール間の DB 依存は公開ビューだけを通す。
