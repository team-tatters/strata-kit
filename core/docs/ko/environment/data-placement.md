# 데이터 배치 경계 (Data Placement)

> 정본: strata-kit `core/docs/ko/environment/data-placement.md` (2026-10-29 strata `docs/06-environment/data-placement.md` 에서 이관, DEC-2026-10-29-11).

> Strata 산출물이 **어디에 살고 누가 추적하는가**의 단일 정본(source of truth).
> 흩어져 있던 규칙(cross-model-bridge 데이터 표, CLAUDE.md, task-spec-schema, 01-context의 local/shared 구분)을 여기로 수렴한다.
> 핵심 원칙: **"세션은 소모품, 데이터는 Core 밖, 작업 이력은 프로젝트 repo 밖."**

## 0. 왜 필요한가 (해결하는 문제)

초기 설계는 **세션 간 공유를 위해 `.strata/handoffs/`·`.strata/tasks/`를 프로젝트 repo에 git 추적**시켰다. 그 결과:

- **커밋 churn**: 핸드오프·태스크는 세션마다 생성·변경되는 *작업 이력*인데, 공유하려고 코드 repo에 커밋되어 커밋 빈도가 비정상적으로 높았다.
- **이중 저장**: 핸드오프를 `.strata/handoffs/*.yaml`(repo)에 쓰고 vault `sessions/*.md`로 동기화하면서 원본을 repo에 그대로 남겨, 같은 정보가 두 곳에 중복됐다.
- **위치 드리프트**: 신규 모델(shared session ledger, task-spec)은 이미 vault를 정본으로 두는데 옛 템플릿/스크립트는 `.strata/`를 가리켜, 한 산출물에 정본이 둘이 됐다.

해법은 **작업 이력을 프로젝트 repo 밖(vault)으로 빼고, repo에는 프로젝트 종속 지침만 남기는 것**이다. 이는 ledger/relay가 이미 vault로 간 결정의 미완성 부분을 마저 정리하는 것이다.

## 1. 3-Tier 경계

```text
Tier L · local      {project}/.strata/local/        git 제외   머신-로컬·휘발성 런타임 상태
Tier P · project    {project}/.strata/              git 추적   프로젝트 종속 '지침' (코드와 함께)
Tier V · vault      $STRATA_VAULT/projects/{n}/     vault git  작업 '이력'·협업 산출물
```

분류 기준 한 줄:

> **휘발성이면 L, 프로젝트 종속 지침이면 P, 작업 이력·협업 산출물이면 V.**

| Tier | 위치 | git | 성격 | 변경 빈도 |
|---|---|---|---|---|
| **L · local** | `{project}/.strata/local/` | 제외 (.gitignore) | 머신 종속, 다른 머신에서 깨짐, 재생성 가능 | 높음 (추적 안 하므로 무관) |
| **P · project SoT** | `{project}/.strata/` (루트) | 추적 | 이 프로젝트의 아키텍처·제약. 코드와 함께 PR 리뷰되어야 함 | 낮음 (아키텍처 변경 시만) |
| **V · vault/shared** | `$STRATA_VAULT/projects/{n}/` | vault git (별도) | 세션 간/사람 간 공유되는 이력·산출물. repo 커밋과 무관 | 높음 (repo 밖이라 churn 없음) |

## 1.5 Placement Profile (embedded | detached)

Tier P의 **물리 위치**는 프로젝트의 repo 정책에 따라 둘 중 하나를 선택한다.
Tier의 의미(프로젝트 종속 지침)와 리뷰 의무는 동일하고, 위치만 달라진다. (DEC-2026-08-19-01)

| Profile | Tier P 정본 위치 | repo 흔적 | 적용 기준 |
|---|---|---|---|
| **embedded** (기본) | `{project}/.strata/` — git 추적 | `.strata/local/` ignore 한 줄 | 개인/통제 repo — Tier P를 코드와 함께 PR 리뷰 가능 |
| **detached** | `$STRATA_VAULT/projects/{n}/strata/` — vault git | gitignored `.strata/local/`만 (커밋 0건) | 팀 repo 등 `.strata` 커밋이 컨벤션 위반인 경우 |

profile의 **정본은 manifest 파일**이다 — 포인터를 머신 로컬에만 두면 새 PC에서 복원되지 않는다 (cross-review 2026-08-19 반영):

| Profile | manifest 위치 | 보존 매체 |
|---|---|---|
| embedded | `{project}/.strata/profile.yaml` (git 추적) | 프로젝트 repo — **결정이 아직 없는 신규 프로젝트도 판별 가능** |
| detached | `$STRATA_VAULT/projects/{n}/strata/profile.yaml` | vault — **새 PC는 vault pull만으로 profile이 복원된다** |

```yaml
# profile.yaml — placement profile manifest
profile: detached        # embedded | detached (repo 쪽 manifest는 embedded만 허용)
project: "{project-name}"
```

`.strata/local/vault-link.yaml`(Tier L, gitignored)은 **선택적 로컬 캐시**다 — SoT가 아니며 없어도 동작한다.

- **Tier P resolver 규칙** (Tier P를 읽는 모든 소비자 공통 — 구현 매핑: `python3 -m kb --help`, `core/docs/ko/kb-engine.md`):
  ① repo `.strata/profile.yaml`(embedded 선언) → embedded
  ② repo `.strata/decisions.yaml`·`.strata/decisions/` 존재(legacy 감지) → embedded
  ③ `.strata/local/vault-link.yaml`(로컬 캐시) → detached
  ④ `$STRATA_VAULT/projects/{디렉토리 basename}/strata/profile.yaml` → detached (새 PC bootstrap)
  ⑤ 전부 없으면 Strata 미적용 프로젝트
- detached Tier P 트리: `strata/{profile.yaml, decisions/, decisions.yaml, constraint-registry.yaml, layer-map.yaml}`
- repo 완전 무접촉이 필요하면 팀 repo `.gitignore` 대신 **global gitignore**(`~/.config/git/ignore`)에 `.strata/`를 등록한다.
- detached에서 PC 간 세션 이어가기는 **vault pull 하나로 완결**된다 (동기화 훅: DEC-2026-08-19-02).
- 팀과 공유해야 하는 결정은 vault 보관과 별개로 repo `docs/`로 승격한다 (§2의 API 계약 승격 규칙과 동일 패턴).

## 2. 산출물별 배치 (정본 표)

| 산출물 | Tier | 경로 | 비고 |
|---|---|---|---|
| active-task (세션별) | L | `.strata/local/active/{session-id}.yaml` | 세션 중단 시 현재 상태 (절대규칙). 동시 다중 세션이 서로 덮어쓰지 않도록 세션별 파일 (DEC-2026-08-19-05) |
| session-plan.yaml | L | `.strata/local/session-plan.yaml` | |
| session-log.txt | L | `.strata/local/session-log.txt` | SessionEnd hook 기록 |
| last-compaction.yaml | L | `.strata/local/last-compaction.yaml` | PreCompact 스냅샷 |
| agent-sessions.yaml (세션 매핑) | L | `.strata/local/agent-sessions.yaml` | claude_id ↔ codex_id, 머신 종속 |
| **profile manifest** | **P** | `.strata/profile.yaml` (embedded) / vault `strata/profile.yaml` (detached) | placement profile 정본 (§1.5) |
| **decision 레코드** | **P** | `.strata/decisions/DEC-{date}-{NN}-{slug}.yaml` | 결정 **정본** — 1결정=1파일. 채번·기록은 decision writer CLI 경유 (동시 세션 안전, DEC-2026-08-19-05) |
| **decisions.yaml (인덱스)** | **P** | `.strata/decisions.yaml` | 레코드에서 **재생성되는 T0 인덱스**. 손편집 금지 |
| **constraint-registry.yaml** | **P** | `.strata/constraint-registry.yaml` | 컨텍스트 제약 레지스트리 |
| **layer-map.yaml** | **P** | `.strata/layer-map.yaml` | 레이어 위반 검사용 매핑 |
| cowork DB | L | `.strata/cowork/cowork.sqlite*` | CoWorking 휘발성 상태 (WAL 포함). 영속 승격물은 tasks(V)·decision 레코드(P)로 |
| ~~shared/~~ | — | `.strata/shared/` | **deprecated** — 작업 이력은 Tier V로 이관 완료 대상. 신규 생성 금지 |
| **handoffs (핸드오프)** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` | shared session ledger와 동일 위치. **vault에 직접 작성** |
| **shared session ledger** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` | 맥락 source of truth |
| **tasks (태스크 명세)** | **V** | `$STRATA_VAULT/projects/{n}/tasks/{date}/{nn}-{title}/` | `_order.yaml` + `task-{nn}.yaml` |
| **relay 기록** | **V** | `$STRATA_VAULT/projects/{n}/relays/` | request/feedback 교환 |
| **Hub delivery state** | **L** | `.strata/local/` 또는 local Hub DB | hub_id, inbox cursor, pull/ack 상태. 머신·세션 종속 |
| **Hub audit projection** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` 또는 `relays/` | 사람이 이어받아야 하는 packet/review/decision 요약 |
| **methodology-backlog (project)** | **V** | `$STRATA_VAULT/projects/{n}/backlog/methodology-backlog.yaml` | 운영 큐 = 작업 이력 성격 |
| **exploration-report / draft api-specs** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` (또는 tasks 인접) | 세션 간 인계 중간 산출물 (accepted API는 승격 — 아래 주석) |
| **DEC 노트 미러** (사람용 ADR 미러) | V | `$STRATA_VAULT/projects/{n}/decisions/DEC-{date}-{NN}.md` + `_generated-index.md` | 레코드에서 생성되는 **사람 읽기·백링크용 미러**. 정본은 Tier P. **생성 시점**: decision writer CLI의 `add`·`regen-index`·`migrate`가 레코드·인덱스를 쓴 **직후 같은 실행 안에서** DEC projection generator를 호출해 해당 프로젝트분을 **전량 재생성**(멱등, 정본 없는 노트 제거). 커밋은 세션 종료 채널(handoff/ledger close → vault commit+push)이 담당, 즉시 반영은 `--sync` (DEC-2026-08-21-01) |

| **주제 노드 트리 (toc.yaml)** | **V** | `$STRATA_VAULT/projects/{n}/_meta/toc.yaml` | 사람이 읽는 목차의 **정본**. 지침 성격이지만 소비자(노드 페이지 생성기·KB 색인·커버리지 리졸버)가 전부 vault 쪽이고 detached 프로젝트는 repo에 둘 곳이 없으므로 V. 코드와 함께 리뷰돼야 하는 변경이 아니다 |
| **노드 페이지** | V | `$STRATA_VAULT/projects/{n}/nodes/{node-id}.md` | toc.yaml + 4면 frontmatter(명세·제약·결정·세션)에서 생성되는 **조인 뷰**(Index 계층, 손편집 금지). **생성 시점**: KB 색인 빌드와 세션 종료 채널(handoff/ledger close)이 같은 실행 안에서 해당 프로젝트분을 전량 재생성(멱등, 정본 없는 페이지 제거). 별도 수동 실행에 맡기지 않는다 — DEC 노트 미러의 교훈 |

> **노드 페이지는 정본이 아니다** — 4면의 정본은 각각 명세(V)·Constraint Card(V)와 registry(P)·decision 레코드(P)·세션(V)이고, 노드 페이지는 이를 읽기 전용으로 모은다. "부채" 면도 표시일 뿐이며 정본은 세션 문서에 `doc_change` 선언이 없다는 사실 자체다.
>
> **decisions 정본은 Tier P다** — 물리 위치는 profile에 따른다 (embedded=repo `.strata/`, detached=vault `projects/{n}/strata/`, §1.5). vault `projects/{n}/decisions/`는 레코드에서 생성되는 **DEC 노트**(사람 읽기·백링크용, 손편집 금지)이며 기계판독 SoT가 아니다.
>
> **DEC 노트 미러의 역할과 한계** (DEC-2026-08-21-01): embedded 프로젝트의 레코드 정본은 **프로젝트 repo 커밋·push 전까지 다른 머신에서 읽을 수 없다**. 미러는 이 공백을 vault 채널로 메우는 크로스 환경 보완 장치이지 정본 대체가 아니다 — 따라서 ① 미러는 레코드 기록과 **같은 실행**에서 생성되어야 하고(별도 수동 실행에 맡기면 비어 있게 된다 — 2026-08-21 한 백엔드 프로젝트의 미러 0건 실사례), ② 세션 종료 게이트(handoff generator·ledger CLI `validate`/`close`)는 repo `.strata/decisions*`의 **미커밋 레코드를 경고**한다(차단 아님). detached 프로젝트는 레코드 자체가 vault에 있어 세션 종료 채널이 함께 커밋하므로 게이트 대상이 아니다.
>
> **API 계약 승격 규칙**: `draft api-specs`는 Tier V(세션 인계 중간물)지만, **accepted API contract**(코드·클라이언트·문서화의 기준이 되는 순간)는 작업 이력이 아니라 project artifact다 → **Tier P 또는 repo `docs/openapi`로 승격**한다.
>
> **backlog 가시성 주의**: project `methodology-backlog` 자체는 운영 큐라 Tier V지만, **accepted 항목이 Tier P(`decisions`/`constraint-registry`/`layer-map`)를 바꾸면 그 Tier P 변경은 같은 PR에 드러나야** 한다 (코드 리뷰 가시성 — backlog가 vault로 빠져도 *결정의 코드 반영*은 repo에서 리뷰).

## 3. .gitignore 규칙 (프로젝트)

Tier L은 제외, Tier P만 추적한다. Tier V는 애초에 프로젝트 repo 밖이라 무관.

```gitignore
# Strata — Tier L(local·cowork) 제외, Tier P(지침)만 추적  [embedded profile]
.strata/local/
.strata/cowork/
.strata/**/*.tmp

# Tier P는 명시적으로 추적 (제외하지 않음):
#   .strata/decisions/  .strata/decisions.yaml
#   .strata/constraint-registry.yaml
#   .strata/layer-map.yaml
```

**detached profile**은 repo `.gitignore`를 건드리지 않는 것이 원칙이다 — global gitignore(`~/.config/git/ignore`)에 `.strata/`를 등록해 repo 흔적을 0으로 유지한다 (§1.5).

> ⚠️ 구(舊) 규칙(`handoffs/`·`tasks/`를 추적)에서 **반전**됐다. 이전엔 "공유 위해 추적"이었으나, 이제 공유는 **vault(Tier V)**가 담당하고 repo는 추적하지 않는다.

## 4. 왜 이 경계인가 (근거)

- **머신 종속(L)은 git에 올리면 깨진다.** 세션 ID·로컬 경로는 다른 머신에서 무의미 (카드 `rec.session.state-in-files` 의 local/shared 원칙과 같다).
- **지침(P)은 코드와 운명을 같이한다.** 아키텍처 결정·제약은 그 코드를 리뷰·롤백할 때 함께 봐야 하므로 같은 repo·같은 PR에 있는 것이 기본이다(embedded). 단, 팀 repo 컨벤션이 `.strata` 커밋을 허용하지 않으면 **위치만** vault로 옮긴다(detached, §1.5) — 지침의 성격과 리뷰 의무는 동일하다. 변경 빈도가 낮아 churn을 만들지 않는다.
- **이력(V)은 공유 채널이 따로 있다.** 핸드오프·ledger·relay는 세션과 사람 사이를 잇는 이력이다. 이 공유는 **vault(자체 git/Obsidian 동기화)**가 전담하므로, 코드 repo에 실을 이유가 없다. 코드 repo는 코드·지침이 바뀔 때만 커밋된다.

## 5. 다른 문서와의 관계

- **vault 동기화**: 핸드오프는 vault에 직접 작성한다(옛 "repo 원본 → vault 변환" 이중저장 흐름은 폐기). vault 생성물마다 쓰는 주체는 DEC-2026-10-29-04 가 정한다 — DEC 노트는 decision writer CLI 실행에 내장(§2 표), 노드 페이지는 librarian(`kb views-publish`), 색인 메타는 머신마다.
- **task-spec-schema.md** (`core/docs/ko/methodology/task-spec-schema.md`): 태스크·backlog는 Tier V. 경로는 이 표가 정본.
