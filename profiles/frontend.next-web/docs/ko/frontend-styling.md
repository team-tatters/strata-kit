# 프론트엔드 Styling Convention

> 정본: strata-kit `profiles/frontend.next-web/docs/ko/frontend-styling.md` — strata `docs/05-conventions/frontend-styling.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> Core 경계: `core/docs/ko/architecture/frontend-web.md` · 디자인 계약: `core/docs/ko/architecture/frontend-design-contract.md` · 토큰 바인딩: `profiles/frontend.next-web/docs/ko/frontend-tokens.md`

이 문서는 스타일링 도구를 Core 레이어에 매핑하는 convention입니다.
Core는 특정 UI 라이브러리나 CSS 도구를 요구하지 않습니다.

## Layer Mapping

- Primitive UI는 alias 토큰과 variant 축(`variant · intent · size · state`)만으로 외형을 정한다.
- Semantic Component는 Primitive의 축 값과 alias 토큰의 조합으로만 외형을 정한다 (Composition Legality).
- Feature Block은 특정 use case 화면 조각이며 레이아웃도 alias(space·radius)로 표현한다.

## 축 값 규칙

- 색 축의 값은 의도(`intent`)다. 팔레트명(`green · red · blue`)을 축 값으로 쓰지 않는다.
- 도메인 상태(예: `pending · completed`)가 필요하면 `intent`에 섞지 않고 별도 `status` 축으로 둔다.
- 디자인 도구의 컴포넌트 속성 이름과 코드 props 이름을 같게 유지한다 — 정합 검사의 전제.

## Project-Specific Mapping

MUI, Tailwind, CSS-in-JS, design-system package 같은 선택은 project profile 또는 이 convention의 프로젝트별 확장에 둡니다.
어떤 도구를 쓰든 규칙은 같다: 유틸리티 클래스·스타일 객체는 alias 이름을 비추고, raw 값과 T1 이름은 Foundation 밖에 나오지 않는다.
그 선택은 Core 규칙이 아니라 프로젝트 constraint입니다.
