# フロントエンド Mobile レイヤーアーキテクチャ

> 正本: strata-kit `core/docs/ja/architecture/frontend-mobile.md` — strata `docs/03-architecture/frontend-mobile.md` から移管 (オーダー 2026.10.29-06, 2026-10-29)。ルール YAML は `core/rules/`。

> 機械可読ルール: `core/rules/layer-rules.yaml` → `frontend.variants.mobile` (DEC-2026-09-11-01)
> この文書は、ネイティブモバイル UI (SwiftUI・Jetpack Compose) variant の人が読むための詳細説明である。
> バインディング: `profiles/frontend.swiftui/docs/ja/frontend-swiftui.md` (検証済み, o-rot) · Compose のバインディングはまだない (§Android)。
> トークン・バリアント・コンポジションとデザイン成果物の整合は `core/docs/ja/architecture/frontend-design-contract.md` が定義する。

## なぜ web と異なる variant なのか

8 つのレイヤーと `can_reference` の表は `web` と**まったく同じ**である。最初の SwiftUI 適用 (o-rot, 2026-09-10) では、違反 46 件のすべてが
ファイル境界の問題で、設計の問題は 0 件だったため、レイヤーの意味はそのまま持ち込む。異なるのは 4 点である。

| 軸 | web | mobile |
|---|---|---|
| 語彙 | URL の入口、`use*Query`、`.service.ts`、Contract の `{Name}ViewModel` = データの形 | ナビゲーショングラフの入口、`Store`/`Repository`、Contract は `UiState`/`UiModel`。**ViewModel という名前は状態の所有者を意味するので、Contract には使わない** |
| Feature の組み立て | Feature Block 間の参照は禁止 | 同じドメインツリー内の**親 → 子**の組み立てを許可 (`composition: parent_child`)。兄弟間・逆方向は禁止 |
| ターゲット | zone・パッケージ | アプリ・ウィジェット・ウォッチ・インテントが**ファイルを複数のターゲットに入れて**共有する。共有できるレイヤーは Core が定める |
| 執行のはしご | import パスの静的解析 | コンパイラ(モジュール境界)が正本で、型参照チェッカーはモジュールの**内側**の補助 |

| Layer | can_reference |
|---|---|
| Foundation | なし |
| Contract | Foundation |
| DataState | Foundation, Contract |
| Primitive UI | Foundation |
| Semantic Component | Foundation, Contract, Primitive UI |
| Feature Block | Foundation, Contract, DataState, Primitive UI, Semantic Component |
| Route Surface | Foundation, Contract, Feature Block, App Shell |
| App Shell | Foundation, Contract, DataState, Primitive UI, Semantic Component |

## レイヤー ↔ モバイルの構成要素

| Layer | SwiftUI | Compose (未検証) |
|---|---|---|
| Foundation | トークン `enum`、純粋な `Shape`、タイムゾーンユーティリティ | トークン `object`、`MaterialTheme` 拡張、純粋なユーティリティ |
| Contract | `Codable` 構造体、`{Name}UiState`、純粋なルール `enum` + `static func`、ディープリンクパーサー | `data class`、`sealed interface UiState`、use case の純粋関数 |
| DataState | `@MainActor final class {Name}Store: ObservableObject` + `actor {Name}Repository` | `ViewModel`(状態の所有) + `Repository`(`suspend` + `Dispatchers.IO`)、Room/DataStore |
| Primitive UI | デザインシステムパッケージの `public struct: View` | `core:designsystem` モジュールの状態を持たないコンポーザブル |
| Semantic Component | props だけを受け取るビュー、`@EnvironmentObject` 0、`{Model}+Style.swift` | `UiState` だけを受け取るコンポーザブル、`hiltViewModel()` 0 |
| Feature Block | `@StateObject`/`@EnvironmentObject` を保持する画面の断片 | `{UseCase}Screen` + `hiltViewModel()` |
| Route Surface | `TabView`・`NavigationStack`・`navigationDestination`、ディープリンクの解決 | `NavHost`・type-safe route、ディープリンク |
| App Shell | `@main App`、グローバル Store の生成・`.environmentObject` の連鎖、`WidgetBundle` | `Application`・`MainActivity`・Hilt モジュール・`Scaffold` |

## Feature の組み立て (composition)

モバイルの画面は階層である — Today 画面が気分シートを出し、アクティビティタブがセッション完了シートを出す。web の「Feature Block 間の参照禁止」
をそのまま置くと、この組み立てがすべて違反になる。mobile はドメインをパスとして使う。

- ドメインは `today`、`today/mood` のように `/` でツリーを作る。`.strata/layer-map.yaml` の `domain:` に明記する。
- **親は子を参照できる。** `today` の Feature Block が `today/mood` のシートを組み立てる。
- 子 → 親、兄弟間 (`today` ↔ `activity`) は禁止。二つのドメインが同じ断片を使うなら、その断片は Semantic Component に下ろす。
- TCA の親リデューサー → 子リデューサーのスコープ、Compose の親 Screen → 子 Screen も同じルールである。

## ターゲット (targets)

Apple ではアプリ・ウィジェット・ウォッチ・ウォッチコンプリケーション・App Intents がそれぞれターゲットで、Android ではアプリ・ウィジェット・Wear モジュールがそれに当たる。一つのファイルを複数のターゲットに
入れるのが慣例であり、コピーはドリフトの種である。Core は**何を共有できるか**だけを定める。

| レイヤー | 共有 | 条件 |
|---|---|---|
| Foundation · Contract · Primitive UI · Semantic Component | 自由 | 状態を持たない |
| DataState | 条件付き | `layer-map targets.shared[].stateful: true` + **ターゲットごとに別のインスタンス**であることを文書に明記 (例: ウォッチの HealthStore は自分の HealthKit を読む) |
| Feature Block · Route Surface · App Shell | 禁止 | ターゲットごとに画面・入口・シェルが異なる |

チェッカーは `layer-map.yaml` の `targets.shared` を読んでレイヤーと照合する (`target_share` 違反)。正本はプロジェクトファイル
(`project.yml` のターゲットごとの `sources`) で、layer-map はその宣言を書き写す。

## 執行のはしご

| 階層 | 担当 | 強度 |
|---|---|---|
| モジュール境界 (SPM パッケージ / Gradle モジュール) | Foundation · Contract · DataState · Primitive UI をアプリターゲットから隔離する。パッケージはアプリを import できない | **コンパイラ強制 — 正本** |
| ターゲット | アプリ・ウィジェット・ウォッチ・テスト。共有はファイル単位のターゲット追加 | コンパイラ強制 |
| 型参照チェッカー (`check-swift-layers.py`) / ArchUnit · Konsist | 一つのモジュールの**内側**でのファイル間の方向・ドメイン隔離・組み立て・ターゲット共有 | CI blocking |
| style ルール | raw 値・システムフォント・`Color(hex:)` の新規流入 | CI blocking、新規行基準 |
| 編集フック | 上と同じコマンドを変更されたファイルに — **git 作業ツリー基準**(ツールイベントではなく) | warning → exit 2 でエージェントへフィードバック |

パッケージを一つ上げるたびに、チェッカーの担当は減る。Contract と DataState がパッケージになると、その境界は `import` に現れ、
Core の import ベースのフックが Swift でも動作する。ブラウンフィールドはデザインシステムパッケージ一つから始め、Contract → DataState の順に上げる。

## Android (未検証)

Compose への対応は上の表の右列がすべてで、実際のプロジェクトでは検証されていない。適用時に確認すること:

- Google 公式ガイドの UI / Domain / Data の 3 層は、mobile の (Primitive+Semantic+Feature+Route) / Contract / DataState に対応する。衝突ではなく詳細化である。
- 執行は Gradle マルチモジュール + `profiles/backend.kotlin-spring-cqrs/enforcement/` のブラウンフィールドモード(layer-map)を再利用する。Kotlin は import が明示的なので、型参照チェッカーは不要である。
- プロセス終了からの復元 (`SavedStateHandle`)・ライフサイクルを考慮した収集・DI モジュールの配置 (App Shell)・KMP `commonMain` (Contract + DataState の共有) は、Compose バインディング文書が定める。方法論バックログ MB-o-rot-2026-004。

## Core / Convention / Profile の分離

- **Core** (この文書 + `core/rules/layer-rules.yaml`): レイヤー・`can_reference`・組み立て・ターゲット共有のルール。プラットフォーム非依存。
- **Convention** (`profiles/frontend.swiftui/docs/ja/frontend-swiftui.md`、今後 `frontend-compose.md`): レイヤーを言語の構成要素に結び付ける方法、並行処理、命名、パッケージ管理。
- **Profile** (プロジェクトの `.strata/layer-map.yaml`・`constraint-registry.yaml`): ファイルのマッピング、ドメインツリー、ターゲット共有リスト、例外。
