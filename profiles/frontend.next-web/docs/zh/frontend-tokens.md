# 前端 Token Convention

> 正本：strata-kit `profiles/frontend.next-web/docs/zh/frontend-tokens.md` — 从 strata `docs/05-conventions/frontend-tokens.md` 迁移（订单 2026.10.29-06，2026-10-29）。规则 YAML 位于 `core/rules/`。

> Core 契约：`core/docs/zh/architecture/frontend-design-contract.md`

本文档是将令牌三层（Primitive → Alias → Component）映射到文件、构建和工具类 CSS 的惯例。
格式和工具项目可以更改，更改后应记录在项目 profile 中，而不是这里。

## 正本文件

- 位置：Foundation 包内的单个文件（例如 `tokens/tokens.json`）。
- 格式：推荐 W3C Design Tokens（DTCG）JSON — 支持 `$value`·`$type`·alias 引用（`{color.blue.80}`），并且设计工具同步插件可以读取。
- 在一个文件中同时放置 T1·T2，用顶层分组区分（`primitive.*`、`alias.*`）。T3 仅在需要时使用 `component.*`。
- 模式通过 alias 值的 `$extensions.modes` 或单独的 mode 文件表达。无论哪种模式，名称只有一个。

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

## 生成物（仅在构建阶段解析）

| 生成物 | 使用者 | 备注 |
|---|---|---|
| CSS 变量（`--color-action-primary-bg-default`） | 工具类 CSS · 运行时主题 | 只暴露 alias。T1 变量用内部前缀隐藏，或不生成 |
| TS 常量（`tokens.color.action.primary.bg.default`） | 需要样式对象的地方 | 类型从 alias 路径推导 |
| 设计工具变量 | 设计师 | 同步工具（例如 Tokens Studio·Variables API）— 方向由 profile 决定 |
| **alias 目录**（`tokens.md`，生成） | 智能体 · 评审者 | 名称·含义·用途各一行。保持在 T0 上下文预算之内的大小 |

组件代码只使用生成物的 **alias 名称**。不直接 import 令牌文件，也不自行计算值。

## 工具类 CSS 映射

工具类是 alias 的传递手段。类名原样反映 alias 路径。

| 允许 | 禁止 |
|---|---|
| `bg-surface-default` · `text-muted` · `border-status-pending` | `bg-blue-80`(T1) · `bg-[#1b4380]`(任意值) · `text-[13px]` |

主题配置（例如 Tailwind `@theme`·preset）是生成物，不得手工编辑。不生成 T1 工具类（`bg-blue-80`）是最简单的强制执行方式。

## 故事（无设计工具时的正本）

- Primitive UI：每个组件至少一个故事，以表格形式展示所有 variant·intent·size 组合。
- Semantic Component：数据状态轴（default · loading · empty · error）各自一个故事。
- Foundation：设置 alias 目录故事（颜色·间距·阴影·字体排印）— 设计师无需工具即可评审的界面。

## 检查

| 检查 | 方法 | 位置 |
|---|---|---|
| Foundation 之外的 raw 值 | 新增行 diff 检查 — hex·rgba·px 字面量·`[…]` 任意值·T1 类模式 | `profiles/frontend.next-web/enforcement/diff-rules.json.template` |
| 例外过期 | 解析 `@strata:token-exception … until YYYY-MM-DD`，今天已超过该日期则失败 | 同一脚本 |
| 令牌变更审批 | 含令牌文件 diff 的 PR，正文中须有 DEC id | CI 规则或 PR 模板 |

## 禁止

- 在组件中使用 T1 名称·raw 值·任意值
- 绕过令牌文件而手工编辑主题
- 在 alias 名称中包含调色板名称·界面名称（`color.blue.button`、`color.dashboard.header`）
