# 前端 Swift/SwiftUI Convention

> 正本：strata-kit `profiles/frontend.swiftui/docs/zh/frontend-swiftui.md` — 自 strata `docs/05-conventions/frontend-swiftui.md` 迁移（订单 2026.10.29-06，2026-10-29）。规则 YAML 位于 `core/rules/`。

> Core 边界：`core/docs/zh/architecture/frontend-mobile.md`（`core/rules/layer-rules.yaml` → `frontend.variants.mobile`）· 设计契约：`core/docs/zh/architecture/frontend-design-contract.md` · 执行：`profiles/frontend.swiftui/enforcement/`
> v1 2026-09-10（web variant 绑定，首次应用于 o-rot）→ **v2 2026-09-11**（mobile variant — 词汇、Feature 组装、目标、执行阶梯、钩子，DEC-2026-09-11-01）

本文档是 SwiftUI 应用实现 Core mobile variant（Foundation → … → App Shell）时的约定。
SwiftUI 不是 Core 的必要前提。Core 只规定“哪项职责必须经过哪些层”以及组装和目标共享的规则，本文档把这些规则落到 Swift 的结构上。

## 摘要

- 识别层的一级键是**文件所含类型的角色**，而不是目录。`.strata/layer-map.yaml` 按角色重新分类，文件不移动。
- **执行的正本是编译器。** 把层提升为本地 SPM 包越多，边界就越多地通过 `import` 显现出来。类型引用检查器（`check-swift-layers.py`）是辅助，负责检查同一模块内文件之间的方向。
- 状态所有者是 Feature Block：用 `@StateObject` 创建或用 `@EnvironmentObject` 接收的视图。只接收 `props` 的视图是 Semantic Component。Store 的**创建**和环境注入链只在 App Shell 这一处。
- Feature 只组装同一领域树中的**父 → 子**（`today` → `today/mood`）。兄弟之间共享的部分下沉为 Semantic Component。
- 跨目标共享不是复制，而是添加目标。Foundation、Contract、Primitive、Semantic 可自由共享；DataState 须声明 `stateful: true` 并写明实例分离；Feature、Route、Shell 禁止。
- 令牌以代码仓库中的 `tokens.json` 为正本，Swift 令牌文件是生成物。视图中禁止使用 hex、系统字体和原始数值。

## 层 ↔ Swift 结构

| 层 | 在 Swift 中是什么 | 标识 | 禁止 |
|---|---|---|---|
| Foundation | 令牌 enum（`Color`·`Font`·spacing）、纯 `Shape`、常量 enum、时区之类的纯工具 | `enum {Name}Tokens` · 仅 `static let` | `ObservableObject`、I/O、`UserDefaults`、视图 |
| Contract | `Codable` 模型和 DTO、界面状态值 `{Name}UiState`、纯计算规则（`enum` + `static func`）、深度链接解析器、端口协议 | 值类型 · 仅 `import Foundation` | 导入 SwiftUI、颜色和图标之类的**显示属性**、**名为 `ViewModel`**（在移动端指状态所有者） |
| DataState | `Store`（主 actor 状态所有者）+ `Repository`/`Service`/`Session`（隔离的 I/O） | `@MainActor final class {Name}Store: ObservableObject` · `actor {Name}Repository` | 视图渲染、直接引用其他领域的 Store |
| Primitive UI | 设计系统包中与领域无关的视图（Button·Chip·Row·TabBar） | `public struct {Name}: View` · 轴（variant·intent·size）props · **必须是单独的包** | 领域模型、Store |
| Semantic Component | 只接收 props/UiState 来绘制的有意义的视图 — 图表、舞台、页头、空状态，以及模型的显示属性扩展 | `struct {Domain}{Purpose}View: View` · `{Model}+Style.swift` · `@EnvironmentObject` 0 | 访问 Store、`@StateObject` |
| Feature Block | 界面片段的状态所有者 — 通过 `@StateObject`/`@EnvironmentObject` 持有 Store，并向下传递 props | `struct {UseCase}View` · `{UseCase}Sheet` · 领域树 `today/mood` | 引用兄弟领域的 Feature、拥有导航图 |
| Route Surface | `TabView`·`NavigationStack` 入口、`navigationDestination`、标签页选择、深度链接解析 | `MainTabView` · `{Flow}Flow` | Store 的**创建或引用**（注入归 App Shell）、导出可复用 UI |
| App Shell | `@main struct App`、全局 Store 的创建和 `.environmentObject` 链、`WidgetBundle`、外壳装饰（标签栏） | `{Name}App` · `{Name}Shell` · `{Name}Bundle` | 领域 use case 逻辑、直接引用 Feature |

`can_reference` 与 Core 的表完全一致。这里只补充 SwiftUI 特有的三点。

- **环境注入就是引用。** `@EnvironmentObject var store: TodoStore` 表示该文件引用了 `TodoStore`。Semantic Component 中不得出现 `@EnvironmentObject`。
- **`@StateObject` 的创建就是拥有。** Store 只在 App Shell 创建，界面范围内的状态只在 Feature Block 中创建。Route Surface 创建 Store 属于违规（o-rot 的 `MainTabView` 曾创建 8 个 store，这条规则由此而来）。
- **`@main` 就是 App Shell。** 如果引导/主界面分支之类的入口判断写在 `@main` 中，就把该分支下沉为 `{Name}Shell` 视图，`@main` 只保留 Store 的创建和注入。在拆分之前，连同 DEC 一起放在 layer-map 的 `exceptions` 中。

## Feature 组装

```
Features/Today/TodayView.swift          domain: today        ← 通过 @EnvironmentObject 持有 Store
Features/Today/Mood/MoodSheetView.swift domain: today/mood   ← 由父级（today）用 .sheet 弹出
Features/Activity/ActivityView.swift    domain: activity     ← 与 today 是兄弟。使用 MoodSheetView 即违规
```

- 领域写在 `layer-map.yaml` 的 `domain:` 中，用 `/` 分隔的路径。检查器只放行父 → 子的引用。
- 如果两个兄弟弹出同一个 sheet，就把该 sheet 的渲染部分下沉为 Semantic Component（`MoodPickerView`），各个 Feature 用自己的 Store 包裹它。
- 如果使用 TCA，父 reducer 的 `Scope` 正是这条边。不规定模式名称 — 只守住边的方向。

## 目标

- 手机、小组件、手表、复杂功能（complication）、intent 各自是一个目标。共享就是在 `project.yml` 各目标的 `sources` 中**添加文件**，不创建副本。
- 把共享列表抄写到 `layer-map.yaml` 的 `targets.shared`。检查器会核对各层（`target_share`）。
- 如果两个目标共享 DataState（例如手表使用手机的 `HealthStore` 文件），就声明 `stateful: true`，并在文档中写明每个目标的实例是各自独立的，以及各自读取什么。
- 目标之间的数据交换（App Group `UserDefaults`、`WatchConnectivity`）由 DataState 的一个 `{Name}Session`/`{Name}Bridge` 文件负责。视图直接打开 `UserDefaults(suiteName:)` 属于违规。

## 状态所有权与观察模型

- 默认是 `ObservableObject` + `@Published` + `@MainActor`。Store 是类，模型是结构体。
- `@Observable`（Observation 框架）**仅在部署目标为 iOS 17 / watchOS 10 及以上时**使用。两种模型的属性包装器不同（`@StateObject` ↔ `@State`），更新粒度也不同，混用会导致初始化时机错位 — 一个项目只使用一种模型。（[Apple: Observation](https://developer.apple.com/documentation/observation)，[Squires: not a drop-in replacement](https://www.jessesquires.com/blog/2024/09/09/swift-observable-macro/)）
- Store 只了解自己的领域。把两个 Store 连起来的组装由 Feature Block 完成。Store 引用另一个 Store，属于 DataState 跨领域引用违规。
- 持久化在 Store/Repository 内部完成。`UserDefaults.standard` 或文件 I/O 出现在视图或 Contract 中即属违规。

## 并发

- Swift 6 语言模式会把数据竞争变成编译错误。引入要**渐进**：`SWIFT_STRICT_CONCURRENCY = targeted` → `complete` → 语言模式 6。不要一次全部开启。（[Apple: Adopting strict concurrency](https://developer.apple.com/documentation/swift/adoptingswift6)）
- 视图接触的 Store 全部是 `@MainActor`。I/O 通过 `actor {Name}Repository`，或 `nonisolated` + `Task { @MainActor in … }` 回到 Store。委托回调（`WCSessionDelegate` 等）遵循同样的约定。
- 模型（结构体）默认符合 `Sendable`。只要 Contract 包仅导出 `Sendable`，actor 边界就自然对齐。

## 命名 — 直接采用 Swift API Design Guidelines

正本是 [swift.org API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/)。与 Core `core/rules/naming-convention.yaml` 的 `common.case_styles` 冲突之处，**以 Swift 约定为准**（见下表）。文件名与其所含的顶层类型相同。

| 项目 | Swift | 与 Core 默认的差异 |
|---|---|---|
| 类型、协议 | `UpperCamelCase` | 相同 |
| 函数、变量、属性、case | `lowerCamelCase` | **enum case 用 lowerCamelCase** — 不使用 Core 的 `UPPER_SNAKE` |
| 常量 | `lowerCamelCase`（`static let graceDays`） | 不使用 Core 的 `UPPER_SNAKE` |
| 布尔值 | 读起来像断言 — `isEmpty` · `hasWatch` · `canDelete` | 与 Core 的 Props 规则相同 |
| 界面状态值 | `{Name}UiState`（Contract） | 不使用 Core web 的 `{Name}ViewModel` — 在移动端 ViewModel 是状态所有者 |
| 状态所有者 | `{Name}Store`（DataState） | 对应 Core web 的 `use{Name}State` |
| 工厂 | `make…` | |
| 变更/非变更成对 | `sort()` / `sorted()`、`append` / `appending` | |
| 协议 | 表示是什么 → 名词，表示能力 → `-able` `-ible` `-ing` | |
| 缩写 | 大小写保持一致 — `hrvSeries` · `isHRV`（仅在以大写开头的位置才全部大写） | |
| 参数标签 | 读起来像句子。第一个参数是介词短语时，标签必写 | |
| 禁用后缀 | `Manager` · `Helper` · `Impl` | 与 Core 相同。`Handler` 仅用于委托方法 |

与 Props 对应的是视图的 `init` 参数和存储属性。适用 Core 的 `Props` 规则：父级状态用不带前缀的名词，变更请求用 `on{State}Change`，事件用 `on{Event}`，内部处理函数用 `handle{Event}`。在 SwiftUI 中，`Binding<T>` 就是“值 + 变更的一对”，因此对应 Core 的 `{state}Control` 组合 — 多个子视图使用同一状态时，向下传递一个 `Binding`。

`layer-map.yaml` 的 `naming:` 块不由检查器执行。文件名 = 顶层类型名是约定，在评审中检查。

## 执行阶梯 — 编译器是正本

| 层级 | 负责 | 强度 |
|---|---|---|
| 本地 SPM 包（`Package.swift`） | 把 Foundation、Contract、DataState、Primitive UI 与应用目标隔离。包不能 import 应用，包之间的依赖只能沿 `dependencies:` 中声明的方向 | **编译器强制 — 正本** |
| 目标（`project.yml` / Xcode 目标） | 应用、小组件、手表、测试。共享源码按文件加入目标 | 编译器强制 |
| `check-swift-layers.py` | 单个模块**内部**文件之间的层方向、领域隔离、Feature 组装、目标共享 | CI blocking |
| `--style` 规则 / SwiftLint custom_rules | 原始值、系统字体、`Color(hex:)` 之类的新增流入 | CI blocking，建议以新增行为准 |
| 编辑钩子 | 对 **git 工作树中变更的文件**运行同一个检查器（`--changed`） | exit 2 → 向智能体反馈 |

- **包的阶段。** 存量项目（brownfield）从一个设计系统（Foundation + Primitive UI）包开始。接着是 Contract（模型、规则、`Sendable` 值），然后是 DataState。每提升一个阶段，该边界就会在 `import` 中显现，Core 基于 import 的钩子在 Swift 中也能工作，类型引用检查器的职责则缩减为应用目标内部（Semantic → Feature → Route → Shell）。骨架：`profiles/frontend.swiftui/enforcement/Package.swift.template`。
- **包管理只用 SPM。** 不新引入 CocoaPods、Carthage。（[DECODE: modularize with SPM](https://decode.agency/article/project-modularization-swift-package-manager/)，[Nimble](https://nimblehq.co/blog/modern-approach-modularize-ios-swiftui-spm)）
- **以声明方式生成项目。** 不手工编辑 `.xcodeproj`，而是由 XcodeGen 的 `project.yml`（或 Tuist）生成。目标图必须以文本形式接受评审，层和目标的决定才会体现在 PR 中。（[XcodeGen vs Tuist](https://medium.com/@sayefeddineh/xcodegen-vs-tuist-choosing-the-right-tool-for-xcode-project-generation-bea093c6e105)）
- 外部包要**固定版本**（`exact` 或 `upToNextMinor`），并提交 `Package.resolved`。
- **编辑钩子按 git 而不是按工具事件来挂。** 如果只把 Claude Code 的 PostToolUse 挂在 `Write|Edit` 上，通过 Bash（sed、heredoc）的编辑就会绕过检查。把 matcher 设为 `Write|Edit|Bash`，检查器在 Bash 事件上回退为 `--changed`（以 git status 为准）。配置模板：`profiles/frontend.swiftui/enforcement/settings.json.template`。

## 令牌与字体排印（设计契约绑定）

- 正本是仓库中的 `tokens.json`。Swift 令牌文件（`{Name}Tokens.swift`）是其生成物，`Color(hex:)` 的初始化**只出现在这个文件内**。
- 视图只使用 alias 名称：`OrotColor.sage700` ○ / `Color(hex: "507663")` ✗ / `.font(.system(size: 13))` ✗ / `.padding(14)` 应使用 spacing 令牌。
- 新增 alias 是一项架构决策 — 顺序为 decision 记录 + `tokens.json` → Swift。临时值写作 `/// @strata:token-exception … until YYYY-MM-DD`。
- 字体排印令牌有三个轴：文本比例（标题、正文、说明文字）、**图标尺寸**（`icon.sm/md/lg` — 取代 SF Symbol 的 `.font(.system(size:))`）、**平台比例**（手表不是手机的缩小，而是单独的比例）。如果因缺少某个轴而仍留有 `.font(.system`，应先做新增令牌的 DEC。
- 无障碍由令牌承载：文本对比度达到 4.5:1 以上的 alias 才能用于文本，低于该值的在名称中标明仅限非文本。Dynamic Type 通过 `Font.custom(_:size:relativeTo:)` 由令牌吸收。

## 格式化与 lint

- 格式化工具使用 Xcode 16+ 工具链自带的 **swift-format**（`swift format`、`xcrun --find swift-format`）。配置只有一个 `.swift-format` 文件（模板：`profiles/frontend.swiftui/enforcement/swift-format.json.template`）。（[Xcode 16 swift-format](https://mjtsai.com/blog/2024/11/06/swift-format-in-xcode-16/)）
- lint 将 SwiftLint 作为**可选**项。Strata 要求的只有几条 `custom_rules`，所以即使没有 SwiftLint，`check-swift-layers.py --style` 也会执行同样的正则表达式。如果使用 SwiftLint，就把 `profiles/frontend.swiftui/enforcement/swiftlint-strata.yml.template` 合并进 `.swiftlint.yml`。（[SwiftLint custom rules](https://github.com/realm/SwiftLint#defining-custom-rules)）

## 标记

写在 `///` 文档注释中（`core/docs/zh/conventions/strata-markers.md`）：

```swift
/// 今日状态转换规则 — 仅限纯函数。
/// @strata:layer Contract
/// @strata:domain today
enum StateEngine { … }
```

## 测试

- 单元测试目标用 `@testable import {App}` 直接验证 Contract 和 DataState。已成为包的层，在包自己的测试目标中验证。视图测试不用快照，而是验证 **Store → 状态 → 界面文案**这条路径。
- Store 测试用 `UserDefaults(suiteName: UUID)` 或临时目录隔离。测试中不要碰 `.standard`。
- 文件名为 `{Type}Tests.swift`，测试目标目录在 layer-map 中用 `_test` 排除。检查器会静默跳过 `swift.sources` 之外的文件。

## 存量项目（brownfield）引入流程

1. 用 `profiles/frontend.swiftui/enforcement/layer-map.yaml.template` 创建 `.strata/layer-map.yaml`（`variant: mobile`）。**按角色**分类，不移动文件。Feature 领域写成 `/` 树。
2. 用 `check-swift-layers.py --summary` 把未映射数降到 0。
3. 把 `project.yml` 中各目标的共享源码抄写到 `targets.shared`。DataState 共享用 `stateful: true` + 文档。
4. 用 `--all` 查看违规，分成三类 — 现在修复的 / 连同 DEC 登记到 `exceptions` 的 / 用 `--write-baseline` 冻结并只拦截新增的。
5. 开启 `--style`，重复同样的流程。
6. 在 CI 中加入 `--all --style --ignore-known`。编辑钩子为 `profiles/frontend.swiftui/enforcement/settings.json.template`（Write|Edit|Bash → stdin，Bash 用 `--changed`）。
7. 爬包的阶梯：设计系统 → Contract → DataState。每个阶段都更新 layer-map 的 `swift.sources` 和映射，并重新生成 baseline。

## 本文档不作规定的内容

不规定架构模式名称（MVVM、TCA、Clean）。无论使用哪个名称，只要遵守“Store 属于 DataState，状态所有权属于 Feature Block，props 视图属于 Semantic，组装是父 → 子”即可。网络层和服务端状态缓存工具也作为项目 constraint 处理 — 但 Core 的规则不变：transport 只在 DataState 内部可见，不暴露给视图。Compose/Android 绑定目前只有 `core/docs/zh/architecture/frontend-mobile.md` §Android 中的对应表，还没有单独的文档。
