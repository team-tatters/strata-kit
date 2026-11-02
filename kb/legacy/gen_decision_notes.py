#!/usr/bin/env python3
"""gen_decision_notes.py — decision 레코드 → vault DEC 노트 생성 (Index 계층; strata-kit/kb/legacy, strata/scripts/gen-decision-notes.py 는 셔틀).

정본 규칙: DEC-2026-08-19-03 (ID 노트화 — 백링크·unlinked mentions로 역추적)
  - 입력: Tier P의 decisions/DEC-*.yaml 레코드 (strata_paths resolver 경유)
  - 출력: $STRATA_VAULT/projects/{name}/decisions/DEC-{date}-{NN}.md
          파일명 = DEC id → [[DEC-YYYY-MM-DD-NN]] 위키링크가 그대로 해석된다.
  - 전량 생성·멱등 — 수동 편집 구간 없음 (재생성 시 덮어쓰고, 레코드가 사라진 노트는 제거)
  - --index: 에이전트용 정적 인덱스(_generated-index.md)도 함께 생성

생성 시점 (DEC-2026-08-21-01 배선):
  - decision writer CLI(decision.py) 의 add / regen-index / migrate 가 레코드·인덱스를 쓴 직후
    같은 실행 안에서 이 스크립트를 호출한다 — 별도 실행은 백필·복구용.
  - 이 스크립트는 vault 파일만 쓴다. 커밋은 세션 종료 채널(vault-git.sh) 또는 decision.py --sync.

legacy 레코드 허용: migrate 로 분해된 구 단일 decisions.yaml 항목은 title/context/consequences/ref
  스키마를 가진다 — topic 은 title 로 대체하고, 존재하는 절만 렌더링한다.

사용: gen-decision-notes.py [--project-dir DIR] [--project-name NAME] [--index]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # strata-kit root — script mode (shuttle) and module mode alike
from kb.legacy.strata_paths import main_worktree, resolve_project_name, resolve_tier_p  # noqa: E402
from kb.decisions import derive_status  # noqa: E402  대체 상태 유도 — 정본 한 곳 (DEC-2026-09-30-03)

try:
    import yaml
except ImportError:
    print("오류: PyYAML 필요", file=sys.stderr)
    sys.exit(2)

VAULT = Path(os.path.expanduser(os.environ["STRATA_VAULT"])) if os.environ.get("STRATA_VAULT") else None   # no silent default (MB-048)
HEADER = "> GENERATED — 편집 금지. 정본: `{record}` / 재생성: `scripts/gen-decision-notes.py`\n"
# vault taxonomy lifecycle (decision 타입은 이 집합만 허용 — build-kb-index 검증)
LIFECYCLE = {"draft", "active", "review-needed", "superseded", "archived"}
LEGACY_STATUS = {"accepted": "active", "proposed": "draft", "deprecated": "archived", "rejected": "archived"}


def load_records(decisions_dir: Path):
    for f in sorted(decisions_dir.glob("DEC-*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        body = data.get("decision")
        if isinstance(body, dict) and body.get("id"):
            yield f, body


def topic_of(body: dict) -> str:
    return str(body.get("topic") or body.get("title") or "").strip()


def status_of(body: dict) -> tuple[str, str | None]:
    """(lifecycle status, legacy 원문) — 허용 집합 밖 값은 매핑하고 원문을 보존한다."""
    raw = str(body.get("status") or "active").strip()
    if raw in LIFECYCLE:
        return raw, None
    return LEGACY_STATUS.get(raw, "active"), raw


def _section(title: str, value) -> str:
    text = str(value).strip() if value is not None else ""
    return f"## {title}\n\n{text}\n\n" if text else ""


def note_text(record_file: Path, body: dict, project: str, derived: tuple[str, list[str]] | None = None) -> str:
    rec_id = body["id"]
    status, legacy = status_of(body)
    superseded_by: list[str] = []
    if derived:
        d_status, superseded_by = derived
        if d_status == "superseded":
            status, legacy = "superseded", None
        elif d_status == "withdrawn":
            status, legacy = "archived", "withdrawn"
    fm = {
        "title": f"{rec_id} — {topic_of(body)}",
        "id": f"dec-{project}-{rec_id.lower().removeprefix('dec-')}",
        "type": "decision",
        "project": project,
        "status": status,
        "created": str(body.get("date", "")),
        "aliases": [rec_id],
        "source_record": record_file.name,
    }
    if legacy:
        fm["legacy_status"] = legacy
    # 주제 노드·결정 사슬 — 레코드의 nodes/supersedes 를 노트 frontmatter 로 그대로 투영 (노드 페이지 생성기가 읽음)
    if body.get("nodes"):
        fm["nodes"] = [str(n) for n in body["nodes"]]
    if body.get("supersedes"):
        fm["supersedes"] = [f"[[{str(s)}]]" for s in body["supersedes"]]
    if superseded_by:
        fm["superseded_by"] = [f"[[{x}]]" for x in superseded_by]
    lines = ["---\n", yaml.safe_dump(fm, allow_unicode=True, sort_keys=False), "---\n\n",
             f"# {rec_id}\n\n",
             HEADER.format(record=record_file.name), "\n",
             f"**Topic** — {topic_of(body)}\n\n"]
    if superseded_by:
        lines.append("> **대체됨** — 현행 결정: " + ", ".join(f"[[{x}]]" for x in superseded_by) + "\n\n")
    elif legacy == "withdrawn":
        lines.append("> **철회됨** — 대체 결정 없음. 사유: " + str(body.get("withdrawn_reason", "")).strip() + "\n\n")
    if body.get("session"):
        # 세션 ledger 가 실제로 있을 때만 링크로 — 없는 이름을 링크로 만들면 깨진 링크가 생성된다 (DEC-2026-09-30-03)
        sess = str(body["session"]).strip()
        exists = (VAULT / "projects" / project / "sessions" / f"{sess}.md").is_file()
        lines.append(f"**Session** — [[{sess}]]\n\n" if exists else f"**Session** — `{sess}`\n\n")
    if body.get("summary"):
        lines.append(f"**Summary** — {str(body['summary']).strip()}\n\n")
    lines.append(_section("Context", body.get("context")))
    lines.append(_section("Decision", body.get("decision")))
    lines.append(_section("Reason", body.get("reason")))
    # 회고 재료 (DEC-2026-10-30-03)
    for title, key in (("Alternatives", "alternatives"), ("Background", "background")):
        if body.get(key):
            lines.append(f"## {title}\n\n")
            lines.extend(f"- {str(x).strip()}\n" for x in body[key])
            lines.append("\n")
    lines.append(_section("Consequences", body.get("consequences")))
    if body.get("affects"):
        lines.append("## Affects\n\n")
        lines.extend(f"- {a}\n" for a in body["affects"])
        lines.append("\n")
    if body.get("supersedes"):
        lines.append("## Supersedes\n\n")
        lines.extend(f"- [[{s}]]\n" for s in body["supersedes"])
        lines.append("\n")
    if body.get("ref"):
        lines.append(f"**Ref** — `{str(body['ref']).strip()}`\n\n")
    if body.get("verification_tier"):
        lines.append(f"---\nverification_tier: `{body['verification_tier']}`\n")
    return "".join(lines).rstrip() + "\n"


def main():
    p = argparse.ArgumentParser(description="decision 레코드 → vault DEC 노트")
    p.add_argument("--project-dir", default=None)
    p.add_argument("--project-name", default=None, help="vault projects/{name} (기본: resolve_project_name — profile.yaml project, worktree 면 메인 프로젝트)")
    p.add_argument("--index", action="store_true", help="에이전트용 정적 인덱스도 생성")
    args = p.parse_args()

    if VAULT is None:
        print("오류: STRATA_VAULT 가 설정되지 않음 — DEC 노트 미러는 vault 에 쓴다(레코드는 그대로 남음)", file=sys.stderr)
        sys.exit(2)
    tier = resolve_tier_p(args.project_dir)
    if tier is None:
        print("오류: Strata 미적용 프로젝트", file=sys.stderr)
        sys.exit(1)
    base = Path(args.project_dir or os.getcwd()).resolve()
    project = args.project_name or resolve_project_name(base)
    # worktree 의 레코드는 브랜치 시점의 부분집합일 수 있다 — 메인에만 있는 노트를 지우지 않는다
    in_worktree = main_worktree(base) is not None
    out_dir = VAULT / "projects" / project / "decisions"
    out_dir.mkdir(parents=True, exist_ok=True)

    records = list(load_records(tier.decisions_dir)) if tier.decisions_dir.is_dir() else []
    derived = derive_status(records)
    known = {str(b["id"]) for _, b in records}
    for _, body in records:
        for old in body.get("supersedes") or []:
            if str(old) not in known:
                print(f"경고: {body['id']} 가 대체한다는 {old} 의 레코드가 없음", file=sys.stderr)
    generated = set()
    for f, body in records:
        note = out_dir / f"{body['id']}.md"
        note.write_text(note_text(f, body, project, derived.get(str(body["id"]))), encoding="utf-8")
        generated.add(note.name)
    # 생성 전용 디렉토리 — 레코드가 사라진(재채번·삭제) 노트는 제거해 미러를 정본과 일치시킨다
    removed = []
    for stale in ([] if in_worktree else out_dir.glob("DEC-*.md")):
        if stale.name not in generated:
            stale.unlink()
            removed.append(stale.name)
    msg = f"DEC 노트 {len(generated)}건 생성 → {out_dir}" + (" (worktree: 정본 없는 노트 제거 생략)" if in_worktree else "")
    if removed:
        msg += f" (정본 없는 노트 {len(removed)}건 제거: {', '.join(sorted(removed))})"
    print(msg)

    if args.index:
        idx = out_dir / "_generated-index.md"
        lines = ["---\ntitle: \"Decision Index (generated)\"\ntype: moc\n"
                 f"project: {project}\n---\n\n# Decisions — {project}\n\n",
                 HEADER.format(record=str(tier.decisions_dir)), "\n",
                 "| id | date | 상태 | topic |\n|---|---|---|---|\n"]
        label = {"active": "현행", "superseded": "대체됨", "withdrawn": "철회"}
        for _, body in records:
            st, by = derived[str(body["id"])]
            cell = label[st] + (" → " + ", ".join(f"[[{x}]]" for x in by) if by else "")
            lines.append(f"| [[{body['id']}]] | {body.get('date', '')} | {cell} | {topic_of(body)} |\n")
        if not records:
            lines.append("| (레코드 없음) | | | |\n")
        idx.write_text("".join(lines), encoding="utf-8")
        print(f"정적 인덱스 생성 → {idx}")


if __name__ == "__main__":
    main()
