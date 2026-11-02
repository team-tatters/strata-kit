# 前端 Mobile 层架构

> 正本：strata-kit `core/docs/zh/architecture/frontend-mobile.md` — 从 strata `docs/03-architecture/frontend-mobile.md` 迁移而来（订单 2026.10.29-06，2026-10-29）。规则 YAML 位于 `core/rules/`。

> 机器可读规则：`core/rules/layer-rules.yaml` → `frontend.variants.mobile` (DEC-2026-09-11-01)
> 本文档是原生移动 UI (SwiftUI、Jetpack Compose) variant 供人阅读的详细说明。
> 绑定：`profiles/frontend.swiftui/docs/zh/frontend-swiftui.md`（已验证，o-rot）· 尚无 Compose 绑定（§Android）。
> token、变体、组合以及设计产物的一致性，由 `core/docs/zh/architecture/frontend-design-contract.md` 定义。

## 为什么是不同于 web 的 variant

8 个层和 `can_reference` 表与 `web` **完全相同**。首次应用 SwiftUI (o-rot, 2026-09-10) 时，46 处违规全部
是文件边界问题，设计问题为 0，因此层的语义原样沿用。不同之处有四点。

| 轴 | web | mobile |
|---|---|---|
| 词汇 | URL 入口、`use*Query`、`.service.ts`、Contract 的 `{Name}ViewModel` = 数据形状 | 导航图入口、`Store`/`Repository`，Contract 使用 `UiState`/`UiModel`。**ViewModel 这个名字表示状态持有者，所以不用于 Contract** |
| Feature 组装 | 禁止 Feature Block 之间互相引用 | 允许在同一领域树内进行**父 → 子**组装 (`composition: parent_child`)。兄弟之间和反方向禁止 |
| 目标 | zone、包 | 应用、小组件、手表、intent **把文件放入多个 target** 来共享。可共享的层由 Core 规定 |
| 执行阶梯 | import 路径的静态分析 | 编译器（模块边界）为正本，类型引用检查器是模块**内部**的辅助 |

| Layer | can_reference |
|---|---|
| Foundation | 无 |
| Contract | Foundation |
| DataState | Foundation, Contract |
| Primitive UI | Foundation |
| Semantic Component | Foundation, Contract, Primitive UI |
| Feature Block | Foundation, Contract, DataState, Primitive UI, Semantic Component |
| Route Surface | Foundation, Contract, Feature Block, App Shell |
| App Shell | Foundation, Contract, DataState, Primitive UI, Semantic Component |

## 层 ↔ 移动端构造

| Layer | SwiftUI | Compose（未验证） |
|---|---|---|
| Foundation | token `enum`、纯 `Shape`、时区工具 | token `object`、`MaterialTheme` 扩展、纯工具 |
| Contract | `Codable` 结构体、`{Name}UiState`、纯规则 `enum` + `static func`、深链接解析器 | `data class`、`sealed interface UiState`、use case 纯函数 |
| DataState | `@MainActor final class {Name}Store: ObservableObject` + `actor {Name}Repository` | `ViewModel`（持有状态）+ `Repository`（`suspend` + `Dispatchers.IO`），Room/DataStore |
| Primitive UI | 设计系统包中的 `public struct: View` | `core:designsystem` 模块中的无状态 composable |
| Semantic Component | 只接收 props 的视图，`@EnvironmentObject` 为 0，`{Model}+Style.swift` | 只接收 `UiState` 的 composable，`hiltViewModel()` 为 0 |
| Feature Block | 持有 `@StateObject`/`@EnvironmentObject` 的画面片段 | `{UseCase}Screen` + `hiltViewModel()` |
| Route Surface | `TabView`、`NavigationStack`、`navigationDestination`，深链接解析 | `NavHost`、type-safe route，深链接 |
| App Shell | `@main App`、全局 Store 的创建与 `.environmentObject` 链、`WidgetBundle` | `Application`、`MainActivity`、Hilt 模块、`Scaffold` |

## Feature 组装 (composition)

移动端的画面是层级结构 — Today 画面弹出心情面板，活动标签页弹出会话完成面板。如果原样保留 web 的“禁止 Feature Block 之间引用”，
这些组装就全部成了违规。mobile 把领域当作路径使用。

- 领域用 `/` 构成树，例如 `today`、`today/mood`。在 `.strata/layer-map.yaml` 的 `domain:` 中明确写出。
- **父可以引用子。** `today` 的 Feature Block 组装 `today/mood` 的面板。
- 子 → 父、兄弟之间 (`today` ↔ `activity`) 禁止。如果两个领域使用同一个片段，该片段下沉为 Semantic Component。
- TCA 的父 reducer → 子 reducer 作用域，以及 Compose 的父 Screen → 子 Screen，遵循同一规则。

## 目标 (targets)

在 Apple 平台上，应用、小组件、手表、手表复杂功能 (complication)、App Intents 各自是一个 target；在 Android 上则是应用、小组件、Wear 模块。把一个文件放入多个 target
是惯例，而复制是漂移（drift）的种子。Core 只规定**什么可以共享**。

| 层 | 共享 | 条件 |
|---|---|---|
| Foundation · Contract · Primitive UI · Semantic Component | 自由 | 没有状态 |
| DataState | 有条件 | `layer-map targets.shared[].stateful: true` + 在文档中明确**每个 target 各有独立实例**（例如手表的 HealthStore 读取自己的 HealthKit） |
| Feature Block · Route Surface · App Shell | 禁止 | 每个 target 的画面、入口、外壳都不同 |

检查器读取 `layer-map.yaml` 的 `targets.shared` 并与各层比对（`target_share` 违规）。正本是项目文件
（`project.yml` 中各 target 的 `sources`），layer-map 只是照抄该声明。

## 执行阶梯

| 层级 | 负责 | 强度 |
|---|---|---|
| 模块边界（SPM 包 / Gradle 模块） | 把 Foundation · Contract · DataState · Primitive UI 与应用 target 隔离。包不能 import 应用 | **编译器强制 — 正本** |
| target | 应用、小组件、手表、测试。共享通过按文件添加 target 实现 | 编译器强制 |
| 类型引用检查器 (`check-swift-layers.py`) / ArchUnit · Konsist | 一个模块**内部**文件之间的方向、领域隔离、组装、target 共享 | CI blocking |
| style 规则 | 新引入的 raw 值、系统字体、`Color(hex:)` | CI blocking，按新增行为准 |
| 编辑钩子 | 对改动的文件执行与上面相同的命令 — **以 git 工作树为准**（而不是工具事件） | warning → 以 exit 2 向智能体反馈 |

每提升一个包，检查器负责的部分就减少一些。当 Contract 和 DataState 成为包后，该边界会体现在 `import` 上，
Core 基于 import 的钩子在 Swift 中也能工作。存量项目（brownfield）先从一个设计系统包开始，再按 Contract → DataState 的顺序提升。

## Android（未验证）

Compose 的对应关系仅是上表的右列，尚未在真实项目中验证。应用时需要确认：

- Google 官方指南的 UI / Domain / Data 三层，对应 mobile 的 (Primitive+Semantic+Feature+Route) / Contract / DataState。这是细化，不是冲突。
- 执行复用 Gradle 多模块 + `profiles/backend.kotlin-spring-cqrs/enforcement/` 的 brownfield 模式 (layer-map)。Kotlin 的 import 是显式的，因此不需要类型引用检查器。
- 进程终止后的恢复 (`SavedStateHandle`)、感知生命周期的收集、DI 模块的放置 (App Shell)、KMP `commonMain`（共享 Contract + DataState），由 Compose 绑定文档规定。方法论待办库 MB-o-rot-2026-004。

## Core / Convention / Profile 分离

- **Core**（本文档 + `core/rules/layer-rules.yaml`）：层、`can_reference`、组装、target 共享规则。与平台无关。
- **Convention**（`profiles/frontend.swiftui/docs/zh/frontend-swiftui.md`，之后的 `frontend-compose.md`）：如何把层对应到语言构造、并发、命名、包管理。
- **Profile**（项目的 `.strata/layer-map.yaml` · `constraint-registry.yaml`）：文件映射、领域树、target 共享列表、例外。
