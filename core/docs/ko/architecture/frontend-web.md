# 프론트엔드 Web 레이어 아키텍처

> 정본: strata-kit `core/docs/ko/architecture/frontend-web.md` — strata `docs/03-architecture/frontend-web.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> 기계 판독 가능한 규칙: `core/rules/layer-rules.yaml` → `frontend.variants.web`
> 이 문서는 프레임워크 독립 웹 프론트엔드 variant의 사람이 읽는 상세 설명입니다.
> 토큰·변형·조합과 디자인 산출물의 정합은 `core/docs/ko/architecture/frontend-design-contract.md`가 정의합니다.

## 경계 원칙

Strata Core의 프론트엔드 지침은 특정 UI 프레임워크, 라우터, 상태관리 라이브러리, 스타일링 도구를 정의하지 않습니다.
Core에는 import/path/정적분석으로 검증 가능한 책임 경계만 둡니다.

레이어 관계는 단일 선형 트리가 아니라 DAG입니다.
아래 표의 `can_reference`가 source of truth이며, 표 밖의 레이어 참조와 `cross_reference: false` 레이어의 동일 레벨 교차 참조는 금지됩니다. Feature Block 에서 금지되는 것은 다른 도메인 사이의 참조입니다(아래 참조).

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

## Variants

Strata 프론트엔드는 세 variant를 지원합니다.

| Variant | 용도 | 상태 |
|---|---|---|
| `atomic` | 기존 L1/LM/L2/Atomic/Molecule/Partial/Page/Layout 구조와 레거시 프로젝트 호환 | 유지 |
| `web` | 프레임워크 독립 웹 애플리케이션 경계 | 기본 |
| `mobile` | 네이티브 모바일 UI(SwiftUI·Compose) — 레이어·can_reference 는 web 과 같고 어휘·조립·타깃 규칙이 다르다 (`core/docs/ko/architecture/frontend-mobile.md`) | 2026-09-11 |

프로젝트별 선택은 `.strata/layer-map.yaml`의 `variant` 또는 `frontend_variant`에 둡니다.
선택값이 없으면 Core 기본값은 `web`입니다.

## Foundation

Semantic token, 순수 함수, 상수, primitive type을 둡니다.

**허용:** token, const, type, util

**금지:** UI 렌더링, transport 호출, 전역 상태 접근, 프레임워크 종속 구현

## Contract

UI와 transport 사이의 안정 계약입니다.
DTO, ViewModel, schema, API port/interface, cache key contract를 둡니다.

**규칙:**
- Foundation만 참조합니다.
- UI 레이어와 DataState를 참조하지 않습니다.
- transport 구현체를 직접 호출하지 않습니다.
- 컴포넌트 파일에 흩어지기 쉬운 interface/type은 이 레이어로 모읍니다.

## DataState

서버 상태, mutation, 클라이언트 상태의 adapter 계층입니다.
구체 라이브러리는 convention에서 정하고, Core는 UI가 transport를 직접 보지 못하게 하는 경계만 정의합니다.

**규칙:**
- Foundation과 Contract만 참조합니다.
- UI 컴포넌트를 렌더링하지 않습니다.
- transport client를 UI에 직접 노출하지 않습니다.
- cache key와 DTO/ViewModel 계약은 Contract를 참조합니다.

**두 구간:** transport(`{name}.service` — HTTP 호출, DTO 반환)와 adapter(`use{Entity}Query` · `use{Entity}{Action}Mutation` · `use{Name}State`).
transport를 import할 수 있는 것은 adapter뿐입니다. 상위 레이어는 adapter만 봅니다.

## Primitive UI

Semantic token에 묶인 저수준 UI입니다.
도메인 의미와 서버 상태를 알지 못해야 합니다.

**규칙:**
- Foundation만 참조합니다.
- Contract의 도메인 모델, DataState, transport를 참조하지 않습니다.
- Props와 Foundation token만으로 동작합니다.

## Semantic Component

사용자 또는 도메인 의미를 가진 UI 컴포넌트입니다.
Atomic/Molecule 같은 크기 분류가 아니라 "무엇을 하는 컴포넌트인가"를 이름과 책임으로 표현합니다.

**검증 가능한 핵심 경계:** Semantic Component는 DataState를 직접 호출하지 않습니다.
서버 상태와 mutation은 props 또는 callback으로 주입받습니다.

Feature Block의 렌더 절반을 떼어낸 컴포넌트는 `{Domain}{Purpose}View`로 이름 짓습니다. 데이터 상태 축(loading · empty · error)은 props로 받습니다.
외형은 Primitive UI의 variant 축 값과 Foundation alias의 조합으로만 정합니다 (Composition Legality — `core/docs/ko/architecture/frontend-design-contract.md`).

## Feature Block

특정 use case의 화면 조각과 데이터/상태를 조립하는 레이어입니다.
DataState 호출은 이 레이어부터 허용됩니다.

**규칙:**
- 서로 다른 도메인의 Feature Block 간 직접 참조는 금지됩니다. 같은 도메인 안에서는 Section이 다른 Section을 자식으로 담을 수 있습니다. 다른 도메인의 화면을 함께 보여야 하면 Route Surface의 `{RouteName}Page`가 각 도메인 Section을 형제로 배치하고 props·이벤트로 잇습니다.
- 도메인은 feature 루트(layer-map `feature_root`, 없으면 layer-rules `Feature_Block.domain_slice`의 접두) 바로 아래 디렉터리 하나입니다. 루트 밖의 Feature Block 파일은 도메인 격리 대상이 아닙니다. 이 경계는 코드 조각의 경계이며 업무 도메인의 의미까지 보장하지는 않습니다.
- Semantic Component, Primitive UI, DataState, Contract를 조립합니다.
- 라우팅과 app-level provider 책임을 갖지 않습니다.

접미는 `{UseCase}Section`(라우트 없는 화면 조각 — atomic variant의 Partial에 해당)이며, 형태에 따라 `Panel` · `Dialog` · `Table`을 씁니다. `Block`·`Container`·`Partial` 접미는 금지입니다(`core/rules/naming-convention.yaml` → `Feature_Block.forbidden_suffixes`).
Section은 **자기 use case 상태의 소유자**입니다(독립 저장 단위인 자식 Section은 자기 상태를 소유합니다) — Props를 선언하고 지역 상태·효과·DataState adapter 훅을 직접 들고, 아래로만 전파합니다. 렌더는 `View`(Semantic Component)에 맡깁니다:
`Route Surface → Section → View → Primitive UI`. 상태 소유는 셋으로 나눕니다 — 로컬 draft의 소유, 서버 캐시의 관찰, 저장 명령의 책임. 같은 도메인의 자식 Section은 그것이 독립 저장 단위인 자기 use case일 때만 그 draft와 mutation을 소유하고, 부모와 공유하는 상태만 props로 받습니다. 여러 Section이 함께 편집하는 draft는 소유자가 하나이고, 여러 Section에 걸친 제출·취소·원자 저장은 조정자(부모 Section) 하나가 맡으며 하위 입력은 View·제어 컴포넌트로 둡니다. 원자성은 DataState·API의 단일 명령이나 트랜잭션으로 얻고, 여러 mutation 뒤의 무효화로 얻지 않습니다. 같은 query key를 여러 Section이 관찰하는 것은 중복 소유가 아닙니다. 상태 로직을 훅으로 분리하는 것은 의무가 아니며, 서비스 호출(transport)과 둘 이상의 Section이 쓰는 공통 가공만 참조 구조로 밖에 둡니다. 분리 기준과 Props 명명은 `profiles/frontend.next-web/docs/ko/frontend-react.md`.

## Route Surface

URL 진입점, route params, 권한 경계, 화면 조립을 담당합니다.

**규칙:**
- Feature Block을 배치합니다 — 원칙적으로 Section 하나. 둘 이상이면 `{RouteName}Page` 조립 컴포넌트를 둡니다. 이 조립 컴포넌트는 놓인 위치(routes·features)와 무관하게 Route Surface입니다 — layer-map에서 Feature Block 매핑보다 앞에 둡니다.
- 재사용 UI로 export하지 않습니다.
- transport 직접 호출은 금지됩니다. DataState 훅 호출도 금지됩니다 — `can_reference`에 DataState가 없습니다.

라우터별 파일 규칙은 Core가 아니라 framework convention에서 정의합니다.

## App Shell

전역 provider, navigation, app-level layout을 담당합니다.

**규칙:**
- Feature Block을 직접 참조하지 않습니다.
- 도메인 use case 로직을 갖지 않습니다.
- 전역 provider와 shell-level layout만 다룹니다.
- 여러 앱(존)이 공유하는 셸 패키지도 App Shell입니다. 앱 경계를 넘는 이동은 URL로만 합니다.

## Core / Convention / Profile 분리

| 성격 | 위치 | 예시 |
|---|---|---|
| 검증 가능한 아키텍처 경계 | Core `core/docs/ko/architecture/frontend-web.md`, `core/rules/layer-rules.yaml` | DataState를 Semantic Component에서 참조 금지 |
| 디자인 계약 (토큰·변형·조합·정합) | Core `core/docs/ko/architecture/frontend-design-contract.md` | 컴포넌트는 alias를 참조(컴포넌트 토큰은 소유 컴포넌트에서만), design_ref·정렬 상태 |
| 프레임워크/라이브러리 바인딩 | `profiles/<id>/docs/ko/` | query hook, router, styling 도구, 토큰 파일 매핑 |
| 프로젝트 레거시/전환 정책 | 프로젝트 `.strata/` | legacy/bridge/target zone |

Strata Core는 "어떤 라이브러리를 쓰는가"가 아니라 "어떤 책임이 어느 레이어를 통과해야 하는가"를 정의합니다.
