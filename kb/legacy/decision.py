#!/usr/bin/env python3
"""decision — Strata decision 레코드 CLI (python -m kb decision; strata/scripts/decision.py 에서 이관 (strata-kit 오더 2026.10.29-01 task-03). strata 쪽 같은 이름은 셔틀.) (record-per-file + 생성형 인덱스 + DEC 노트 미러).

정본 규칙: DEC-2026-08-19-05
  - 정본: {tier_p}/decisions/DEC-{date}-{NN}[-{slug}].yaml (1결정 = 1파일)
  - {tier_p}/decisions.yaml 은 레코드에서 재생성되는 T0 인덱스 — 손편집 금지
  - 채번(NN)·인덱스 재생성은 이 CLI만 수행 (flock 직렬화 — 동시 다중 세션 안전)
  - Tier P 위치는 placement profile을 따름 (strata_paths.resolve_tier_p)

DEC 노트 미러 (DEC-2026-08-19-03, 배선: DEC-2026-08-21-01):
  - add / regen-index / migrate 가 레코드·인덱스를 쓴 **직후 같은 실행 안에서**
    DEC projection generator(gen-decision-notes.py --index)를 호출해
    $STRATA_VAULT/projects/{name}/decisions/ 를 전량 재생성한다 (멱등, 실패는 경고만).
  - vault commit+push 는 세션 종료 채널(handoff / ledger close → vault-git.sh)에 맡긴다.
    즉시 반영이 필요하면 --sync (vault-git.sh commit-push 를 바로 실행).
  - embedded 프로젝트의 레코드는 프로젝트 repo 커밋이 별도로 필요하다 —
    check-uncommitted 가 미커밋 레코드를 경고한다 (handoff 게이트에서 호출).

사용:
  decision.py add --slug api-versioning --topic "..." --decision "..." --reason "..." \
      [--affects X --affects Y] [--session S] [--tier solo] [--summary "..."] \
      [--alternative "대안: 진 이유" ...] [--background "참고한 개념·자료" ...] \
      [--project-dir DIR] [--no-notes] [--sync]
  decision.py regen-index [--repair] [--project-dir DIR] [--no-notes] [--sync]
  decision.py list [--since YYYY-MM-DD] [--grep PATTERN] [--project-dir DIR]
  decision.py migrate [--input FILE] [--project-dir DIR] [--no-notes] [--sync]
  decision.py check-uncommitted [--project-dir DIR] [--strict]
  decision.py supersede --id NEW --target OLD [--project-dir DIR]   # 기존 레코드에 대체 관계 추가
  decision.py withdraw --id X --reason "..." [--project-dir DIR]    # 대체 없이 철회

대체·철회 상태 (DEC-2026-09-30-03):
  - 대체 상태는 저장하지 않고 **유도**한다 — 어떤 레코드의 supersedes 에 등장한 레코드는 superseded.
    대체된 쪽 파일을 고치지 않으므로 두 파일이 어긋날 일이 없다.
  - 철회는 대체할 결정이 없는 경우에만 레코드에 status: withdrawn 과 사유를 적는다.
  - 인덱스·DEC 노트는 유도된 status 와 superseded_by 를 함께 싣는다.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import fcntl
import os
import re
import subprocess
import sys
from pathlib import Path

from kb.legacy.strata_paths import resolve_project_name, resolve_tier_p  # noqa: E402
from kb.legacy._kit import KIT, RULES, VAULT_GIT, kb_argv, kb_env  # noqa: E402,F401

NOTES_GENERATOR = KIT / "kb" / "legacy" / "gen_decision_notes.py"

try:
    import yaml
except ImportError:
    print("오류: PyYAML 필요 (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

RECORD_RE = re.compile(r"^DEC-(\d{4}-\d{2}-\d{2})-(\d{2,})(?:-(.+))?\.yaml$")
INDEX_HEADER = (
    "# Decision Index — GENERATED (T0 로드용 컴팩트 인덱스)\n"
    "# 정본은 decisions/DEC-*.yaml 레코드 파일. 이 파일은 손편집 금지.\n"
    "# 재생성: scripts/decision.py regen-index\n"
    "---\n"
)


def _fail(msg: str) -> "NoReturn":  # noqa: F821
    print(f"오류: {msg}", file=sys.stderr)
    sys.exit(1)


def _tier_p(project_dir: str | None):
    tier = resolve_tier_p(project_dir)
    if tier is None:
        _fail("Strata 미적용 프로젝트 — .strata/decisions* 또는 vault-link.yaml 없음")
    tier.decisions_dir.mkdir(parents=True, exist_ok=True)
    return tier


class _Lock:
    """decisions/.lock 기반 flock — mint+write+regen을 하나의 임계구역으로."""

    def __init__(self, decisions_dir: Path):
        self._path = decisions_dir / ".lock"

    def __enter__(self):
        self._fh = open(self._path, "a+")
        fcntl.flock(self._fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self._fh, fcntl.LOCK_UN)
        self._fh.close()
        return False


def _load_records(decisions_dir: Path) -> list[tuple[Path, dict]]:
    records = []
    for f in sorted(decisions_dir.glob("DEC-*.yaml")):
        if not RECORD_RE.match(f.name):
            print(f"경고: 레코드 파일명 규격 불일치 — 건너뜀: {f.name}", file=sys.stderr)
            continue
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            _fail(f"레코드 파싱 실패 {f.name}: {e}")
        body = (data or {}).get("decision")
        if not isinstance(body, dict) or "id" not in body:
            _fail(f"레코드 스키마 불일치 (decision.id 필요): {f.name}")
        records.append((f, body))
    return records


def _yaml_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _block(s: str, indent: str) -> str:
    lines = [line.rstrip() for line in s.strip().splitlines()]
    return "|\n" + "\n".join(f"{indent}{line}" if line else "" for line in lines)


def _topic_of(body: dict) -> str:
    """topic — legacy 레코드(migrate로 분해된 구 decisions.yaml)는 title 을 쓴다."""
    return str(body.get("topic") or body.get("title") or "").strip()


def _summary_of(body: dict) -> str:
    if body.get("summary"):
        return str(body["summary"]).strip()
    decision_text = str(body.get("decision", "")).strip()
    first = decision_text.splitlines()[0].lstrip("-• ").strip() if decision_text else ""
    return (first or _topic_of(body))[:200]


def derive_status(records: list[tuple[Path, dict]]) -> dict[str, tuple[str, list[str]]]:
    """id → (status, superseded_by). status ∈ active | superseded | withdrawn.

    superseded 는 다른 레코드의 supersedes 로부터 유도한다 (대체된 쪽 파일은 고치지 않는다).
    withdrawn 은 레코드에 명시된 경우만. 둘 다 해당하면 superseded 가 우선한다. 철회된 레코드의 supersedes 는 세지 않는다.
    """
    by: dict[str, list[str]] = {}
    for _, body in records:
        if str(body.get("status") or "").strip() == "withdrawn":
            continue   # a withdrawn record retires nothing — what it named stays as it was
        for old in body.get("supersedes") or []:
            by.setdefault(str(old).strip(), []).append(str(body["id"]))
    out: dict[str, tuple[str, list[str]]] = {}
    for _, body in records:
        rid = str(body["id"])
        if rid in by:
            out[rid] = ("superseded", sorted(by[rid]))
        elif str(body.get("status") or "").strip() == "withdrawn":
            out[rid] = ("withdrawn", [])
        else:
            out[rid] = ("active", [])
    return out


def _write_index(tier, records: list[tuple[Path, dict]]) -> None:
    entries = sorted(records, key=lambda r: r[1]["id"])
    derived = derive_status(records)
    out = [INDEX_HEADER, "decisions:\n"]
    for f, body in entries:
        out.append(f"  - id: {_yaml_quote(body['id'])}\n")
        out.append(f"    date: {_yaml_quote(str(body.get('date', '')))}\n")
        out.append(f"    topic: {_yaml_quote(_topic_of(body))}\n")
        out.append(f"    summary: {_yaml_quote(_summary_of(body))}\n")
        out.append(f"    record: {_yaml_quote('decisions/' + f.name)}\n")
        status, superseded_by = derived[str(body["id"])]
        if status != "active":
            out.append(f"    status: {_yaml_quote(status)}\n")
        if superseded_by:
            out.append(f"    superseded_by: [{', '.join(_yaml_quote(x) for x in superseded_by)}]\n")
        if f is not entries[-1][0]:
            out.append("\n")
    tier.decisions_index.write_text("".join(out), encoding="utf-8")


# ── DEC 노트 미러 · vault 동기화 · 미커밋 게이트 ─────────────────────────────

def _project_root(project_dir: str | None) -> Path:
    return Path(project_dir or os.getcwd()).resolve()


def _project_name(project_dir: str | None) -> str:
    """vault projects/{name} — gen-decision-notes.py 와 동일 규칙(strata_paths.resolve_project_name: worktree 면 메인 프로젝트)."""
    return resolve_project_name(_project_root(project_dir))


def project_notes(project_dir: str | None, *, index: bool = True) -> bool:
    """DEC projection generator 호출 — vault projects/{name}/decisions/ 전량 재생성.

    레코드·인덱스는 이미 기록된 뒤이므로 실패해도 호출자를 실패시키지 않는다 (경고만).
    생성물은 vault(Tier V)에 쓰이며 커밋은 세션 종료 채널 또는 --sync 가 담당한다.
    """
    if not NOTES_GENERATOR.is_file():
        print(f"경고: DEC 노트 생성기 없음 — {NOTES_GENERATOR}", file=sys.stderr)
        return False
    cmd = kb_argv("gen-decision-notes",
           "--project-dir", str(_project_root(project_dir)),
           "--project-name", _project_name(project_dir))
    if index:
        cmd.append("--index")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False, env=kb_env())
    except OSError as e:  # pragma: no cover — 인터프리터 실행 자체 실패
        print(f"경고: DEC 노트 생성 실패 (실행 오류): {e}", file=sys.stderr)
        return False
    if res.returncode != 0:
        detail = (res.stderr or res.stdout).strip()
        print(f"경고: DEC 노트 생성 실패 (exit {res.returncode}) — vault 미러가 갱신되지 않음. "
              f"수동: python -m kb gen-decision-notes --project-dir {_project_root(project_dir)} --index\n"
              f"  {detail}", file=sys.stderr)
        return False
    for line in res.stdout.strip().splitlines():
        print(f"DEC 노트: {line}")
    return True


def vault_sync(message: str, paths: list[str] | None = None) -> None:
    """즉시 반영용 — vault-git.sh commit-push MSG [PATH...] (항상 exit 0, 실패는 스크립트가 경고)."""
    if not VAULT_GIT.is_file():
        print(f"경고: vault-git.sh 없음 — {VAULT_GIT}", file=sys.stderr)
        return
    subprocess.run(["sh", str(VAULT_GIT), "commit-push", message, *(paths or [])], check=False)


def _after_write(args, message: str) -> None:
    """레코드/인덱스 기록 직후 공통 후처리: DEC 노트 재생성 (+ --sync 시 vault commit+push)."""
    if getattr(args, "no_notes", False):
        print("DEC 노트: 생략 (--no-notes) — 수동: gen-decision-notes.py --index")
        return
    ok = project_notes(args.project_dir)
    if getattr(args, "sync", False):
        if ok:
            _pname = _project_name(getattr(args, "project_dir", None))
            vault_sync(message, [f"projects/{_pname}/decisions"])
        else:
            print("경고: 노트 생성 실패로 --sync 생략", file=sys.stderr)


def uncommitted_records(project_dir: str | None = None) -> list[str] | None:
    """Tier P 레코드/인덱스 중 git 미커밋 경로 목록.

    - embedded: 프로젝트 repo 기준 (`git status --porcelain -- decisions/ decisions.yaml`).
      세션 종료 채널은 vault만 커밋하므로, 여기 남은 레코드는 push 전까지 다른 머신에서 보이지 않는다.
    - detached: 레코드가 vault 에 있으므로 vault-git.sh commit-push 가 처리 — 검사 대상 아님(None).
    - Strata 미적용 / git repo 아님 → None.
    반환: 미커밋 경로 리스트(빈 리스트 = clean). None = 검사 불가/불필요.
    """
    try:
        tier = resolve_tier_p(project_dir)
    except ValueError as e:
        print(f"경고: Tier P 해석 실패 — {e}", file=sys.stderr)
        return None
    if tier is None or tier.profile != "embedded":
        return None
    repo = _project_root(project_dir)
    targets = [p for p in (tier.decisions_dir, tier.decisions_index) if p.exists()]
    if not targets:
        return []
    try:
        res = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all", "--"]
            + [str(p) for p in targets],
            capture_output=True, text=True, check=False)
    except OSError:
        return None
    if res.returncode != 0:  # git repo 아님 등
        return None
    out = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if path.endswith("/.lock") or path.endswith(".lock"):
            continue
        out.append(f"{line[:2].strip() or '??'} {path}")
    return out


def warn_uncommitted(project_dir: str | None = None, *, label: str = "") -> int:
    """미커밋 레코드가 있으면 stderr 경고. 반환: 건수 (None 상황은 0)."""
    items = uncommitted_records(project_dir)
    if not items:
        return 0
    where = label or str(_project_root(project_dir))
    print(f"경고: {where} — repo .strata/decisions* 에 미커밋 레코드/인덱스 {len(items)}건. "
          "세션 종료 채널은 vault만 커밋하므로 프로젝트 repo 커밋 전까지 다른 머신에서 정본을 읽을 수 없다 "
          "(DEC 노트 미러는 vault로 전달되지만 정본은 아님):", file=sys.stderr)
    for it in items:
        print(f"  {it}", file=sys.stderr)
    return len(items)


def _check_duplicates(records, repair: bool, tier) -> list[tuple[Path, dict]]:
    by_id: dict[str, list] = {}
    for item in records:
        by_id.setdefault(item[1]["id"], []).append(item)
    dups = {k: v for k, v in by_id.items() if len(v) > 1}
    if not dups:
        return records
    if not repair:
        for rid, items in dups.items():
            files = ", ".join(i[0].name for i in items)
            print(f"경고: 중복 id {rid} — {files} (regen-index --repair 로 복구)", file=sys.stderr)
        return records
    # repair: mtime이 이른 쪽이 id 유지, 나중 파일은 해당 날짜의 다음 빈 NN으로 재채번
    for rid, items in dups.items():
        items.sort(key=lambda i: i[0].stat().st_mtime)
        for f, body in items[1:]:
            m = RECORD_RE.match(f.name)
            date, slug = m.group(1), m.group(3)
            nn = _next_nn(f.parent, date, exclude=f)
            new_id = f"DEC-{date}-{nn:02d}"
            new_name = f"{new_id}-{slug}.yaml" if slug else f"{new_id}.yaml"
            text = f.read_text(encoding="utf-8").replace(body["id"], new_id, 1)
            new_path = f.parent / new_name
            new_path.write_text(text, encoding="utf-8")
            f.unlink()
            print(f"복구: {f.name} → {new_name} (id {rid} → {new_id})")
    return _load_records(tier.decisions_dir)


def _next_nn(decisions_dir: Path, date: str, exclude: Path | None = None) -> int:
    used = set()
    for f in decisions_dir.glob(f"DEC-{date}-*.yaml"):
        if exclude is not None and f == exclude:
            continue
        m = RECORD_RE.match(f.name)
        if m:
            used.add(int(m.group(2)))
    nn = 1
    while nn in used:
        nn += 1
    return nn


def cmd_add(args) -> None:
    tier = _tier_p(args.project_dir)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.slug):
        _fail("--slug 은 kebab-case ASCII (예: api-versioning)")
    date = args.date or _dt.date.today().isoformat()
    with _Lock(tier.decisions_dir):
        nn = _next_nn(tier.decisions_dir, date)
        rec_id = f"DEC-{date}-{nn:02d}"
        path = tier.decisions_dir / f"{rec_id}-{args.slug}.yaml"
        lines = [
            "# Decision Record — 정본 (1 결정 = 1 파일)\n",
            "decision:\n",
            f"  id: {_yaml_quote(rec_id)}\n",
            f"  date: {_yaml_quote(date)}\n",
        ]
        if args.session:
            lines.append(f"  session: {_yaml_quote(args.session)}\n")
        lines.append(f"  topic: {_yaml_quote(args.topic)}\n")
        if args.summary:
            lines.append(f"  summary: {_yaml_quote(args.summary)}\n")
        lines.append(f"  decision: {_block(args.decision, '    ')}\n")
        lines.append(f"  reason: {_block(args.reason, '    ')}\n")
        # 회고 재료 (DEC-2026-10-30-03) — 검토한 대안과 진 이유, 참고한 개념·자료
        alternatives = [a.strip() for a in (args.alternative or []) if a.strip()]
        if alternatives:
            lines.append("  alternatives:\n")
            lines.extend(f"    - {_yaml_quote(a)}\n" for a in alternatives)
        background = [b.strip() for b in (args.background or []) if b.strip()]
        if background:
            lines.append("  background:\n")
            lines.extend(f"    - {_yaml_quote(b)}\n" for b in background)
        lines.append(f"  verification_tier: {_yaml_quote(args.tier)}\n")
        if args.affects:
            lines.append("  affects:\n")
            lines.extend(f"    - {_yaml_quote(a)}\n" for a in args.affects)
        # 주제 노드·결정 사슬 (DEC-2026-09-08-01) — 노드 페이지의 "결정" 면이 이 두 필드로 조인된다
        nodes = [n.strip() for v in (args.nodes or []) for n in str(v).split(",") if n.strip()]
        if nodes:
            lines.append("  nodes:\n")
            lines.extend(f"    - {_yaml_quote(n)}\n" for n in nodes)
        supersedes = [s.strip() for v in (args.supersedes or []) for s in str(v).split(",") if s.strip()]
        if supersedes:
            lines.append("  supersedes:\n")
            lines.extend(f"    - {_yaml_quote(s)}\n" for s in supersedes)
        path.write_text("".join(lines), encoding="utf-8")
        _write_index(tier, _load_records(tier.decisions_dir))
    print(f"{rec_id} 기록: {path}")
    if not alternatives:
        print("⚠ 검토한 대안이 없음 — 있었다면 --alternative '대안: 진 이유' 로 남기세요 (DEC-2026-10-30-03)",
              file=sys.stderr)
    print(f"인덱스 재생성: {tier.decisions_index}")
    _after_write(args, f"decision {_project_name(args.project_dir)} {rec_id}: {args.topic}")


def _record_path(tier, rec_id: str) -> Path:
    hits = [f for f in tier.decisions_dir.glob("DEC-*.yaml")
            if RECORD_RE.match(f.name) and (f.name == f"{rec_id}.yaml" or f.name.startswith(f"{rec_id}-"))]
    if len(hits) != 1:
        _fail(f"레코드를 하나로 특정할 수 없음: {rec_id} ({len(hits)}건)")
    return hits[0]


def _safe_rewrite(path: Path, text: str, check) -> None:
    """레코드 텍스트를 바꾸기 전에 결과를 파싱해 확인한다 — 실패하면 쓰지 않는다 (정본 손상 방지)."""
    try:
        body = (yaml.safe_load(text) or {}).get("decision")
    except yaml.YAMLError as e:
        _fail(f"수정 결과가 YAML 로 파싱되지 않아 쓰지 않음 ({path.name}): {e}")
    if not isinstance(body, dict) or not check(body):
        _fail(f"수정 결과 검증 실패 — 쓰지 않음 ({path.name}). 레코드를 직접 확인하세요.")
    path.write_text(text, encoding="utf-8")


def _drop_key(text: str, key: str) -> str:
    """decision 매핑의 최상위 키 하나(블록 목록·흐름 목록·블록 스칼라·빈 줄 포함)를 지운다."""
    lines = text.splitlines(keepends=True)
    out, i = [], 0
    while i < len(lines):
        if re.match(rf"^  {re.escape(key)}:", lines[i]):
            i += 1
            # 값의 연속 줄: 더 깊은 들여쓰기, 같은 깊이의 목록 항목("  - "), 빈 줄
            while i < len(lines) and (lines[i].startswith("   ") or lines[i].startswith("  - ")
                                      or lines[i].strip() == ""):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "".join(out)


def cmd_supersede(args) -> None:
    """기존 레코드(NEW)의 supersedes 에 OLD 를 추가한다. OLD 파일은 고치지 않는다 (상태는 유도)."""
    tier = _tier_p(args.project_dir)
    with _Lock(tier.decisions_dir):
        records = _load_records(tier.decisions_dir)
        ids = {str(b["id"]) for _, b in records}
        for rid in (args.id, args.target):
            if rid not in ids:
                _fail(f"없는 결정: {rid}")
        if args.id == args.target:
            _fail("자기 자신을 대체할 수 없음")
        path = _record_path(tier, args.id)
        body = next(b for f, b in records if f == path)
        current = [str(x) for x in (body.get("supersedes") or [])]
        if args.target in current:
            print(f"이미 기록됨: {args.id} → {args.target}")
            return
        # 순환 방지: target 이 (직간접으로) id 를 대체하고 있으면 거부
        graph = {str(b["id"]): [str(x) for x in (b.get("supersedes") or [])] for _, b in records}
        stack, seen = [args.target], set()
        while stack:
            cur = stack.pop()
            if cur == args.id:
                _fail(f"대체 순환: {args.target} 가 이미 {args.id} 를 대체함")
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(graph.get(cur, []))
        wanted = current + [args.target]
        text = _drop_key(path.read_text(encoding="utf-8"), "supersedes").rstrip("\n")
        text += "\n  supersedes:\n" + "".join(f"    - {_yaml_quote(x)}\n" for x in wanted)
        _safe_rewrite(path, text, lambda b: [str(x) for x in (b.get("supersedes") or [])] == wanted
                      and str(b.get("id")) == args.id)
        _write_index(tier, _load_records(tier.decisions_dir))
    print(f"{args.id} 가 {args.target} 를 대체 — {args.target} 는 superseded 로 유도됨")
    _after_write(args, f"decision {_project_name(args.project_dir)} {args.id} supersedes {args.target}")


def cmd_withdraw(args) -> None:
    """대체할 결정 없이 철회 — 레코드에 status: withdrawn 과 사유를 적는다."""
    tier = _tier_p(args.project_dir)
    with _Lock(tier.decisions_dir):
        path = _record_path(tier, args.id)
        text = path.read_text(encoding="utf-8")
        text = _drop_key(_drop_key(text, "status"), "withdrawn_reason").rstrip("\n")
        text += f'\n  status: "withdrawn"\n  withdrawn_reason: {_block(args.reason, "    ")}\n'
        _safe_rewrite(path, text, lambda b: b.get("status") == "withdrawn"
                      and str(b.get("withdrawn_reason", "")).strip() == args.reason.strip()
                      and str(b.get("id")) == args.id)
        _write_index(tier, _load_records(tier.decisions_dir))
    print(f"{args.id} 철회 기록: {path}")
    _after_write(args, f"decision {_project_name(args.project_dir)} {args.id} withdrawn")


def cmd_regen(args) -> None:
    tier = _tier_p(args.project_dir)
    with _Lock(tier.decisions_dir):
        records = _load_records(tier.decisions_dir)
        records = _check_duplicates(records, args.repair, tier)
        _write_index(tier, records)
    print(f"인덱스 재생성 완료: {len(records)}건 → {tier.decisions_index}")
    _after_write(args, f"decision {_project_name(args.project_dir)} regen-index: {len(records)}건")


def cmd_check_uncommitted(args) -> None:
    tier = resolve_tier_p(args.project_dir)
    if tier is None:
        _fail("Strata 미적용 프로젝트 — .strata/decisions* 또는 vault-link.yaml 없음")
    if tier.profile != "embedded":
        print(f"detached profile — 레코드가 vault({tier.root})에 있으므로 세션 종료 채널(vault-git.sh)이 커밋한다. 검사 대상 아님.")
        return
    items = uncommitted_records(args.project_dir)
    if items is None:
        print("검사 불가 — 프로젝트가 git repo 가 아니거나 git 실행 실패 (경고 없이 통과).")
        return
    if not items:
        print(f"clean — {tier.decisions_dir} 미커밋 레코드 없음")
        return
    n = warn_uncommitted(args.project_dir, label=_project_name(args.project_dir))
    if args.strict:
        sys.exit(3)
    print(f"(경고 {n}건 — 차단 아님. 커밋: git add {tier.decisions_dir} {tier.decisions_index})")


def cmd_list(args) -> None:
    tier = _tier_p(args.project_dir)
    records = _load_records(tier.decisions_dir)
    derived = derive_status(records)
    for _, body in records:
        if args.since and str(body.get("date", "")) < args.since:
            continue
        status, by = derived[str(body["id"])]
        mark = "" if status == "active" else f"  [{status}{' → ' + ','.join(by) if by else ''}]"
        line = f"{body['id']}  {body.get('topic', '')}{mark}"
        if args.grep and not re.search(args.grep, line + str(body.get("decision", ""))):
            continue
        print(line)


def cmd_migrate(args) -> None:
    tier = _tier_p(args.project_dir)
    src = Path(args.input) if args.input else tier.decisions_index
    if not src.is_file():
        _fail(f"입력 파일 없음: {src}")
    data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    entries = data.get("decisions") or []
    if not entries:
        _fail(f"decisions 리스트가 비어 있음: {src}")
    if all("record" in e for e in entries):
        _fail("이미 생성형 인덱스 형식 — 마이그레이션 불필요")
    with _Lock(tier.decisions_dir):
        created = 0
        for e in entries:
            rec_id = e.get("id")
            if not rec_id:
                print(f"경고: id 없는 항목 건너뜀: {e.get('topic')}", file=sys.stderr)
                continue
            path = tier.decisions_dir / f"{rec_id}.yaml"
            if path.exists() or list(tier.decisions_dir.glob(f"{rec_id}-*.yaml")):
                print(f"존재함, 건너뜀: {rec_id}")
                continue
            payload = yaml.safe_dump(
                {"decision": e}, allow_unicode=True, sort_keys=False, default_flow_style=False
            )
            path.write_text("# Decision Record — 정본 (legacy migrate)\n" + payload, encoding="utf-8")
            created += 1
        if src == tier.decisions_index:
            src.rename(src.with_suffix(".yaml.bak"))
        _write_index(tier, _load_records(tier.decisions_dir))
    print(f"마이그레이션 완료: 레코드 {created}건 생성, 인덱스 재생성 (원본 → {src.name}.bak)" if src != tier.decisions_index
          else f"마이그레이션 완료: 레코드 {created}건 생성, 원본은 decisions.yaml.bak")
    _after_write(args, f"decision {_project_name(args.project_dir)} migrate: 레코드 {created}건")


def main() -> None:
    p = argparse.ArgumentParser(description="Strata decision 레코드 CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--project-dir", default=None, help="프로젝트 루트 (기본: cwd)")

    def writer(sp):
        common(sp)
        sp.add_argument("--no-notes", action="store_true",
                        help="vault DEC 노트 재생성 생략 (기본: 기록 직후 gen-decision-notes.py --index 호출)")
        sp.add_argument("--sync", action="store_true",
                        help="vault 즉시 commit+push (기본: 세션 종료 채널 handoff/ledger close 에 위임)")

    sp = sub.add_parser("add", help="결정 레코드 추가 + 인덱스 재생성 + vault DEC 노트 재생성")
    writer(sp)
    sp.add_argument("--slug", required=True)
    sp.add_argument("--topic", required=True)
    sp.add_argument("--decision", required=True)
    sp.add_argument("--reason", required=True)
    sp.add_argument("--affects", action="append", default=[])
    sp.add_argument("--nodes", action="append", default=[],
                    help="주제 노드 id (toc.yaml) — 반복 또는 쉼표 구분. 노드 페이지 '결정' 면의 조인 키")
    sp.add_argument("--supersedes", action="append", default=[],
                    help="이 결정이 대체하는 이전 DEC id — 반복 또는 쉼표 구분 (대상의 superseded 상태는 자동 유도)")
    sp.add_argument("--session", default=None)
    sp.add_argument("--summary", default=None)
    sp.add_argument("--tier", default="solo", choices=["solo", "self_verified", "cross_verified"])
    sp.add_argument("--alternative", action="append", default=[],
                    help="검토한 대안과 진 이유, '대안: 이유' (반복)")
    sp.add_argument("--background", action="append", default=[],
                    help="참고한 개념·자료 (반복)")
    sp.add_argument("--date", default=None, help="기본: 오늘 (테스트용)")
    sp.set_defaults(func=cmd_add)

    sp = sub.add_parser("supersede", help="기존 레코드에 대체 관계 추가 (대체된 쪽은 superseded 로 유도)")
    writer(sp)
    sp.add_argument("--id", required=True, help="대체하는 (새) 결정")
    sp.add_argument("--target", required=True, help="대체되는 (이전) 결정")
    sp.set_defaults(func=cmd_supersede)

    sp = sub.add_parser("withdraw", help="대체 없이 철회 — status: withdrawn + 사유")
    writer(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--reason", required=True)
    sp.set_defaults(func=cmd_withdraw)

    sp = sub.add_parser("regen-index", help="레코드 → 인덱스·DEC 노트 재생성 (멱등)")
    writer(sp)
    sp.add_argument("--repair", action="store_true", help="중복 id 재채번 복구")
    sp.set_defaults(func=cmd_regen)

    sp = sub.add_parser("check-uncommitted",
                        help="embedded 프로젝트 repo 의 미커밋 레코드/인덱스 경고 (handoff 게이트)")
    common(sp)
    sp.add_argument("--strict", action="store_true", help="미커밋 레코드가 있으면 exit 3")
    sp.set_defaults(func=cmd_check_uncommitted)

    sp = sub.add_parser("list", help="인덱스 나열")
    common(sp)
    sp.add_argument("--since", default=None)
    sp.add_argument("--grep", default=None)
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("migrate", help="legacy 단일 decisions.yaml → 레코드 분해 (+ 인덱스·DEC 노트 재생성)")
    writer(sp)
    sp.add_argument("--input", default=None, help="기본: {tier_p}/decisions.yaml")
    sp.set_defaults(func=cmd_migrate)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
