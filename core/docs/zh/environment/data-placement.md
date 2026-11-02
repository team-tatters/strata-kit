# 数据放置边界 (Data Placement)

> 正本: strata-kit `core/docs/zh/environment/data-placement.md` (2026-10-29 从 strata `docs/06-environment/data-placement.md` 迁移, DEC-2026-10-29-11)。

> 关于 Strata 产出物**放在哪里、由谁跟踪**的唯一正本 (source of truth)。
> 把原先分散的规则 (cross-model-bridge 的数据表、CLAUDE.md、task-spec-schema、01-context 中 local/shared 的区分) 收敛到这里。
> 核心原则: **"会话是消耗品, 数据在 Core 之外, 工作历史在项目 repo 之外。"**

## 0. 为什么需要 (要解决的问题)

早期设计为了**在会话之间共享, 把 `.strata/handoffs/`、`.strata/tasks/` 在项目 repo 中用 git 跟踪**。结果:

- **提交 churn**: 交接和任务是每个会话都会创建、修改的*工作历史*, 却为了共享而提交到代码 repo, 提交频率高得不正常。
- **重复存储**: 交接先写入 `.strata/handoffs/*.yaml` (repo), 再同步为 vault 的 `sessions/*.md`, 同时把原件原样留在 repo 中, 同一信息重复存在于两处。
- **位置漂移**: 新模型 (shared session ledger、task-spec) 已经以 vault 为正本, 旧模板/脚本却仍指向 `.strata/`, 一个产出物有了两个正本。

解决办法是**把工作历史移出项目 repo (放进 vault), repo 里只留项目专属的指引**。这是在补完"ledger/relay 已迁入 vault"那项决定中尚未完成的部分。

## 1. 3-Tier 边界

```text
Tier L · local      {project}/.strata/local/        git 排除   机器本地、易失的运行时状态
Tier P · project    {project}/.strata/              git 跟踪   项目专属的"指引" (与代码在一起)
Tier V · vault      $STRATA_VAULT/projects/{n}/     vault git  工作"历史"与协作产出物
```

一句话的分类标准:

> **易失的是 L, 项目专属的指引是 P, 工作历史和协作产出物是 V。**

| Tier | 位置 | git | 性质 | 变更频率 |
|---|---|---|---|---|
| **L · local** | `{project}/.strata/local/` | 排除 (.gitignore) | 依赖机器, 在其他机器上会失效, 可重新生成 | 高 (不跟踪, 所以无关紧要) |
| **P · project SoT** | `{project}/.strata/` (根) | 跟踪 | 本项目的架构与约束。应与代码一起通过 PR 评审 | 低 (仅在架构变更时) |
| **V · vault/shared** | `$STRATA_VAULT/projects/{n}/` | vault git (独立) | 在会话之间、人与人之间共享的历史与产出物。与 repo 提交无关 | 高 (在 repo 之外, 没有 churn) |

## 1.5 Placement Profile (embedded | detached)

Tier P 的**物理位置**按项目的 repo 政策在两者中选一个。
Tier 的含义 (项目专属指引) 和评审义务相同, 只有位置不同。(DEC-2026-08-19-01)

| Profile | Tier P 正本位置 | repo 中的痕迹 | 适用标准 |
|---|---|---|---|
| **embedded** (默认) | `{project}/.strata/` — git 跟踪 | `.strata/local/` 的一行 ignore | 个人/受控 repo — Tier P 可与代码一起通过 PR 评审 |
| **detached** | `$STRATA_VAULT/projects/{n}/strata/` — vault git | 仅有 git 排除的 `.strata/local/` (零提交) | 团队 repo 等提交 `.strata` 违反惯例的情况 |

profile 的**正本是 manifest 文件** — 如果只在机器本地保存指针, 换新 PC 就无法恢复 (已体现 cross-review 2026-08-19):

| Profile | manifest 位置 | 保存介质 |
|---|---|---|
| embedded | `{project}/.strata/profile.yaml` (git 跟踪) | 项目 repo — **即使是尚无决定的新项目也能识别** |
| detached | `$STRATA_VAULT/projects/{n}/strata/profile.yaml` | vault — **新 PC 只需 pull vault 就能恢复 profile** |

```yaml
# profile.yaml — placement profile manifest
profile: detached        # embedded | detached (repo 一侧的 manifest 只允许 embedded)
project: "{project-name}"
```

`.strata/local/vault-link.yaml` (Tier L, git 排除) 是**可选的本地缓存** — 不是 SoT, 没有它也能运行。

- **Tier P resolver 规则** (所有读取 Tier P 的使用方通用 — 实现对应: `python3 -m kb --help`、`core/docs/zh/kb-engine.md`):
  ① repo 的 `.strata/profile.yaml` (embedded 声明) → embedded
  ② repo 中存在 `.strata/decisions.yaml`·`.strata/decisions/` (legacy 检测) → embedded
  ③ `.strata/local/vault-link.yaml` (本地缓存) → detached
  ④ `$STRATA_VAULT/projects/{目录 basename}/strata/profile.yaml` → detached (新 PC bootstrap)
  ⑤ 全都没有则为未应用 Strata 的项目
- detached 的 Tier P 树: `strata/{profile.yaml, decisions/, decisions.yaml, constraint-registry.yaml, layer-map.yaml}`
- 如果需要完全不碰 repo, 不要用团队 repo 的 `.gitignore`, 而是把 `.strata/` 登记到 **global gitignore** (`~/.config/git/ignore`)。
- 在 detached 下, 跨 PC 接续会话**只需一次 vault pull 即可完成** (同步钩子: DEC-2026-08-19-02)。
- 必须与团队共享的决定, 在 vault 保管之外, 另行提升到 repo 的 `docs/` (与 §2 的 API 契约提升规则是同一模式)。

## 2. 按产出物的放置 (正本表)

| 产出物 | Tier | 路径 | 备注 |
|---|---|---|---|
| active-task (按会话) | L | `.strata/local/active/{session-id}.yaml` | 会话中断时的当前状态 (绝对规则)。按会话分文件, 避免并发的多个会话互相覆盖 (DEC-2026-08-19-05) |
| session-plan.yaml | L | `.strata/local/session-plan.yaml` | |
| session-log.txt | L | `.strata/local/session-log.txt` | SessionEnd hook 记录 |
| last-compaction.yaml | L | `.strata/local/last-compaction.yaml` | PreCompact 快照 |
| agent-sessions.yaml (会话映射) | L | `.strata/local/agent-sessions.yaml` | claude_id ↔ codex_id, 依赖机器 |
| **profile manifest** | **P** | `.strata/profile.yaml` (embedded) / vault `strata/profile.yaml` (detached) | placement profile 的正本 (§1.5) |
| **decision 记录** | **P** | `.strata/decisions/DEC-{date}-{NN}-{slug}.yaml` | 决定的**正本** — 1 个决定 = 1 个文件。编号与记录经由 decision writer CLI (并发会话安全, DEC-2026-08-19-05) |
| **decisions.yaml (索引)** | **P** | `.strata/decisions.yaml` | 由记录**重新生成的 T0 索引**。禁止手工编辑 |
| **constraint-registry.yaml** | **P** | `.strata/constraint-registry.yaml` | 上下文约束注册表 |
| **layer-map.yaml** | **P** | `.strata/layer-map.yaml` | 用于层违规检查的映射 |
| cowork DB | L | `.strata/cowork/cowork.sqlite*` | CoWorking 的易失状态 (含 WAL)。需持久化的提升物进入 tasks(V)·decision 记录(P) |
| ~~shared/~~ | — | `.strata/shared/` | **deprecated** — 工作历史应完成向 Tier V 的迁移。禁止新建 |
| **handoffs (交接)** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` | 与 shared session ledger 位置相同。**直接写入 vault** |
| **shared session ledger** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` | 上下文 source of truth |
| **tasks (任务规格)** | **V** | `$STRATA_VAULT/projects/{n}/tasks/{date}/{nn}-{title}/` | `_order.yaml` + `task-{nn}.yaml` |
| **relay 记录** | **V** | `$STRATA_VAULT/projects/{n}/relays/` | request/feedback 往来 |
| **Hub delivery state** | **L** | `.strata/local/` 或本地 Hub DB | hub_id、inbox cursor、pull/ack 状态。依赖机器和会话 |
| **Hub audit projection** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` 或 `relays/` | 需要由人接手的 packet/review/decision 摘要 |
| **methodology-backlog (project)** | **V** | `$STRATA_VAULT/projects/{n}/backlog/methodology-backlog.yaml` | 运营队列 = 工作历史性质 |
| **exploration-report / draft api-specs** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` (或 tasks 旁边) | 会话间交接的中间产出物 (accepted API 需提升 — 见下方注释) |
| **DEC 笔记镜像** (供人阅读的 ADR 镜像) | V | `$STRATA_VAULT/projects/{n}/decisions/DEC-{date}-{NN}.md` + `_generated-index.md` | 由记录生成的**供人阅读、做反向链接的镜像**。正本是 Tier P。**生成时点**: decision writer CLI 的 `add`·`regen-index`·`migrate` 写完记录和索引的**紧接着, 在同一次运行内**调用 DEC projection generator, **全量重新生成**该项目的部分 (幂等, 删除没有正本的笔记)。提交由会话结束通道 (handoff/ledger close → vault commit+push) 负责, 需要立即反映时用 `--sync` (DEC-2026-08-21-01) |

| **主题节点树 (toc.yaml)** | **V** | `$STRATA_VAULT/projects/{n}/_meta/toc.yaml` | 供人阅读的目录的**正本**。性质上是指引, 但使用方 (节点页生成器·KB 索引·覆盖率 resolver) 全部在 vault 一侧, 而 detached 项目在 repo 中无处可放, 所以归 V。它不是必须与代码一起评审的变更 |
| **节点页** | V | `$STRATA_VAULT/projects/{n}/nodes/{node-id}.md` | 由 toc.yaml 和四面 frontmatter (规格·约束·决定·会话) 生成的**联接视图** (Index 层, 禁止手工编辑)。**生成时点**: KB 索引构建和会话结束通道 (handoff/ledger close) 在同一次运行内全量重新生成该项目的部分 (幂等, 删除没有正本的页面)。不交给单独的手动运行 — DEC 笔记镜像的教训 |

> **节点页不是正本** — 四面的正本分别是规格(V)、Constraint Card(V) 与 registry(P)、decision 记录(P)、会话(V), 节点页只是以只读方式把它们汇集起来。"债务"一面也只是标示, 其正本是会话文档中没有 `doc_change` 声明这一事实本身。
>
> **decisions 的正本是 Tier P** — 物理位置依 profile 而定 (embedded = repo `.strata/`, detached = vault `projects/{n}/strata/`, §1.5)。vault 的 `projects/{n}/decisions/` 是由记录生成的 **DEC 笔记** (供人阅读、做反向链接, 禁止手工编辑), 不是机器可读的 SoT。
>
> **DEC 笔记镜像的作用与局限** (DEC-2026-08-21-01): embedded 项目的记录正本**在项目 repo 提交并 push 之前, 其他机器读不到**。镜像是通过 vault 通道填补这一空白的跨环境补充装置, 不能取代正本 — 因此 ① 镜像必须在记录写入的**同一次运行**中生成 (交给单独的手动运行就会是空的 — 2026-08-21 某个后端项目镜像为 0 件的实际案例), ② 会话结束闸门 (handoff generator、ledger CLI 的 `validate`/`close`) 会对 repo `.strata/decisions*` 中**未提交的记录发出警告** (不阻断)。detached 项目的记录本身就在 vault 中, 由会话结束通道一并提交, 所以不是闸门的对象。
>
> **API 契约提升规则**: `draft api-specs` 属于 Tier V (会话交接的中间物), 但 **accepted API contract** (成为代码、客户端、文档的依据的时刻) 不是工作历史而是 project artifact → **提升到 Tier P 或 repo 的 `docs/openapi`**。
>
> **backlog 可见性注意**: project 的 `methodology-backlog` 本身是运营队列, 属于 Tier V, 但 **如果 accepted 项目改动了 Tier P (`decisions`/`constraint-registry`/`layer-map`), 该 Tier P 的改动必须出现在同一个 PR 中** (代码评审可见性 — 即使 backlog 移到了 vault, *决定在代码中的落实*仍要在 repo 评审)。

## 3. .gitignore 规则 (项目)

排除 Tier L, 只跟踪 Tier P。Tier V 本来就在项目 repo 之外, 所以无关。

```gitignore
# Strata — 排除 Tier L(local·cowork), 只跟踪 Tier P(指引)  [embedded profile]
.strata/local/
.strata/cowork/
.strata/**/*.tmp

# Tier P 明确跟踪 (不排除):
#   .strata/decisions/  .strata/decisions.yaml
#   .strata/constraint-registry.yaml
#   .strata/layer-map.yaml
```

**detached profile** 的原则是不碰 repo 的 `.gitignore` — 把 `.strata/` 登记到 global gitignore (`~/.config/git/ignore`), 让 repo 中的痕迹保持为 0 (§1.5)。

> ⚠️ 与旧规则 (跟踪 `handoffs/`·`tasks/`) 相比**发生了反转**。以前是"为了共享而跟踪", 现在共享由 **vault (Tier V)** 负责, repo 不再跟踪。

## 4. 为什么是这条边界 (依据)

- **依赖机器的数据 (L) 放进 git 就会失效。** 会话 ID 和本地路径在其他机器上没有意义 (与卡片 `rec.session.state-in-files` 的 local/shared 原则相同)。
- **指引 (P) 与代码同命运。** 架构决定和约束在评审、回滚那段代码时需要一并查看, 所以默认放在同一个 repo、同一个 PR 中 (embedded)。但如果团队 repo 的惯例不允许提交 `.strata`, 就**只把位置**移到 vault (detached, §1.5) — 指引的性质和评审义务不变。变更频率低, 不会产生 churn。
- **历史 (V) 有独立的共享通道。** 交接、ledger、relay 是连接会话与人的历史。这种共享由 **vault (自带的 git/Obsidian 同步)** 专门负责, 没有理由放进代码 repo。代码 repo 只在代码或指引变化时才提交。

## 5. 与其他文档的关系

- **vault 同步**: 交接直接写入 vault (旧的"repo 原件 → vault 转换"重复存储流程作废)。vault 的每种产出物由谁来写, 由 DEC-2026-10-29-04 决定 — DEC 笔记内置于 decision writer CLI 的运行中 (§2 的表), 节点页面由 librarian (`kb views-publish`) 写, 索引元数据按机器各自保存。
- **task-spec-schema.md** (`core/docs/zh/methodology/task-spec-schema.md`): 任务和 backlog 属于 Tier V。路径以这张表为正本。
