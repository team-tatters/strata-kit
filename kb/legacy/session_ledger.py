#!/usr/bin/env python3
"""session_ledger — Shared Session Ledger CLI (python -m kb ledger; strata/scripts/session-ledger.py 에서 이관 (strata-kit 오더 2026.10.29-01 task-03). strata 쪽 같은 이름은 셔틀.) (단일 writer + flock).

core/docs/ko/methodology/agent-operations.md §5 Shared Session Ledger 의 기계 인터페이스.
현재 ledger 포맷을 source of truth 로 본다:

  ---
  <frontmatter yaml>          # session_id, project, status, actors, topic, created, next_session ...
  ---
  ... 자유 산문 ...
  ## [actor] <ISO8601 ts>
  <!-- seq=N — desc -->       # 선택 (advisory)
  ```yaml
  <엔트리 본문>
  ```
  ...
  ## next_session
  ```yaml
  next: "..."
  reason: |
    ...
  ```

4 동사:
  append   <ledger> --actor A [--tool T] [--desc D] (--body YAML | --body-file F | stdin)
  read     <ledger> [--last N] [--actor A]
  close    <ledger> --next NEXT [--reason R]
  validate <ledger>

단일 writer: append/close = flock(LOCK_EX), read/validate = flock(LOCK_SH).
배경: agent-operations §5.4(B3) — CLI 내부 flock 으로 동시 append 직렬화.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML 필요 — pip install pyyaml", file=sys.stderr)
    sys.exit(1)

HEADER_RE = re.compile(r'^## \[([^\]]+)\]\s+(.+?)\s*$', re.M)
NEXTSESS_RE = re.compile(r'^## next_session\s*$', re.M)
YAML_BLOCK_RE = re.compile(r'```yaml\n(.*?)\n```', re.S)
SEQ_RE = re.compile(r'seq=(\d+)')
FM_RE = re.compile(r'^---\n(.*?)\n---\n?(.*)$', re.S)
REQUIRED_FM = ["session_id", "project", "status", "actors", "topic", "created", "next_session"]
VALID_STATUS = {"open", "handoff", "closed"}
CORE_ROLES = {"user", "primary", "reviewer", "coordinator", "archivist"}  # agent-operations §5.2


def err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(2)


@contextmanager
def locked(path: Path, exclusive: bool):
    if not path.exists():
        err(f"ledger 없음: {path}")
    mode = "r+" if exclusive else "r"
    f = open(path, mode, encoding="utf-8")
    try:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield f
    finally:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


def split_doc(text: str):
    """(frontmatter dict, frontmatter raw, body) — frontmatter 없으면 ({}, None, text)."""
    m = FM_RE.match(text)
    if not m:
        return {}, None, text
    fm = yaml.safe_load(m.group(1)) or {}
    return fm, m.group(1), m.group(2)


def parse_entries(body: str):
    """'## [actor] ts' 엔트리 목록 (next_session 이전까지)."""
    out = []
    nexts = NEXTSESS_RE.search(body)
    limit = nexts.start() if nexts else len(body)
    heads = [h for h in HEADER_RE.finditer(body) if h.start() < limit]
    for i, h in enumerate(heads):
        stop = heads[i + 1].start() if i + 1 < len(heads) else limit
        seg = body[h.end():stop]
        ym = YAML_BLOCK_RE.search(seg)
        sm = SEQ_RE.search(seg[:ym.start()] if ym else seg)
        out.append({
            "actor": h.group(1),
            "ts": h.group(2),
            "seq": int(sm.group(1)) if sm else None,
            "yaml": ym.group(1) if ym else None,
            "raw": body[h.start():stop].rstrip(),
        })
    return out


def _project_dir_for(fm: dict, explicit: str | None):
    """ledger frontmatter project → 프로젝트 디렉토리 (미커밋 decision 레코드 게이트용)."""
    if explicit:
        return explicit
    name = fm.get("project")
    if not name:
        return None
    cands = [Path.cwd()]
    if os.environ.get("STRATA_PROJECTS"):
        cands.append(Path(os.environ["STRATA_PROJECTS"]) / name)
    if os.environ.get("STRATA_VAULT"):
        cands.append(Path(os.environ["STRATA_VAULT"]).expanduser().parent / name)  # vault 형제 체크아웃 (strata·strata-kit 등, projects/ 밖)
    for c in cands:
        if c.name == name and c.is_dir():
            return str(c)
    return None


def decision_gate(fm: dict, explicit_dir: str | None) -> int:
    """세션 종료 게이트 — embedded repo .strata/decisions* 미커밋 레코드 경고 (차단 아님).

    배경: 2026-08-21 한 프로젝트에서 DEC 2건이 빅뱅 커밋에서 누락된 채 발견됨.
    세션 종료 채널(vault commit+push)은 프로젝트 repo 를 건드리지 않으므로 여기서 드러내야 한다.
    반환: 미커밋 건수 (검사 불가 0).
    """
    try:
        from kb.legacy.decision import warn_uncommitted  # decision writer CLI 의 게이트 함수
    except Exception as e:  # pragma: no cover
        print(f"WARN: decision 레코드 게이트 생략 ({e})", file=sys.stderr)
        return 0
    pdir = _project_dir_for(fm, explicit_dir)
    if pdir is None:
        print("WARN: 미커밋 decision 레코드 검사 생략 — 프로젝트 디렉토리 미확인 "
              f"(project={fm.get('project')!r}; --project-dir 로 지정)", file=sys.stderr)
        return 0
    return warn_uncommitted(pdir, label=str(fm.get("project") or pdir))


def coverage_gate(fm: dict, explicit_dir: str | None, ledger_path: Path, quiet: bool = False) -> list:
    """세션 종료 커버리지 게이트 (agent-operations §5.7) — 경고 목록 반환, 차단 아님.

    변경 파일 → 소유 명세(covers) → 갱신 여부·doc_change 선언·nodes 대조. 구현: 커버리지 게이트 모듈.
    """
    try:
        from kb.gates.coverage import run_gate, format_report
    except Exception as e:  # pragma: no cover
        print(f"WARN: 커버리지 게이트 생략 ({e})", file=sys.stderr)
        return []
    pdir = _project_dir_for(fm, explicit_dir)
    if pdir is None:
        return ["커버리지 게이트 생략 — 프로젝트 디렉토리 미확인 (--project-dir 로 지정)"]
    try:
        res = run_gate(pdir, fm, None, str(fm.get("created") or "")[:10] or None)
    except Exception as e:  # noqa: BLE001
        return [f"커버리지 게이트 실패 — {e}"]
    if not quiet:
        print(format_report(res), file=sys.stderr)
    return list(res.get("warnings") or [])


def _regen_node_pages(fm: dict, explicit_dir: str | None) -> None:
    """close 뒤 노드 페이지 재생성 — 프로젝트 부분 색인(색인 빌더가 끝에 생성기를 호출). 실패해도 조용히."""
    name = fm.get("project")
    vault = os.environ.get("STRATA_VAULT")
    if not name or not vault:
        return
    import subprocess as _sp
    from kb.legacy._kit import kb_argv, kb_env
    try:
        _sp.run(kb_argv("build-index", "--project", str(name)), capture_output=True, text=True, timeout=120, env=kb_env())
    except (OSError, _sp.SubprocessError):
        pass


def read_body_arg(args) -> str:
    if args.body is not None:
        return args.body
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    err("본문이 없음 — --body, --body-file, 또는 stdin 중 하나 필요")


# ── commands ──────────────────────────────────────────────────────────

def cmd_append(args) -> int:
    body_text = read_body_arg(args).strip()
    try:
        parsed = yaml.safe_load(body_text)
    except yaml.YAMLError as e:
        err(f"본문이 유효한 YAML 이 아님: {e}")
    if not isinstance(parsed, dict) or not parsed:
        err("본문은 비어있지 않은 YAML 매핑(dict)이어야 함 (빈/스칼라 엔트리 거부)")
    if args.actor not in CORE_ROLES:
        err(f"actor '{args.actor}' 는 Core role 아님 — {sorted(CORE_ROLES)} 중 하나 (도구명은 --tool 으로)")
    if args.tool:
        body_text = f'tool: "{args.tool}"\n{body_text}'

    with locked(Path(args.ledger), exclusive=True) as f:
        text = f.read()
        fm, _, body = split_doc(text)
        if fm.get("status") == "closed":
            err("closed ledger 에는 append 불가 (lifecycle 위반)")
        ents = parse_entries(body)
        seq = max([e["seq"] for e in ents if e["seq"]] or [0]) + 1
        if fm.get("actors") and args.actor not in fm["actors"]:
            print(f"WARN: actor '{args.actor}' 가 frontmatter actors {fm['actors']} 에 없음",
                  file=sys.stderr)
        ts = datetime.now().astimezone().isoformat(timespec="seconds")
        desc = f" — {args.desc}" if args.desc else ""
        entry = (f"## [{args.actor}] {ts}\n"
                 f"<!-- seq={seq}{desc} -->\n"
                 f"```yaml\n{body_text}\n```\n")
        nm = NEXTSESS_RE.search(text)
        if nm:
            new_text = text[:nm.start()].rstrip() + "\n\n" + entry + "\n" + text[nm.start():]
        else:
            new_text = text.rstrip() + "\n\n" + entry
        f.seek(0)
        f.write(new_text)
        f.truncate()
    print(f"appended seq={seq} [{args.actor}] {ts}")
    return 0


def cmd_read(args) -> int:
    with locked(Path(args.ledger), exclusive=False) as f:
        text = f.read()
    _, _, body = split_doc(text)
    ents = parse_entries(body)
    if args.actor:
        ents = [e for e in ents if e["actor"] == args.actor]
    if args.last:
        ents = ents[-args.last:]
    if args.last or args.actor:
        for e in ents:
            print(e["raw"] + "\n")
    else:
        print(text)
    return 0


def link_gate(project: str | None = None) -> int:
    """이 세션 프로젝트의 링크만 본다 — 다른 프로젝트·병렬 세션의 새 위반이 내 세션 종료를 막지 않게."""
    import subprocess as _sp
    from kb.legacy._kit import kb_argv, kb_env
    cmd = kb_argv("link-check", *(["--project", project] if project else []))
    r = _sp.run(cmd, capture_output=True, text=True, env=kb_env())
    if r.returncode == 0:
        return 0
    print(r.stdout.rstrip(), file=sys.stderr)
    if r.returncode == 1 and os.environ.get("STRATA_LINK_CHECK") == "warn":
        print("WARN: 새 링크 위반 — STRATA_LINK_CHECK=warn 이라 동기화를 계속합니다", file=sys.stderr)
        return 0
    if r.returncode == 1:
        print("BLOCK: 기준선 밖 새 링크 위반 — 고친 뒤 close 를 다시 실행하세요 (vault 동기화 보류). "
              "규칙: strata-kit core/docs/ko/knowledge-base/linking-convention.md §7", file=sys.stderr)
    else:
        print(f"WARN: 링크 검사 실행 실패 (exit {r.returncode}) — 동기화는 계속합니다\n{r.stderr.strip()}", file=sys.stderr)
        return 0
    return 1


def cmd_close(args) -> int:
    with locked(Path(args.ledger), exclusive=True) as f:
        text = f.read()
        fm, fm_raw, _ = split_doc(text)
        if fm_raw is None:
            err("frontmatter 없는 ledger — close 불가")
        # frontmatter 의 status / next_session 라인만 교체 (주석·서식 보존)
        new_fm = fm_raw
        new_fm = re.sub(r'(?m)^status:.*$', 'status: "closed"', new_fm, count=1)
        next_line = f'next_session: "{args.next}"'
        if re.search(r'(?m)^next_session:.*$', new_fm):
            new_fm = re.sub(r'(?m)^next_session:.*$', next_line, new_fm, count=1)
        else:
            new_fm += f"\n{next_line}"
        text = re.sub(FM_RE, lambda m: f"---\n{new_fm}\n---\n{m.group(2)}", text, count=1)
        # ## next_session 블록 교체/추가
        reason = (args.reason or "").strip() or "none"
        block = (f"## next_session\n```yaml\n"
                 f'next: "{args.next}"\n'
                 f"reason: |\n  {reason}\n```\n")
        nm = NEXTSESS_RE.search(text)
        text = (text[:nm.start()] + block) if nm else (text.rstrip() + "\n\n" + block)
        f.seek(0)
        f.write(text)
        f.truncate()
    print(f"closed → next={args.next}")
    # 세션 종료 게이트: embedded repo 에 미커밋 decision 레코드가 남아 있으면 경고 (DEC-2026-08-21-01)
    decision_gate(fm, getattr(args, "project_dir", None))
    # 커버리지 게이트 (agent-operations §5.7, DEC-2026-09-08-01) — 경고만. 이어서 노드 페이지 재생성
    if "nodes" not in fm:
        print("WARN: frontmatter nodes 없음 — 주제 노드 소속 (§5.2, 경고 등급)", file=sys.stderr)
    coverage_gate(fm, getattr(args, "project_dir", None), Path(args.ledger))
    _regen_node_pages(fm, getattr(args, "project_dir", None))
    # 링크 현행성 게이트 (DEC-2026-09-30-03) — 이 프로젝트에 기준선 밖 새 링크 위반이 있으면 멈춘다
    # (--no-sync 여부와 무관하게 exit 4 — 동기화하지 않는 close 도 세션 종료 판정이므로).
    # ledger 자체는 이미 closed 로 기록됐으므로, 링크를 고친 뒤 close 를 다시 실행하면 된다 (멱등).
    # 급할 때만 STRATA_LINK_CHECK=warn 으로 경고 강등.
    if link_gate(str(fm.get("project") or "") or None) != 0:
        return 4
    if not getattr(args, "no_sync", False):
        # DEC-2026-08-19-02: close 시 vault 자동 commit+push (실패해도 경고만 — vault-git.sh가 보장)
        import datetime as _dt
        import subprocess as _sp
        msg = (f"session {fm.get('project', '?')} {_dt.date.today().isoformat()}: "
               f"{fm.get('topic', Path(args.ledger).stem)}")
        _proj = str(fm.get("project") or "")
        # 생성물(.kb/manifest.json·_index/·노드 페이지)은 세션이 커밋하지 않는다 — 노드 페이지는 librarian 몫 (DEC-2026-10-29-04)
        _paths = [f"projects/{_proj}", f":(exclude)projects/{_proj}/nodes"] if _proj else []
        from kb.legacy._kit import VAULT_GIT
        _sp.run(["sh", str(VAULT_GIT), "commit-push", msg, *_paths])
    return 0


def cmd_validate(args) -> int:
    with locked(Path(args.ledger), exclusive=False) as f:
        text = f.read()
    fm, fm_raw, body = split_doc(text)
    errors, warns = [], []

    if fm_raw is None:
        errors.append("frontmatter(--- ... ---) 없음")
    else:
        for k in REQUIRED_FM:
            if k not in fm:
                errors.append(f"frontmatter 필수 필드 누락: {k}")
        if fm.get("status") not in VALID_STATUS:
            errors.append(f"status 값 비정상: {fm.get('status')} (open|handoff|closed)")

    ents = parse_entries(body)
    if not ents:
        warns.append("엔트리(## [actor] ts)가 하나도 없음")
    declared = set(fm.get("actors") or [])
    last_seq = 0
    for e in ents:
        tag = f"[{e['actor']}] {e['ts']}"
        if e["yaml"] is None:
            errors.append(f"{tag}: yaml 블록 없음")
        else:
            try:
                yaml.safe_load(e["yaml"])
            except yaml.YAMLError as ex:
                errors.append(f"{tag}: yaml 파싱 실패 ({ex})")
        try:
            datetime.fromisoformat(e["ts"])
        except ValueError:
            warns.append(f"{tag}: timestamp 가 ISO8601 아님")
        if declared and e["actor"] not in declared:
            errors.append(f"{tag}: actor 가 frontmatter actors 에 없음")
        if e["seq"] is not None:
            if e["seq"] <= last_seq:
                warns.append(f"{tag}: seq={e['seq']} 가 비단조 (advisory)")
            last_seq = e["seq"]

    # actor Core enum — 도구명-as-actor hard-fail (도구명은 actor 금지, tool 필드 사용)
    non_core = sorted({e["actor"] for e in ents if e["actor"] not in CORE_ROLES})
    if non_core:
        errors.append(f"actor 가 Core role 아님: {non_core} "
                      f"(user|primary|reviewer|coordinator|archivist). 도구명은 actor 금지 — tool 필드 사용")

    if fm.get("status") == "closed":
        nxt = fm.get("next_session")
        if nxt in (None, "", "pending"):
            errors.append(f"status=closed 인데 next_session 미지정({nxt}) — §5.6 위반")

    # handoff 게이트: repo .strata/decisions* 미커밋 레코드 경고 (차단 아님 — DEC-2026-08-21-01)
    n_uncommitted = decision_gate(fm, getattr(args, "project_dir", None))
    if n_uncommitted:
        warns.append(f"미커밋 decision 레코드 {n_uncommitted}건 — 프로젝트 repo 커밋 필요 (handoff 게이트)")

    # 커버리지 게이트 (agent-operations §5.7) — 경고 등급. nodes 는 §5.2 필수지만 도입기라 경고
    if fm_raw is not None and "nodes" not in fm:
        warns.append("frontmatter nodes 없음 — 주제 노드 소속 (§5.2, 경고 등급)")
    warns.extend(f"커버리지: {w}" for w in coverage_gate(fm, getattr(args, "project_dir", None), Path(args.ledger), quiet=True))

    for w in warns:
        print(f"WARN: {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print(f"❌ invalid — {len(errors)} error, {len(warns)} warn", file=sys.stderr)
        return 2
    print(f"✅ valid — {len(ents)} 엔트리, {len(warns)} warn")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Shared Session Ledger CLI (append/read/close/validate)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("append", help="엔트리 추가 (flock LOCK_EX)")
    pa.add_argument("ledger")
    pa.add_argument("--actor", required=True)
    pa.add_argument("--tool")
    pa.add_argument("--desc")
    pa.add_argument("--body")
    pa.add_argument("--body-file")
    pa.set_defaults(fn=cmd_append)

    pr = sub.add_parser("read", help="읽기 (flock LOCK_SH)")
    pr.add_argument("ledger")
    pr.add_argument("--last", type=int)
    pr.add_argument("--actor")
    pr.set_defaults(fn=cmd_read)

    pc = sub.add_parser("close", help="닫기 — status=closed + next_session 강제 + vault 동기화")
    pc.add_argument("ledger")
    pc.add_argument("--next", required=True, dest="next")
    pc.add_argument("--reason")
    pc.add_argument("--no-sync", action="store_true", help="vault commit+push 생략")
    pc.add_argument("--project-dir", help="미커밋 decision 레코드 게이트용 프로젝트 루트 (기본: cwd / $STRATA_PROJECTS/{project})")
    pc.set_defaults(fn=cmd_close)

    pv = sub.add_parser("validate", help="포맷 검사 + 미커밋 decision 레코드 경고 (exit 2 if invalid)")
    pv.add_argument("ledger")
    pv.add_argument("--project-dir", help="미커밋 decision 레코드 게이트용 프로젝트 루트 (기본: cwd / $STRATA_PROJECTS/{project})")
    pv.set_defaults(fn=cmd_validate)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
