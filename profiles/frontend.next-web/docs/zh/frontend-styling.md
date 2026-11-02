# 前端 Styling Convention

> 正本：strata-kit `profiles/frontend.next-web/docs/zh/frontend-styling.md` — 从 strata `docs/05-conventions/frontend-styling.md` 迁移（订单 2026.10.29-06，2026-10-29）。规则 YAML 位于 `core/rules/`。

> Core 边界：`core/docs/zh/architecture/frontend-web.md` · 设计契约：`core/docs/zh/architecture/frontend-design-contract.md` · 令牌绑定：`profiles/frontend.next-web/docs/zh/frontend-tokens.md`

本文档是将样式工具映射到 Core 层的 convention。
Core 不要求特定的 UI 库或 CSS 工具。

## Layer Mapping

- Primitive UI 仅通过 alias 令牌和 variant 轴（`variant · intent · size · state`）决定外观。
- Semantic Component 仅通过 Primitive 的轴值与 alias 令牌的组合决定外观（Composition Legality）。
- Feature Block 是特定 use case 的界面片段，布局也用 alias（space·radius）来表达。

## 轴值规则

- 颜色轴的值是意图（`intent`）。不得把调色板名称（`green · red · blue`）用作轴值。
- 如果需要领域状态（例如 `pending · completed`），不要混入 `intent`，而是单独设一个 `status` 轴。
- 设计工具中的组件属性名称与代码中的 props 名称保持一致 — 这是一致性检查的前提。

## Project-Specific Mapping

MUI、Tailwind、CSS-in-JS、design-system package 之类的选择，放在 project profile 或本 convention 的项目级扩展中。
无论使用哪种工具，规则都相同：工具类·样式对象反映 alias 名称，raw 值和 T1 名称不得出现在 Foundation 之外。
这一选择不是 Core 规则，而是项目的 constraint。
