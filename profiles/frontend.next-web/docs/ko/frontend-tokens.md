# 프론트엔드 Token Convention

> 정본: strata-kit `profiles/frontend.next-web/docs/ko/frontend-tokens.md` — strata `docs/05-conventions/frontend-tokens.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> Core 계약: `core/docs/ko/architecture/frontend-design-contract.md`

이 문서는 토큰 3단(Primitive → Alias → Component)을 파일·빌드·유틸리티 CSS에 매핑하는 관례다.
형식과 도구는 프로젝트가 바꿀 수 있고, 바꾸면 여기가 아니라 프로젝트 profile에 적는다.

## 정본 파일

- 위치: Foundation 패키지 안의 단일 파일 (예: `tokens/tokens.json`).
- 형식: W3C Design Tokens(DTCG) JSON 권장 — `$value`·`$type`·alias 참조(`{color.blue.80}`)를 지원하고 디자인 도구 동기화 플러그인이 읽는다.
- 한 파일에 T1·T2를 모두 두되 최상위 그룹으로 나눈다 (`primitive.*`, `alias.*`). T3는 필요할 때만 `component.*`.
- 모드는 alias 값에 `$extensions.modes` 또는 별도 mode 파일로 표현한다. 이름은 모드와 무관하게 하나.

```json
{
  "primitive": { "color": { "blue": { "80": { "$type": "color", "$value": "#1b4380" } } } },
  "alias": {
    "color": {
      "action": { "primary": { "bg": { "default": { "$value": "{primitive.color.blue.80}" } } } },
      "surface": { "default": { "$value": "{primitive.color.common.0}" } }
    }
  }
}
```

## 생성물 (빌드 단계에서만 해석)

| 생성물 | 소비자 | 비고 |
|---|---|---|
| CSS 변수 (`--color-action-primary-bg-default`) | 유틸리티 CSS · 런타임 테마 | alias만 노출. T1 변수는 내부용 접두로 숨기거나 생성하지 않는다 |
| TS 상수 (`tokens.color.action.primary.bg.default`) | 스타일 객체가 필요한 곳 | 타입은 alias 경로에서 유도 |
| 디자인 도구 변수 | 디자이너 | 동기화 도구(예: Tokens Studio·Variables API) — 방향은 profile 결정 |
| **alias 카탈로그** (`tokens.md`, 생성) | 에이전트 · 리뷰어 | 이름·의미·사용처 한 줄씩. T0 컨텍스트 예산 안에 들어가는 크기로 유지 |

컴포넌트 코드는 생성물의 **alias 이름**만 쓴다. 토큰 파일을 직접 import하거나 값을 계산하지 않는다.

## 유틸리티 CSS 매핑

유틸리티 클래스는 alias의 전달 수단이다. 클래스명은 alias 경로를 그대로 비춘다.

| 허용 | 금지 |
|---|---|
| `bg-surface-default` · `text-muted` · `border-status-pending` | `bg-blue-80`(T1) · `bg-[#1b4380]`(임의 값) · `text-[13px]` |

테마 설정(예: Tailwind `@theme`·preset)은 생성물이며 손편집하지 않는다. T1 유틸리티(`bg-blue-80`)를 생성하지 않는 것이 가장 단순한 집행이다.

## 스토리 (디자인 도구 부재 시 정본)

- Primitive UI: 컴포넌트당 스토리 1개 이상, 모든 variant·intent·size 조합을 표로 노출.
- Semantic Component: 데이터 상태 축(default · loading · empty · error)을 각각 스토리로.
- Foundation: alias 카탈로그 스토리(색·간격·그림자·타이포)를 둔다 — 디자이너가 도구 없이 검토하는 화면.

## 검사

| 검사 | 방법 | 위치 |
|---|---|---|
| Foundation 밖 raw 값 | 신규 라인 diff 검사 — hex·rgba·px 리터럴·`[…]` 임의 값·T1 클래스 패턴 | `profiles/frontend.next-web/enforcement/diff-rules.json.template` |
| 예외 만료 | `@strata:token-exception … until YYYY-MM-DD` 파싱, 그 날짜가 지났으면(오늘이 until 보다 뒤면) 실패 | 같은 스크립트 |
| 토큰 변경 승인 | 토큰 파일 diff가 있는 PR은 본문에 DEC id | CI 규칙 또는 PR 템플릿 |

## 금지

- 컴포넌트에서 T1 이름·raw 값·임의 값 사용
- 토큰 파일을 우회하는 테마 손편집
- alias 이름에 팔레트명·화면명 포함 (`color.blue.button`, `color.dashboard.header`)
