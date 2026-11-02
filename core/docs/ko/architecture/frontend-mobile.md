# 프론트엔드 Mobile 레이어 아키텍처

> 정본: strata-kit `core/docs/ko/architecture/frontend-mobile.md` — strata `docs/03-architecture/frontend-mobile.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> 기계 판독 가능한 규칙: `core/rules/layer-rules.yaml` → `frontend.variants.mobile` (DEC-2026-09-11-01)
> 이 문서는 네이티브 모바일 UI(SwiftUI·Jetpack Compose) variant 의 사람이 읽는 상세 설명입니다.
> 바인딩: `profiles/frontend.swiftui/docs/ko/frontend-swiftui.md`(검증됨, o-rot) · Compose 바인딩은 아직 없다(§Android).
> 토큰·변형·조합과 디자인 산출물의 정합은 `core/docs/ko/architecture/frontend-design-contract.md` 가 정의합니다.

## 왜 web 과 다른 variant 인가

레이어 8개와 `can_reference` 표는 `web` 과 **완전히 같다**. 첫 SwiftUI 적용(o-rot, 2026-09-10)에서 위반 46건이 전부
파일 경계 문제였고 설계 문제는 0건이었으므로 레이어 의미는 그대로 가져간다. 다른 것은 넷이다.

| 축 | web | mobile |
|---|---|---|
| 어휘 | URL 진입점, `use*Query`, `.service.ts`, Contract 의 `{Name}ViewModel` = 데이터 형상 | 내비게이션 그래프 진입점, `Store`/`Repository`, Contract 는 `UiState`/`UiModel`. **ViewModel 이라는 이름은 상태 소유자를 뜻하므로 Contract 에 쓰지 않는다** |
| Feature 조립 | Feature Block 간 참조 금지 | 같은 도메인 트리의 **부모 → 자식** 조립 허용(`composition: parent_child`). 형제·역방향 금지 |
| 타깃 | 존(zone)·패키지 | 앱·위젯·워치·인텐트가 **파일을 여러 타깃에 넣어** 공유한다. 공유 가능 레이어를 Core 가 정한다 |
| 집행 사다리 | import 경로 정적 분석 | 컴파일러(모듈 경계) 가 정본, 타입 참조 검사기는 모듈 **안** 보조 |

| Layer | can_reference |
|---|---|
| Foundation | 없음 |
| Contract | Foundation |
| DataState | Foundation, Contract |
| Primitive UI | Foundation |
| Semantic Component | Foundation, Contract, Primitive UI |
| Feature Block | Foundation, Contract, DataState, Primitive UI, Semantic Component |
| Route Surface | Foundation, Contract, Feature Block, App Shell |
| App Shell | Foundation, Contract, DataState, Primitive UI, Semantic Component |

## 레이어 ↔ 모바일 구조물

| Layer | SwiftUI | Compose (미검증) |
|---|---|---|
| Foundation | 토큰 `enum`, 순수 `Shape`, 시간대 유틸 | 토큰 `object`, `MaterialTheme` 확장, 순수 유틸 |
| Contract | `Codable` 구조체, `{Name}UiState`, 순수 규칙 `enum` + `static func`, 딥링크 파서 | `data class`, `sealed interface UiState`, use case 순수 함수 |
| DataState | `@MainActor final class {Name}Store: ObservableObject` + `actor {Name}Repository` | `ViewModel`(상태 소유) + `Repository`(`suspend` + `Dispatchers.IO`), Room/DataStore |
| Primitive UI | 디자인 시스템 패키지의 `public struct: View` | `core:designsystem` 모듈의 무상태 컴포저블 |
| Semantic Component | props 만 받는 뷰, `@EnvironmentObject` 0, `{Model}+Style.swift` | `UiState` 만 받는 컴포저블, `hiltViewModel()` 0 |
| Feature Block | `@StateObject`/`@EnvironmentObject` 를 쥔 화면 조각 | `{UseCase}Screen` + `hiltViewModel()` |
| Route Surface | `TabView`·`NavigationStack`·`navigationDestination`, 딥링크 해석 | `NavHost`·type-safe route, 딥링크 |
| App Shell | `@main App`, 전역 Store 생성·`.environmentObject` 사슬, `WidgetBundle` | `Application`·`MainActivity`·Hilt 모듈·`Scaffold` |

## Feature 조립 (composition)

모바일 화면은 계층이다 — 오늘 화면이 기분 시트를 띄우고, 활동 탭이 세션 완료 시트를 띄운다. web 의 "Feature Block 간 참조 금지"
를 그대로 두면 이 조립이 전부 위반이 된다. mobile 은 도메인을 경로로 쓴다.

- 도메인은 `today`, `today/mood` 처럼 `/` 로 트리를 만든다. `.strata/layer-map.yaml` 의 `domain:` 에 명시한다.
- **부모는 자식을 참조할 수 있다.** `today` 의 Feature Block 이 `today/mood` 의 시트를 조립한다.
- 자식 → 부모, 형제 간(`today` ↔ `activity`) 은 금지. 두 도메인이 같은 조각을 쓰면 그 조각은 Semantic Component 로 내려간다.
- TCA 의 부모 리듀서 → 자식 리듀서 스코프, Compose 의 부모 Screen → 자식 Screen 도 같은 규칙이다.

## 타깃 (targets)

Apple 은 앱·위젯·워치·워치 컴플리케이션·앱 인텐트가 각각 타깃이고, Android 는 앱·위젯·Wear 모듈이다. 한 파일을 여러 타깃에
넣는 것이 관례이며 복사는 드리프트의 씨앗이다. Core 는 **무엇을 공유할 수 있는가**만 정한다.

| 레이어 | 공유 | 조건 |
|---|---|---|
| Foundation · Contract · Primitive UI · Semantic Component | 자유 | 상태가 없다 |
| DataState | 조건부 | `layer-map targets.shared[].stateful: true` + **타깃마다 인스턴스가 따로**임을 문서에 명시 (예: 워치 HealthStore 는 자기 HealthKit 을 읽는다) |
| Feature Block · Route Surface · App Shell | 금지 | 타깃마다 화면·진입점·셸이 다르다 |

검사기는 `layer-map.yaml` 의 `targets.shared` 를 읽어 레이어를 대조한다(`target_share` 위반). 정본은 프로젝트 파일
(`project.yml` 의 타깃별 `sources`) 이고 layer-map 은 그 선언을 옮겨 적는다.

## 집행 사다리

| 계층 | 담당 | 강도 |
|---|---|---|
| 모듈 경계 (SPM 패키지 / Gradle 모듈) | Foundation · Contract · DataState · Primitive UI 를 앱 타깃에서 격리. 패키지는 앱을 import 할 수 없다 | **컴파일러 강제 — 정본** |
| 타깃 | 앱·위젯·워치·테스트. 공유는 파일 단위 타깃 추가 | 컴파일러 강제 |
| 타입 참조 검사기 (`check-swift-layers.py`) / ArchUnit·Konsist | 한 모듈 **안** 파일 간 방향·도메인 격리·조립·타깃 공유 | CI blocking |
| style 규칙 | raw 값·시스템 폰트·`Color(hex:)` 신규 유입 | CI blocking, 신규 라인 기준 |
| 편집 훅 | 위와 같은 명령을 바뀐 파일에 — **git 작업 트리 기준**(도구 이벤트가 아니라) | warning → exit 2 로 에이전트 피드백 |

패키지를 하나 올릴 때마다 검사기 몫이 줄어든다. Contract·DataState 가 패키지가 되면 그 경계는 `import` 에 드러나
Core 의 import 기반 훅이 Swift 에서도 동작한다. 브라운필드는 디자인 시스템 패키지 하나로 시작해 Contract → DataState 순으로 올린다.

## Android (미검증)

Compose 대응은 위 표의 오른쪽 열이 전부이고, 실제 프로젝트에서 검증되지 않았다. 적용 시 확인할 것:

- Google 공식 가이드의 UI / Domain / Data 3층은 mobile 의 (Primitive+Semantic+Feature+Route) / Contract / DataState 에 대응한다. 충돌이 아니라 상세화.
- 집행은 Gradle 멀티모듈 + `profiles/backend.kotlin-spring-cqrs/enforcement/` 의 브라운필드 모드(layer-map) 를 재사용한다. Kotlin 은 import 가 명시적이라 타입 참조 검사기가 필요 없다.
- 프로세스 종료 복원(`SavedStateHandle`)·생명주기 인지 수집·DI 모듈 배치(App Shell)·KMP `commonMain`(Contract + DataState 공유) 은 Compose 바인딩 문서가 정한다. 방법론 backlog MB-o-rot-2026-004.

## Core / Convention / Profile 분리

- **Core** (이 문서 + `core/rules/layer-rules.yaml`): 레이어·`can_reference`·조립·타깃 공유 규칙. 플랫폼 독립.
- **Convention** (`profiles/frontend.swiftui/docs/ko/frontend-swiftui.md`, 추후 `frontend-compose.md`): 레이어를 언어 구조물에 붙이는 법, 동시성, 네이밍, 패키지 관리.
- **Profile** (프로젝트 `.strata/layer-map.yaml`·`constraint-registry.yaml`): 파일 매핑, 도메인 트리, 타깃 공유 목록, 예외.
