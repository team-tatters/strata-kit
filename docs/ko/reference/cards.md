---
title: 카드
status: ready
generated: true
---

# 카드

> 이 문서는 원천에서 생성된다 — 손으로 고치지 않는다.

권고 카드 전체. must 는 협상하지 않고, should 는 사유를 남기면 끌 수 있으며, may 는 조언이다.

| 카드 | 강도 | 주장 | 적용 |
|---|---|---|---|
| `rec.architecture.no-layer-violation` | must | 선언된 레이어 방향으로만 의존하고, 검사기의 차단을 우회하지 않는다. | 프로젝트 프로필이 layer-map 을 선언한다 |
| `rec.data.soft-delete-only` | must | 도메인 데이터는 물리 삭제하지 않고 삭제 표시로 남겨 기본 조회에서 뺀다. | 영속 도메인 엔티티 |
| `rec.decision.orchestrator-decisions-flow-to-records` | must | 오케스트레이터(릴레이·승인·플로우)에서 난 결정도 프로젝트를 맡은 세션이 레코드로 남기고 릴레이·승인 id 를 출처로 적는다. | Quilt 나 다른 오케스트레이터 아래의 세션, 교차 모델 검토 |
| `rec.decision.record-immediately` | must | 아키텍처 결정은 같은 세션에서 decision CLI 로 기록한다. 인덱스는 손으로 고치지 않는다. | 앞으로의 코드를 구속하는 모든 선택: 레이어, 계약, 데이터 배치, 정책 |
| `rec.deploy.only-for-env-specific-verification` | must | 로컬로 확인할 수 있는 것은 배포로 확인하지 않는다. 배포 전 목적·사실과 추정·되돌림을 보고한다. | 공유 환경 dev·stage·prod |
| `rec.handoff.pending-has-blocker` | must | 핸드오프의 미결 항목에는 blocker 와 unblocked_by 를 함께 적는다. | 모든 핸드오프와 ledger close |
| `rec.kb.covers-owner` | must | 계약이 의존하는 코드는 소유 문서(covers)가 하나다. 바꾸면 그 문서를 고치거나 이유와 함께 doc_change: none 을 선언한다. | 지식 기반과 covers 선언이 있는 프로젝트 |
| `rec.kb.generated-views` | must | 생성 뷰(인덱스·DEC 노트·노드 페이지·검색 색인)는 손으로 고치지 않는다. 틀리면 출처나 생성기를 고친다. | 공유 정책의 generated_paths 와 색인 manifest 에 적힌 모든 생성 경로 |
| `rec.kb.link-currency` | must | 링크는 파일 이름으로, 현행 문서만 가리킨다. 기준선을 넘는 새 링크 위반은 세션 종료를 막는다. | 위키링크가 있는 모든 vault 문서 |
| `rec.kb.session-records-in-vault` | must | 핸드오프·ledger·태스크·오더·릴레이 패킷은 vault 에 쓰고 코드 저장소에는 쓰지 않는다. | 모든 프로젝트의 모든 세션 |
| `rec.naming.follow-convention` | must | 이름은 프로필 네이밍 컨벤션을 따른다. 일탈은 이유를 적는다. | 프로필에 naming-convention 파일이 있다 |
| `rec.placement.minimal-strata-in-code-repo` | must | 코드 저장소에는 CI 가 돌리는 집행 설정과 .strata/profile.yaml 포인터만 둔다. 지침·훅·기록은 팀이 kit 을 채택하지 않았으면 밖에 둔다. | 공유 코드 저장소(업무 영역)와 다른 사람이 커밋하는 모든 저장소 |
| `rec.process.confirm-before-state-change` | must | 상태를 바꾸기 전(파일·커밋·배포·삭제·외부 호출) 목적·영향·되돌림을 보이고 확인받는다. 읽기는 예외. | 모든 세션, 모든 실행 모드 |
| `rec.session.state-in-files` | must | 상태를 바꾸는 세션은 활성 태스크·진행 상태·핸드오프를 대화가 아니라 파일(로컬 active·vault)에 둔다. 읽기 전용 세션은 남기지 않는다. | 파일이나 외부 상태를 바꾸는 세션(단일 세션·여러 세션·오케스트레이션 모드) |
| `rec.verify.evidence-not-impression` | must | 완료는 증거(테스트 출력·종료 코드·경로)와 함께만 보고하고, 검증하지 못한 것은 적는다. | 모든 태스크 완료 보고 |
| `rec.workflow.worktree-only-with-consent` | must | 단일 체크아웃에서 순차로 일한다. 작업 트리는 제안해 수락받은 뒤에만 만든다. | 자동 모드를 포함한 모든 모드 |
| `rec.backend.cqrs-layers` | should | 코드는 L1 → LM1 → L2 → LM2 → L3 → Route 의 아래 방향으로만 의존한다. 명령과 조회는 별도 경로이고, REST DTO 는 아래 레이어로 내려가지 않는다. 같은 레이어 참조는 선언된 의미 안에서만 허용한다. | 애그리거트가 둘 이상인 Kotlin·Java Spring 서비스 |
| `rec.context.entry-view-budget` | should | 모든 세션이 행동 전에 읽는 것(AGENTS.md, CLAUDE.md 목차, must 카드 요약)은 12KB 아래로 둔다. 결정 인덱스·레지스트리·노드 페이지는 진입 뷰의 링크로 필요할 때 읽는다. | 모든 프로젝트 |
| `rec.decision.extract-constraint` | should | 기록된 결정이 코드가 따라야 할 규칙(금지 호출·필수 패턴·레이어 경계)을 낳으면, 같은 세션에서 그 규칙을 프로젝트 constraint-registry 에 결정 id 를 source 로 적어 뽑는다. 그래야 규칙이 결정 본문 안에 머물지 않고 태스크 명세와 리뷰에 닿는다. | 결정 본문이 코드 규칙을 담은 결정 레코드 |
| `rec.frontend.design-contract` | should | 색·타이포·간격·반경·모션은 디자인 토큰으로 참조한다. 컴포넌트는 임의의 prop 대신 이름 있는 변형을 노출한다. 결정적 검사기가 UI 코드의 리터럴 값을 표시한다. | 디자인 시스템이나 공유 UI 패키지가 있다 |
| `rec.frontend.layered-surfaces` | should | UI 코드는 Foundation → Contract → DataState → Primitive UI → Semantic Component → Feature Block → Route Surface → App Shell 방향으로만 의존한다. 데이터 호출은 DataState 에 있고, 라우트 표면은 기능 블록을 조합할 뿐 다른 것을 소유하지 않는다. | 화면이 여럿이거나 공유 컴포넌트 셋이 있는 앱 |
| `rec.kb.document-roles` | should | 지식 문서는 만들어진 형상을 적고 제자리 갱신한다. 기획 문서는 바라는 형상과 구현 검토를 담는다. 아카이브 문서(세션·태스크·릴레이)는 증거이며 사후에 고치지 않는다. 인덱스(MOC·노드 페이지·DEC 노트)는 생성물이다. 한 문서가 역할을 섞지 않는다. | 모든 vault 문서 |
| `rec.kb.update-in-place` | should | 지식 문서는 그 자리에서 고친다. 해당 절을 바꾸고 updated 와 sources 를 적으며, 이전 상태는 git 이력에 있다. 날짜 붙은 새 사본, 문서 안의 변경 이력 덧붙이기, 내용 검토 없는 날짜 갱신은 갱신이 아니다. | 지식 문서(as-built) |
| `rec.session.split-at-task-boundary` | should | 세션은 작업이 끝나거나 모양이 바뀔 때, 핸드오프를 쓴 뒤에 나눈다. 정리는 컨텍스트의 약 75% 에서 시작하고, 작업·활성 오류·편집 중인 파일은 지키며 실패한 시도는 결론만 남긴다. 두 신호는 단위를 반으로 자르지 않고 분할을 앞당긴다. 대화가 경고선(기본 약 40만 토큰, 한계선 약 60만, 실측 근거 없는 출발값, 사용자 설정 session.restart_tokens·session.restart_limit)을 넘으면 하던 단위를 마무리하고 다음 작업 경계에서, 늦어도 한계선 전에 나눈다. 시도가 두 번 막히면 세 번째 우회를 찾지 말고 멈춰서 실측 사실과 선택지를 보고한다. 같은 가설로 두 번 실패한다는 것은 같은 원인 추정 위에서 고친 시도 둘이 같은 증상으로 실패한 것이다. 이때 핸드오프는 확인된 사실, 확인하지 못한 추정, 버린 가설을 나눠 적는다. | 긴 세션과 여러 작업 |
| `rec.spec.desired-vs-as-built` | should | 요구와 인수 기준은 바라는 명세(planning)에, 현재 동작은 지식 문서(as-built)에 둔다. 미래 요구를 구현된 것처럼 as-built 문서에 쓰지 않는다. 완료란 둘이 같아지는 것이고 그 수렴 확인이 게이트다. | 기획 문서가 있는 모든 기능 작업 |
| `rec.structure.prepaid` | should | 변경 비용을 상쇄하는 구조는 처음부터 갖춘다. 지금 규모가 작다고 레이어를 줄이지 않는다. 레이어가 덮지 못하는 세 경계(데이터 소유, 도메인 간 쓰기, 도메인 간 읽기)는 명시적으로 선언한다. | 예상 수명 1년 이상, 또는 데이터를 쓰는 도메인이 둘 이상 |
