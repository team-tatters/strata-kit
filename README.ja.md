<div align="center">
    <img src="./media/strata-kit-symbol.svg" alt="strata-kit symbol: layers stitched across a fault" width="160" height="160"/>
    <h1>strata-kit</h1>
    <h3><em>Work in layers. Keep the thread.</em></h3>
    <p align="center">層で積み、糸は手放さない。</p>
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
    <strong>日本語</strong> ·
    <a href="./README.zh-CN.md">简体中文</a> ·
    <a href="./README.es.md">Español</a> ·
    <a href="./README.fr.md">Français</a>
</p>

strata-kit は、AI コーディングエージェントと協働するための方法論をキットにまとめたものである。中心にあるのは記録だ。作業のすべての段階をプレーンな Markdown フォルダ（vault）に書き残し、トピックごとに文書を一つだけ置いてその場で更新し、新しいセッション・エージェント・人のいずれも同じ文書から始める。そのため会話のたびにやり直すことなく、作業の一貫性が保たれ、セッションをまたいで続いていく。

最優先は Claude Code で、`AGENTS.md` と `SKILL.md` を読む Codex やその他のエージェントでも動く。API キーで自分で動かすエージェントも含む。

作者: n0roo · ライセンス: [MIT](LICENSE)

## どこから始めるか

| やりたいこと | 始める場所 | 得られるもの |
|---|---|---|
| 一つのプロジェクトで試す | [クイックスタート](#クイックスタート) | vault、プラグイン、生成されたガイダンス、最初のセッション |
| 考え方を理解する | [得られるもの](#得られるもの) | 記録・仕様・推奨カード・スキル・検査を一ページで |
| 自分のスタックに合うルールを選ぶ | [プロファイル](#プロファイル) | 実プロジェクトで実証済みのプロファイルと、まだ草案のプロファイル |
| 何かを調べる | [ドキュメント](#ドキュメント) | カード・スキル・コマンド・プロファイルの生成済み一覧表 |
| まず限界を知る | [現状と限界](#現状と限界) | 計測したことと、まだ計測していないこと |

## 対象

主にコーディングエージェントと一緒に働く開発者、なかでも企画から本番運用までプロジェクトを一人で担うエンジニアのためのものである。企画者・デザイナー・運用担当者は、同じ記録、つまり企画文書と仕様、決定、運用シグナルを通じて関わる。これらの役割のための独自の完全なワークフローはまだなく、チーム全体で使われたこともまだない。

## 得られるもの

- **最新であり続ける記録。** vault は三種類の記録を持つ。作業ログ（セッション、タスク、テスト証拠）は追記するだけである。生きた文書はトピックごとに一つずつ、いまどうなっているかを説明し、その場で更新され、元になった作業ログを出典として示す。索引（決定一覧、トピックページ）はこの二つから生成され、手で編集しない。決定は CLI が一件につき一ファイルで書き、それを置き換えるレコードによってのみ変わる。各セッションは、何が未完了で何がそれを妨げているかを記したハンドオフで終わる。
- **収束する仕様。** 企画文書は現状の形を記した仕様にリンクし、仕様は `covers` によってコードを所有する。カバレッジゲートは、所有者のいないまま変更されたコードと、実装済みの企画なのにコードが移動したものを報告する。等級はプロジェクトごとに決め（`advisory` · `default` · `block`）、導入前からある欠落はベースラインとして扱う。
- **エージェントなしでも身につく方法。** 規約（役割によるレイヤーと言語による命名、コードの前に仕様、仕様の前に企画、ファイルに残す決定とハンドオフ）はエージェント向けに書かれているが、人も同じように学んで使える。
- **散文のルールではなく推奨カード。** 各カードには主張、強度（`must` · `should` · `may`）、適用する条件としない条件、根拠、反例、検証方法がある。`must` は交渉しない。`should` は理由を記録すればオフにできる。八つの基本ルールはすべてのプロジェクトに適用される。
- **証拠で終わるスキル。** 16 のコアスキル（入口とルーティング、ガイダンスウィザード、企画、仕様、オーダー、ビルドタスク、検証、レビュー、決定、知識の更新、ハンドオフ、蒸留、翻訳、振り返り、運用シグナル、セキュリティ）が六つの言語で揃い、さらにオプションのパック（アイデア出し、デザイン）がある。各スキルには、いつ使うか、どの証拠で終わるか、エージェントが手順を飛ばしたくなったときに持ち出す言い訳と、そのそれぞれへの答えが書かれている。六つの役割（builder、worker、reviewer、supporter、operator、librarian）には、それぞれしてよいこととしないことがある。
- **アプリにフックがあればフックで、なければプレーンなファイルで。** Claude Code では、フックとカードが流れを導く。セッション開始時のヘッダーがプロジェクトとその `must` カード、ファイルから読んだ次の行動を示し、コンテキストが圧縮される前にフックが状態を保存する。フックのない環境では、同じガイダンスとスキルがプレーンな `AGENTS.md` と `SKILL.md` ファイルになり、知識ベースエンジンはコマンドラインツールと MCP サーバーとして使える。
- **すでに使っている検査器を包む等級付き検査。** `kb enforce run` は既存の検査器（レイヤーテスト、dependency-cruiser、リント）を包み、実行のたびに記録を残す。そのためルール群は、数値が分かった時点で昇格できる。

## ドキュメント

ソースから生成した参照表: [カード](docs/reference/cards.md) · [スキル](docs/reference/skills.md) · [コマンド](docs/reference/cli.md) · [プロファイル](docs/reference/profiles.md)（韓国語: `docs/ko/reference/`）。ガイドと概念のページは執筆中である。エージェント向けの方法論の完全なリファレンスは `core/docs/en/` にある。

## 構成

```text
core/       基本ルール(constitution/)、推奨カード、役割、スキーマ、レイヤー・命名ルール、ドキュメント(六言語)
profiles/   スタックごとのバンドル: カードの選択、layer-map と検査器のテンプレート、規約
skills/     SKILL.md の手順と registry.yaml(入口スキルが読むルーティング表); packs/
kb/         知識ベースエンジン: ストア、検索、ゲート、決定 CLI、MCP サーバー
tools/      ウィザード、プラグイン・バンドル生成器、検証器、doctor、計測、evals 実行器
adapters/   Claude Code プラグインと Codex バンドルの入力
i18n/       用語集と翻訳待ちの印
```

## プロファイル

| プロファイル | 状態 |
|---|---|
| `core.generic` | active |
| `frontend.next-web` (Next.js / React) | active |
| `backend.kotlin-spring-cqrs` | active |
| `backend.go-service`, `backend.typescript-nest`, `cli.go`, `frontend.swiftui`, `service.rust` | draft |

*active* は、そのプロファイルが実プロジェクトで使われ、レイヤールールの検査器がそこで実行されて記録を残したことを意味する。draft のプロファイルは文書とルールを備えているが、検査器はまだプロジェクトで実証されていない。

## クイックスタート

必要なもの: Python 3.11+、git、MCP サーバー用の [uv](https://docs.astral.sh/uv/)、プラグイン用の Claude Code。

1. キットと vault を用意する。vault はハンドオフ、タスク、知識文書、計測が置かれるプレーンな Markdown フォルダである（git リポジトリを推奨）。`kb vault-init` は `core/templates/vault/` のテンプレートから vault を作り、既存のファイルは決して上書きしない。

   ```sh
   git clone https://github.com/team-tatters/strata-kit.git ~/workspace/strata-kit
   export STRATA_KIT=~/workspace/strata-kit
   cd "$STRATA_KIT" && uv sync
   python3 "$STRATA_KIT/kb" vault-init ~/workspace/vault --project my-app   # add --detached to keep Tier P in the vault
   export STRATA_VAULT=~/workspace/vault        # required: the engine never guesses a vault path
   ```

2. Claude Code プラグインをビルドしてインストールする。

   ```sh
   python3 "$STRATA_KIT/tools/gen_claude_plugin.py" --locale en
   claude plugin marketplace add "$STRATA_KIT/dist/claude"
   claude plugin install strata-kit@strata-kit
   ```

   セッション開始ヘッダーのフック、圧縮前スナップショットのフック、スキル、六つの役割エージェント、知識ベースの MCP サーバーが登録される。Codex では `tools/gen_codex_bundle.py` がスキルと役割の指示を書き出す。

3. プロジェクトのガイダンスを生成する。エージェントに「このプロジェクトに strata のガイダンスを設定して」と頼んでもよい。

   ```sh
   python3 "$STRATA_KIT/tools/wizard.py" diagnose  <project>
   python3 "$STRATA_KIT/tools/wizard.py" recommend <project> --profile <id> --uses-vault yes
   python3 "$STRATA_KIT/tools/wizard.py" generate  <project> --apply
   python3 "$STRATA_KIT/tools/wizard.py" verify    <project>
   ```

4. プロジェクトでセッションを開く。ヘッダーがプロジェクトとその must カード、ファイルから読んだ次の行動を示す。やりたいことを伝えれば、入口スキルが適切なスキルに振り分ける。閉じるときは「handoff」と言う。

プロジェクトは、共有リポジトリに strata をまったく置かないこともできる（`detached`）。その場合、ガイダンスと記録は vault に置かれ、リポジトリには CI が実行するものだけが入る。

## 現状と限界

- すべてのコアスキルには、スキルなしでは失敗し、スキルがあれば通過する圧力シナリオがある（`skills/*/evals/`）。
- この方法が作業を良くするという根拠は、一人が少数のプロジェクトで得たものである。他の場所で再現されたことはなく、他の働き方より優れているという計測もまだない。
- `core/docs/en/` 以下のドキュメントツリーと、ルールファイル、テンプレート、検査器の README は英語である。`kb` のコードコメントの多くと一部のコマンドラインメッセージはまだ韓国語である。
- キットと並行して作られたオーケストレーター Quilt は、オプションのアダプターである（`--harness quilt`）。そのアダプターはまだこのリポジトリにない。ほかに Quilt に依存するものはない。
- 新しいチームはすべての検査を `advisory` で始め、数値を見てからルール群を昇格させるべきである。

## コントリビュート

Issue とプルリクエストを歓迎する。[CONTRIBUTING.md](CONTRIBUTING.md) を参照のこと。セキュリティ上の問題は [SECURITY.md](SECURITY.md) に記された方法で報告してほしい。

サードパーティの素材は、その隣にある `NOTICE.md` ファイルに記載している（`skills/packs/*/`）。
