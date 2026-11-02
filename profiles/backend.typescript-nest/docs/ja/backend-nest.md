# バックエンド TypeScript(NestJS) — 概念モデルの投影

> 正本: strata-kit `profiles/backend.typescript-nest/docs/ja/backend-nest.md` (2026-10-29, DEC-2026-10-29-06)
> 概念モデル: `core/docs/ja/architecture/backend-cqrs.md`

## 要約

- NestJS はモジュール・DI・provider の構造が JVM の形とほぼ同じで、概念モデルが最もそのまま移る陣営である。モジュールの単位は **Nest モジュール(ドメインごと)** で、レイヤーは **provider の接尾辞とフォルダ**として現れる。
- 基準スタック: NestJS・ORM は Prisma(型付きクライアント)または TypeORM・`class-validator`(リクエスト検証)・テストは Jest。CQRS バス(`@nestjs/cqrs`)は任意である — 概念モデルのコマンド・クエリ分離はサービスの分離だけで十分で、バスはイベント処理が多いときに選ぶ。
- 境界は Nest の DI が守る: **モジュールの `exports` に入れていない provider は、他のモジュールが注入できない。** ファイルの import 境界は `dependency-cruiser` が守る。

## 配置

```
src/
  kit/                          L1 — 純粋関数・エラーコード・型 (Nest の import なし)
  platform/                     LM1 — PrismaService(または DataSource)、トランザクションヘルパー、設定モジュール
  order/
    order.module.ts             モジュール: providers と exports(公開するものだけ)
    data/
      order.repository.ts       L2 下段 — Prisma 呼び出しをラップした Repository
      order.template.ts         L2 下段 — 複雑な照会(raw SQL・結合)
      order-command.service.ts  L2 上段 — 書き込み、トランザクション
      order-query.service.ts    L2 上段 — 読み取り専用、DTO を返す
    coordinate/                 LM2 — 同じ関心事の L2 の組み合わせ (必要なときだけ)
    order-command.composite-service.ts   L3 — ユースケース
    order.listener.ts           L3 — イベント処理 (@OnEvent)
    order.task.ts               L3 — スケジュール (@Cron)
    order.controller.ts         Route — DTO 検証・認証ガード・レスポンス変換、composite だけを呼ぶ
    dto/                        リクエスト・レスポンス DTO (class-validator)
  payment/ …
```

| 概念レイヤー | Nest では | 名前 |
|---|---|---|
| L1 | `src/kit`、ドメインフォルダの純粋関数 | `convertUnit()` |
| LM1 | `PlatformModule` | `PrismaService`, `TransactionHost` |
| L2 下段 | `@Injectable()` の Repository・Template | `OrderRepository`, `OrderTemplate` |
| L2 上段 | `@Injectable()` のサービス | `OrderCommandService`, `OrderQueryService` |
| LM2 | `@Injectable()` の Coordinator | `PaymentCoordinator` |
| L3 | `@Injectable()` の CompositeService・Listener・Task | `OrderCommandCompositeService` |
| Route | `@Controller()` | `OrderController` |

## モジュール境界

```ts
// order.module.ts
@Module({
  imports: [PlatformModule, PaymentModule],
  providers: [OrderRepository, OrderTemplate, OrderCommandService, OrderQueryService, OrderCommandCompositeService],
  controllers: [OrderController],
  exports: [OrderCommandCompositeService],     // 他のモジュールにはユースケースだけを公開
})
export class OrderModule {}
```

- `exports` に L2 サービスや Repository を入れない。他のドメインは、このモジュールのユースケース(または契約インターフェース)だけを注入される — L2 を飛ばす経路は DI の段階で遮断される。
- モジュール間の循環(`forwardRef`)が必要になったら、それは設計上のシグナルである。片側をイベントに置き換えるか、関心事を LM2 に引き上げる。
- 同一段の参照禁止(サービス ↔ サービス)は同じモジュール内なので DI では防げない。コンストラクタ注入対象の検査で守る(下記「強制」)。

## コマンドとクエリ

- 書き込み: `OrderCommandService` が `prisma.$transaction(...)`(または TypeORM の `DataSource.transaction`)の中で実行する。トランザクションは L2 上段だけに置く。
- 読み取り: `OrderQueryService` は `select`・結合の結果をレスポンス DTO にそのまま入れる。エンティティモデルを経由しなくてよい。
- Prisma の生成型(エンティティ)は L2 の外に返さない。L2 の境界で DTO に変換する。

## 強制

| 対象 | ツール |
|---|---|
| 他のモジュールの L2 の注入の遮断 | Nest モジュールの `exports` (実行時の DI エラー) |
| ファイル import の方向(コントローラー → repository 禁止、`kit` は何も import しない、ドメインフォルダ同士の禁止) | `dependency-cruiser` ルール(`profiles/frontend.next-web/enforcement/` の depcruise テンプレートと同じ方式) |
| 同一段サービスの注入禁止 | コンストラクタ引数の型の検査 — eslint のカスタムルールまたは dependency-cruiser のファイル単位ルール |
| フォーマット・リント・型 | `biome` または `eslint`+`prettier`, `tsc --noEmit` |

## マーカー

JSDoc に置く(`core/docs/ja/conventions/strata-markers.md`):

```ts
/** @strata:layer L2-QueryService */
@Injectable()
export class OrderQueryService { … }
```
