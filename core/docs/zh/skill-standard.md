# 技能标准

strata-kit 的技能是智能体要遵循的工作流，而不是随手翻阅的参考资料。`core/schemas/skill.schema.yaml` 中的模式固定了其形态；本页说明每个部分为何存在以及如何撰写。

## 形态

```text
skills/<name>/
├── SKILL.md            English canonical: frontmatter + yaml block + six sections
├── i18n/ko.md …        localized bodies, same section order
├── evals/              pressure scenarios and results (RED / GREEN / REFACTOR)
├── references/         long material the body links to
└── scripts/            bundled tools, run through their interpreter
```

## Frontmatter

`name` 是 harness 用来匹配的扁平标识符。核心技能为 `strata.<verb>`；入口技能为 `using-strata`。

`description` 是智能体在决定是否打开该技能之前唯一能看到的内容。它以 “Use when” 开头，随后列出情境、症状和关键词。它绝不概括工作流：读到摘要的智能体会按摘要行事而不是按正文行事，而检查点恰恰在正文里。

## yaml 块

紧跟在 H1 之后是一个带围栏的 `yaml` 块，含有 `id`、`version`、`owner`、`triggers`、`inputs`、`outputs`、`required_context`、`allowed_tools`、`validation`、`failure_modes`。它是正文的机器可读孪生版本，生成器读取它来构建适配器和注册表。`validation` 与“验证”一节一一对应。

## 六个部分

1. **概述**：一段话，说明该技能产出什么。
2. **适用场景**：触发条件和明确的非触发条件。
3. **流程**：编号步骤。每一步都指明一个检查点及其留下的证据（文件、命令输出、记录 id）。
4. **借口与反驳**：智能体用来跳过某一步的借口（“这只是个小改动”“我记得这条规则”），每条都附有反驳。智能体默认走最短路径；本节是与之相抗衡的力量。
5. **警示信号**：表明技能被跳过或误用的可观察迹象，写成评审者或关卡能够检测到的形式。
6. **验证**：在技能可以报告完成之前，什么必须成立，以及什么证据可以证明。“看起来对”永远不是证据。

## 为智能体而写

- 对于智能体明知故犯而跳过的步骤，用禁止性表述。对于遗漏，用带必填槽位的模板。对于取决于条件的行为，用条件句。
- 不要留有余地的措辞。“除非有影响，否则不要做 X” 会重开谈判；把真正的例外写成单独的条件句。
- 保持 `SKILL.md` 在 300 行以内。较长的参考材料放入 `references/` 并以链接引用，这样技能在被需要之前消耗的 token 很少。
- 一个完整、可运行的示例胜过三个残缺的示例。

## 测试技能

编写技能就是把测试驱动开发应用于流程。用一个没有该技能的子智能体运行 `evals/` 中的场景，记录它跳过了什么以及如何为此辩解（RED）。编写能解决这些失败的最小技能并再次运行（GREEN）。堵住它发现的漏洞并再运行一次（REFACTOR）。将场景、转录摘要和结论保存在 `evals/` 中。没有记录过 RED 运行的技能只是草稿。

## 本地化

只翻译正文。yaml 块、frontmatter 和所有标识符保持英文。技能变为 `active` 之前，`en` 和 `ko` 是必需的；其余四种语言环境带警告回退到英文（见 `LOCALES.md`）。
