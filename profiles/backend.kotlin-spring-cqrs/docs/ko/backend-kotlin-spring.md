# 백엔드 Kotlin/Spring Convention

> 정본: strata-kit `profiles/backend.kotlin-spring-cqrs/docs/ko/backend-kotlin-spring.md` — strata `docs/05-conventions/backend-kotlin-spring.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> Core 경계: `core/docs/ko/architecture/backend-cqrs.md`, `core/rules/layer-rules.yaml`
> 선지불 원칙과 세 경계(데이터 소유·도메인 간 쓰기·도메인 간 읽기): `core/docs/ko/architecture/prepaid-structure.md`

이 문서는 Kotlin + Spring 프로젝트가 Core CQRS 레이어를 구현할 때의 관례를 설명합니다.
Kotlin/Spring은 Core의 필수 전제가 아닙니다.

## 레이어 ↔ 패키지 매핑

JVM에서 레이어 식별의 1급 키는 디렉토리가 아닌 **패키지 세그먼트**입니다
(`core/rules/layer-rules.yaml`의 `language_patterns.kotlin.package_identifier`).

| 레이어 | 패키지 세그먼트 | 예시 |
|---|---|---|
| L1_Component | `..component..` | `com.example.order.component.MoneyUtil` |
| LM1_Inherite | `..inherite..` | `com.example.order.inherite.BaseEntity` |
| L2_DataLayer | `..data.{domain}..` | `com.example.order.data.payment.PaymentQueryService` |
| LM2_Coordinate | `..coordinate.{domain}..` | `com.example.order.coordinate.payment.PaymentQueryCoordinator` |
| L3_Composite | `..composite.{domain}..` | `com.example.order.composite.checkout.CheckoutCommandCompositeService` |
| Route_Controller | `..controller..` | `com.example.order.controller.CheckoutController` |

파일명은 Core 기본 PascalCase 패턴(`{Domain}QueryService.kt` 등)을 그대로 따릅니다. L3 접미는 `CompositeService` 입니다(`{Domain}CommandCompositeService`, 행위가 드러나야 하면 `{Domain}{Action}CompositeService` — DEC-2026-10-29-05).

실제 프로젝트는 위 세그먼트와 다른 패키지를 쓸 수 있습니다. 예를 들어 shop-api 는 L3 를 `rest/<domain>/services/`, LM2 를 `rest/<domain>/coordinator/` 에 둡니다. 레이어는 패키지 이름이 아니라 프로젝트 `layer-map.yaml` 의 경로 매핑으로 판정되므로, 매핑만 맞으면 됩니다.

## L2 두 단과 같은 단 참조

| 단 | Kotlin 요소 | 참조 |
|---|---|---|
| 아래 단 | `*Repository`(Spring Data JPA 인터페이스), `*Template`(jOOQ·QueryDSL DSL) | 위 단을 모른다. Repository ↔ Template 금지 |
| 위 단 | `*CommandService`(`@Transactional`), `*QueryService`(`readOnly`) | 아래 단을 생성자 주입으로 쓴다. 서비스 ↔ 서비스 주입 금지 |

- 두 서비스가 같은 조합을 반복하면 LM2 `*Coordinator` 로 올린다. 기준은 같은 도메인 관심사인가다.
- 단위 환산·산식처럼 주입이 필요 없는 계산은 `object` 로 빼서 단 밖에 둔다(예: `UnitConversions.convert(...)`).
- 엔티티 모듈 안에서만 쓰는 서비스·헬퍼는 Kotlin `internal` 로 숨긴다. `internal` 은 같은 Gradle 소스셋 안에서만 보이므로, 서비스 모듈의 L3 가 우회해서 부르는 것을 컴파일러가 막는다. 생성자를 받는 public 클래스는 `internal constructor` 로 둔다.

## 모듈 경계 (Gradle 멀티모듈)

- 도메인 경계는 가능하면 Gradle 모듈로 분리합니다. 모듈 의존이 `build.gradle.kts`에
  선언되지 않으면 import가 컴파일 에러가 되므로, "L2 간 상호참조 금지"류 규칙이
  도구 없이 컴파일러 수준에서 강제됩니다.
- 모듈 의존은 `implementation`을 기본으로 합니다. `api`는 해당 타입이 모듈의 공개 계약일
  때만 사용합니다 — 전이 의존 누수는 레이어 우회의 통로가 됩니다.
- 모듈 내부의 레이어 방향은 ArchUnit 테스트가 정본으로 검증합니다 (아래 집행 구조).

## Spring 바인딩 관례

- **의존성 주입은 생성자 주입만** 사용합니다. 필드 `@Autowired`·`lateinit var` 주입 금지.
  생성자 주입은 타입 참조를 바이트코드에 남겨 정적 레이어 검증이 동작하는 전제입니다.
- **문자열 빈 조회 금지**: `applicationContext.getBean("...")`, `@Qualifier` 남용 등
  타입 참조를 숨기는 패턴은 레이어 검증을 우회하므로 금지 (ArchUnit이 차단).
- **트랜잭션 경계는 L2 CommandService**: `@Transactional`은 CommandService에 둡니다
  (Core 규칙). QueryService는 읽기 전용 — `@Transactional(readOnly = true)` 또는 생략.
- **JPA Entity는 L2 밖으로 반환하지 않습니다**: LM1의 공통 엔티티 정의를 제외하면,
  Entity는 L2 내부에서 DTO/도메인 타입으로 변환 후 상위로 전달합니다.
  Controller가 `..entity..`·Entity 타입을 참조하면 위반입니다.
- **Controller는 얇게**: URI 정의, 파라미터 검증(`@Valid`), 인증 컨텍스트 주입,
  Response DTO 변환만. 비즈니스 분기는 L3로.
- L1_Component는 Spring import 자체를 금지합니다 (Core 규칙 "외부 프레임워크 import 금지").

## 집행 구조 (3단)

| 계층 | 담당 | 강도 |
|---|---|---|
| Gradle 멀티모듈 | 모듈(도메인) 경계 | 컴파일러 강제 |
| ArchUnit | 레이어 방향 + 도메인 슬라이스 격리 + getBean 차단 | CI blocking (정본) |
| Hook | 편집 시 실시간 피드백 | 휴리스틱 (warning) |

ArchUnit 테스트는 `core/rules/layer-rules.yaml`을 런타임에 직접 읽으므로 규칙을 테스트 코드에
복제하지 않습니다. 템플릿과 적용 방법: `profiles/backend.kotlin-spring-cqrs/enforcement/README.md`

## 마커

KDoc 형식을 사용합니다 (`core/docs/ko/conventions/strata-markers.md`):

```kotlin
/** @strata:port L2-PaymentQueryService */
```
