# 백엔드 TypeScript(NestJS) — 개념 모델의 투영

> 정본: strata-kit `profiles/backend.typescript-nest/docs/ko/backend-nest.md` (2026-10-29, DEC-2026-10-29-06)
> 개념 모델: `core/docs/ko/architecture/backend-cqrs.md`

## 요약

- NestJS 는 모듈·DI·provider 구조가 JVM 형상과 거의 같아, 개념 모델이 가장 그대로 옮겨지는 진영이다. 모듈 단위는 **Nest 모듈(도메인별)** 이고, 레이어는 **provider 접미와 폴더** 로 드러난다.
- 기준 스택: NestJS · ORM 은 Prisma(타입 있는 클라이언트) 또는 TypeORM · `class-validator`(요청 검증) · 테스트는 Jest. CQRS 버스(`@nestjs/cqrs`)는 선택이다 — 개념 모델의 명령·조회 분리는 서비스 분리만으로 충분하고, 버스는 이벤트 처리가 많을 때 고른다.
- 경계는 Nest DI 가 막는다: **모듈 `exports` 에 넣지 않은 provider 는 다른 모듈이 주입받을 수 없다.** 파일 import 경계는 `dependency-cruiser` 가 막는다.

## 배치

```
src/
  kit/                          L1 — 순수 함수·오류 코드·타입 (Nest import 없음)
  platform/                     LM1 — PrismaService(또는 DataSource), 트랜잭션 헬퍼, 설정 모듈
  order/
    order.module.ts             모듈: providers 와 exports(공개할 것만)
    data/
      order.repository.ts       L2 아래 단 — Prisma 호출을 감싼 Repository
      order.template.ts         L2 아래 단 — 복잡 조회(raw SQL·조인)
      order-command.service.ts  L2 위 단 — 쓰기, 트랜잭션
      order-query.service.ts    L2 위 단 — 읽기 전용, DTO 반환
    coordinate/                 LM2 — 같은 관심사의 L2 조합 (필요할 때만)
    order-command.composite-service.ts   L3 — 유스케이스
    order.listener.ts           L3 — 이벤트 처리 (@OnEvent)
    order.task.ts               L3 — 스케줄 (@Cron)
    order.controller.ts         Route — DTO 검증·인증 가드·응답 변환, composite 만 호출
    dto/                        요청·응답 DTO (class-validator)
  payment/ …
```

| 개념 레이어 | Nest 에서 | 이름 |
|---|---|---|
| L1 | `src/kit`, 도메인 폴더의 순수 함수 | `convertUnit()` |
| LM1 | `PlatformModule` | `PrismaService`, `TransactionHost` |
| L2 아래 단 | `@Injectable()` Repository·Template | `OrderRepository`, `OrderTemplate` |
| L2 위 단 | `@Injectable()` 서비스 | `OrderCommandService`, `OrderQueryService` |
| LM2 | `@Injectable()` Coordinator | `PaymentCoordinator` |
| L3 | `@Injectable()` CompositeService·Listener·Task | `OrderCommandCompositeService` |
| Route | `@Controller()` | `OrderController` |

## 모듈 경계

```ts
// order.module.ts
@Module({
  imports: [PlatformModule, PaymentModule],
  providers: [OrderRepository, OrderTemplate, OrderCommandService, OrderQueryService, OrderCommandCompositeService],
  controllers: [OrderController],
  exports: [OrderCommandCompositeService],     // 다른 모듈에는 유스케이스만 공개
})
export class OrderModule {}
```

- `exports` 에 L2 서비스나 Repository 를 넣지 않는다. 다른 도메인은 이 모듈의 유스케이스(또는 계약 인터페이스)만 주입받는다 — L2 를 건너뛰는 경로가 DI 단계에서 막힌다.
- 모듈 사이 순환(`forwardRef`)이 필요해지면 설계 신호다. 한쪽을 이벤트로 바꾸거나 관심사를 LM2 로 올린다.
- 같은 단 참조 금지(서비스 ↔ 서비스)는 같은 모듈 안이라 DI 가 막지 못한다. 생성자 주입 대상 검사로 지킨다(아래 집행).

## 명령과 조회

- 쓰기: `OrderCommandService` 가 `prisma.$transaction(...)`(또는 TypeORM `DataSource.transaction`) 안에서 실행한다. 트랜잭션은 L2 위 단에만.
- 읽기: `OrderQueryService` 는 `select`·조인 결과를 응답 DTO 에 바로 담는다. 엔티티 모델을 거치지 않아도 된다.
- Prisma 의 생성 타입(엔티티)은 L2 밖으로 반환하지 않는다. L2 경계에서 DTO 로 바꾼다.

## 집행

| 무엇 | 도구 |
|---|---|
| 다른 모듈의 L2 주입 차단 | Nest 모듈 `exports` (실행 시 DI 오류) |
| 파일 import 방향(컨트롤러 → repository 금지, `kit` 은 아무것도 import 하지 않음, 도메인 폴더끼리 금지) | `dependency-cruiser` 규칙(`profiles/frontend.next-web/enforcement/` 의 depcruise 템플릿과 같은 방식) |
| 같은 단 서비스 주입 금지 | 생성자 매개변수 타입 검사 — eslint 커스텀 규칙 또는 dependency-cruiser 의 파일 단위 규칙 |
| 포맷·린트·타입 | `biome` 또는 `eslint`+`prettier`, `tsc --noEmit` |

## 마커

JSDoc 에 둔다(`core/docs/ko/conventions/strata-markers.md`):

```ts
/** @strata:layer L2-QueryService */
@Injectable()
export class OrderQueryService { … }
```
