# strata.init-wizard

## 概述

指引向导根据建议卡片为项目组装指引。它只就代码无法回答的事项进行访谈，依据配置文件的检测规则诊断技术栈，连同证据提出建议卡片，在用户批准后生成适配器，并验证结果。当核心修订变动时，它也是重新生成的路径。它绝不会写入已批准提案所列路径之外的位置。

## 适用场景

- 项目没有 `.strata/profile.yaml`（using-strata 会把你送到这里）。
- 用户要求设置、修改或重新生成指引。
- 配置文件、建议卡片或豁免必须变更。
- 日常工作不适用：那由 using-strata 路由到负责的技能。

## 流程

1. **先从代码诊断。** 运行 `python3 tools/wizard.py diagnose <project>`。它读取构建文件和清单，匹配配置文件的检测规则，度量始终加载的预算，并列出它无法判定的事项。证据：`.strata/kit/diagnosis.yaml`。
2. **一次只问一个问题。** 只询问诊断中遗留的开放问题（团队规模、预期寿命、存在跨领域写入的领域数量、共享环境、在用的运行环境）。绝不询问诊断已经回答的内容。证据：答案追加到 `diagnosis.yaml` 的 `answers` 下。
3. **提出建议卡片。** 运行 `python3 tools/wizard.py recommend <project> --profile <id> [--locale ko]`。逐张呈现建议卡片：id、强度、claim、证据引用以及反例。must 卡片要解释，不可协商。用户拒绝某张 should 卡片时，记录 `waived_reason`。用户对某张 must 卡片提出异议时，记录一条 counter_example 候选（进入待办库，不进入项目）。可选采用的 must 卡片（`adoption: opt_in`，不在宪章内）以提问方式确认：提案为每张卡片标出默认值（用户 `~/.strata/config.yaml` 的 `wizard.adopt_cards`，其次是配置文件的 `cards_default`），答案用 `--adopt <id>` 或 `--decline <id>=<理由>` 记录（拒绝连同理由记入提案和注册表）。条件式 must 卡片（`adoption: conditional`）不询问：项目符合其事实时即载入——`uses_vault`（`--uses-vault yes|no`）、`uses_quilt`（`--harness …,quilt`）、`domain_work`（领域）。说明载入了哪些卡片及原因。 按规则族（`layers`、`naming`、`rules`）询问执行等级：advisory 只记录违规，default 若无附理由和期限的覆盖则失败，block 失败；未声明的规则族保持 block。用 `--enforce <规则族>=<等级>` 记录，写入清单，检查器通过 `kb enforce run` 包装。输出违规却以 0 结束的警告模式检查器用 `--violation-exit 0,1 --violation-pattern <违规标记>` 包装；记错的条目不改写，用 `kb enforce correct` 追加更正条目。 证据：`.strata/kit/proposal.yaml`，其中 `approved: true` 由用户设置。
4. **生成。** 运行 `python3 tools/wizard.py generate <project> --apply`。它只写入提案中列出的路径，并写上 `core_revision` 和 `adapter_revision`。已有的手写文件（开头没有生成标记）只有在提案的 `overwrite_handwritten` 中列出时才会被替换；替换前先把其内容移到 `.strata/kit/notes.<locale>.md`。证据：命令输出中已写入文件的列表。
5. **验证。** 运行 `python3 tools/wizard.py verify <project>`。它检查预算（始终加载的字节数）、修订头和注册表，并通过注册表触发条件运行五个示例请求。证据：退出码 0 及报告。
6. **记录。** 如果配置文件的选择或某项豁免对本项目而言是架构决策，用决策记录写入工具记录下来。证据：回复中的 DEC id。

## 借口与反驳

| 想法 | 反驳 |
|---|---|
| “技术栈很明显，跳过 diagnose。” | diagnose 还会度量预算并发现漂移。运行它；只是一条命令。 |
| “用户了解规则，跳过证据。” | 没有证据的建议卡片只是意见。展示引用；这正是关键所在。 |
| “这张 must 卡片不适合这里，豁免它。” | must 不可豁免。向用户解释，并把异议记录为 counter_example 候选。 |
| “全部生成，不要的让他们删。” | 只写入已批准的路径。未被要求的文件就是漂移。 |
| “上次验证通过了。” | 核心修订可能已经变动。每次 generate 之后都要验证。 |

## 警示信号

- 访谈问题的答案其实就在 `package.json`、`build.gradle`、`go.mod` 或 `Cargo.toml` 中。
- 提案中有建议卡片没有 `evidence` 条目。
- 生成的 AGENTS.md 头部没有 `core_revision`。
- 文件被写到提案路径列表之外。

## 验证

- `.strata/kit/proposal.yaml` 存在且 `approved: true`，每张建议卡片都有证据。
- 每张被豁免的 should 卡片都有 `waived_reason`。
- `tools/wizard.py verify <project>` 退出码为 0，其报告已在回复中给出。
- 所做的任何决策都已记录，其 id 已在回复中给出。
