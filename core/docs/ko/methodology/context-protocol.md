# 09 — Context Protocol: Constraint-Aware Context Loading

> 정본: strata-kit `core/docs/ko/methodology/context-protocol.md` (2026-10-29 strata `docs/09-context-protocol.md` 에서 이관, DEC-2026-10-29-11).

> kit 카드(`rec.context.entry-view-budget`·`rec.session.split-at-task-boundary`·`rec.session.state-in-files`)와 `core/docs/ko/methodology/session-splitting.md` 의 원칙을 기반으로, 제약(Constraint) 인식 컨텍스트 로딩 규칙을 정의합니다.

## 1. 문제 정의

ADR에 결정된 도메인 제약(예: "hard-delete 금지", "Bitemporal 필수")이 구현 단계에서 유실되는 경로:

1. ADR 산문이 너무 길어 매번 전문을 읽을 수 없음
2. Compaction 시 ADR 상세가 유실됨
3. Worker는 독립 컨텍스트 — Builder 세션의 ADR 논의를 모름
4. 태스크 명세에 도메인 제약이 누락되면 Worker가 감지할 수 없음

## 2. 해결: 제약은 진입 뷰에 요약으로, 레지스트리 전문은 필요할 때 읽는다

### 컨텍스트 계층

```
T0 — Universal (항상 로드, 12KB 이내 — rec.context.entry-view-budget)
  ├── AGENTS.md + CLAUDE.md            (생성 지침 — must 카드 요약, 제약 요약 2KB 이내)
  └── active/{session-id}.yaml         (세션별 active-task — DEC-2026-08-19-05)

T1 — Session (세션 시작 시)
  ├── 최신 handoff 파일
  ├── decisions.yaml                   (생성형 인덱스, 필요할 때 — 정본은 decisions/ 레코드)
  └── constraint-registry.yaml         (필요할 때 — 진입 뷰의 링크로)

T2 — Domain (태스크 대상별)
  ├── 해당 주제 노드의 노드 페이지 (최종형상·정책·결정·작업이력·부채 조인 — 생성물, 진입점)
  ├── 해당 도메인의 Constraint Card 전문
  └── 관련 ADR의 Decision Outcome 섹션

T3 — Implementation (구현 시)
  ├── 대상 소스 파일
  ├── 테스트 파일
  └── layer-rules.yaml (해당 레이어 섹션)
```

### constraint-registry.yaml 규칙

- **위치**: `.strata/constraint-registry.yaml` (프로젝트 내)
- **크기 제한**: 3KB 이내. 생성 지침에는 2KB 요약만 싣고 전문은 링크로 둔다
- **3KB 초과 시**: `severity: should` 항목을 별도 파일로 분리. `must`/`must-not`만 registry에 유지
- **갱신 시점**: ADR accepted 전환 시 + Constraint Card 생성 시 동시 갱신
- **형식**: `decisions.yaml`과 동일한 YAML 인덱스

```yaml
constraints:
  - id: CC-NNN-01
    source: ADR-NNN
    severity: must
    scope: {domains: [{domain}], layers: [{layer}]}
    rule: "{1줄 실행 가능 규칙}"
    status: active
```

### decisions.yaml 규칙 (2026-08-19 정정)

- 필요할 때 읽는 `decisions.yaml`은 **레코드(`.strata/decisions/DEC-*.yaml`)에서 재생성되는 컴팩트 인덱스**다. 손편집 금지.
- 결정 추가·채번·인덱스 재생성은 **decision writer CLI**만 수행한다 (flock 직렬화 — 동시 다중 세션 안전, DEC-2026-08-19-05. 역할→구현 매핑: `python3 -m kb --help`, `core/docs/ko/kb-engine.md`).
- 상세가 필요하면 인덱스 항목의 `record:` 경로로 레코드 전문을 로드한다 — Registry(1줄)→Card(~50줄)→ADR(~200줄)의 계층적 상세화와 동일 패턴 (인덱스 요약→레코드 전문).
- Tier P의 물리 위치는 placement profile을 따른다 (`core/docs/ko/environment/data-placement.md` §1.5 — embedded=repo, detached=vault `projects/{n}/strata/`).

## 3. Agent Role별 Context 로딩

### Builder

| 상황 | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| 태스크 생성 | ✓ constraint-registry 필터링 | ✓ | 노드 페이지 → 해당 도메인 Card | - |
| ADR 작성 | ✓ | ✓ | 노드 페이지 (결정 사슬 확인) | - |
| Constraint 추출 | ✓ | - | - | - |

Builder는 constraint-registry.yaml을 읽고, 태스크의 도메인/레이어로 필터링하여
해당 constraint를 태스크 명세의 `scope.constraints`에 주입합니다.
같은 방식으로 변경 범위를 소유한 명세(`covers`)를 커버리지 리졸버로 찾아 `scope.docs_to_update`에 주입합니다.
노드 페이지는 이 두 주입의 진입점입니다 — 노드 하나를 열면 현행 명세·활성 제약·현행 결정이 한 화면에 있습니다.

### Worker

| 상황 | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| 태스크 실행 | CLAUDE.md만 | - | - | ✓ |

**Worker는 constraint-registry.yaml을 직접 읽지 않습니다.** 노드 페이지도 직접 읽지 않습니다.

Builder가 태스크 명세의 `scope.constraints`와 `scope.docs_to_update`에 주입한 내용만 사용합니다.
이것이 태스크 명세의 **자기완결성** 원칙과 일치합니다.

```yaml
# Worker가 받는 태스크 명세
scope:
  layer: "L2_DataLayer"
  constraints:
    - id: "CC-NNN-01"
      rule: "해당 scope에 적용되는 제약"
    - id: "CC-NNN-02"
      rule: "또 다른 제약"
```

Worker는 이 `scope.constraints`를 완료 보고의 `constraint_compliance`로 변환합니다.

### Supporter

| 상황 | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| Constraint 검색 | ✓ registry 검색 | - | 검색 결과만 | - |

Supporter는 Builder의 요청으로 특정 도메인/레이어의 constraint를 검색합니다.

## 4. Context Budget 규칙

```
CB-1: T0(AGENTS.md + CLAUDE.md)는 12KB, 상속 지침 포함 14KB 이내 (wizard verify)
  → 제약 레지스트리·결정 인덱스는 T0 가 아니다. 제약은 생성 지침에 2KB 요약으로 싣는다
  → 지침이 넘치면 목차화(참조 중심)로 축소 우선
  → using-strata 가 읽는 진입 경로(스킬 본문·코어 레지스트리·헌법)는 verify 가 따로 보고한다(2026-10-29, 상한 없음)

CB-2: T2 Constraint Card는 도메인당 10KB 이내
  → 10KB 초과 시 Card 전문 대신 registry의 1줄 요약만 로드

CB-3: 총 .strata/ 로드량 30KB 이내 (T0+T1+T2 합산)
  → 초과 시 T2를 registry 해당 행으로 대체

CB-4: ADR 전문은 Builder(ADR 작성/Constraint 추출)만 로드
  → 다른 역할은 Constraint Card로 ADR 결정에 접근
  → 이것이 Constraint Card의 존재 이유

CB-5: 노드 페이지는 노드당 8KB 이내 (CB-2의 Card 예산과 합쳐 T2 상한 유지)
  → 생성기가 작업이력 면을 최근 5건으로, 결정 면을 현행 + 직전 1건으로 절단해 예산 안에 맞춘다
  → 그래도 초과하면 최종형상·정책 면만 남기고 나머지는 링크로 대체
```

## 5. Compaction 복원력

```
Compaction 전:  ADR 전문 + 상세 논의 (컨텍스트에 존재)
Compaction 후:  요약만 남음 — ADR 상세 유실 위험

Constraint 복원 경로:
  constraint-registry.yaml (파일에 있으므로 언제든 다시 읽을 수 있음)
  → 1줄 요약으로 "무엇을 지켜야 하는가" 즉시 확인
  → 상세 필요 시 개별 Constraint Card 참조 (T2)
  → 더 깊은 맥락 필요 시 source_adr 참조

계층적 상세화 (Layered Detail):
  Registry (1줄)  →  노드 페이지 (~100줄)  →  Card (~50줄)  →  ADR (~200줄)
  요약은 진입 뷰      도메인 진입 시 한 번     필요 시 로드       거의 안 로드
```

노드 페이지는 Card와 ADR을 대체하지 않는다. 어느 Card·어느 ADR·어느 명세가 현행인지 알려 주는 진입점이며, 본문은 링크 너머에 있다.

## 6. 기존 컨텍스트 관리와의 관계

| 기존 (kit 카드·session-splitting.md) | 본 문서 (확장) |
|---|---|
| CLAUDE.md 계층 설계 (§2·§4, `wizard verify`) | 유지 — 제약 요약은 생성 지침에, 레지스트리 전문은 필요할 때 |
| 핸드오프 프로토콜 (`strata.handoff`, session-splitting.md §5) | 유지 — 핸드오프에 constraint 추출 상태 추가 |
| Compaction 방어 (execution-modes.md, `kb pre-compact`, SessionStart compact) | 강화 — registry가 추가 복원 앵커 |
| 토큰 예산 가이드 (session-splitting.md §5.2) | 확장 — CB-1~5 규칙 추가 |
| Memory vs Handoff vs KB 구분 (§7, rec.session.state-in-files, rec.kb.session-records-in-vault) | 유지 — Constraint Card는 KB에 배치 |
| (신규) 주제 노드 | T2 진입점 — 노드 페이지는 Index 계층의 생성물, 정본 아님 (core/docs/ko/knowledge-base/vault-structure.md) |

## 7. 메모리·핸드오프·KB 구분

하네스 메모리(Claude Code 는 `~/.claude/projects/<프로젝트>/memory/`)는 세션이 시작할 때마다 인덱스가 자동으로 읽히는 곳이다. 그래서 무엇을 두느냐가 다음 세션의 판단을 바꾼다.

| 무엇 | 어디에 | 이유 |
|---|---|---|
| 진행 상태 — 하던 일, 다음 할 일, 미커밋, 막힌 것 | 활성 파일(`.strata/local/active/`)과 핸드오프 | 세션이 끝나면 낡는다. 메모리에 두면 다음 세션이 지난 상태를 지금 사실로 읽는다 |
| 오래 유효한 사실 — 사용자의 선호, 일하는 방식에 대한 지시, 외부 자원의 위치 | 하네스 메모리 | 매 세션 자동으로 읽혀야 하는 것 |
| 결정과 정책 | 결정 레코드, 카드 | 검토된 정본이다. 메모리의 피드백이 정책이 되면 이쪽으로 옮긴다 |
| 설계·명세·지식 | vault KB | 링크와 커버리지로 코드와 묶인다 |

**진행 상태는 메모리에 두지 않는다.** 세션을 닫을 때 그 세션이 메모리에 쓴 진행 상태성 항목은 핸드오프로 옮긴다(`strata.handoff` 메모리 점검 단계, DEC-2026-10-31-16).

**확인일.** 메모리 항목의 머리말에 마지막으로 맞다고 확인한 날을 `verified: YYYY-MM-DD` 로 적는다(DEC-2026-10-31-14·34). 하네스가 적는 `modified` 는 바뀐 날이고, `verified` 는 내용이 아직 맞다고 본 날이다. 에이전트가 항목을 쓰거나 고칠 때 적고, 핸드오프 점검에서 사람이 "아직 맞다"고 답한 항목도 갱신한다.

**정리.** `python3 -m kb hygiene --memory` 가 지금 폴더의 메모리에서 정리 후보를 이유와 함께 보인다. 이유는 오래됨(확인일, 없으면 수정일이 60일 넘음 — 사용자 설정 `memory.stale_days`), 날짜 없음, 상태성 표현 일치, 형식 모름, 반대 피드백 후보 쌍, 인덱스와 파일의 불일치다. 도구는 읽기만 하고 본문을 출력하지 않는다. 상태성 표현은 일치일 뿐 판정이 아니다 — 상태를 이름으로 부르는 규칙도 걸린다. 옮기기·합치기·지우기는 사람이 항목마다 승인한 것만 한다. 지울 때는 같은 디렉터리의 `_archive/` 로 옮기고 머리말에 `retired`·`retired_reason` 을 적고 인덱스 줄을 뺀다(DEC-2026-10-31-17). 메모리 인덱스 크기는 `wizard verify` 가 보이고 12KB 를 넘으면 경고만 한다(DEC-2026-10-31-19). Codex 메모리는 아직 범위 밖이다(DEC-2026-10-31-13).
