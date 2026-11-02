# 프론트엔드 디자인 계약 (Design Contract)

> 정본: strata-kit `core/docs/ko/architecture/frontend-design-contract.md` — strata `docs/03-architecture/frontend-design-contract.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> 기계 판독 가능한 규칙: `core/rules/layer-rules.yaml` → `frontend.variants.web` (Foundation · Primitive_UI · Semantic_Component),
> `core/rules/naming-convention.yaml` → `frontend.Foundation.token_alias` · `markers.token_exception`
> 이 문서는 디자인(토큰·변형·조합)과 구현 사이의 **검증 가능한 계약**을 정의한다.
> 특정 디자인 도구, CSS 도구, UI 라이브러리를 전제하지 않는다. 도구 바인딩은 `profiles/frontend.next-web/docs/ko/frontend-tokens.md`.

## 경계 원칙

Core는 두 질문에만 답한다 — "이 컴포넌트는 무엇을 하는가"와 "이 컴포넌트의 외형은 어디서 결정되는가".
"어떻게 보이는가"는 토큰과 변형 축의 조합으로 유도되어야 하며, 컴포넌트 코드 안에서 직접 결정되면 안 된다.

한 단어 "토큰"에 섞여 있는 세 개념을 분리한다.

| 개념 | 정의 | 사는 곳 |
|---|---|---|
| Token | 값 체계. 원값(primitive)과 의도(alias) | Foundation |
| Variant | 컴포넌트가 공개하는 축 (variant · intent · size · state) | Primitive UI |
| Composition | 컴포넌트의 조합. 크기가 아니라 **계약**(이름 = 의미, props = 의도, slots)으로 표현 | Semantic Component · Feature Block |

## 토큰 3단

| 단 | 역할 | 명명 예 | 참조 허용 | 디자인 도구 |
|---|---|---|---|---|
| T1 Primitive | 팔레트 스케일·간격·타이포 원값 | `cool-neutral-30` · `blue-80` · `space-4` | T2만. 컴포넌트 참조 금지 | 변수 컬렉션 "Primitive" |
| T2 Alias | 의도. **에이전트·디자이너·코드가 공유하는 유일한 어휘** | `color.surface.default` · `color.text.muted` · `color.action.primary.bg.hover` · `color.status.pending.fg` | Primitive UI · Semantic · Feature | 변수 컬렉션 "Semantic" (모드: light/dark/density) |
| T3 Component | 컴포넌트별 override. 생성물이며 선택. raw 값이 아니라 T2 alias를 가리킨다 | `button.solid.primary.bg` | 그 토큰을 소유한 컴포넌트(와 그 내부)만 | 두지 않는 것이 기본 |

**Alias 명명**: `{category}.{object}.{role}.{state?}` — category(color·space·radius·shadow·typography), object(surface·text·border·action·status·…), role(default·muted·bg·fg·…), state(hover·active·disabled·…).
모드(라이트·다크·밀도)는 alias의 **값 층**에서 갈라지고 이름은 하나다.

**규칙**
- T1은 T2에서만 참조된다. 컴포넌트 코드에 T1 이름이 등장하면 위반.
- T3 컴포넌트 토큰은 그것을 소유한 컴포넌트(와 그 내부)만 참조하며, raw 값이 아니라 alias를 가리킨다. 다른 컴포넌트나 화면에 같은 값이 필요하면 alias로 승격한다.
- Foundation 밖에서 raw 값(hex·px·rgba·팔레트 스케일명)은 금지이며, 디자인 속성별로 적용한다: 색, 간격, 글자 크기와 줄 높이, 모서리 반경, 그림자, z-index. 실행 중에 계산하거나 측정하는 값(가상 스크롤 오프셋, 측정한 기준 너비, 데이터 열 너비 같은 연속적인 치수)은 `@strata:computed <reason>`으로 표시한 예외로 허용한다(만료 없음, 이유가 비어 있으면 인정하지 않는다). alias 변수를 참조하는 임의 값은 raw 값이 아니다. 유틸리티 CSS 클래스명은 alias 이름을 그대로 비춰야 한다.
- 새 alias 추가는 아키텍처 결정이다 — decision 레코드 필수 (`@strata:token-exception`은 만료 있는 임시 탈출구, 아래 §예외 정책).

## Variant 축

Primitive UI가 공개하는 축은 넷이다. 축의 **값에 팔레트명을 쓰지 않는다** — "어떻게 보이는가"가 아니라 "무엇을 뜻하는가"로 값을 정한다.

| 축 | 값 (기본 어휘) | 비고 |
|---|---|---|
| `variant` | solid · outline · subtle · clean | 형태 |
| `intent` | primary · neutral · danger · success · warning · info | 의도. 프로젝트는 도메인 상태 축(예: `status: pending · completed`)을 **별도 축**으로 확장할 수 있다. 같은 축에 섞지 않는다 |
| `size` | sm · md · lg | 프로젝트가 값 재정의 가능 |
| `state` | default · hover · focus · active · disabled | 상호작용 상태. **데이터 상태**(loading · empty · error)는 Semantic Component부터 갖는다 |

디자인 도구의 컴포넌트 속성 이름과 코드 props 이름은 **동일**해야 한다. 이것이 정합 검사의 전제다.

## Composition Legality — 조합의 합법성

> Semantic Component와 Feature Block의 외형은 **(하위 Primitive UI의 variant 축 값) × (Alias 토큰)의 순수 함수**여야 한다.

여기서 "외형"은 컴포넌트 자신의 시각 속성을 말한다: 색, 타이포그래피, 안쪽 여백(padding), 테두리, 상태별 모양. 컴포넌트 사이의 배치, 바깥 여백(margin), 뷰포트와 반응형 동작, 콘텐츠와 에셋은 이 규칙 밖이며, 부모가 배치하는 레이아웃 요소(grid, stack 등)의 몫이다. raw 값 검사와 팔레트 검사가 재는 것도 이 범위다.

이 한 줄이 Atomic Design의 Molecule/Organism(크기 분류)을 대체한다. 조합은 크기가 아니라 합법성으로 판정한다.

| 판정 | 예 |
|---|---|
| 합법 | `<Button intent="danger" variant="outline">` + `color.text.muted` · alias 변수를 참조하는 임의 값 · 이유 주석이 달린, 실행 중에 측정한 너비 |
| 위반 | `bg-blue-80`(T1 직접 참조) · `style={{color:'#303140'}}`(raw 값) · `className="bg-[#fff]"`(임의 값) |

Atomic variant와의 대응은 `core/docs/ko/architecture/frontend-atomic.md` §매핑을 따른다. 요지: Atom → Primitive UI, Molecule → Semantic Component(데이터 무지) 또는 Feature Block(DataState 호출), Organism 폐기, Partial → Feature Block(Section).

## 디자인 산출물과 정합

기능 하나에 산출물 셋이 있다. 각각 버전을 갖고, **어느 것이든 진입점**이 될 수 있다. 게이트는 순서가 아니라 쌍 사이의 정합 검사다.

| 산출물 | 담는 것 | 형태 |
|---|---|---|
| Spec | 무엇을 하는가 — 요구·행위·상태 | task 명세 · KB specification |
| Design | 어떻게 보이는가 | `design_ref` (아래) |
| Impl | 코드 | 저장소 |

**design_ref** (`core/docs/ko/methodology/task-spec-schema.md` → `inputs.design_ref`)

| kind | 뜻 |
|---|---|
| `figma` | 디자인 도구 파일·노드 참조 |
| `storybook` | 스토리가 디자인 산출물 (디자인 도구 부재 시 정본) |
| `claude_design` | 초안 캔버스. `spec_first` 진입점의 산출물, 확정 시 `storybook` 또는 `figma`로 승격 |
| `none` | 디자인 산출물 없음을 **명시** — `reason` 필수 (예: 내부 도구, 텍스트 전용) |

**정합(aligned)의 정의**: 컴포넌트 계약 — 이름, variant 축과 값, 사용 alias, 상태 축 — 이 Design과 Impl에서 동일하다.
도구는 이 정의 위에서 비교한다(속성 이름 대조, 스토리 렌더와 프레임 대조). 사람 검수도 같은 정의를 쓴다.

**정렬 상태** (`completion.design_sync`)

```text
aligned   Design ↔ Impl 계약 일치
stale     한쪽이 바뀌어 재검사 필요 — 이 상태로 완료 선언 불가
waived    의도적 불일치. reason + until(만료일) 필수
none      design_ref.kind: none 인 작업
```

**진입점** (`_order.entry_point`)

```text
design_first   Design → (Design↔Spec) → Impl → (Impl↔Design)
dev_first      Impl → (Impl↔Spec) → Design(retrofit) → (Impl↔Design)
spec_first     Spec → Design·Impl 병행 → 두 정합 검사
change         어느 산출물이든 변경 → 나머지 stale → 정합 회복까지 미완료   (기본값)
```

리뷰는 별도 단계가 아니라 **모든 산출물 전이가 발생시키는 것**이다. 순서를 고정하지 않는다.
검증 독립성은 `core/docs/ko/methodology/verification-tier.md`의 `design_verified` 축이 정의한다.

## 디자인 도구의 정본 범위

디자인 도구(예: Figma)에 두는 것은 좁게 정한다.

| 정본 후보 | 참조(정본 아님) | 두지 않는 것 |
|---|---|---|
| T1·T2 토큰 변수(모드 포함) | Feature 수준 화면 프레임 | 조합 로직 · 데이터 흐름 · 훅 경계 |
| Primitive UI 컴포넌트와 variant 속성 | | i18n 문구 (키는 코드, 도구에는 키 주석) |
| Semantic Component의 상태 축(loading·empty·error) | | 라우팅 · 권한 경계 · 레이아웃 원값 |

**토큰 정본은 코드 저장소의 토큰 파일**(권장). 이유: 에이전트·CI가 안정적으로 읽고, 컨텍스트 예산(`core/docs/ko/methodology/context-protocol.md` CB-1)에 맞는 alias 카탈로그를 생성할 수 있으며, 디자인 도구 접근성에 종속되지 않는다.
디자인 도구 → 코드 방향 동기화는 허용하되 충돌은 decision 레코드로 푼다. 반대 선택(도구 정본)은 프로젝트 profile의 결정으로 가능하다.

**토큰 해석 지점은 하나** — Foundation 빌드 단계(토큰 파일 → CSS 변수 · TS 상수 · 도구 변수). 컴포넌트는 alias 이름을 참조하고, 컴포넌트 토큰은 그것을 소유한 컴포넌트만 참조한다.

## 디자인 도구가 없을 때

규칙은 하나다 — **Primitive UI와 Semantic Component는 스토리를 갖는다.** 디자인 도구가 없으면 스토리가 `design_ref`이고, 도구가 생기면 스토리↔도구 정합 검사로 이어진다.
초안 도구(Claude Design 등) 산출물은 확정 전까지만 `design_ref`가 되며, 확정 시 승격한다.

## 예외 정책

디자이너가 도입한 일회성 값이 alias로 표현되지 않을 때:

1. **승격** — 새 alias를 decision 레코드와 함께 추가. 토큰 파일 변경 PR은 DEC id를 참조한다.
2. **예외 태그** — `@strata:token-exception {reason} until {YYYY-MM-DD}`. 만료 시 검사 실패. 문법은 `core/docs/ko/conventions/strata-markers.md`.
3. **측정** — Foundation 밖 raw 값 수를 디자인 속성별로 세어 diff 기준 0으로 유지 (`profiles/frontend.next-web/enforcement/`).

실행 중에 계산하거나 측정하는 값(가상 스크롤 오프셋, 측정한 기준 너비, 데이터 열 너비 같은 연속적인 치수)은 일회성 디자인 값이 아니다. 이런 값은 코드에 예외로 남기되 하나하나 `@strata:computed <reason>`으로 표시하며, raw 값으로 세지 않는다. 일회성 디자인 값은 만료가 있는 `@strata:token-exception`을 쓴다.

## Core / Convention / Profile 분리

| 성격 | 위치 | 예시 |
|---|---|---|
| 검증 가능한 계약 | 이 문서 · `core/rules/layer-rules.yaml` · `core/rules/naming-convention.yaml` | 컴포넌트는 alias를 참조(컴포넌트 토큰은 소유 컴포넌트에서만), 정합 정의, 진입점 enum |
| 도구 바인딩 | `profiles/frontend.next-web/docs/ko/frontend-tokens.md` · `profiles/frontend.next-web/docs/ko/frontend-styling.md` | 토큰 파일 형식, 생성기, 유틸리티 CSS 클래스 매핑, 스토리 도구 |
| 프로젝트 정책 | 프로젝트 Tier P (`layer-map.yaml` · decisions) | 토큰 파일 경로, intent 확장 축, 정본 방향, zone별 집행 강도 |
