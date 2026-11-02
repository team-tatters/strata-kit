# 프론트엔드 Next.js Convention

> 정본: strata-kit `profiles/frontend.next-web/docs/ko/frontend-next.md` — strata `docs/05-conventions/frontend-next.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> Core 경계: `core/docs/ko/architecture/frontend-web.md`

이 문서는 Next.js 프로젝트가 Core의 Route Surface와 App Shell을 어떻게 매핑하는지 설명합니다.
Next.js는 Core의 필수 전제가 아닙니다.

## App Router

- route file(`page.tsx`)은 Route Surface입니다.
- layout/provider/shell file은 App Shell입니다.
- 재사용 가능한 화면 조각은 Feature Block(`Section`)으로 분리합니다.
- route params, search params, metadata, authorization boundary는 Route Surface에서 해석합니다.

### page.tsx 예산

`page.tsx`는 **params 해석 · 인증 가드 · metadata · Section 하나 배치**만 한다. 서버 상태 훅(query/mutation)과 transport 호출은 금지 — Feature Block으로 내린다.
Section이 둘 이상 필요하면 `{Route}Page` 조립 컴포넌트를 Feature 영역에 두고 page.tsx는 그것 하나만 렌더한다.

## Pages Router

Pages Router는 레거시 variant 또는 project migration zone에서 관리합니다.
신규 target 영역은 App Router 매핑을 우선합니다. `pages/**`는 layer-map에서 Route Surface로 매핑하고 zone을 legacy로 둔다.

## Server / Client Boundary

Server Component, Client Component, server action 사용 여부는 framework convention입니다.
Core 경계는 동일합니다. transport 직접 호출과 DataState 호출 위치가 레이어 규칙을 깨면 안 됩니다.

## Multi-zone

여러 앱(존)이 하나의 도메인 아래 rewrite로 합쳐지는 구조에서:

- 존을 가로지르는 셸 패키지(네비게이션·세션 provider)는 **App Shell**이다. Feature Block을 참조하지 않는다.
- 존별로 QueryClient가 분리되지 않을 수 있으므로 query key 첫 원소는 존 식별자다 (`profiles/frontend.next-web/docs/ko/frontend-query-state.md`).
- 존 간 이동은 링크(URL)로만 한다. 다른 존의 Feature Block을 import하지 않는다.
