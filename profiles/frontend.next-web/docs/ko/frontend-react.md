# 프론트엔드 React Convention

> 정본: strata-kit `profiles/frontend.next-web/docs/ko/frontend-react.md` — strata `docs/05-conventions/frontend-react.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> Core 경계: `core/docs/ko/architecture/frontend-web.md` · 디자인 계약: `core/docs/ko/architecture/frontend-design-contract.md`

이 문서는 React 프로젝트가 Core 웹 레이어를 구현할 때의 관례를 설명합니다.
React는 Core의 필수 전제가 아닙니다.

## 단방향 사슬 — Page → Section → View → Primitive

라우트에서 화면까지 한 방향으로만 흐른다. **Section이 자기 use case 상태의 소유자**다(독립 저장 단위인 자식 Section은 자기 상태를 소유한다) — Section이 Props를 선언하고 상태를 들고, 아래로만 전파한다.

```
route file (Route Surface)
  └─ params · guard · metadata · <XxxSection/> 하나. 훅은 라우팅 훅만
      └─ XxxSection (Feature Block) — 상태 소유자
           │  useState · useEffect · 로컬 훅 · DataState adapter 훅(use*Query · use*Mutation)을 여기서 직접 호출
           ├─ <XxxView/>          Semantic Component — props만 받아 그린다
           └─ <XxxSubSection/>    필요 시 같은 도메인의 하위 Section — 독립 저장 단위면 상태 소유자:
                                  자기 use case 데이터는 직접 조회·저장하고, 부모와 공유하는 상태만 props로 받는다.
                                  부모와 함께 제출·취소하는 입력이면 Section이 아니라 View·제어 컴포넌트로 두고
                                  부모가 draft와 제출을 맡는다 (원자 저장은 단일 명령·트랜잭션으로)
                └─ Primitive UI + alias 토큰
```

## Section의 상태 소유와 분리 기준

Section 안에 두는 것과 밖으로 빼는 것은 **개수가 아니라 종류**로 가른다. 상태 로직을 훅으로 분리하는 것은 의무가 아니다.

| 종류 | 위치 | 이유 |
|---|---|---|
| 지역 상태 (`useState` · `useReducer`), 효과 (`useEffect`), 파생값 (`useMemo`), 이 Section만 쓰는 로컬 훅 | **Section 안** | 상태의 소유자가 한 곳에 보여야 한다 |
| 서버 상태 읽기·쓰기 | Section이 DataState adapter 훅을 **호출**. 구현은 `query-hooks/` | transport는 Section에 나타나지 않는다 |
| 서비스 호출 (HTTP · storage · 외부 SDK) | **항상 밖** — DataState transport | 컴포넌트는 transport를 모른다 |
| 둘 이상의 Section이 쓰는 가공·계산·상태 로직 | **밖** — `features/{domain}/hooks/use{Thing}` 또는 Foundation util | 공통단은 참조 구조로 |
| 한 Section의 상태 로직을 다른 Section이 통째로 재사용하거나 단독 테스트해야 할 때 | 선택 — `use{UseCase}Section`으로 분리 | 분리는 필요할 때만. 기본은 Section 안 |

## 접미 의미

| 접미 | 레이어 | DataState 호출 | 라우터 훅 | 비고 |
|---|---|---|---|---|
| `{Route}Page` / route file | Route Surface | 금지 | 허용 | Section 1개 배치가 원칙. 2개 이상이면 `{Route}Page` 조립 컴포넌트 — routes·features 어디에 두든 Route Surface(layer-map 에서 Feature Block 매핑보다 앞). 다른 도메인 Section 은 여기서 형제로 배치한다 |
| `{UseCase}Section` | Feature Block | 허용 | 금지 — Page가 주입 | 상태 소유자. 라우트 없는 화면 조각, 여러 라우트에서 재사용 가능. 다른 도메인의 Section import 금지, 같은 도메인의 Section은 자식으로 담을 수 있다 |
| `{UseCase}Panel` · `Dialog` · `Table` | Feature Block | 허용 | 금지 | 오버레이·측면·표 형태의 Section |
| `{Domain}{Purpose}View` | Semantic Component | 금지 | 금지 | props만. 로컬 UI 상태(열림·호버)만 가질 수 있다 |
| Primitive 컴포넌트 | Primitive UI | 금지 | 금지 | alias + variant 축만 |

`Container`·`Block`·`Partial` 접미는 금지다 — `Section`을 쓴다(형태에 따라 `Panel` · `Dialog` · `Table`).

## Props 명명 — 소유자와 방향을 이름에 담는다

Section이 소유한 상태와 훅이 여러 자식으로 내려갈 때, prop 이름만 보고 **누가 소유하는지 · 어느 방향으로 흐르는지 · 값인지 행위인지**를 알 수 있어야 한다. 접두·접미는 그 셋을 말한다. 기계 판독: `core/rules/naming-convention.yaml` → `frontend.Props`.

| 역할 | 형태 | 예 | 규칙 |
|---|---|---|---|
| 부모 소유 상태의 현재 값 (읽기) | 명사, 접두 없음 | `selectedIds` · `filter` · `page` | 접두 없음 = "부모 소유, 자식은 읽기만" |
| 부모 상태 변경 요청 (자식 → 부모) | `on{State}Change` | `onSelectedIdsChange` · `onFilterChange` | setter를 그대로 넘기지 않는다. `set*` prop 금지 |
| 부모 행위 트리거 (이벤트) | `on{Event}` (동사) | `onSubmit` · `onRowClick` · `onDelete` | 결과를 자식이 알 필요 없을 때 |
| 값 + 변경 쌍을 **여러 자식이 공유** | `{state}Control` 묶음 | `selectionControl={{ value, onChange }}` | 다중 참조 표식. 타입 `{State}Control`. 같은 상태를 값·콜백 두 prop으로 여러 자식에 흩뿌리지 않는다 |
| 파생·표시 전용 데이터 묶음 | `{name}Model` | `orderModel` | Contract의 ViewModel. 콜백을 넣지 않는다 |
| 초기값 (자식이 소유) | `default{State}` | `defaultPage` | 비제어. 부모는 이후 관여하지 않는다 |
| 불리언 | `is` · `has` · `can` · `should` | `isEditing` · `canDelete` · `shouldAutoFocus` | 긍정형. `disabled`처럼 HTML 속성명은 예외 |
| 서버 상태 슬라이스 | 데이터 명사 + `is{Entity}Loading` + `{entity}Error` | `orders` · `isOrdersLoading` · `ordersError` | query 결과 객체를 통째로 넘기지 않는다 |
| 렌더 위임 | `render{Slot}` | `renderRow` | |
| ref | `{name}Ref` | `scrollRef` | |

**권고 — 다중 참조는 Control 묶음으로.** 부모 상태 하나를 자식 셋이 읽고 쓰면 `value`·`onChange`·파생값을 `{state}Control` 객체 하나로 묶어 내려보낸다. 이름의 접미가 "부모가 소유하고 여러 곳이 공유하는 상태"라는 사실을 드러내고, 자식이 늘어도 prop 수가 늘지 않는다. `shared*`·`section*` 같은 평면 접두는 소유는 말해도 방향(읽기/쓰기)을 말하지 못하므로 쓰지 않는다.

```tsx
// Section — 상태 소유자
const [selectedIds, setSelectedIds] = useState<number[]>([]);
const selectionControl: SelectionControl = { value: selectedIds, onChange: setSelectedIds, count: selectedIds.length };
const { data: orders = [], isLoading: isOrdersLoading } = useOrderListQuery(filter);

<OrderTableView orders={orders} isOrdersLoading={isOrdersLoading} selectionControl={selectionControl} onRowClick={handleRowClick} />
<OrderBulkActionView selectionControl={selectionControl} onDelete={handleDelete} />
```

내부 핸들러 함수 이름은 `handle{Event}`, 자식에 넘기는 prop 이름은 `on{Event}`다. 둘을 같은 이름으로 쓰지 않는다.

## Component Boundary

- 한 파일에는 하나의 exported component를 둡니다.
- 파일 내부 보조 함수와 private subcomponent는 허용하되, 재사용되면 별도 파일로 분리합니다.
- DTO, ViewModel, schema, interface는 Contract로 이동합니다.
- Semantic Component는 DataState hook을 직접 호출하지 않고 props/callback으로 주입받습니다.
- 데이터 상태 축(loading · empty · error)은 View의 props로 받아 렌더한다. Section이 값을 결정한다.

## State Boundary

- use case 조립과 DataState 호출은 Feature Block(Section)에서 시작합니다.
- shared UI component에 서버 상태 라이브러리 의존성을 넣지 않습니다.
- feature-local context는 props 전달이 깊어질 때만 제한적으로 사용합니다. Control 묶음으로 해결되면 context를 만들지 않습니다.
