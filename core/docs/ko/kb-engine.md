# KB 엔진: 저장 계약

지식 기반은 문서·코드 표면·결정·세션·카드의 그래프이며, vault 옆의 파일 기반 저장소 하나에 담깁니다. 저장소 안의 모든 것은 출처에서 생성되고(rec.kb.generated-views), 저장소는 언제든 다시 만들 수 있는 캐시입니다.

## 왜 저장소 하나인가

지금 vault 에는 FTS5 색인, 노드 페이지, DEC 노트 미러, coverage 대응표, 링크 기준선이 각각 다른 스크립트로 만들어져 각자의 파일에 있습니다. 코드 그래프 결정(strata DEC-2026-10-28-05)은 코드 심볼과 영향 엣지를 더하고, 임베딩은 벡터를 더합니다. 각자 파일을 가지면 정작 중요한 질문(바뀐 함수를 소유한 문서는 무엇인가, 이 세션이 기댄 규칙을 어떤 결정이 대체했는가, 이 노드를 건드린 세션은 무엇인가)에 도구 사이의 조인이 필요합니다. 스키마 하나를 가진 저장소 하나면 질의 하나로 답하고, 백엔드가 바뀌어도 스키마는 바뀌지 않습니다.

## 스키마

```text
nodes(id, kind, project, path, title, status, updated, revision, payload_json)
  kind ∈ {doc, code, decision, session, order, task, card, node, profile}
edges(src, dst, kind, confidence, source_ref, created)
  kind ∈ {covers, supersedes, kb_updates, orders, decisions_made, relay, calls, imports, tests, member_of, links, implementation}
  confidence ∈ {declared, extracted, inferred}
chunks(node_id, seq, heading, text, title, tags, locale, embedding?, meta_json)
  전문 검색과 벡터 검색의 단위. heading·title·tags 를 함께 두어 FTS(unicode61, 네 열)가 legacy 색인과 같은 순위를 낸다. meta_json 은 heading_level·line_start·line_end·char_count. 문서·결정·오더가 FTS 테이블 하나, bm25 척도 하나를 쓴다. legacy 색인과 같은 순위는 목표가 아니다 (DEC-2026-10-28-08)
baselines(gate, project, key, recorded)                링크·coverage 기준선
revisions(store_rev, kit_rev, built_at, sources_hash)  저장소 전체의 출처 기록
```

선언된 엣지는 frontmatter(covers, supersedes, orders, kb_updates, decisions_made)와 결정 레코드에서 옵니다. 추출·추론된 엣지는 그래프 provider(imports, calls, tests)에서 오고 provider 의 신뢰도 표시를 그대로 가집니다. 저장소 안에는 손으로 쓴 것이 없습니다.

## 백엔드

| 백엔드 | 역할 | 상태 |
|---|---|---|
| SQLite (FTS5 + sqlite-vec) | 기본. vault 당 파일 하나, 서버 없음, MCP 프로세스에 내장 | 현재(FTS5), vec 는 미구현 |
| DuckDB | 같은 테이블 위의 분석(coverage 보고, 최신성, 프로젝트 횡단 질의), 공유용 parquet 내보내기 | 어댑터 미구현 |
| RocksDB | 오케스트레이터에서 오는 쓰기 많은 세션 스트림(릴레이 패킷, 승인)을 노드·엣지로 접기 전에 담는 키값 저장 | 어댑터 미구현 |

모든 백엔드는 같은 계약을 구현합니다. `put_nodes`, `put_edges`, `query`, `search_text`, `search_vector`, `rebuild(sources)`. 엔진은 어댑터 밖에서 백엔드 고유 기능에 의존하지 않습니다.

## provider

| provider | 만드는 것 | 계약 |
|---|---|---|
| vault 스캐너 | 문서 노드(모든 마크다운 — 색인 대상만 청크, 생성 미러는 표시), 선언된 엣지, 본문 `links` 엣지 | frontmatter + taxonomy |
| 결정 레코드 | 결정 노드, supersedes 엣지 | decision writer 출력 |
| 코드 그래프 — 자체 provider(`kb/providers/code_graph.py`) | 저장소마다 디렉터리·파일·타입 심볼 코드 노드(git 추적 파일만, Kotlin·Java·TS/JS·Python), `member_of`(extracted)·`imports`(extracted, 와일드카드·패키지는 inferred 로 디렉터리에)·`tests`(inferred) 엣지. vault 의 covers 대상(`code:<p>:paths:<dir>/`, `code:<p>:symbols:<Name>`)을 해석한다 | strata DEC-2026-10-28-05. `python3 -m kb code deps·impact·tests-for·symbol·owner-gate`; flow(request) 는 외부 어댑터 몫(선택) |
| 오케스트레이터 스트림(Quilt) | 세션 노드 사이의 릴레이·승인 엣지 | rec.decision.orchestrator-decisions-flow-to-records |
| 임베더(로컬 또는 opt-in 클라우드) | 청크 벡터 | 로케일을 알고, 엔진 동작에 필수는 아님 |

## 저장소를 읽는 게이트

- coverage gate: 바뀐 코드 노드 → covers 엣지 → 소유 문서. 소유자도 doc_change 선언도 없는 바뀐 노드가 새 위반입니다(rec.kb.covers-owner).
- 링크 게이트: 본문의 위키링크·마크다운 링크는 `links` 엣지입니다(source_ref 에 해석 결과 file · id · alias · none · md 를 적습니다). 깨진 링크, id·별칭으로만 해석되는 링크, 지식 문서가 대체된 문서를 가리키는 것이 기준선 밖의 위반입니다(rec.kb.link-currency). 기준선의 정본은 `.kb/link-baseline.json` 이고 store 의 baselines 는 미러입니다. 비마크다운 대상과 `--code-root` 대조는 파일시스템·git 으로 확인합니다(DEC-2026-10-28-07).
- 최신성: covers 가 맡은 코드의 revision 이 문서의 updated 보다 새로운 문서 노드.
- 검색: heading·text·title·tags 위의 FTS 하나(bm25). 임베더 provider(BAAI/bge-m3, 로컬)의 밀집 벡터는 `embeddings(model, text_hash, dim, vector)` 캐시에 두고 청크에 붙이며, 코사인은 브루트포스(이 규모에 ANN 불필요), 하이브리드는 둘의 RRF 융합. `python3 -m kb search-eval` 이 vault 의 질의 세트로 recall@k 를 잰다(DEC-2026-10-28-09).
- 수렴: 같은 주제의 바라는 명세 노드와 as-built 문서 노드의 대조(rec.spec.desired-vs-as-built).

## strata/scripts 에서의 이관

엔진은 셔틀 방식(이 저장소의 DEC-2026-10-28-01)으로 `strata-kit/kb/` 에 들어왔습니다. `strata/scripts/<name>.py` 는 각각 `strata-kit/kb` 를 부르는 얇은 호출이고, 훅은 그대로 동작하며, 모든 호출자가 kit 을 가리키면 셔틀을 지웁니다.

첫 이정표였던 동등성은 통과했고, 그 다음 이정표로 legacy FTS 색인(`.kb/kb.sqlite`)을 지웠습니다(DEC-2026-10-28-13). 지금 vault 에는 store 하나만 있습니다.

- `python3 -m kb build-index` 가 세션 종료 채널의 빌드입니다. store 를 전체 재생성한 뒤 노드 페이지(`kb.views.node_pages`)·Obsidian sortspec·리뷰 Inbox(`.kb/review-candidates.json`, `_index/review-needed.md`)·`manifest.json`·taxonomy 검증 경고(block 위반이면 exit 2)를 store 에서 냅니다. `--project` 는 보고 범위만 좁히고 store 는 항상 전체입니다.
- 문서 규칙(발견·frontmatter·청크·taxonomy 병합·검증)은 `kb/docrules.py` 한 곳입니다. 스캐너가 문서 노드 payload 에 `discovered`(발견 집합)와 `diagnostics`(검증 결과)를 실어 빌드가 색인 없이 경고를 냅니다.
- 신선도는 `engine.ensure_fresh_store`(원천 mtime 비교)가 맡습니다. 예전 `kb_freshness.py` 와 manifest 해시 증분은 없습니다.
- 증거: 2026-10-28 에 원본 빌더(strata@b4b0c86)와 `kb build-index` 가 실제 vault 사본 두 개에서 같은 노드 페이지·sortspec·리뷰 Inbox·manifest files·검증 경고 줄·exit code 를 냈습니다(문서 760·노드 페이지 66). legacy 색인을 지운 뒤 비교 스크립트도 지웠습니다(오더 2026.10.29-11).
