---
title: "표현 예시 — 글래스모피즘·뉴모피즘·겹 테두리와 그림자·역할"
type: design-expression
scope: brand
owner: example
status: active
---

# 표현 예시

> `python3 -m kb taste expression <이 파일> --show` 가 계산값을 보인다. 원값은 한 곳에만 있고, 기법은 원값의 이름과 관계식으로만 적는다.

## 원값

밝은 회청색 바탕에 거의 검은 글자. 유리는 반쯤 비치고 16px 로 흐린다. 모서리는 넉넉하게 둥글다.

```yaml
primitives:
  color.page: "#dfe5ee"
  color.surface: "#f2f4f7"
  color.ink: "#1b1f24"
  color.accent: "#3b6ef5"
  color.night: "#111418"
  opacity.glass: 0.55
  blur.glass: 16px
  radius.card: 16px
  space.edge: 1px
  shadow.y: 8px
  shadow.blur: 24px
  font.body: "Pretendard"
```

## 기법: 글래스모피즘

바탕이 비치는 반투명 면 위에 바탕보다 조금 밝은 가는 테두리를 둔다. 면이 반투명이어도 글자는 바탕 위에서 4.5 대 1 이상 읽혀야 한다.

```yaml
derive:
  glass.fill: alpha(color.surface, opacity.glass)
  glass.edge: alpha(lighten(color.surface, 0.04), 0.8)
layers:
  - {fill: glass.fill, blur: blur.glass, radius: radius.card}
  - {border: glass.edge, width: space.edge}
relations:
  - contrast(color.ink, glass.fill, color.page) >= 4.5
  - lightness(glass.edge) > lightness(color.page)
```

## 기법: 뉴모피즘

면은 바탕과 같은 색이고, 위쪽은 밝은 그림자, 아래쪽은 어두운 그림자로 솟아 보인다. 밝은 쪽과 어두운 쪽은 바탕에서 같은 거리만큼 떨어진다.

```yaml
derive:
  neu.light: lighten(color.page, 0.06)
  neu.dark: darken(color.page, 0.06)
layers:
  - {fill: color.page, radius: radius.card}
  - {shadow: neu.light, y: shadow.y, blur: shadow.blur}
  - {shadow: neu.dark, y: shadow.y, blur: shadow.blur}
relations:
  - lightness(neu.light) > lightness(color.page)
  - lightness(neu.dark) < lightness(color.page)
  - contrast(color.ink, color.page) >= 7
```

## 기법: 겹 테두리와 그림자

강조색 테두리 바깥에 강조색을 어둡게 한 두 번째 테두리, 그 아래 옅은 그림자. 안쪽 테두리가 바깥 테두리보다 밝다.

```yaml
derive:
  stack.inner: color.accent
  stack.outer: darken(color.accent, 0.15)
  stack.shade: alpha(darken(color.page, 0.3), 0.25)
layers:
  - {border: stack.inner, width: space.edge}
  - {border: stack.outer, width: space.edge}
  - {shadow: stack.shade, y: shadow.y, blur: shadow.blur}
relations:
  - lightness(stack.inner) > lightness(stack.outer)
  - contrast(stack.outer, color.page) >= 3
```

## 기법: 역할

제품 계약이 없는 슬라이드·포스터·리포트에서 쓰는 역할 이름. 본문 글자는 바탕 위에서 4.5 대 1, 큰 글자와 강조는 3 대 1 이상. 어두운 바탕에서는 같은 강조색을 쓰지 않고 명도를 올린 값을 쓴다.

```yaml
derive:
  bg: color.page
  text.primary: color.ink
  accent: color.accent
  bg.dark: color.night
  text.primary.dark: color.surface
  accent.dark: lighten(color.accent, 0.2)
layers:
  - {fill: bg}
relations:
  - contrast(text.primary, bg) >= 4.5
  - contrast(accent, bg) >= 3
  - contrast(text.primary.dark, bg.dark) >= 4.5
  - contrast(accent.dark, bg.dark) >= 3
  - lightness(accent.dark) > lightness(accent)
```
