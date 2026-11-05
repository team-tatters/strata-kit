<div align="center">
    <img src="./media/strata-kit-symbol.svg" alt="strata-kit symbol: layers stitched across a fault" width="160" height="160"/>
    <h1>strata-kit</h1>
    <h3><em>Work in layers. Keep the thread.</em></h3>
    <p align="center">分层构建，线索不断。</p>
</div>

<p align="center">
    <a href="https://github.com/team-tatters/strata-kit/stargazers"><img src="https://img.shields.io/github/stars/team-tatters/strata-kit?style=social" alt="GitHub stars"/></a>
    <a href="https://github.com/team-tatters/strata-kit/blob/main/LICENSE"><img src="https://img.shields.io/github/license/team-tatters/strata-kit" alt="License: MIT"/></a>
    <img src="https://img.shields.io/badge/python-3.11%2B-3776AB" alt="Python 3.11+"/>
    <img src="https://img.shields.io/badge/agents-Claude_Code_%C2%B7_Codex_%C2%B7_AGENTS.md-263D3A" alt="Agents: Claude Code, Codex, AGENTS.md"/>
    <img src="https://img.shields.io/badge/locales-6-C86646" alt="6 locales"/>
</p>

<p align="center">
    <a href="./README.md">English</a> ·
    <a href="./README.ko.md">한국어</a> ·
    <a href="./README.ja.md">日本語</a> ·
    <strong>简体中文</strong> ·
    <a href="./README.es.md">Español</a> ·
    <a href="./README.fr.md">Français</a>
</p>

strata-kit 是一套与 AI 编程智能体协作的方法论，以工具包的形式提供。它的核心是记录：工作的每一步都写进一个普通的 Markdown 文件夹（vault），每个主题只保留一份就地更新的文档，每个新的会话、智能体或人都从这些相同的文档开始。正因如此，工作才能保持一致并跨会话延续，而不是每次对话都从头再来。

它首先运行在 Claude Code 上，也可以运行在 Codex 以及任何读取 `AGENTS.md` 和 `SKILL.md` 的智能体上，包括你用 API 密钥自行运行的智能体。

作者：n0roo · 许可证：[MIT](LICENSE)

## 从哪里开始

| 你想要 | 从这里开始 | 你会得到 |
|---|---|---|
| 在一个项目上试用 | [快速开始](#快速开始) | 一个 vault、插件、生成的指引和第一次会话 |
| 理解其理念 | [它提供什么](#它提供什么) | 在一页中了解记录、规格、建议卡片、技能和检查 |
| 为你的技术栈挑选规则 | [配置文件](#配置文件) | 哪些配置文件已在真实项目中验证，哪些仍是草案 |
| 查阅资料 | [文档](#文档) | 卡片、技能、命令和配置文件的生成表格 |
| 先了解局限 | [现状与局限](#现状与局限) | 哪些已经测量过，哪些还没有 |

## 适用对象

主要面向与编程智能体协作的开发者，尤其是独自把项目从规划带到生产环境的工程师。规划者、设计师和运维人员通过同样的记录参与进来：规划文档与规格、决策以及运维信号。本工具包还没有为这些角色准备完整的专属工作流，也还没有被整个团队使用过。

## 它提供什么

- **始终保持最新的记录。** vault 保存三类记录。工作日志（会话、任务、测试证据）只追加不修改。活文档按主题各一份，描述事物现在的状态，就地更新，并引用其来源的工作日志。索引（决策列表、主题页面）由前两者生成，从不手工编辑。决策由 CLI 写入，每条一个文件，只能通过一条替代它的记录来改变。每个会话都以一次交接结束，交接写明哪些事项未完成以及是什么阻碍了它们。
- **趋于收敛的规格。** 规划文档链接到描述现状形态的规格；规格通过 `covers` 拥有代码；覆盖率门禁会报告没有所有者的已变更代码，以及代码已发生移动的已实现规划，并按项目分级（`advisory` · `default` · `block`），对采用之前就已存在的缺口设有基线。
- **不借助智能体也能学会的方法。** 这些约定（按角色分层、按语言命名，先规划再规格再代码，决策与交接写入文件）是为智能体编写的，但人也可以用同样的方式学习和使用。
- **建议卡片，而不是散文式规则。** 每张卡片都有主张、强度（`must` · `should` · `may`）、适用与不适用的情形、证据、反例以及验证方法。`must` 不容商量；`should` 可以在记录理由后关闭。八条基础规则适用于每个项目。
- **以证据收尾的技能。** 16 个核心技能（入口与路由、指引向导、规划、规格、订单、构建任务、验证、评审、决策、知识更新、交接、提炼、翻译、回顾、运维信号、安全），提供六种语言，另有可选扩展包（构思、设计）。每个技能都说明何时使用、以什么证据结束，以及智能体想跳过某一步时会找的借口和对每个借口的回答。六个角色（builder、worker、reviewer、supporter、operator、librarian）各自规定了可以做和不可以做的事。
- **应用有钩子就用钩子，没有就用普通文件。** 在 Claude Code 中，钩子和卡片引导整个流程：会话开始时的头部信息显示项目、它的 `must` 卡片以及从文件中读取的下一步行动，并且在上下文被压缩之前由钩子保存状态。在没有钩子的地方，同样的指引和技能就是普通的 `AGENTS.md` 和 `SKILL.md` 文件，知识库引擎则是一个命令行工具和一个 MCP 服务器。
- **围绕你已有检查器的分级检查。** `kb enforce run` 包装现有的检查器（分层测试、dependency-cruiser、lint），并记录每一次运行，因此一个规则族可以在其数据明确之后再提升等级。

## 文档

由源文件生成的参考表格：[卡片](docs/reference/cards.md) · [技能](docs/reference/skills.md) · [命令](docs/reference/cli.md) · [配置文件](docs/reference/profiles.md)（韩语：`docs/ko/reference/`）。指南和概念页面正在编写中。面向智能体的完整方法论参考位于 `core/docs/en/`。

## 目录结构

```text
core/       基础规则(constitution/)、建议卡片、角色、模式、分层与命名规则、文档(六种语言)
profiles/   按技术栈打包: 卡片选择、layer-map 与检查器模板、约定
skills/     SKILL.md 流程与 registry.yaml(入口技能读取的路由表); packs/
kb/         知识库引擎: 存储、搜索、门禁、决策 CLI、MCP 服务器
tools/      向导、插件与打包生成器、校验器、doctor、度量、evals 运行器
adapters/   Claude Code 插件与 Codex 打包的输入
i18n/       术语表与待翻译标记
```

## 配置文件

| 配置文件 | 状态 |
|---|---|
| `core.generic` | active |
| `frontend.next-web` (Next.js / React) | active |
| `backend.kotlin-spring-cqrs` | active |
| `backend.go-service`, `backend.typescript-nest`, `cli.go`, `frontend.swiftui`, `service.rust` | draft |

*active* 表示该配置文件已在真实项目中使用，其分层规则的检查器已在该项目上运行并留下了记录。draft 配置文件已有文档和规则，但其检查器尚未在项目中得到验证。

## 快速开始

环境要求：Python 3.11+、git、用于 MCP 服务器的 [uv](https://docs.astral.sh/uv/)、用于插件的 Claude Code。

1. 准备好工具包和 vault。vault 是一个普通的 Markdown 文件夹（建议使用 git 仓库），交接、任务、知识文档和度量都存放在这里。`kb vault-init` 会根据 `core/templates/vault/` 中的模板创建 vault，并且绝不覆盖已有文件。

   ```sh
   git clone https://github.com/team-tatters/strata-kit.git ~/workspace/strata-kit
   export STRATA_KIT=~/workspace/strata-kit
   cd "$STRATA_KIT" && uv sync
   python3 "$STRATA_KIT/kb" vault-init ~/workspace/vault --project my-app   # add --detached to keep Tier P in the vault
   export STRATA_VAULT=~/workspace/vault        # required: the engine never guesses a vault path
   ```

2. 构建并安装 Claude Code 插件。

   ```sh
   python3 "$STRATA_KIT/tools/gen_claude_plugin.py" --locale en
   claude plugin marketplace add "$STRATA_KIT/dist/claude"
   claude plugin install strata-kit@strata-kit
   ```

   它会注册会话开始头部信息钩子、压缩前快照钩子、各项技能、六个角色智能体以及知识库 MCP 服务器。对于 Codex，`tools/gen_codex_bundle.py` 会写出技能和角色说明。

3. 为项目生成指引，或者直接对智能体说“为这个项目设置 strata 指引”。

   ```sh
   python3 "$STRATA_KIT/tools/wizard.py" diagnose  <project>
   python3 "$STRATA_KIT/tools/wizard.py" recommend <project> --profile <id> --uses-vault yes
   python3 "$STRATA_KIT/tools/wizard.py" generate  <project> --apply
   python3 "$STRATA_KIT/tools/wizard.py" verify    <project>
   ```

4. 在项目中打开一个会话。头部信息会显示项目、它的 must 卡片以及从文件中读取的下一步行动；说出你想做的事，入口技能会把它分派到合适的技能。结束时说“handoff”。

项目也可以完全不把 strata 放进共享仓库（`detached`）：此时指引和记录都存放在 vault 中，仓库只接收其 CI 要运行的内容。

## 现状与局限

- 每个核心技能都有压力场景：没有该技能时失败，有该技能时通过（`skills/*/evals/`）。
- 证明这一方法能让工作变得更好的证据，来自一个人在少量项目上的实践。它尚未在其他地方得到复现，也还没有测量表明它优于其他工作方式。
- `core/docs/en/` 下的文档树以及规则文件、模板和检查器 README 都是英文的。许多 `kb` 代码注释和部分命令行消息仍是韩文。
- Quilt 是与本工具包一同构建的编排器，作为可选适配器提供（`--harness quilt`）；其适配器尚未包含在本仓库中。除此之外没有任何部分依赖它。
- 新团队应当把所有检查都从 `advisory` 开始，只有在看过某个规则族的数据之后再提升其等级。

## 参与贡献

欢迎提交 Issue 和 Pull Request，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。安全问题请按照 [SECURITY.md](SECURITY.md) 中的说明报告。

第三方材料列在其旁边的 `NOTICE.md` 文件中（`skills/packs/*/`）。
