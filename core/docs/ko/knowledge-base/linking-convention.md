# Knowledge Base — 링크 규칙

> 정본: strata-kit `core/docs/ko/knowledge-base/linking-convention.md` (2026-10-29 strata `docs/07-knowledge-base/linking-convention.md` 에서 이관, DEC-2026-10-29-11).

## 개요

vault 내부 링크는 Obsidian 호환성을 최우선으로 합니다.
vault 외부(strata-kit, projects)로의 참조는 환경 변수 기반입니다.

## 링크 유형

### 1. vault 내부 링크 — Wikilink 사용

```markdown
<!-- 같은 vault 내 문서 참조 -->
[[overview]]
[[decisions/001-use-jwt-auth]]
[[glossary#JWT]]

<!-- 표시 텍스트 변경 -->
[[decisions/001-use-jwt-auth|JWT 인증 결정]]
```

**규칙:**
- vault 내부는 항상 `[[wikilink]]` 사용
- 경로는 vault 루트 기준 상대경로
- 확장자 `.md` 생략
- Obsidian Graph View에서 관계가 시각화됨

### 2. vault → kit 참조 — 환경 변수

```markdown
<!-- vault 문서에서 kit 방법론 참조 시 -->
레이어 규칙은 `$STRATA_KIT/core/rules/layer-rules.yaml` 참조.
```

**규칙:**
- 절대경로 사용 금지
- 반드시 `$STRATA_KIT` 환경 변수 사용
- vault 문서에서 kit 참조는 최소화 (vault는 지식, kit은 방법론)

### 3. vault → project 참조 — 환경 변수

```markdown
<!-- vault 문서에서 프로젝트 코드 참조 시 -->
구현: `$STRATA_PROJECTS/{project-name}/src/auth/AuthService.ts`
```

**규칙:**
- `$STRATA_PROJECTS` 환경 변수 사용
- 코드 참조는 경로만 기록 (코드 복사 금지)

### 4. project CLAUDE.md → vault 참조 — @ 구문

```markdown
<!-- 프로젝트 CLAUDE.md에서 vault 참조 시 -->
프로젝트 지식: @$STRATA_VAULT/projects/my-api/
```

**규칙:**
- Claude Code의 `@` lazy loading 구문 사용
- 환경 변수로 경로 해석

### 5. project CLAUDE.md → kit 참조 — @ 구문

```markdown
<!-- 프로젝트 CLAUDE.md에서 kit 참조 시 -->
레이어 규칙: @$STRATA_KIT/core/rules/layer-rules.yaml
```

### 6. typed frontmatter link — 관계의 종류를 데이터로

본문 wikilink는 "관련 있음"만 말한다. 관계의 **종류**는 frontmatter 필드로 적는다 (DEC-2026-08-19-03). 생성기·검증·노드 페이지는 이 필드만 읽고 본문 링크는 읽지 않는다.

| 필드 | 방향 | 쓰는 타입 | 뜻 |
|---|---|---|---|
| `sources` | Knowledge → Archive | KB·pattern | 이 문서의 근거가 된 세션·태스크. Knowledge 갱신 시 필수 |
| `up` | 자식 → 부모 | 모든 문서 | 이 문서를 포함하는 상위 개념·MOC |
| `decisions` | 문서 → 결정 | KB·session·task | 이 문서가 따르거나 만든 결정 |
| `supersedes` / `superseded_by` | 새 결정 → 옛 결정 / 옛 → 새 | decision | 대체 관계의 양끝. 검증이 대칭을 확인 |
| `nodes` | 문서 → 주제 노드 | decision·session·task·specification·concept·constraint | 이 문서가 속한 목차 단위 |
| `covers` | 명세 → 코드 표면 | specification·concept | 이 문서가 **정본**인 코드 경로·심볼·엔드포인트·테이블 |
| `related` | 문서 ↔ 문서 | 모든 문서 | 언급·참고 관계. 소유가 아니다 |

**규칙:**
- `sources`·`up`·`decisions`·`supersedes`·`related`의 값은 `[[wikilink]]`다. `nodes`의 값은 toc.yaml의 노드 id, `covers`의 값은 저장소 상대 포인터다. 둘은 wikilink가 아니다.
- 관계 필드는 값이 없으면 생략한다. 빈 배열을 두면 검증이 "의도적 비움인가"를 묻는다.
- 같은 관계를 본문 wikilink로도 적는 것은 허용한다(Obsidian 그래프용). 그러나 정본은 frontmatter다.
- 값 형식의 정본: `nodes`·`covers`·`doc_change`·`supersedes`는 document-format.md "노드·커버리지 필드" 절, `sources`는 같은 문서의 frontmatter 스키마.

### 7. 링크가 항상 현행을 가리키게 하는 규칙 (DEC-2026-09-30-03)

- **wikilink 대상은 파일명(또는 vault 상대 경로)으로 해석돼야 한다.** frontmatter `id:` 나 `aliases`(태스크 id 등)로만 해석되는 링크는 Obsidian 에서 깨지므로 쓰지 않는다. 파일을 옮기거나 이름을 바꾸면 옛 이름을 `aliases:` 에 남기되(검색·unlinked mention 용), 링크 자체는 검사기가 찾아 주는 대로 새 파일명으로 고친다.
- **자유 텍스트를 링크로 감싸지 않는다.** `[[restdocs 양식 정렬]]` 처럼 대상 문서가 없는 링크는 금지한다. 설명이 필요하면 표시 텍스트를 쓴다 (`[[session-2026-09-02-x|task05 후속]]`).
- **대체된 문서로 향하는 본문 링크는 현행 문서로 바꾼다.** 대체 관계 필드(`supersedes`·`superseded_by`)와 이력을 설명하는 문장은 예외다. 검사기는 둘을 구분할 수 없어 이 항목은 참고(경고)로만 보고한다.
- **코드는 경로보다 심볼로 가리킨다.** `covers.symbols` 에 클래스·함수 이름을 적고, 본문에서도 `CollaboratorCommandService.invite` 처럼 심볼로 쓴다. 경로는 모듈·패키지 수준까지만 적는다. 파일은 옮겨져도 심볼 이름은 잘 바뀌지 않기 때문이다.
- **검사:** `python3 "$STRATA_KIT/kb" link-check` 가 깨진 wikilink, 자유 텍스트 링크, id 로만 해석되는 링크, 대체된 문서로의 본문 링크를 찾는다. 생성·임포트 문서(DEC 노트, 노드 페이지, 기획 원문, `_index/`)의 위반은 손으로 고칠 수 없으므로 보고만 하고 차단하지 않는다(고칠 곳은 생성기). 세션 종료 게이트는 그 세션 프로젝트의 문서만 본다. 기존 위반은 기준선(`$STRATA_VAULT/.kb/link-baseline.json`)으로 묶고, **기준선 밖의 새 위반이 있을 때만 실패**한다. 세션 종료(`python3 "$STRATA_KIT/kb" ledger close`)가 이 검사로 vault 동기화를 멈추고, 핸드오프 생성(`python3 "$STRATA_KIT/kb" handoff`)은 경고만 한다. 급할 때만 `STRATA_LINK_CHECK=warn` 으로 경고 강등한다. 기준선은 고친 만큼 `--shrink-baseline` 으로 줄인다.
- **코드 대조:** `--code-root {project}=<repo>` 를 주면 KB `covers.paths` 가 저장소에 있는지, `covers.symbols` 이름이 코드에서 검색되는지도 확인한다 (코드 저장소가 있는 머신에서만).

## 금지 사항

| 금지 패턴 | 이유 | 대안 |
|---|---|---|
| vault 내 절대경로 (`/home/alice/...`) | 머신 간 호환 불가 | `$STRATA_KIT`, `$STRATA_VAULT` 사용 |
| vault 내 마크다운 링크 `[text](path)` | Obsidian Graph에 표시 안 됨 | `[[wikilink]]` 사용 |
| 코드 블록 복사 | 코드 rot | 경로 참조만 기록 |
| 프로젝트 간 직접 참조 | 의존성 생성 | vault/patterns/에 공통 패턴으로 추출 |
| 관계의 종류를 본문 링크에만 의존 | 생성기·검증이 읽지 못함 | §6 typed frontmatter link |

`covers`의 코드 포인터는 wikilink가 아니어도 된다. frontmatter 안의 저장소 상대경로는 "vault 내 마크다운 링크 금지"의 대상이 아니다.

## 임베드

Obsidian 임베드 문법도 활용 가능합니다:

```markdown
<!-- 다른 문서의 특정 섹션 임베드 -->
![[decisions/001-use-jwt-auth#결정]]

<!-- 이미지 임베드 -->
![[architecture-diagram.png]]
```

임베드는 참조 문서의 내용이 바뀌면 자동 반영되므로, 중복 작성보다 임베드를 권장합니다.
