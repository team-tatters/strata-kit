# 프론트엔드 Query / State Convention

> 정본: strata-kit `profiles/frontend.next-web/docs/ko/frontend-query-state.md` — strata `docs/05-conventions/frontend-query-state.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> Core 경계: `core/docs/ko/architecture/frontend-web.md`

이 문서는 DataState 레이어를 특정 라이브러리에 매핑하는 convention입니다.
Core의 source of truth는 "UI가 transport를 직접 호출하지 않는다"이며, 이 문서는 구현 선택을 설명합니다.

## DataState 안의 두 구간

| 구간 | 파일 | 역할 | 참조 가능 |
|---|---|---|---|
| transport | `{name}.service.ts` | HTTP client 호출, DTO 반환 | Foundation · Contract |
| adapter | `use{Entity}Query.ts` · `use{Entity}{Action}Mutation.ts` · `use{Name}State.ts` | 서버/클라이언트 상태 훅 | Foundation · Contract · **transport** |

transport를 import할 수 있는 것은 adapter뿐이다. 컴포넌트(Section)·Route Surface·공통 훅은 adapter만 본다.

## 훅 명명

| 종류 | 이름 | 위치 (레이어) |
|---|---|---|
| 서버 상태 읽기 | `use{Entity}Query` · `use{Entity}ListQuery` | DataState adapter |
| 서버 상태 쓰기 | `use{Entity}{Action}Mutation` (Create · Update · Delete · Submit …) | DataState adapter |
| Section 상태 로직 분리 (선택) | `use{UseCase}Section` — 다른 Section이 재사용하거나 단독 테스트할 때만. 기본은 Section 안 | Feature Block |
| 공통 가공·계산 | `use{Thing}` — 둘 이상의 Section이 쓰는 로직 | Feature Block hooks 또는 Foundation |
| 클라이언트 상태 | `use{Name}State` · `use{Name}Store` | DataState adapter |
| 순수 유틸 | `use{Thing}` — 프레임워크 훅만 의존 | Foundation |

**금지 접두**: `useFetch · useGet · usePost · usePut · usePatch · useDelete`. HTTP 동사는 transport의 어휘이고 훅은 도메인 어휘다.
기존 코드는 손대지 않고 신규 라인만 검사한다 (`profiles/frontend.next-web/enforcement/`).

## Query Key — 형태 · 소유 · 집행

키는 키 팩토리로만 만든다 — 기능(도메인)마다 하나씩, 그 기능의 `{domain}.keys.ts`에 둔다.

```ts
// features/{domain}/{domain}.keys.ts
export const orderKeys = {
  all:     ['shop', 'order'] as const,                       // [scope, domain]
  lists:   () => [...orderKeys.all, 'list'] as const,
  list:    (p: OrderListRequest) => [...orderKeys.lists(), p] as const,
  details: () => [...orderKeys.all, 'detail'] as const,
  detail:  (id: number) => [...orderKeys.details(), id] as const,
};
```

- **형태**: `[scope, domain, entity/scope…, params]`. 첫 원소는 앱·존 식별자 — 여러 앱이 QueryClient를 공유할 수 있으므로 충돌을 막는다.
- **계층**: `all → lists → list(p)`, `all → details → detail(id)`. 평면 키(`['orders']`)는 부분 무효화가 안 되므로 미달.
- **소유**: 무효화는 mutation 훅에서만, 그 훅이 **영향 키로 선언한** 키만 한다 — mutation의 `meta.invalidates` 태그 목록이나 훅 안의 명시적 목록으로 선언한다. 선언하는 키는 `keys.lists()` 같은 부분 트리, `keys.detail(id)` 같은 정확한 상세 키, 다른 도메인의 키 모두 될 수 있으며, 언제나 그 키를 소유한 기능의 키 팩토리로 만든다. 컴포넌트에서 `invalidateQueries` 직접 호출 금지.
- **집행**: 정적 의존 분석으로는 인라인 리터럴을 못 잡는다 — diff 규칙(`no-inline-query-key`, `no-component-invalidate`)으로 신규 라인만 차단.

## 기본 규칙

- 서버 상태는 query/mutation adapter로 감쌉니다.
- mutation 이후 cache invalidation 정책은 DataState에 둡니다.
- 전역 상태는 기본 선택지가 아닙니다. URL state, query cache, local state를 먼저 검토합니다.
- props 전달이 과도해지면 Feature Block 내부 composition boundary 또는 feature-local context를 둡니다.

## 금지

- UI 컴포넌트에서 transport client 직접 호출
- Route Surface에서 use case별 mutation 세부 로직 보유
- Semantic Component에서 server-state adapter 직접 호출
- `*.keys.ts` 밖의 queryKey 리터럴

## 라이브러리 매핑

React 계열 프로젝트에서는 DataState를 query hook, mutation hook, client-state hook으로 구현할 수 있습니다.
구체 라이브러리와 버전별 API는 프로젝트 profile 또는 framework convention에서 정합니다.
