# フロントエンド Swift/SwiftUI Convention

> 正本: strata-kit `profiles/frontend.swiftui/docs/ja/frontend-swiftui.md` — strata `docs/05-conventions/frontend-swiftui.md` から移管（オーダー 2026.10.29-06、2026-10-29）。ルール YAML は `core/rules/`。

> Core の境界: `core/docs/ja/architecture/frontend-mobile.md`（`core/rules/layer-rules.yaml` → `frontend.variants.mobile`）· デザイン契約: `core/docs/ja/architecture/frontend-design-contract.md` · 執行: `profiles/frontend.swiftui/enforcement/`
> v1 2026-09-10（web variant バインディング、o-rot に初適用）→ **v2 2026-09-11**（mobile variant — 語彙・Feature 組み立て・ターゲット・執行のはしご・フック、DEC-2026-09-11-01）

この文書は、SwiftUI アプリが Core の mobile variant（Foundation → … → App Shell）を実装するときの慣例である。
SwiftUI は Core の必須前提ではない。Core は「どの責務がどのレイヤーを通らなければならないか」と、組み立て・ターゲット共有のルールだけを定める。この文書はそれを Swift の構造物に結びつける。

## 要約

- レイヤー識別の第一級のキーは**ファイルが持つ型の役割**であり、ディレクトリではない。`.strata/layer-map.yaml` が役割で再分類し、ファイルは移動しない。
- **執行の正本はコンパイラである。** レイヤーをローカル SPM パッケージに上げるほど、境界が `import` として現れる。型参照チェッカー（`check-swift-layers.py`）は、1 つのモジュール内のファイル間の向きを見る補助である。
- 状態の所有者は Feature Block である。`@StateObject` で作るか `@EnvironmentObject` で受け取るビューがそれにあたる。`props` だけを受け取るビューは Semantic Component である。Store の**生成**と環境注入のチェーンは App Shell の 1 か所に置く。
- Feature は同じドメインツリーの**親 → 子**だけを組み立てる（`today` → `today/mood`）。兄弟間で共有する部品は Semantic Component に下ろす。
- ターゲット間の共有はコピーではなくターゲットの追加である。Foundation・Contract・Primitive・Semantic は自由、DataState は `stateful: true` とインスタンス分離の明記が必要、Feature・Route・Shell は禁止。
- トークンはコードリポジトリの `tokens.json` が正本であり、Swift のトークンファイルは生成物である。ビューで hex・システムフォント・生の数値を使うことは禁止。

## レイヤー ↔ Swift の構造物

| レイヤー | Swift では何か | 標識 | 禁止 |
|---|---|---|---|
| Foundation | トークン enum（`Color`・`Font`・spacing）、純粋な `Shape`、定数 enum、タイムゾーンのような純粋ユーティリティ | `enum {Name}Tokens` · `static let` のみ | `ObservableObject`、I/O、`UserDefaults`、ビュー |
| Contract | `Codable` モデル・DTO、画面状態値 `{Name}UiState`、純粋な計算ルール（`enum` + `static func`）、ディープリンクパーサー、ポートプロトコル | 値型 · `import Foundation` のみ | SwiftUI の import、色・アイコンのような**表示プロパティ**、**`ViewModel` という名前**（モバイルでは状態所有者を意味する） |
| DataState | `Store`（メインアクターの状態所有者）+ `Repository`/`Service`/`Session`（隔離された I/O） | `@MainActor final class {Name}Store: ObservableObject` · `actor {Name}Repository` | ビューのレンダリング、他ドメインの Store の直接参照 |
| Primitive UI | デザインシステムパッケージの、ドメインを知らないビュー（Button・Chip・Row・TabBar） | `public struct {Name}: View` · 軸（variant・intent・size）の props · **必ず別パッケージ** | ドメインモデル、Store |
| Semantic Component | props/UiState だけを受け取って描く意味のあるビュー — チャート・ステージ・ヘッダー・空状態、モデルの表示プロパティ拡張 | `struct {Domain}{Purpose}View: View` · `{Model}+Style.swift` · `@EnvironmentObject` 0 | Store へのアクセス、`@StateObject` |
| Feature Block | 画面の断片の状態所有者 — `@StateObject`/`@EnvironmentObject` で Store を保持し、下へ props を伝える | `struct {UseCase}View` · `{UseCase}Sheet` · ドメインツリー `today/mood` | 兄弟ドメインの Feature の参照、ナビゲーショングラフの所有 |
| Route Surface | `TabView`・`NavigationStack` の入口、`navigationDestination`、タブ選択、ディープリンクの解決 | `MainTabView` · `{Flow}Flow` | Store の**生成・参照**（注入は App Shell）、再利用 UI の export |
| App Shell | `@main struct App`、グローバル Store の生成と `.environmentObject` チェーン、`WidgetBundle`、シェルのクローム（タブバー） | `{Name}App` · `{Name}Shell` · `{Name}Bundle` | ドメインのユースケースロジック、Feature の直接参照 |

`can_reference` は Core の表のとおりである。SwiftUI 固有の 3 点だけを加える。

- **環境注入は参照である。** `@EnvironmentObject var store: TodoStore` は、そのファイルが `TodoStore` を参照したことを意味する。Semantic Component に `@EnvironmentObject` があってはならない。
- **`@StateObject` の生成は所有である。** Store の生成は App Shell で、画面限定の状態は Feature Block でのみ行う。Route Surface が Store を作れば違反である（o-rot の `MainTabView` が 8 個のストアを作っていた形が、このルールを生んだ）。
- **`@main` は App Shell である。** オンボーディング/メインの分岐のような入口の判断が `@main` にあるなら、その分岐を `{Name}Shell` ビューに下ろし、`@main` には Store の生成と注入だけを残す。分離するまでは、layer-map の `exceptions` に DEC とともに置く。

## Feature の組み立て

```
Features/Today/TodayView.swift          domain: today        ← @EnvironmentObject で Store を保持する
Features/Today/Mood/MoodSheetView.swift domain: today/mood   ← 親（today）が .sheet で表示する
Features/Activity/ActivityView.swift    domain: activity     ← today の兄弟。MoodSheetView を使えば違反
```

- ドメインは `layer-map.yaml` の `domain:` に `/` 区切りのパスで書く。チェッカーは親 → 子の参照だけを通す。
- 2 つの兄弟が同じシートを表示するなら、そのシートの描画部分を Semantic Component（`MoodPickerView`）に下ろし、各 Feature が自分の Store で包む。
- TCA を使うなら、親リデューサーの `Scope` がまさにこの辺である。パターン名は定めない — 辺の向きだけを守る。

## ターゲット

- フォン・ウィジェット・ウォッチ・コンプリケーション・インテントは、それぞれがターゲットである。共有とは `project.yml` のターゲットごとの `sources` に**ファイルを加えること**であり、コピーは作らない。
- 共有リストを `layer-map.yaml` の `targets.shared` に書き写す。チェッカーがレイヤーを照合する（`target_share`）。
- 2 つのターゲットが DataState を共有する場合（例: ウォッチがフォンの `HealthStore` ファイルを使う）、`stateful: true` と宣言し、ターゲットごとにインスタンスが別であること、そしてそれぞれが何を読むかを文書に書く。
- ターゲット間のデータ交換（App Group の `UserDefaults`、`WatchConnectivity`）は、DataState の `{Name}Session`/`{Name}Bridge` ファイル 1 つが担う。ビューが `UserDefaults(suiteName:)` を直接開けば違反である。

## 状態の所有と監視モデル

- 既定は `ObservableObject` + `@Published` + `@MainActor`。Store はクラス、モデルは構造体。
- `@Observable`（Observation フレームワーク）は**デプロイメントターゲットが iOS 17 / watchOS 10 以上のときだけ**使う。2 つのモデルはプロパティラッパーが異なり（`@StateObject` ↔ `@State`）、更新の単位も異なるため、混用すると初期化のタイミングがずれる — 1 つのプロジェクトは 1 つのモデルだけを使う。（[Apple: Observation](https://developer.apple.com/documentation/observation)、[Squires: not a drop-in replacement](https://www.jessesquires.com/blog/2024/09/09/swift-observable-macro/)）
- Store は自分のドメインだけを知る。2 つの Store を結びつける組み立ては Feature Block が行う。Store が他の Store を参照すれば、DataState のドメイン交差参照違反である。
- 永続化は Store/Repository の中で完結させる。`UserDefaults.standard` やファイル I/O がビューや Contract に現れれば違反である。

## 並行性

- Swift 6 言語モードは、データ競合をコンパイルエラーにする。導入は**段階的**に行う: `SWIFT_STRICT_CONCURRENCY = targeted` → `complete` → 言語モード 6。一度に有効にしない。（[Apple: Adopting strict concurrency](https://developer.apple.com/documentation/swift/adoptingswift6)）
- ビューが触れる Store はすべて `@MainActor`。I/O は `actor {Name}Repository`、または `nonisolated` + `Task { @MainActor in … }` で Store に戻す。デリゲートのコールバック（`WCSessionDelegate` など）も同じ慣例に従う。
- モデル（構造体）は `Sendable` に合わせることを基本とする。Contract パッケージが `Sendable` だけを公開すれば、アクターの境界はおのずと合う。

## 命名 — Swift API Design Guidelines をそのまま

正本は [swift.org API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/) である。Core の `core/rules/naming-convention.yaml` にある `common.case_styles` と衝突する箇所では、**Swift の慣例が勝つ**（下の表）。ファイル名は、収める最上位の型と同じにする。

| 項目 | Swift | Core の既定との違い |
|---|---|---|
| 型・プロトコル | `UpperCamelCase` | 同じ |
| 関数・変数・プロパティ・case | `lowerCamelCase` | **enum case は lowerCamelCase** — Core の `UPPER_SNAKE` は使わない |
| 定数 | `lowerCamelCase`（`static let graceDays`） | Core の `UPPER_SNAKE` は使わない |
| 真偽値 | 断定文として読める — `isEmpty` · `hasWatch` · `canDelete` | Core の Props ルールと同じ |
| 画面状態値 | `{Name}UiState`（Contract） | Core web の `{Name}ViewModel` は使わない — モバイルで ViewModel は状態所有者 |
| 状態所有者 | `{Name}Store`（DataState） | Core web の `use{Name}State` に対応 |
| ファクトリ | `make…` | |
| 変更/非変更のペア | `sort()` / `sorted()`、`append` / `appending` | |
| プロトコル | 何であるか → 名詞、能力 → `-able` `-ible` `-ing` | |
| 略語 | 大文字小文字を揃える — `hrvSeries` · `isHRV`（大文字で始まる位置でのみ全部大文字） | |
| 引数ラベル | 文のように読めるようにする。最初の引数が前置詞句ならラベル必須 | |
| 禁止接尾辞 | `Manager` · `Helper` · `Impl` | Core と同じ。`Handler` はデリゲートメソッドにのみ |

Props に当たるものは、ビューの `init` 引数と格納プロパティである。Core の `Props` ルールを適用する: 親の状態は接頭辞のない名詞、変更の要求は `on{State}Change`、イベントは `on{Event}`、内部ハンドラーは `handle{Event}`。SwiftUI では `Binding<T>` が「値 + 変更のペア」なので、Core の `{state}Control` のまとまりに当たる — 複数の子が同じ状態を使うなら、`Binding` を 1 つ下ろす。

`layer-map.yaml` の `naming:` ブロックは、チェッカーが執行しない。ファイル名 = 最上位の型名は慣例であり、レビューで見る。

## 執行のはしご — コンパイラが正本

| 階層 | 担当 | 強度 |
|---|---|---|
| ローカル SPM パッケージ（`Package.swift`） | Foundation・Contract・DataState・Primitive UI をアプリターゲットから隔離する。パッケージはアプリを import できず、パッケージ間の依存は `dependencies:` で宣言した向きだけ | **コンパイラ強制 — 正本** |
| ターゲット（`project.yml` / Xcode ターゲット） | アプリ・ウィジェット・ウォッチ・テスト。共有ソースはファイル単位でターゲットに加える | コンパイラ強制 |
| `check-swift-layers.py` | 1 つのモジュールの**内側**にあるファイル間のレイヤーの向き・ドメイン隔離・Feature の組み立て・ターゲット共有 | CI blocking |
| `--style` ルール / SwiftLint custom_rules | 生の値・システムフォント・`Color(hex:)` のような新規の流入 | CI blocking、新規の行を基準にすることを推奨 |
| 編集フック | 同じチェッカーを **git 作業ツリーで変わったファイル**に (`--changed`) | exit 2 → エージェントへのフィードバック |

- **パッケージの段階。** ブラウンフィールドは、デザインシステム（Foundation + Primitive UI）パッケージ 1 つから始める。次は Contract（モデル・ルール・`Sendable` の値）、その次が DataState。1 段階上げるたびにその境界が `import` に現れるので、Core の import ベースのフックが Swift でも動き、型参照チェッカーの受け持ちはアプリターゲットの内部（Semantic → Feature → Route → Shell）に縮む。骨格: `profiles/frontend.swiftui/enforcement/Package.swift.template`。
- **パッケージ管理は SPM 1 本にする。** CocoaPods・Carthage は新規に導入しない。（[DECODE: modularize with SPM](https://decode.agency/article/project-modularization-swift-package-manager/)、[Nimble](https://nimblehq.co/blog/modern-approach-modularize-ios-swiftui-spm)）
- **プロジェクトの生成は宣言的に行う。** `.xcodeproj` を手で編集せず、XcodeGen の `project.yml`（または Tuist）から生成する。ターゲットグラフがテキストでレビューされてこそ、レイヤーとターゲットの決定が PR に現れる。（[XcodeGen vs Tuist](https://medium.com/@sayefeddineh/xcodegen-vs-tuist-choosing-the-right-tool-for-xcode-project-generation-bea093c6e105)）
- 外部パッケージは**バージョンを固定**（`exact` または `upToNextMinor`）し、`Package.resolved` をコミットする。
- **編集フックはツールイベントではなく git を基準に掛ける。** Claude Code の PostToolUse を `Write|Edit` にだけ掛けると、Bash（sed・heredoc）による編集が検査をすり抜ける。matcher を `Write|Edit|Bash` とし、チェッカーが Bash イベントでは `--changed`（git status 基準）にフォールバックする。設定テンプレート: `profiles/frontend.swiftui/enforcement/settings.json.template`。

## トークン・タイポグラフィ（デザイン契約バインディング）

- 正本はリポジトリの `tokens.json`。Swift のトークンファイル（`{Name}Tokens.swift`）はその生成物であり、`Color(hex:)` の初期化は**このファイルの中にだけ**現れる。
- ビューは alias 名だけを使う: `OrotColor.sage700` ○ / `Color(hex: "507663")` ✗ / `.font(.system(size: 13))` ✗ / `.padding(14)` は spacing トークンで。
- 新しい alias はアーキテクチャの決定である — decision レコード + `tokens.json` → Swift の順。一時的な値は `/// @strata:token-exception … until YYYY-MM-DD`。
- タイポグラフィトークンは 3 つの軸を持つ: テキストスケール（見出し・本文・キャプション）、**アイコンサイズ**（`icon.sm/md/lg` — SF Symbol の `.font(.system(size:))` の代わり）、**プラットフォームスケール**（ウォッチはフォンの縮小ではなく別のスケール）。軸がないために `.font(.system` が残るなら、トークン追加の DEC が先である。
- アクセシビリティはトークンが担う: テキストのコントラストが 4.5:1 以上の alias だけをテキストに使い、それ未満のものは非テキスト専用であることを名前に示す。Dynamic Type は `Font.custom(_:size:relativeTo:)` によってトークンが吸収する。

## フォーマット・リント

- フォーマッターは、Xcode 16 以降のツールチェーンに入っている **swift-format**（`swift format`、`xcrun --find swift-format`）を使う。設定は `.swift-format` ファイル 1 つ（テンプレート: `profiles/frontend.swiftui/enforcement/swift-format.json.template`）。（[Xcode 16 swift-format](https://mjtsai.com/blog/2024/11/06/swift-format-in-xcode-16/)）
- リントは SwiftLint を**任意**とする。Strata が求めるのは `custom_rules` 数個だけなので、SwiftLint がなくても `check-swift-layers.py --style` が同じ正規表現を実行する。SwiftLint を使うなら、`profiles/frontend.swiftui/enforcement/swiftlint-strata.yml.template` を `.swiftlint.yml` にマージする。（[SwiftLint custom rules](https://github.com/realm/SwiftLint#defining-custom-rules)）

## マーカー

`///` ドキュメントコメントに置く（`core/docs/ja/conventions/strata-markers.md`）:

```swift
/// 今日の状態の変換ルール — 純粋関数のみ。
/// @strata:layer Contract
/// @strata:domain today
enum StateEngine { … }
```

## テスト

- 単体テストターゲットは `@testable import {App}` で Contract・DataState を直接検証する。パッケージになったレイヤーは、パッケージ自身のテストターゲットで検証する。ビューのテストはスナップショットではなく、**Store → 状態 → 画面の文言**の経路を検証する。
- Store のテストは `UserDefaults(suiteName: UUID)` や一時ディレクトリで隔離する。テストで `.standard` に触れない。
- ファイル名は `{Type}Tests.swift`、テストターゲットのディレクトリは layer-map で `_test` として除外する。チェッカーは `swift.sources` の外にあるファイルを黙ってスキップする。

## ブラウンフィールド導入手順

1. `profiles/frontend.swiftui/enforcement/layer-map.yaml.template` から `.strata/layer-map.yaml` を作る（`variant: mobile`）。**役割で**分類し、ファイルは移動しない。Feature のドメインは `/` ツリーで書く。
2. `check-swift-layers.py --summary` で未マッピングを 0 にする。
3. `project.yml` のターゲットごとの共有ソースを `targets.shared` に書き写す。DataState の共有は `stateful: true` + 文書化。
4. `--all` で違反を見る。3 つに分ける — 今直すもの / DEC とともに `exceptions` に登録するもの / `--write-baseline` で凍結して新規だけを止めるもの。
5. `--style` を有効にして、同じ手順を繰り返す。
6. CI に `--all --style --ignore-known` を掛ける。編集フックは `profiles/frontend.swiftui/enforcement/settings.json.template`（Write|Edit|Bash → stdin、Bash は `--changed`）。
7. パッケージのはしごを登る: デザインシステム → Contract → DataState。各段階で layer-map の `swift.sources` とマッピングを更新し、baseline を再生成する。

## この文書が定めないこと

アーキテクチャのパターン名（MVVM・TCA・Clean）は定めない。どの名前を使っても、「Store は DataState、状態の所有は Feature Block、props ビューは Semantic、組み立ては親 → 子」が守られていればよい。ネットワーク層やサーバー状態のキャッシュツールもプロジェクトの constraint とする — ただし、transport は DataState の中でのみ見え、ビューには露出しないという Core ルールは同じである。Compose/Android バインディングについては、`core/docs/ja/architecture/frontend-mobile.md` の §Android にある対応表しかなく、別の文書はまだない。
