# 프론트엔드 Atomic Variant 레이어 아키텍처

> 정본: strata-kit `core/docs/ko/architecture/frontend-atomic.md` — strata `docs/03-architecture/frontend-atomic.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> 기계 판독 가능한 규칙: `core/rules/layer-rules.yaml` → `frontend.variants.atomic`
> 신규 웹 프로젝트의 기본 variant는 `frontend.variants.web`이며, 상세는 `core/docs/ko/architecture/frontend-web.md`를 참조합니다.
> **상태: 유지(레거시 호환)** — 신규 채택 비권장. Molecule/Organism의 크기 분류는 web variant의 Composition Legality(`core/docs/ko/architecture/frontend-design-contract.md`)로 대체되었습니다.

## web variant 매핑

| Atomic | web variant | 판정 기준 |
|---|---|---|
| Atom | Primitive UI | 도메인 무지, alias 토큰 + variant 축만 |
| Molecule | Semantic Component **또는** Feature Block | DataState를 호출하면 Feature Block, 아니면 Semantic Component. **크기로 판정하지 않는다** |
| Organism | (폐기) | Feature Block으로 흡수 |
| Partial | Feature Block (`{UseCase}Section`) | 라우트 없는 화면 조각 |
| Page · Layout | Route Surface · App Shell | 그대로 |
| L2 Hook | DataState adapter | `useQuery{Name}` → `use{Entity}Query` |
| LM | Contract + DataState transport | ViewModel·DTO는 Contract, API Client는 `{name}.service` |

## 레이어 구조

```
Page / Layout
    ↓
Partial (페이지 수준 공통 UI 집합)
    ↓
Molecule (행위 특화 컴포넌트)
    ↓
Atomic (순수 UI 컴포넌트)
    ↓
L2 (상태 관리 Hook)
    ↓
LM (ViewModel, DTO, API Client)
    ↓
L1 (순수 함수, 타입, 상수)
```

## L1 — 순수 함수 계층

백엔드 L1과 동일한 원칙. UI 프레임워크에 종속되지 않는 순수 로직.
순수 상태 관리 Hook은 허용하지만 API 호출은 금지한다.

**예시:** useDebounce, useLocalStorage, formatDate, validateEmail

## LM — 데이터 모델 계층

서버와의 통신을 담당하는 중간 계층.

**구성:** ViewModel (표시 전용 데이터 구조), DTO (서버 요청/응답 매핑), 
API Port/Client Interface (transport 호출 경계), Interface (계약 정의)

**규칙:** UI 렌더링 로직 금지. 데이터 변환과 통신만 담당.

## L2 — 상태 관리 계층

서버/클라이언트 상태 adapter Hook.

**규칙:** LM의 API Client를 사용하여 서버 상태 동기화.
UI 컴포넌트를 직접 렌더링하지 않음. Hook만 export.

## Atomic — 최소 단위 UI

L2 이하의 모든 의존성이 제거된 순수 UI 컴포넌트.
Props만으로 동작하며, 전역 상태 접근 금지.

**예시:** Button, Input, Badge, Avatar, Tooltip, Card

## Molecule — 행위 특화 UI

Atomic을 조합하고 L2 Hook을 바인딩한 컴포넌트.
특정 도메인 행위에 특화되어 있음.

**예시:** SearchBar (Input + Button + useSearchStore),
OrderCard (Card + Badge + useOrderQuery)

## Partial — 페이지 수준 공통 집합

여러 페이지에서 공유되는 UI 블록.
Molecule과 Atomic의 조합.

**예시:** OrderListPartial, UserProfilePartial, NotificationPanel

## Page — 라우트 대상

실제 URL에 매핑되는 최상위 컴포넌트.
Layout, Partial, Molecule, Atomic을 조합하여 완전한 화면 구성.

## Layout — 구조적 래퍼

네비게이션, 사이드바, 푸터 등 페이지 구조를 정의.
Page 컴포넌트를 children으로 수신.
