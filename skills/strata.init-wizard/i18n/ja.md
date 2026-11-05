# strata.init-wizard

## 概要

ウィザードは、推奨カードからプロジェクトのガイダンスを組み立てます。コードでは答えが出ないことだけをインタビューし、プロファイルの検出ルールに照らしてスタックを診断し、証拠付きでカードを提案し、ユーザーが承認したらアダプターを生成して、結果を検証します。コアのリビジョンが進んだときの再生成の経路でもあります。承認された提案に列挙されたパスの外には、決して書き込みません。

## 使う場面

- プロジェクトに `.strata/profile.yaml` がない(using-strata がここへ送ります)。
- ユーザーがガイダンスの設定・変更・再生成を求める。
- プロファイル、カード、免除のいずれかを変更する必要がある。
- 日常の作業には使いません。それは using-strata が担当スキルへルーティングします。

## 手順

1. **まずコードから診断します。** `python3 tools/wizard.py diagnose <project> --apply` を実行します。ビルドファイルとマニフェストを読み、プロファイルの検出ルールと照合し、常時ロードの予算を測り、判断できなかったことを列挙します。証拠: `.strata/kit/diagnosis.yaml`。
2. **質問は一度に一つずつ行います。** 診断で残った未解決の質問(チーム規模、想定寿命、ドメイン間書き込みのあるドメイン数、共有環境、使用中のハーネス)だけを尋ねます。診断がすでに答えたことは決して尋ねません。回答は recommend に `--answer <キー>=<値> --because <キー>=<理由>` で残します(キー `team_size`・`lifetime`・`cross_domain_writes`・`shared_envs`・`runtime`・`strata_python`)。提案書が `answers` に保持し、次の recommend が引き継ぎます。**実行環境。** 診断の `runtime` 部分 — 実行経路(対話シェル・Claude Code フック・MCP・launchd・非対話 sh)ごとに実際に動く python、不足している kit の依存、見つかった管理ツールとバージョンファイル — を示し、kit をどの python で動かすか尋ねます。recommend が出力する選択肢と長所・短所をそのまま示します(`asdf`: 複数言語を一つのファイルで、ただし shim は launchd・非対話の PATH にないため絶対パスが必要 / `uv-venv`: 隔離され、ロックファイルで再現でき、python も入れる、言語は一つ / `mise`: asdf 互換に env・task / `pyenv` / `brew`・`system`: 簡単だが固定・隔離が弱い)。既定の `uv-venv` とその理由(kit は uv の venv、人の言語ランタイム管理はそのまま)も伝えます。選んだ答えは `--answer runtime=<選択>` で残し、generate が一つの STRATA_PYTHON を `.strata/kit/runtime/` の断片ファイル(フック・settings env、MCP コマンド、launchd EnvironmentVariables、`~/.zshenv` の行)に書きます。適用は人が行います — ホームのファイルを自分で編集しません。証拠: 提案書の `answers`・`runtime`、人が適用した後に runtime 項目のない `tools/doctor.py`。
3. **カードを提案します。** `python3 tools/wizard.py recommend <project> --profile <id> [--locale ko] --apply` を実行します。各カードを、id、strength、claim、証拠の参照、反例の順で提示します。must カードは説明するもので、交渉の対象ではありません。ユーザーが断った should カードごとに `waived_reason` を記録します。must カードへの異論ごとに、counter_example の候補を記録します(それは backlog に入り、プロジェクトには入りません)。オプトイン型の must カード(`adoption: opt_in`、憲法の外)は質問として尋ねます。提案書が各カードの既定値(ユーザーの `~/.strata/config.yaml` の `wizard.adopt_cards`、次にプロファイルの `cards_default`)を示し、答えは `--adopt <id>` か `--decline <id>=<理由>` で残します(拒否は理由とともに提案書とレジストリに残ります)。条件付き must カード(`adoption: conditional`)は尋ねません。プロジェクトにその事実が当てはまれば載ります — `uses_vault`(`--uses-vault yes|no`)、`uses_quilt`(`--harness …,quilt`)、`domain_work`(領域)。どのカードがなぜ載ったかを述べます。 ルール群(`layers`・`naming`・`rules`)ごとに執行等級を尋ねます。advisory は違反を記録するだけ、default は理由と期限つきの上書きがなければ失敗、block は失敗です。宣言しない群は block のままです。`--enforce <群>=<等級>` で残すとマニフェストに入り、検査器は `kb enforce run` で包みます。違反を出力しても 0 で終わる警告モードの検査器は `--violation-exit 0,1 --violation-pattern <違反の目印>` で包み、誤って残った記録は書き換えず `kb enforce correct` で訂正項目を追記します。 証拠: ユーザーが `approved: true` を設定した `.strata/kit/proposal.yaml`。
4. **生成します。** `python3 tools/wizard.py generate <project> --apply` を実行します。提案に列挙されたパスだけに書き込み、`core_revision` と `adapter_revision` を刻印します。手書きの既存ファイル(先頭に生成マークがないもの)は、提案の `overwrite_handwritten` に名前があるときだけ置き換えます。置き換える前に、その内容を `.strata/kit/notes.<locale>.md` に移します。証拠: コマンド出力にある書き込んだファイルの一覧。
5. **検証します。** `python3 tools/wizard.py verify <project>` を実行します。予算(常時ロードのバイト数)、リビジョンヘッダー、レジストリを検査し、レジストリのトリガーを通して五つのサンプル依頼を実行します。証拠: 終了コード 0 とそのレポート。
6. **記録します。** プロファイルの選択や免除がこのプロジェクトのアーキテクチャ上の決定である場合は、decision writer で記録します。証拠: 返信にある DEC id。

## 言い訳と反論

| 考え | 反論 |
|---|---|
| 「スタックは明らかだから、diagnose は省略しよう。」 | diagnose は予算も測り、ドリフトも見つけます。コマンド一つなので実行してください。 |
| 「ユーザーはルールを知っているから、証拠は省こう。」 | 証拠のないカードは意見にすぎません。参照を示してください。それがすべての要点です。 |
| 「この must カードはここに合わないから、免除しよう。」 | must は免除されません。説明し、異論を counter_example の候補として記録してください。 |
| 「全部生成して、要らないものはユーザーに消してもらおう。」 | 承認されたパスだけに書いてください。頼まれていないファイルはドリフトです。 |
| 「前回は検証を通った。」 | コアのリビジョンが進んでいるかもしれません。generate のたびに検証してください。 |

## 警告サイン

- 答えが `package.json`、`build.gradle`、`go.mod`、`Cargo.toml` の中にあるインタビューの質問。
- `evidence` の項目がないカードを含む提案。
- ヘッダーに `core_revision` がない、生成された AGENTS.md。
- 提案のパス一覧の外に書き込まれたファイル。

## 検証

- `.strata/kit/proposal.yaml` が存在して `approved: true` であり、すべてのカードに証拠がある。
- 免除されたすべての should カードに `waived_reason` がある。
- `tools/wizard.py verify <project>` が 0 で終了し、そのレポートが返信に入っている。
- なされた決定はすべて記録され、その id が返信に入っている。
