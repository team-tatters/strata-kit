"""Planning bundles (planning/planning-stage, DEC-2026-11-01-04·05): the planning stage is a filter. A bundle keeps
the source as evidence, turns it into a fact list where every row gets a destination, and only the refined documents
(PRD · Logical Tech Spec · terms · tree) and decisions are injected or shared.

  projects/<p>/planning/<bundle>/            a bundle is a planning folder that has an audit/ folder
      source/…            the original text, kept as evidence (or frontmatter category: source)
      audit/facts*.md     fact list   | # | source location | type | content | role | axes | subtopic |
      audit/coverage*.md  crosswalk   | # | source location | destination | note |
      audit/defects*.md   defects     | # | kind | content | how the refined documents handled it |
      audit/isolated*.md  isolated rules
      *.md                refined documents (frontmatter planning_doc: prd | tech-spec | terms | tree)

Tables are read by column position, so any locale's headers work.

  python3 -m kb planning check <bundle-dir>                 destinations · double counts · hand-offs · axes · limits · code
  python3 -m kb planning boundary [--share PATH]           connector exclusions and the share.yaml never lines
  python3 -m kb planning boundary --list [--project P]     refined documents that may be injected
  python3 -m kb planning impact <bundle | planning.md> [--depth 1] [--print]
                           specifications · code · dependents · decisions · other planning on the same nodes
                           (bundle → audit/impact.md, generated; DEC-2026-11-01-16)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EVIDENCE_DIRS = ("source", "audit")
AXES = {"동일성": "identity", "시간": "time", "파생": "derivation", "소멸": "expiry", "충돌": "conflict",
        "identity": "identity", "time": "time", "derivation": "derivation", "expiry": "expiry", "conflict": "conflict",
        "同一性": "identity", "時間": "time", "派生": "derivation", "消滅": "expiry", "衝突": "conflict",
        "时间": "time", "消亡": "expiry", "冲突": "conflict",
        "identidad": "identity", "tiempo": "time", "derivación": "derivation", "extinción": "expiry", "conflicto": "conflict",
        "identité": "identity", "temps": "time", "dérivation": "derivation", "extinction": "expiry",
        "caducidad": "expiry", "expiration": "expiry", "conflit": "conflict"}
AXIS_NAMES_KO = {"identity": "동일성", "time": "시간", "derivation": "파생", "expiry": "소멸", "conflict": "충돌"}
RULE_TYPES = {"규칙", "상태전이", "상태 전이", "예외", "rule", "state transition", "state-transition", "exception",
              "規則", "状態遷移", "例外", "规则", "状态转换", "regla", "transición de estado", "excepción",
              "règle", "transition d'état"}
LIMITS = {"prd": {"words": 800, "rules": 10}, "tech-spec": {"words": 1200}}

# destination prefixes, ko and en; anything else non-empty is "document + rule number"
DEST_PREFIXES = {
    "격리": "isolated", "isolated": "isolated",
    "결함": "defect", "defect": "defect",
    "코드": "code", "code": "code",
    "배경": "background", "background": "background",
    "중복": "duplicate", "duplicate": "duplicate",
    "범위 밖": "out-of-scope", "범위밖": "out-of-scope", "out of scope": "out-of-scope", "out-of-scope": "out-of-scope",
}

CODE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("테이블·컬럼·스키마", re.compile(r"테이블|컬럼|칼럼|스키마|\b(?:table|column|schema|varchar|primary key|foreign key)\b"
                                 r"|\bselect\s+[\w*,\s]+\s+from\b|\b[a-z][a-z0-9]*_[a-z0-9_]+\b", re.I)),
    ("클래스·모듈·서비스명", re.compile(r"클래스|\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b|\b\w+(?:Service|Controller|Repository|Handler)\b"
                                 r"|`[A-Za-z_][\w.]*(?:\(\))?`")),
    ("API 경로·HTTP 코드", re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+/|(?<![\w.])/(?:api|v\d+)/[\w/{}:.-]*|\bHTTP\s*\d{3}\b"
                                  r"|\b[1-5]\d{2}\s+(?:OK|Created|No Content|Bad Request|Unauthorized|Forbidden|Not Found|Conflict"
                                  r"|Unprocessable|Internal Server Error)\b|\b[45]xx\b")),
    ("프레임워크·라이브러리·벤더명", re.compile(
        r"\b(?:Spring|Django|Flask|FastAPI|Rails|React|Vue|Angular|Next\.js|Node\.js|Express|JPA|Hibernate|Kafka|RabbitMQ"
        r"|Redis|PostgreSQL|Postgres|MySQL|MongoDB|DynamoDB|Elasticsearch|AWS|S3|SQS|SNS|Lambda|GCP|Azure|Firebase"
        r"|Stripe|Toss|GraphQL|gRPC|Docker|Kubernetes|Terraform)\b")),
]


# -- reading ---------------------------------------------------------------

def split_frontmatter(text: str) -> tuple[dict, str, int]:
    """(frontmatter, body, number of lines the frontmatter takes)."""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            import yaml
            try:
                fm = yaml.safe_load(text[4:end]) or {}
            except yaml.YAMLError:
                fm = {}
            head = text[:end + 4]
            rest = text[end + 4:]
            if rest.startswith("\n"):
                rest, head = rest[1:], head + "\n"
            return (fm if isinstance(fm, dict) else {}), rest, head.count("\n")
    return {}, text, 0


def table_rows(text: str) -> list[list[str]]:
    """Body rows of every markdown table (header and separator dropped), cells stripped."""
    out, in_table, header_seen = [], False, False
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            in_table = header_seen = False
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not in_table:
            in_table, header_seen = True, False
            continue                                 # header row
        if not header_seen and all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            header_seen = True
            continue
        out.append(cells)
    return out


def _row_id(cell: str) -> str | None:
    c = cell.strip().strip("*").lstrip("#").strip()
    return c if re.fullmatch(r"[A-Za-z]*\d+(?:[-.]\d+)*", c) else None


def _cell(row: list[str], i: int) -> str:
    return row[i] if i < len(row) else ""


def is_bundle(d: Path) -> bool:
    return d.is_dir() and (d / "audit").is_dir()


def layer_of(rel: str, fm: dict | None, vault: Path | None) -> str:
    """'' (not planning) · original · refined · source · audit, for a vault-relative path under projects/<p>/planning/."""
    parts = rel.split("/")
    if not (len(parts) > 3 and parts[0] == "projects" and parts[2] == "planning"):
        return ""
    cat = str((fm or {}).get("category") or "")
    if len(parts) > 5 and parts[4] in EVIDENCE_DIRS:
        return parts[4]
    if cat in EVIDENCE_DIRS:
        return cat
    if len(parts) > 4 and vault is not None and is_bundle(vault.joinpath(*parts[:4])):
        return "refined"
    return "original"


def refined_docs(bundle: Path) -> list[Path]:
    out = []
    for p in sorted(bundle.rglob("*.md")):
        rel = p.relative_to(bundle).parts
        if rel[0] in EVIDENCE_DIRS:
            continue
        fm, _, _ = split_frontmatter(p.read_text(encoding="utf-8"))
        if str(fm.get("category") or "") in EVIDENCE_DIRS:
            continue
        out.append(p)
    return out


def doc_kind(p: Path, fm: dict) -> str:
    k = str(fm.get("planning_doc") or "").lower()
    if k:
        return k
    n = p.stem.lower()
    if "prd" in n:
        return "prd"
    if "tech-spec" in n or "techspec" in n or "logical" in n:
        return "tech-spec"
    return ""


def _audit_rows(bundle: Path, prefix: str) -> list[tuple[str, int, list[str]]]:
    """(file name, row index, cells) of rows with an id in audit/<prefix>*.md."""
    out = []
    for p in sorted((bundle / "audit").glob(f"{prefix}*.md")):
        _, body, _ = split_frontmatter(p.read_text(encoding="utf-8"))
        for i, row in enumerate(table_rows(body)):
            if row and _row_id(row[0]):
                out.append((p.name, i, row))
    return out


def parse_destination(text: str) -> tuple[str, str]:
    """(kind, argument). kind: refined · isolated · defect · code · background · duplicate · out-of-scope · '' (empty)."""
    t = text.strip().strip("`")
    if not t:
        return "", ""
    m = re.match(r"\s*([^:：]+?)\s*[:：]\s*(.*)$", t)
    head = (m.group(1) if m else t).strip().lower()
    if head in DEST_PREFIXES:
        return DEST_PREFIXES[head], (m.group(2).strip() if m else "")
    return "refined", t


# -- check -----------------------------------------------------------------

def code_hits(text: str, line_offset: int = 0) -> list[tuple[int, list[str], str]]:
    """(line number in the file, kinds, line) for every line with a code or architecture expression."""
    out, fence = [], False
    for i, line in enumerate(text.splitlines(), start=1 + line_offset):
        if line.strip().startswith("```"):
            fence = not fence
            out.append((i, ["코드 블록"], line.strip()))
            continue
        if fence:
            continue
        kinds = [k for k, rx in CODE_PATTERNS if rx.search(line)]
        if kinds:
            out.append((i, kinds, line.strip()))
    return out


def axes_in(cell: str) -> set[str]:
    """Axis names found anywhere in an axes cell (Latin words by word boundary, other scripts by substring)."""
    low = cell.lower()
    return {AXES[k] for k in AXES if (re.search(rf"\b{re.escape(k)}\b", low) if k.isascii() else k in low)}


def check(bundle: Path) -> dict:
    """Problems of one bundle. Keys hold lists; 'answered_axes' is informational."""
    r: dict = {"missing": [], "unknown": [], "double": [], "handoff": [], "duplicate_target": [], "defect_unlisted": [],
               "no_doc": [], "axes": [], "unanswered_axes": [], "limits": [], "code": []}
    facts = {}
    for fname, _, row in _audit_rows(bundle, "facts"):
        facts[_row_id(row[0])] = {"file": fname, "type": _cell(row, 2), "axes": _cell(row, 5), "loc": _cell(row, 1)}
    cov: dict[str, list[tuple[str, str]]] = {}
    for fname, _, row in _audit_rows(bundle, "coverage"):
        cov.setdefault(_row_id(row[0]), []).append((fname, _cell(row, 2)))
    defects = {_row_id(row[0]) for _, _, row in _audit_rows(bundle, "defects")}
    refined = refined_docs(bundle)
    stems = {p.stem.lower() for p in refined} | {p.name.lower() for p in refined}

    for rid in facts:
        entries = cov.get(rid, [])
        dests = [d for _, d in entries if d.strip()]
        if not dests:
            r["missing"].append(rid)
        if len(entries) > 1:
            r["double"].append((rid, [d for _, d in entries]))
    for rid in cov:
        if rid not in facts:
            r["unknown"].append(rid)
    for rid, entries in cov.items():
        for _, d in entries:
            kind, arg = parse_destination(d)
            if kind == "out-of-scope":
                target = bundle.parent / arg.strip().removesuffix("/")
                if not arg.strip():
                    r["handoff"].append((rid, "", "받는 쪽이 비어 있음"))
                elif not is_bundle(target):
                    r["handoff"].append((rid, arg, "받는 묶음이 없음"))
                elif rid not in {_row_id(row[0]) for _, _, row in _audit_rows(target, "coverage")}:
                    r["handoff"].append((rid, arg, "받는 쪽 대조표에 같은 행이 없음"))
            elif kind == "duplicate":
                ref = _row_id(arg)
                if not ref or ref not in facts:
                    r["duplicate_target"].append((rid, arg))
            elif kind == "defect" and rid not in defects:
                r["defect_unlisted"].append(rid)
            elif kind == "refined":
                name = re.split(r"[\s#]", d.strip())[0].lower()
                if name and name not in stems and name.removesuffix(".md") not in stems:
                    r["no_doc"].append((rid, d))

    answered = set()
    for rid, f in facts.items():
        cell = f["axes"].strip()
        answered |= axes_in(cell)                 # "time", "시간, 소멸", "identity: order line; time: 14 days" all read
        if f["type"].strip().lower() in RULE_TYPES and not cell:
            r["axes"].append(rid)
    if facts:
        r["unanswered_axes"] = [AXIS_NAMES_KO[a] for a in ("identity", "time", "derivation", "expiry", "conflict") if a not in answered]

    for p in refined:
        text = p.read_text(encoding="utf-8")
        fm, body, offset = split_frontmatter(text)
        kind = doc_kind(p, fm)
        lim = LIMITS.get(kind, {})
        words = len(body.split())
        if "words" in lim and words > lim["words"]:
            r["limits"].append((p.name, f"{words}단어 (상한 {lim['words']})"))
        if "rules" in lim:
            rules = set(re.findall(r"\bR\d+\b", body))
            if len(rules) > lim["rules"]:
                r["limits"].append((p.name, f"규칙 {len(rules)}개 (상한 {lim['rules']})"))
        for ln, kinds, line in code_hits(body, offset):
            r["code"].append((p.name, ln, kinds, line))
    r["facts"], r["rows"] = len(facts), sum(len(v) for v in cov.values())
    return r


PROBLEM_KEYS = ("missing", "unknown", "double", "handoff", "duplicate_target", "defect_unlisted", "no_doc", "axes", "limits", "code")


def report(bundle: Path, r: dict) -> list[str]:
    out = [f"{bundle.name}: 사실 {r['facts']}행 · 대조표 {r['rows']}행"]
    if r["missing"]:
        out.append(f"  행선지 없는 행: {', '.join('#' + x for x in r['missing'])}")
    if r["unknown"]:
        out.append(f"  사실 목록에 없는 대조표 행: {', '.join('#' + x for x in r['unknown'])}")
    for rid, ds in r["double"]:
        out.append(f"  두 번 센 행 #{rid}: {' / '.join(ds)}")
    for rid, target, why in r["handoff"]:
        out.append(f"  넘긴 행 #{rid} → {target or '?'}: {why}")
    for rid, arg in r["duplicate_target"]:
        out.append(f"  중복 행 #{rid}: 가리키는 행 {arg or '?'} 이 사실 목록에 없음")
    if r["defect_unlisted"]:
        out.append(f"  결함 문서에 없는 결함 행: {', '.join('#' + x for x in r['defect_unlisted'])}")
    for rid, d in r["no_doc"]:
        out.append(f"  행 #{rid}: 행선지 문서가 묶음에 없음 ({d})")
    if r["axes"]:
        out.append(f"  축이 빈 규칙 행: {', '.join('#' + x for x in r['axes'])} (해당 없으면 '해당 없음')")
    if r["unanswered_axes"]:
        out.append(f"  묶음 전체에서 답하지 않은 축: {', '.join(r['unanswered_axes'])} (참고)")
    for name, what in r["limits"]:
        out.append(f"  상한 초과 {name}: {what} — 복잡도 검토 신호")
    for name, ln, kinds, line in r["code"]:
        out.append(f"  코드 표현 {name}:{ln} [{', '.join(kinds)}] {line[:100]}")
    if not any(r[k] for k in PROBLEM_KEYS):
        out.append("  문제 없음")
    return out


# -- boundary ----------------------------------------------------------------

EXCLUDE_GLOBS = ("projects/*/planning/**/source/**", "projects/*/planning/**/audit/**")


def bundles(vault: Path, project: str | None = None) -> list[Path]:
    roots = [vault / "projects" / project / "planning"] if project else sorted((vault / "projects").glob("*/planning"))
    return [d for root in roots if root.is_dir() for d in sorted(root.iterdir()) if is_bundle(d)]


def injectable(vault: Path, project: str | None = None) -> list[str]:
    return [p.relative_to(vault).as_posix() for b in bundles(vault, project) for p in refined_docs(b)]


def boundary_lines(share: Path | None) -> list[str]:
    have = share.read_text(encoding="utf-8") if share and share.is_file() else ""
    out = ["# 주입 경계 (DEC-2026-11-01-05) — 원문(source/)·근거(audit/)는 주입하지 않는다",
           "", "## GitHub 커넥터 제외 경로 (vault 기준)"]
    out += list(EXCLUDE_GLOBS)
    out += ["", "## share.yaml never 에 넣을 줄"]
    for g in EXCLUDE_GLOBS:
        mark = "있음" if f'"{g}"' in have else "없음"
        out.append(f'  - "{g}"   # {mark}')
    out += ["", "## Notion", "정리본을 게시할 자리와 원문 자리를 나누고, 커넥터 범위는 정리본 쪽으로 둔다 (kit 밖)"]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kb planning", description="planning bundles: check · boundary · impact")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="destinations · double counts · hand-offs · axes · limits · code expressions")
    c.add_argument("bundle", nargs="+", help="planning/<bundle> folder (has audit/)")
    b = sub.add_parser("boundary", help="connector exclusions and share.yaml never lines; --list the injectable documents")
    b.add_argument("--list", action="store_true", help="refined documents that may be injected")
    b.add_argument("--project")
    b.add_argument("--share", help="share.yaml to compare (default $STRATA_VAULT/_meta/share.yaml)")
    im = sub.add_parser("impact", help="what the planning touches: specifications · code · dependents · decisions · other planning")
    im.add_argument("target", help="planning/<bundle> folder or one planning document")
    im.add_argument("--depth", type=int, default=1, help="dependency hops from the covered code (default 1)")
    im.add_argument("--print", action="store_true", help="print only, even for a bundle")
    a = ap.parse_args(argv)
    if a.cmd == "impact":
        from kb.planning_impact import run
        try:
            rc, out = run(Path(a.target), a.depth, a.print)
        except ValueError as e:
            print(f"오류: {e}", file=sys.stderr)
            return 2
        print(out, file=sys.stderr if rc else sys.stdout)
        return rc
    if a.cmd == "check":
        rc = 0
        for s in a.bundle:
            d = Path(s)
            if not is_bundle(d):
                print(f"{s}: 묶음이 아님 (audit/ 폴더가 없음)", file=sys.stderr)
                rc = 2
                continue
            r = check(d)
            print("\n".join(report(d, r)))
            if any(r[k] for k in PROBLEM_KEYS):
                rc = max(rc, 1)
        return rc
    from kb import vault_root
    v = vault_root()
    if a.list:
        if not v:
            print("STRATA_VAULT 가 없음", file=sys.stderr)
            return 2
        print("\n".join(injectable(v, a.project)))
        return 0
    share = Path(a.share) if a.share else (v / "_meta" / "share.yaml" if v else None)
    print("\n".join(boundary_lines(share)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
