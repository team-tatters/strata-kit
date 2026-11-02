# 프론트엔드 Swift/SwiftUI Convention

> 정본: strata-kit `profiles/frontend.swiftui/docs/ko/frontend-swiftui.md` — strata `docs/05-conventions/frontend-swiftui.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> Core 경계: `core/docs/ko/architecture/frontend-mobile.md` (`core/rules/layer-rules.yaml` → `frontend.variants.mobile`) · 디자인 계약: `core/docs/ko/architecture/frontend-design-contract.md` · 집행: `profiles/frontend.swiftui/enforcement/`
> v1 2026-09-10 (web variant 바인딩, o-rot 첫 적용) → **v2 2026-09-11** (mobile variant — 어휘·Feature 조립·타깃·집행 사다리·훅, DEC-2026-09-11-01)

이 문서는 SwiftUI 앱이 Core mobile variant(Foundation → … → App Shell)를 구현할 때의 관례다.
SwiftUI 는 Core 의 필수 전제가 아니다. Core 는 "어떤 책임이 어느 레이어를 통과해야 하는가"와 조립·타깃 공유 규칙만 정하고, 이 문서는 그것을 Swift 의 구조물에 붙인다.

## 요약

- 레이어 식별의 1급 키는 **파일이 담는 타입의 역할**이다. 디렉토리가 아니다. `.strata/layer-map.yaml` 이 역할로 재분류하고, 파일은 옮기지 않는다.
- **집행의 정본은 컴파일러다.** 레이어를 로컬 SPM 패키지로 올릴수록 경계가 `import` 로 드러난다. 타입 참조 검사기(`check-swift-layers.py`)는 한 모듈 안 파일 간 방향을 보는 보조다.
- 상태 소유자는 Feature Block 이다: `@StateObject` 로 만들거나 `@EnvironmentObject` 로 받는 뷰. `props` 만 받는 뷰는 Semantic Component. Store 의 **생성**과 환경 주입 사슬은 App Shell 한 곳.
- Feature 는 같은 도메인 트리의 **부모 → 자식**만 조립한다(`today` → `today/mood`). 형제 간 공유 조각은 Semantic Component 로 내린다.
- 타깃 간 공유는 복사가 아니라 타깃 추가다. Foundation·Contract·Primitive·Semantic 은 자유, DataState 는 `stateful: true` + 인스턴스 분리 명시, Feature·Route·Shell 은 금지.
- 토큰은 코드 저장소의 `tokens.json` 이 정본이고 Swift 토큰 파일은 생성물이다. 뷰에서 hex·시스템 폰트·raw 수치는 금지.

## 레이어 ↔ Swift 구조물

| 레이어 | Swift 에서 무엇인가 | 표식 | 금지 |
|---|---|---|---|
| Foundation | 토큰 enum(`Color`·`Font`·spacing), 순수 `Shape`, 상수 enum, 시간대 같은 순수 유틸 | `enum {Name}Tokens` · `static let` 만 | `ObservableObject`, I/O, `UserDefaults`, 뷰 |
| Contract | `Codable` 모델·DTO, 화면 상태 값 `{Name}UiState`, 순수 계산 규칙(`enum` + `static func`), 딥링크 파서, 포트 프로토콜 | 값 타입 · `import Foundation` 만 | SwiftUI import, 색·아이콘 같은 **표시 속성**, **`ViewModel` 이라는 이름**(모바일에선 상태 소유자를 뜻한다) |
| DataState | `Store`(메인 액터 상태 소유자) + `Repository`/`Service`/`Session`(격리된 I/O) | `@MainActor final class {Name}Store: ObservableObject` · `actor {Name}Repository` | 뷰 렌더링, 다른 도메인 Store 직접 참조 |
| Primitive UI | 디자인 시스템 패키지의 도메인 무지 뷰 (Button·Chip·Row·TabBar) | `public struct {Name}: View` · 축(variant·intent·size) props · **반드시 별도 패키지** | 도메인 모델, Store |
| Semantic Component | props/UiState 만 받아 그리는 의미 있는 뷰 — 차트·무대·헤더·빈 상태, 모델의 표시 속성 확장 | `struct {Domain}{Purpose}View: View` · `{Model}+Style.swift` · `@EnvironmentObject` 0 | Store 접근, `@StateObject` |
| Feature Block | 화면 조각의 상태 소유자 — `@StateObject`/`@EnvironmentObject` 로 Store 를 쥐고 아래로 props 전파 | `struct {UseCase}View` · `{UseCase}Sheet` · 도메인 트리 `today/mood` | 형제 도메인 Feature 참조, 내비게이션 그래프 소유 |
| Route Surface | `TabView`·`NavigationStack` 진입점, `navigationDestination`, 탭 선택, 딥링크 해석 | `MainTabView` · `{Flow}Flow` | Store **생성·참조**(주입은 App Shell), 재사용 UI export |
| App Shell | `@main struct App`, 전역 Store 생성·`.environmentObject` 사슬, `WidgetBundle`, 셸 크롬(탭바) | `{Name}App` · `{Name}Shell` · `{Name}Bundle` | 도메인 use case 로직, Feature 직접 참조 |

`can_reference` 는 Core 표 그대로다. SwiftUI 특유의 세 가지만 덧붙인다.

- **환경 주입은 참조다.** `@EnvironmentObject var store: TodoStore` 는 그 파일이 `TodoStore` 를 참조한 것이다. Semantic Component 에는 `@EnvironmentObject` 가 없어야 한다.
- **`@StateObject` 생성은 소유다.** Store 생성은 App Shell 에서, 화면 한정 상태는 Feature Block 에서만 한다. Route Surface 가 Store 를 만들면 위반이다 (o-rot `MainTabView` 가 스토어 8개를 만들던 형상이 이 규칙을 낳았다).
- **`@main` 은 App Shell 이다.** 온보딩/메인 분기 같은 진입점 판단이 `@main` 에 있으면 그 분기를 `{Name}Shell` 뷰로 내리고 `@main` 은 Store 생성·주입만 남긴다. 분리 전까지는 layer-map `exceptions` 에 DEC 와 함께 둔다.

## Feature 조립

```
Features/Today/TodayView.swift          domain: today        ← @EnvironmentObject 로 Store 를 쥔다
Features/Today/Mood/MoodSheetView.swift domain: today/mood   ← 부모(today)가 .sheet 로 띄운다
Features/Activity/ActivityView.swift    domain: activity     ← today 와 형제. MoodSheetView 를 쓰면 위반
```

- 도메인은 `layer-map.yaml` 의 `domain:` 에 `/` 경로로 적는다. 검사기는 부모 → 자식 참조만 통과시킨다.
- 두 형제가 같은 시트를 띄우면 그 시트의 렌더 부분을 Semantic Component(`MoodPickerView`)로 내리고, 각 Feature 가 자기 Store 로 감싼다.
- TCA 를 쓰면 부모 리듀서의 `Scope` 가 정확히 이 간선이다. 패턴 이름은 정하지 않는다 — 간선 방향만 지킨다.

## 타깃

- 폰·위젯·워치·컴플리케이션·인텐트는 각각 타깃이다. 공유는 `project.yml` 의 타깃별 `sources` 에 **파일을 더하는 것**이고 복사본은 만들지 않는다.
- 공유 목록을 `layer-map.yaml` 의 `targets.shared` 에 옮겨 적는다. 검사기가 레이어를 대조한다(`target_share`).
- DataState 를 두 타깃이 공유하면(예: 워치가 폰의 `HealthStore` 파일을 씀) `stateful: true` 로 선언하고, 타깃마다 인스턴스가 따로이며 무엇을 각자 읽는지 문서에 적는다.
- 타깃 간 데이터 교환(App Group `UserDefaults`, `WatchConnectivity`)은 DataState 의 `{Name}Session`/`{Name}Bridge` 파일 하나가 맡는다. 뷰가 `UserDefaults(suiteName:)` 을 직접 열면 위반이다.

## 상태 소유와 관찰 모델

- 기본은 `ObservableObject` + `@Published` + `@MainActor`. Store 는 클래스, 모델은 구조체.
- `@Observable`(Observation 프레임워크)은 **배포 타깃이 iOS 17 / watchOS 10 이상일 때만** 쓴다. 두 모델은 프로퍼티 래퍼가 다르고(`@StateObject` ↔ `@State`) 갱신 단위가 달라 혼용하면 초기화 시점이 어긋난다 — 한 프로젝트는 한 모델만 쓴다. ([Apple: Observation](https://developer.apple.com/documentation/observation), [Squires: not a drop-in replacement](https://www.jessesquires.com/blog/2024/09/09/swift-observable-macro/))
- Store 는 자기 도메인만 안다. 두 Store 를 엮는 조립은 Feature Block 이 한다. Store 가 다른 Store 를 참조하면 DataState 도메인 교차 참조 위반이다.
- 영속은 Store/Repository 안에서 끝낸다. `UserDefaults.standard`·파일 I/O 가 뷰나 Contract 에 나타나면 위반이다.

## 동시성

- Swift 6 언어 모드는 데이터 경합을 컴파일 오류로 만든다. 도입은 **점진적**으로: `SWIFT_STRICT_CONCURRENCY = targeted` → `complete` → 언어 모드 6. 한 번에 켜지 않는다. ([Apple: Adopting strict concurrency](https://developer.apple.com/documentation/swift/adoptingswift6))
- 뷰가 만지는 Store 는 전부 `@MainActor`. I/O 는 `actor {Name}Repository` 또는 `nonisolated` + `Task { @MainActor in … }` 로 Store 에 되돌린다. 델리게이트 콜백(`WCSessionDelegate` 등)도 같은 관례.
- 모델(구조체)은 `Sendable` 을 기본으로 맞춘다. Contract 패키지가 `Sendable` 만 내보내면 액터 경계가 저절로 맞는다.

## 네이밍 — Swift API Design Guidelines 를 그대로

정본은 [swift.org API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/) 다. Core `core/rules/naming-convention.yaml` 의 `common.case_styles` 와 충돌하는 곳은 **Swift 관례가 이긴다** (아래 표). 파일명은 담는 최상위 타입과 같게 한다.

| 항목 | Swift | Core 기본과 다른 점 |
|---|---|---|
| 타입·프로토콜 | `UpperCamelCase` | 같음 |
| 함수·변수·프로퍼티·case | `lowerCamelCase` | **enum case 는 lowerCamelCase** — Core 의 `UPPER_SNAKE` 를 쓰지 않는다 |
| 상수 | `lowerCamelCase` (`static let graceDays`) | Core 의 `UPPER_SNAKE` 를 쓰지 않는다 |
| 불리언 | 단언문으로 읽힌다 — `isEmpty` · `hasWatch` · `canDelete` | Core Props 규칙과 같음 |
| 화면 상태 값 | `{Name}UiState` (Contract) | Core web 의 `{Name}ViewModel` 을 쓰지 않는다 — 모바일에서 ViewModel 은 상태 소유자 |
| 상태 소유자 | `{Name}Store` (DataState) | Core web 의 `use{Name}State` 대응 |
| 팩토리 | `make…` | |
| 변이/비변이 쌍 | `sort()` / `sorted()`, `append` / `appending` | |
| 프로토콜 | 무엇인가 → 명사, 능력 → `-able` `-ible` `-ing` | |
| 약어 | 케이스를 균일하게 — `hrvSeries` · `isHRV`(전부 대문자 시작 위치에서만) | |
| 인자 라벨 | 문장처럼 읽히게. 첫 인자가 전치사구면 라벨 필수 | |
| 금지 접미 | `Manager` · `Helper` · `Impl` | Core 와 같음. `Handler` 는 델리게이트 메서드에만 |

Props 에 해당하는 것은 뷰의 `init` 인자·저장 프로퍼티다. Core `Props` 규칙을 적용한다: 부모 상태는 접두 없는 명사, 변경 요청은 `on{State}Change`, 이벤트는 `on{Event}`, 내부 핸들러는 `handle{Event}`. SwiftUI 에서는 `Binding<T>` 이 "값 + 변경 쌍" 이므로 Core 의 `{state}Control` 묶음에 해당한다 — 여러 자식이 같은 상태를 쓰면 `Binding` 하나를 내려보낸다.

`layer-map.yaml` 의 `naming:` 블록은 검사기가 집행하지 않는다. 파일명 = 최상위 타입명은 관례이며 리뷰에서 본다.

## 집행 사다리 — 컴파일러가 정본

| 계층 | 담당 | 강도 |
|---|---|---|
| 로컬 SPM 패키지 (`Package.swift`) | Foundation · Contract · DataState · Primitive UI 를 앱 타깃에서 격리. 패키지는 앱을 import 할 수 없고, 패키지 간 의존은 `dependencies:` 로 선언한 방향만 | **컴파일러 강제 — 정본** |
| 타깃 (`project.yml` / Xcode 타깃) | 앱·위젯·워치·테스트. 공유 소스는 파일 단위로 타깃에 더한다 | 컴파일러 강제 |
| `check-swift-layers.py` | 한 모듈 **안**의 파일 간 레이어 방향·도메인 격리·Feature 조립·타깃 공유 | CI blocking |
| `--style` 규칙 / SwiftLint custom_rules | raw 값·시스템 폰트·`Color(hex:)` 같은 신규 유입 | CI blocking, 신규 라인 기준 권장 |
| 편집 훅 | 같은 검사기를 **git 작업 트리에서 바뀐 파일**에 (`--changed`) | exit 2 → 에이전트 피드백 |

- **패키지 단계.** 브라운필드는 디자인 시스템(Foundation + Primitive UI) 패키지 하나로 시작한다. 다음은 Contract(모델·규칙·`Sendable` 값), 그다음 DataState. 한 단계 올릴 때마다 그 경계는 `import` 에 드러나 Core 의 import 기반 훅이 Swift 에서도 동작하고, 타입 참조 검사기의 몫은 앱 타깃 내부(Semantic → Feature → Route → Shell)로 줄어든다. 골격: `profiles/frontend.swiftui/enforcement/Package.swift.template`.
- **패키지 관리는 SPM 하나로 한다.** CocoaPods·Carthage 는 신규 도입하지 않는다. ([DECODE: modularize with SPM](https://decode.agency/article/project-modularization-swift-package-manager/), [Nimble](https://nimblehq.co/blog/modern-approach-modularize-ios-swiftui-spm))
- **프로젝트 생성은 선언적으로 한다.** `.xcodeproj` 를 손으로 편집하지 않고 XcodeGen `project.yml`(또는 Tuist) 에서 생성한다. 타깃 그래프가 텍스트로 리뷰되어야 레이어·타깃 결정이 PR 에 드러난다. ([XcodeGen vs Tuist](https://medium.com/@sayefeddineh/xcodegen-vs-tuist-choosing-the-right-tool-for-xcode-project-generation-bea093c6e105))
- 외부 패키지는 **버전을 고정**(`exact` 또는 `upToNextMinor`)하고 `Package.resolved` 를 커밋한다.
- **편집 훅은 도구 이벤트가 아니라 git 기준으로 건다.** Claude Code 의 PostToolUse 를 `Write|Edit` 에만 걸면 Bash(sed·heredoc) 편집이 검사를 건너뛴다. matcher 를 `Write|Edit|Bash` 로 두고 검사기가 Bash 이벤트에서 `--changed`(git status 기준) 로 폴백한다. 설정 템플릿: `profiles/frontend.swiftui/enforcement/settings.json.template`.

## 토큰·타이포 (디자인 계약 바인딩)

- 정본은 저장소의 `tokens.json`. Swift 토큰 파일(`{Name}Tokens.swift`)은 그 생성물이며 `Color(hex:)` 초기화는 **이 파일 안에서만** 나타난다.
- 뷰는 alias 이름만 쓴다: `OrotColor.sage700` ○ / `Color(hex: "507663")` ✗ / `.font(.system(size: 13))` ✗ / `.padding(14)` 는 spacing 토큰으로.
- 새 alias 는 아키텍처 결정이다 — decision 레코드 + `tokens.json` → Swift 순서. 임시 값은 `/// @strata:token-exception … until YYYY-MM-DD`.
- 타이포 토큰은 세 축을 가진다: 텍스트 스케일(제목·본문·캡션), **아이콘 크기**(`icon.sm/md/lg` — SF Symbol 의 `.font(.system(size:))` 대체), **플랫폼 스케일**(워치는 폰의 축소가 아니라 별도 스케일). 축이 없어 `.font(.system` 이 남으면 토큰 추가 DEC 가 먼저다.
- 접근성은 토큰이 담는다: 텍스트 대비 4.5:1 이상인 alias 만 텍스트에 쓰고, 그 미만은 비텍스트 전용으로 이름에 표시한다. Dynamic Type 은 `Font.custom(_:size:relativeTo:)` 로 토큰이 흡수한다.

## 포맷·린트

- 포맷터는 Xcode 16+ 툴체인에 들어 있는 **swift-format** (`swift format`, `xcrun --find swift-format`) 을 쓴다. 설정은 `.swift-format` 파일 하나(템플릿: `profiles/frontend.swiftui/enforcement/swift-format.json.template`). ([Xcode 16 swift-format](https://mjtsai.com/blog/2024/11/06/swift-format-in-xcode-16/))
- 린트는 SwiftLint 를 **선택**으로 둔다. Strata 가 요구하는 것은 `custom_rules` 몇 개뿐이라 SwiftLint 없이도 `check-swift-layers.py --style` 이 같은 정규식을 실행한다. SwiftLint 를 쓰면 `profiles/frontend.swiftui/enforcement/swiftlint-strata.yml.template` 을 `.swiftlint.yml` 에 합친다. ([SwiftLint custom rules](https://github.com/realm/SwiftLint#defining-custom-rules))

## 마커

`///` 문서 주석에 둔다 (`core/docs/ko/conventions/strata-markers.md`):

```swift
/// 오늘 상태 번역 규칙 — 순수 함수만.
/// @strata:layer Contract
/// @strata:domain today
enum StateEngine { … }
```

## 테스트

- 단위 테스트 타깃은 `@testable import {App}` 으로 Contract·DataState 를 직접 검증한다. 패키지가 된 레이어는 패키지 자체의 테스트 타깃에서. 뷰 테스트는 스냅샷이 아니라 **Store → 상태 → 화면 문구** 경로를 검증한다.
- Store 테스트는 `UserDefaults(suiteName: UUID)` 나 임시 디렉토리로 격리한다. `.standard` 를 테스트에서 건드리지 않는다.
- 파일명은 `{Type}Tests.swift`, 테스트 타깃 디렉토리는 layer-map 에서 `_test` 로 제외한다. 검사기는 `swift.sources` 밖의 파일을 조용히 건너뛴다.

## 브라운필드 도입 절차

1. `profiles/frontend.swiftui/enforcement/layer-map.yaml.template` 로 `.strata/layer-map.yaml` 을 만든다 (`variant: mobile`). **역할로** 분류하고 파일은 옮기지 않는다. Feature 도메인은 `/` 트리로.
2. `check-swift-layers.py --summary` 로 미매핑 0 을 만든다.
3. `project.yml` 의 타깃별 공유 소스를 `targets.shared` 에 옮겨 적는다. DataState 공유는 `stateful: true` + 문서.
4. `--all` 로 위반을 본다. 셋으로 가른다 — 지금 고칠 것 / `exceptions` 에 DEC 와 함께 등록할 것 / `--write-baseline` 으로 동결하고 신규만 막을 것.
5. `--style` 을 켜고 같은 절차를 반복한다.
6. CI 에 `--all --style --ignore-known` 을 건다. 편집 훅은 `profiles/frontend.swiftui/enforcement/settings.json.template` (Write|Edit|Bash → stdin, Bash 는 `--changed`).
7. 패키지 사다리를 오른다: 디자인 시스템 → Contract → DataState. 각 단계마다 layer-map 의 `swift.sources` 와 매핑을 갱신하고 baseline 을 재생성한다.

## 이 문서가 정하지 않는 것

아키텍처 패턴 이름(MVVM·TCA·Clean)은 정하지 않는다. 어떤 이름을 쓰든 "Store 는 DataState, 상태 소유는 Feature Block, props 뷰는 Semantic, 조립은 부모 → 자식" 이 지켜지면 된다. 네트워크 계층·서버 상태 캐시 도구도 프로젝트 constraint 로 둔다 — 단 transport 는 DataState 안에서만 보이고 뷰에 노출되지 않는다는 Core 규칙은 같다. Compose/Android 바인딩은 `core/docs/ko/architecture/frontend-mobile.md` §Android 의 대응표만 있고 별도 문서는 아직 없다.
