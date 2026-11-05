<div align="center">
    <img src="./media/strata-kit-symbol.svg" alt="strata-kit symbol: layers stitched across a fault" width="160" height="160"/>
    <h1>strata-kit</h1>
    <h3><em>Work in layers. Keep the thread.</em></h3>
    <p align="center">층으로 쌓고, 실은 놓지 않습니다.</p>
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
    <strong>한국어</strong> ·
    <a href="./README.ja.md">日本語</a> ·
    <a href="./README.zh-CN.md">简体中文</a> ·
    <a href="./README.es.md">Español</a> ·
    <a href="./README.fr.md">Français</a>
</p>

strata-kit 은 AI 코딩 에이전트와 함께 일하는 방법론을 키트로 묶은 것입니다. 중심은 기록입니다. 일의 모든 단계를
평범한 Markdown 폴더(vault)에 적고, 주제마다 문서 하나를 두고 그 자리에서 고쳐 쓰며, 새 세션·에이전트·사람 모두 같은
문서에서 출발합니다. 그래서 대화마다 처음부터 다시 시작하지 않고, 일이 일관되게 유지되며 세션을 넘어 이어집니다.

Claude Code 를 우선으로 동작하고, `AGENTS.md` 와 `SKILL.md` 를 읽는 Codex 와 다른 에이전트에서도 동작합니다. API 키로
직접 실행하는 에이전트도 포함합니다.

만든 사람: n0roo · 라이선스: [MIT](LICENSE)

## 어디서 시작할까

| 하고 싶은 것 | 시작할 곳 | 얻는 것 |
|---|---|---|
| 프로젝트 하나에 써 보기 | [빠른 시작](#빠른-시작) | vault, 플러그인, 생성된 지침, 첫 세션 |
| 생각을 이해하기 | [키트가 주는 것](#키트가-주는-것) | 기록·명세·권고 카드·스킬·검사를 한 페이지에 |
| 내 스택에 맞는 규칙 고르기 | [프로필](#프로필) | 실제 프로젝트에서 검증된 프로필과 아직 초안인 프로필 |
| 무언가 찾아보기 | [문서](#문서) | 카드·스킬·명령·프로필의 생성된 표 |
| 한계부터 알기 | [상태와 한계](#상태와-한계) | 측정한 것과 아직 측정하지 않은 것 |

## 누구를 위한 키트인가

주로 코딩 에이전트와 함께 일하는 개발자, 그중에서도 프로젝트를 기획부터 운영까지 혼자 끌고 가는 엔지니어를 위한
것입니다. 기획자·디자이너·운영자는 같은 기록, 곧 기획 문서와 명세, 결정, 운영 신호를 통해 참여합니다. 이 역할들을 위한
독자적인 전체 작업 흐름은 아직 없고, 팀 전체가 써 본 적도 아직 없습니다.

## 키트가 주는 것

- **최신으로 유지되는 기록.** vault 는 세 종류의 기록을 가집니다. 작업 이력(세션, 태스크, 테스트 증거)은 쌓기만
  합니다. 최신 문서는 지금 어떻게 되어 있는지를 주제마다 하나씩 설명하며, 그 자리에서 고쳐 쓰고 근거가 된 작업 이력을
  출처로 답니다. 색인(결정 목록, 주제 페이지)은 앞의 두 가지에서 생성되며 손으로 고치지 않습니다. 결정은 CLI 가 한 건에
  파일 하나로 쓰고, 그것을 대체하는 레코드를 통해서만 바뀝니다. 세션은 무엇이 열려 있고 무엇이 막고 있는지 적은
  핸드오프로 끝납니다.
- **수렴하는 명세.** 기획 문서는 만들어진 형상을 적은 명세로 연결되고, 명세는 `covers` 로 코드를 소유합니다. 커버리지
  게이트는 소유자 없이 바뀐 코드와, 구현된 기획인데 코드가 옮겨 간 경우를 보고합니다. 등급은 프로젝트마다
  정하고(`advisory` · `default` · `block`), 도입 전부터 있던 빈틈은 기준선으로 둡니다.
- **에이전트 없이도 익힐 수 있는 방법.** 컨벤션(역할에 따른 레이어와 언어에 따른 이름, 코드 전에 명세, 명세 전에 기획,
  파일로 남기는 결정과 핸드오프)은 에이전트를 위해 쓰였지만, 사람도 같은 방식으로 익혀서 쓸 수 있습니다.
- **산문 규칙이 아니라 권고 카드.** 카드마다 주장, 강도(`must` · `should` · `may`), 적용 조건과 제외 조건, 근거, 반례,
  검증 방법이 있습니다. `must` 는 협상하지 않습니다. `should` 는 사유를 기록하면 끌 수 있습니다. 기본 규칙 여덟 개는
  모든 프로젝트에 적용됩니다.
- **증거로 끝나는 스킬.** 코어 스킬 16개(진입과 라우팅, 지침 마법사, 기획, 명세, 오더, 빌드 태스크, 검증, 리뷰, 결정,
  지식 갱신, 핸드오프, 증류, 번역, 회고, 운영 신호, 보안)가 여섯 개 언어로 있고, 선택 팩(아이디에이션, 디자인)이 더
  있습니다. 스킬마다 언제 쓰는지, 어떤 증거로 끝나는지, 에이전트가 단계를 건너뛰고 싶을 때 꺼내는 핑계와 그 각각에 대한
  답을 적습니다. 역할 여섯(builder, worker, reviewer, supporter, operator, librarian)은 각자 할 수 있는 일과 하지 않는
  일을 가집니다.
- **앱에 훅이 있으면 훅으로, 없으면 평범한 파일로.** Claude Code 에서는 훅과 카드가 흐름을 이끕니다. 세션 시작
  머리말이 프로젝트와 그 `must` 카드, 파일에서 읽은 다음 행동을 보여 주고, 컨텍스트가 압축되기 전에 훅이 상태를
  저장합니다. 훅이 없는 곳에서는 같은 지침과 스킬이 평범한 `AGENTS.md` 와 `SKILL.md` 파일이고, 지식 기반 엔진은 명령줄
  도구이자 MCP 서버입니다.
- **이미 쓰는 검사기를 감싸는 등급 검사.** `kb enforce run` 은 기존 검사기(레이어 테스트, dependency-cruiser, 린트)를
  감싸고 실행마다 기록을 남깁니다. 그래서 규칙 묶음은 숫자가 확인된 뒤에 승격할 수 있습니다.

## 문서

출처에서 생성한 참조 표: [카드](docs/reference/cards.md) · [스킬](docs/reference/skills.md) ·
[명령](docs/reference/cli.md) · [프로필](docs/reference/profiles.md) (한국어: `docs/ko/reference/`). 가이드와 개념
페이지는 쓰는 중입니다. 에이전트용 전체 방법론 참조는 `core/docs/en/` 에 있습니다.

## 구조

```text
core/       기본 규칙(constitution/), 권고 카드, 역할, 스키마, 레이어·네이밍 규칙, 문서(여섯 개 언어)
profiles/   스택별 묶음: 카드 선택, layer-map 과 검사기 템플릿, 컨벤션
skills/     SKILL.md 절차와 registry.yaml(진입 스킬이 읽는 라우팅 표); packs/
kb/         지식 기반 엔진: 저장소, 검색, 게이트, 결정 CLI, MCP 서버
tools/      마법사, 플러그인·번들 생성기, 검증기, doctor, 측정, evals 실행기
adapters/   Claude Code 플러그인과 Codex 번들의 입력
i18n/       용어집과 번역 대기 표시
```

## 프로필

| 프로필 | 상태 |
|---|---|
| `core.generic` | active |
| `frontend.next-web` (Next.js / React) | active |
| `backend.kotlin-spring-cqrs` | active |
| `backend.go-service`, `backend.typescript-nest`, `cli.go`, `frontend.swiftui`, `service.rust` | draft |

*active* 는 그 프로필을 실제 프로젝트에서 쓰고, 레이어 규칙 검사기가 그 프로젝트에서 돌아 기록을 남겼다는 뜻입니다.
draft 프로필은 문서와 규칙은 갖췄지만 검사기가 아직 프로젝트에서 검증되지 않았습니다.

## 빠른 시작

필요한 것: Python 3.11+, git, MCP 서버용 [uv](https://docs.astral.sh/uv/), 플러그인용 Claude Code.

1. 키트와 vault 를 준비합니다. vault 는 핸드오프·태스크·지식 문서·측정이 사는 평범한 Markdown 폴더입니다(git 저장소를
   권합니다). `kb vault-init` 은 `core/templates/vault/` 의 템플릿으로 vault 를 깔아 주며, 기존 파일은 덮어쓰지 않습니다.

   ```sh
   git clone https://github.com/team-tatters/strata-kit.git ~/workspace/strata-kit
   export STRATA_KIT=~/workspace/strata-kit
   cd "$STRATA_KIT" && uv sync
   python3 "$STRATA_KIT/kb" vault-init ~/workspace/vault --project my-app   # add --detached to keep Tier P in the vault
   export STRATA_VAULT=~/workspace/vault        # required: the engine never guesses a vault path
   ```

2. Claude Code 플러그인을 빌드하고 설치합니다.

   ```sh
   python3 "$STRATA_KIT/tools/gen_claude_plugin.py" --locale en
   claude plugin marketplace add "$STRATA_KIT/dist/claude"
   claude plugin install strata-kit@strata-kit
   ```

   세션 시작 머리말 훅, 압축 전 스냅숏 훅, 스킬, 역할 에이전트 여섯, 지식 기반 MCP 서버가 등록됩니다. Codex 에서는
   `tools/gen_codex_bundle.py` 가 스킬과 역할 지침을 씁니다.

3. 프로젝트의 지침을 생성합니다. 에이전트에게 "이 프로젝트에 strata 지침을 세팅해 줘"라고 해도 됩니다.

   ```sh
   python3 "$STRATA_KIT/tools/wizard.py" diagnose  <project>
   python3 "$STRATA_KIT/tools/wizard.py" recommend <project> --profile <id> --uses-vault yes
   python3 "$STRATA_KIT/tools/wizard.py" generate  <project> --apply
   python3 "$STRATA_KIT/tools/wizard.py" verify    <project>
   ```

4. 프로젝트에서 세션을 엽니다. 머리말이 프로젝트와 그 must 카드, 파일에서 읽은 다음 행동을 보여 줍니다. 하고 싶은 일을
   말하면 진입 스킬이 알맞은 스킬로 보냅니다. 닫을 때는 "handoff"라고 말합니다.

프로젝트는 공유 저장소에 strata 를 아예 두지 않을 수도 있습니다(`detached`). 이때 지침과 기록은 vault 에 있고, 저장소는
CI 가 돌리는 것만 받습니다.

## 상태와 한계

- 모든 코어 스킬에는 스킬 없이는 실패하고 스킬이 있으면 통과하는 압력 시나리오가 있습니다(`skills/*/evals/`).
- 이 방법이 일을 낫게 만든다는 근거는 한 사람이 적은 수의 프로젝트에서 얻은 것입니다. 다른 곳에서 재현된 적이 없고,
  다른 일하는 방식보다 낫다는 측정도 아직 없습니다.
- `core/docs/en/` 아래 문서 트리와 규칙 파일, 템플릿, 검사기 README 는 영어입니다. `kb` 코드 주석 상당수와 일부
  명령줄 메시지는 아직 한국어입니다.
- 키트와 함께 만들어진 오케스트레이터 Quilt 는 선택 어댑터입니다(`--harness quilt`). 그 어댑터는 아직 이 저장소에
  없습니다. 다른 어떤 것도 Quilt 에 기대지 않습니다.
- 새 팀은 모든 검사를 `advisory` 로 시작하고, 숫자를 본 뒤에만 규칙 묶음을 승격하는 것이 좋습니다.

## 기여

이슈와 풀 리퀘스트를 환영합니다. [CONTRIBUTING.md](CONTRIBUTING.md) 를 참고하세요. 보안 문제는
[SECURITY.md](SECURITY.md) 에 적힌 대로 알려 주세요.

제3자 자료는 그 옆의 `NOTICE.md` 파일에 적혀 있습니다(`skills/packs/*/`).
