# strata.init-wizard

## 개요

마법사는 권고 카드로부터 프로젝트의 지침을 조립합니다. 코드가 답할 수 없는 것만 묻고, 프로필 감지 규칙으로 스택을 진단하고, 근거와 함께 카드를 제안하고, 사용자가 승인하면 어댑터를 생성하고, 결과를 검증합니다. 코어 revision 이 바뀌었을 때 재생성하는 길이기도 합니다. 승인된 제안에 적힌 경로 밖에는 아무것도 쓰지 않습니다.

## 언제 쓰는가

- 프로젝트에 `.strata/profile.yaml` 이 없을 때(using-strata 가 여기로 보냅니다).
- 사용자가 지침을 만들거나 바꾸거나 다시 생성해 달라고 할 때.
- 프로필, 카드, 해제가 바뀌어야 할 때.
- 일상 작업에는 쓰지 않습니다. 그것은 using-strata 가 담당 스킬로 보냅니다.

## 절차

1. **코드에서 먼저 진단합니다.** `python3 tools/wizard.py diagnose <project> --apply` 를 실행합니다. 빌드 파일과 매니페스트를 읽고, 프로필 감지 규칙에 맞추고, 항상 읽히는 묶음의 크기를 재고, 정하지 못한 것을 나열합니다. 증거: `.strata/kit/diagnosis.yaml`.
2. **한 번에 한 질문씩 인터뷰합니다.** 진단에서 남은 열린 질문(영역, 팀 규모, 예상 수명, 도메인 간 쓰기가 있는 도메인 수, 공유 환경, 쓰는 하네스)만 묻습니다. 진단이 이미 답한 것은 절대 묻지 않습니다. 답은 recommend 에 `--answer <키>=<값> --because <키>=<사유>` 로 남깁니다(키 `team_size`·`lifetime`·`cross_domain_writes`·`shared_envs`·`runtime`·`strata_python`). 제안서가 `answers` 에 담고 다음 recommend 가 이어받습니다. **실행 환경.** 진단의 `runtime` 부분 — 실행 경로(대화 셸·Claude Code 훅·MCP·launchd·비대화 sh)마다 실제로 도는 python, 빠진 kit 의존성, 찾은 관리자와 버전 파일 — 을 보이고, kit 을 어떤 python 으로 돌릴지 묻습니다. recommend 가 출력하는 선택지와 장단점을 그대로 보입니다(`asdf`: 여러 언어를 한 파일로, 하지만 shim 이 launchd·비대화 PATH 에 없어 절대 경로가 필요 / `uv-venv`: 격리, 잠금 파일로 재현, python 도 설치, 언어 하나 / `mise`: asdf 호환에 env·task / `pyenv` / `brew`·`system`: 쉽지만 판 고정·격리 약함). 기본 `uv-venv` 와 그 근거(kit 은 uv venv, 사람의 언어 런타임 관리자는 유지)도 말합니다. 고른 답은 `--answer runtime=<선택>` 으로 남기고, generate 가 STRATA_PYTHON 하나를 `.strata/kit/runtime/` 아래 조각 파일(훅·settings env, MCP 명령, launchd EnvironmentVariables, `~/.zshenv` 줄)로 씁니다. 적용은 사람이 합니다 — 홈 파일을 직접 고치지 않습니다. 증거: 제안서의 `answers`·`runtime`, 사람이 적용한 뒤 runtime 항목이 없는 `tools/doctor.py`.
3. **카드를 제안합니다.** `python3 tools/wizard.py recommend <project> --profile <id> [--locale ko] --apply` 를 실행합니다. 카드마다 id, 강도, 주장, 근거 참조, 반례를 보입니다. must 카드는 설명하되 협상하지 않습니다. 채택형 must 카드(`adoption: opt_in`, 헌법 밖)는 질문으로 묻습니다. 제안서가 카드마다 기본값(사용자 `~/.strata/config.yaml` 의 `wizard.adopt_cards`, 그다음 프로필 `cards_default`)을 보이고, 답은 `--adopt <id>` 나 `--decline <id>=<사유>` 로 남깁니다(거절은 사유와 함께 제안서와 레지스트리에 남습니다). 조건부 must 카드(`adoption: conditional`)는 묻지 않습니다. 프로젝트에 그 사실이 맞으면 실립니다 — `uses_vault`(`--uses-vault yes|no`), `uses_quilt`(`--harness …,quilt`), `domain_work`(영역). 어떤 카드가 왜 실렸는지 말합니다. 규칙 묶음(`layers`·`naming`·`rules`)마다 집행 등급을 묻습니다. advisory 는 위반을 기록만 하고, default 는 사유·기한이 있는 덮어쓰기가 없으면 실패, block 은 실패입니다. 선언하지 않은 묶음은 block 입니다. `--enforce <묶음>=<등급>` 으로 남기면 매니페스트에 들어가고, 검사기는 `kb enforce run` 으로 감쌉니다. 위반을 출력하고도 0 으로 끝나는 경고 모드 검사기는 `--violation-exit 0,1 --violation-pattern <위반 표식>` 으로 감싸고, 잘못 남은 기록은 고치지 않고 `kb enforce correct` 로 정정 항목을 덧붙입니다. 사용자가 거절한 should 카드마다 `waived_reason` 을 기록합니다. must 카드에 대한 반박은 반례 후보로 기록합니다(프로젝트가 아니라 방법론 backlog 로 갑니다). `--apply`(또는 `--out <dir>`) 없이 diagnose·recommend 는 출력만 합니다. 이전 답은 직전 제안서에서 읽습니다. detached 프로젝트는 vault 사본(`$STRATA_VAULT/projects/<p>/strata/kit/proposal.yaml`)을 먼저 읽고, 지금 준 답이 이깁니다. 승인된 `proposal.yaml` 은 바꾸지 않습니다. 새 제안은 `proposal.next.yaml` 로 가니 차이를 보이고, 사용자가 동의하면 `proposal.yaml` 로 옮긴 뒤 사용자가 `approved: true` 를 표시하게 합니다. 증거: 사용자가 `approved: true` 로 표시한 `.strata/kit/proposal.yaml`.
4. **생성합니다.** `python3 tools/wizard.py generate <project> --apply` 를 실행합니다. 제안에 적힌 경로만 쓰고 `core_revision` 과 `adapter_revision` 을 찍습니다. 손으로 쓴 기존 파일(머리에 생성 표시가 없는 파일)은 제안의 `overwrite_handwritten` 에 이름이 있을 때만 바꿉니다. 바꾸기 전에 그 내용을 `.strata/kit/notes.<locale>.md` 로 옮깁니다. 증거: 명령 출력의 쓴 파일 목록.
5. **검증합니다.** `python3 tools/wizard.py verify <project>` 를 실행합니다. 예산(항상 읽히는 바이트), revision 헤더, 레지스트리를 검사하고 샘플 요청 다섯 개를 레지스트리 트리거에 통과시킵니다. 증거: exit 0 과 보고.
6. **기록합니다.** 프로필 선택이나 해제가 이 프로젝트의 아키텍처 결정이면 decision writer 로 기록합니다. 증거: 답변의 DEC id.

## 합리화

| 생각 | 반박 |
|---|---|
| "스택이 뻔하니 진단은 건너뛰자." | 진단은 예산도 재고 drift 도 찾습니다. 명령 하나이니 실행하세요. |
| "사용자가 규칙을 아니 근거는 생략하자." | 근거 없는 카드는 의견입니다. 참조를 보이세요. 그것이 핵심입니다. |
| "이 must 카드는 여기에 안 맞으니 해제하자." | must 는 해제되지 않습니다. 설명하고, 반박을 반례 후보로 기록하세요. |
| "전부 생성하면 필요 없는 건 지우겠지." | 승인된 경로만 씁니다. 요청하지 않은 파일은 drift 입니다. |
| "지난번에 검증을 통과했다." | 코어 revision 이 움직였을 수 있습니다. 생성할 때마다 검증하세요. |

## 적신호

- `package.json`, `build.gradle`, `go.mod`, `Cargo.toml` 에 답이 있는 인터뷰 질문.
- `evidence` 항목이 없는 카드가 든 제안.
- 헤더에 `core_revision` 이 없는 생성된 AGENTS.md.
- 제안의 경로 목록 밖에 쓰인 파일.

## 검증

- `.strata/kit/proposal.yaml` 이 `approved: true` 로 존재하고 모든 카드에 근거가 있다.
- 해제된 should 카드마다 `waived_reason` 이 있다.
- `tools/wizard.py verify <project>` 가 exit 0 이고 그 보고가 답변에 있다.
- 내린 결정은 기록됐고 그 id 가 답변에 있다.
