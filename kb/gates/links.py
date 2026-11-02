"""Link-currency gate, reading the store (strata/scripts/kb-link-check.py is a shuttle to this module).

Violations (same names and hints as the legacy script, DEC-2026-09-30-03 / DEC-2026-10-28-07):
  broken            wikilink resolves to nothing
  id-only           resolves only through frontmatter id — breaks in Obsidian
  alias-only        resolves only through aliases — breaks in Obsidian
  superseded-target a knowledge document points at a superseded document (advisory)
  md-link           vault-internal markdown link whose target file does not exist
  code-path / code-symbol  (--code-root) covers.paths / covers.symbols not found in the code repository

Body links are `links` edges the vault scanner emitted (source_ref = "wiki:<file|id|alias|none>:<target>" or
"md:<file|dir|none>:<href>"). Generated documents (decisions/, nodes/, planning/, _index/) and advisory types are
reported but never block. The baseline of record is $STRATA_VAULT/.kb/link-baseline.json; the store's
baselines table (gate "link") mirrors it on every run. Exit 1 only for new blocking violations.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from kb.store import Node, SqliteStore
from kb.providers.vault_scanner import is_generated, is_origin_immutable

ADVISORY_TYPES = {"superseded-target"}


def is_knowledge(path: str) -> bool:
    return "/knowledge-base/" in f"/{path}" or path.startswith("patterns/")


def blocking(v: dict) -> bool:
    return v["type"] not in ADVISORY_TYPES and not is_generated(v["file"]) and not v.get("origin_immutable")


def key_of(v: dict) -> str:
    return f"{v['file']}::{v['type']}::{v['target']}"


def doc_nodes(store: SqliteStore) -> dict[str, Node]:
    out: dict[str, Node] = {}
    for kind in ("doc", "session", "task"):
        for n in store.query(kind=kind):
            if n.id.startswith("doc:"):
                out[n.path] = n
    return out


_grep_cache: dict[tuple[str, str], bool] = {}


def _grep_word(root: Path, word: str) -> bool:
    key = (str(root), word)
    if key not in _grep_cache:
        r = subprocess.run(["git", "-C", str(root), "grep", "-q", "-w", "-F", word, "--", "*.kt", "*.java", "*.ts",
                            "*.tsx", "*.go", "*.rs", "*.py", "*.swift", "*.sql", "*.yml", "*.yaml"],
                           capture_output=True)
        _grep_cache[key] = r.returncode == 0
    return _grep_cache[key]


def check(store: SqliteStore, project: str | None = None, code_roots: dict[str, Path] | None = None) -> list[dict]:
    code_roots = code_roots or {}
    docs = doc_nodes(store)
    out: list[dict] = []

    def add(src, kind, target, hint=""):
        row = {"file": src, "type": kind, "target": target, "hint": hint}
        if src in docs and is_origin_immutable(docs[src].payload):
            row["origin_immutable"] = True   # verbatim export: the link belongs to the source system (advisory)
        out.append(row)

    for rel in sorted(docs):
        if project and not rel.startswith(f"projects/{project}/"):
            continue
        n = docs[rel]
        relation_targets = set(n.payload.get("supersedes") or []) | set(n.payload.get("superseded_by") or [])
        for e in store.neighbors(n.id, kind="links"):
            scheme, how, target = e.source_ref.split(":", 2)
            if scheme == "wiki":
                dst = e.dst.split(":", 1)[1] if e.dst.startswith(("doc:", "file:")) else None
                if how == "none":
                    add(rel, "broken", target)
                elif how in ("id", "alias"):
                    add(rel, f"{how}-only", target, f"파일명 {Path(dst).stem} 로 바꿀 것")
                elif (dst and dst.endswith(".md") and is_knowledge(rel) and dst in docs
                      and docs[dst].status == "superseded" and target not in relation_targets and dst != rel):
                    repl = docs[dst].payload.get("superseded_by_raw")
                    add(rel, "superseded-target", target, f"현행 문서: {repl}" if repl else "")
            elif scheme == "md" and how == "none":
                add(rel, "md-link", target)
        if code_roots and is_knowledge(rel):
            proj = rel.split("/")[1] if rel.startswith("projects/") else None
            root = code_roots.get(proj or "")
            covers = n.payload.get("covers") if isinstance(n.payload.get("covers"), dict) else {}
            if root and covers:
                for pth in covers.get("paths") or []:
                    if not (root / str(pth)).exists():
                        add(rel, "code-path", str(pth))
                for sym in covers.get("symbols") or []:
                    name = str(sym).split(".")[0].split("#")[0].strip()
                    if name and not _grep_word(root, name):
                        add(rel, "code-symbol", str(sym))
    return out


def _mirror_baseline(store: SqliteStore, keys: set[str]) -> None:
    """Keep the store's baselines(gate=link) equal to the file of record."""
    try:
        have = store.baselines("link")
        for k in keys - have:
            proj = k.split("/")[1] if k.startswith("projects/") else ""
            store.put_baseline("link", proj, k, recorded="link-baseline.json")
        if have - keys:
            with store.conn:
                store.conn.executemany("DELETE FROM baselines WHERE gate = 'link' AND key = ?", [(k,) for k in have - keys])
    except Exception as e:  # noqa: BLE001 — the mirror never blocks the gate
        print(f"WARN: store baseline mirror skipped: {e}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kb-link-check", description="vault 링크 현행성 검사 (기준선 밖 새 위반만 실패)")
    ap.add_argument("--project", default=None, help="projects/{name} 만 검사")
    ap.add_argument("--code-root", action="append", default=[], metavar="PROJECT=PATH",
                    help="KB covers 를 대조할 코드 저장소 (반복 가능)")
    ap.add_argument("--baseline", default=None, help="기본: $STRATA_VAULT/.kb/link-baseline.json")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--shrink-baseline", action="store_true")
    ap.add_argument("--all", action="store_true", help="기준선 포함 전체 위반 출력")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--db", default=None, help="store.sqlite 경로 (기본 $STRATA_VAULT/.kb/store.sqlite)")
    args = ap.parse_args(argv)

    from kb import vault_root
    vault = vault_root()   # no silent default: a guessed vault would check the wrong documents (MB-strata-kit-2026-048)
    if vault is None:
        print("오류: STRATA_VAULT 가 설정되지 않음 — vault 경로를 환경 변수로 준다", file=sys.stderr)
        return 2
    if not vault.is_dir():
        print(f"오류: vault 없음 — {vault}", file=sys.stderr)
        return 2
    code_roots = {}
    for spec in args.code_root:
        name, _, path = spec.partition("=")
        if not path or not Path(path).is_dir():
            print(f"오류: --code-root 형식 PROJECT=PATH (존재하는 디렉토리): {spec}", file=sys.stderr)
            return 2
        code_roots[name] = Path(path)

    from kb.gates.coverage import get_store
    store = get_store(args.db)
    violations = check(store, args.project, code_roots)
    baseline_path = Path(args.baseline) if args.baseline else vault / ".kb" / "link-baseline.json"
    baseline: set[str] = set()
    if baseline_path.is_file():
        baseline = set(json.loads(baseline_path.read_text(encoding="utf-8")).get("violations", []))
    _mirror_baseline(store, baseline)
    current = {key_of(v) for v in violations if blocking(v)}
    if args.project and not (args.write_baseline or args.shrink_baseline):
        baseline = {k for k in baseline if k.startswith(f"projects/{args.project}/")}

    if args.write_baseline or args.shrink_baseline:
        if args.project or code_roots:
            print("오류: 기준선은 vault 전체·링크 검사 기준으로만 쓴다 (--project/--code-root 와 함께 쓰지 않음)",
                  file=sys.stderr)
            return 2
        keep = sorted(current if args.write_baseline else (baseline & current))
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps({
            "note": "GENERATED — kb-link-check.py. 기존 링크 위반 기준선. 줄어드는 방향으로만 갱신 (--shrink-baseline).",
            "violations": keep}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        _mirror_baseline(store, set(keep))
        removed = len(baseline - current) if args.shrink_baseline else 0
        print(f"기준선 {'기록' if args.write_baseline else '축소'}: {len(keep)}건"
              + (f" (고쳐진 {removed}건 제거)" if args.shrink_baseline else "") + f" → {baseline_path}")
        return 0

    new = [v for v in violations if blocking(v) and key_of(v) not in baseline]
    shown = violations if args.all else new
    if args.json:
        print(json.dumps({"total": len(violations), "baseline": len(baseline), "new": len(new),
                          "fixed": len(baseline - current), "violations": shown}, ensure_ascii=False, indent=1))
    else:
        by_type: dict[str, int] = {}
        for v in violations:
            by_type[v["type"]] = by_type.get(v["type"], 0) + 1
        summary = ", ".join(f"{k} {n}" for k, n in sorted(by_type.items())) or "없음"
        advisory = sum(1 for v in violations if not blocking(v))
        print(f"링크 검사: 전체 위반 {len(violations)}건 ({summary}) · 참고(생성 문서·원문 불변 문서·대체 문서 참조) {advisory}건 · "
              f"기준선 {len(baseline)}건 · 새 위반 {len(new)}건 · 고쳐짐 {len(baseline - current)}건")
        for v in shown:
            hint = f"  — {v['hint']}" if v["hint"] else ""
            tag = " BLOCK" if blocking(v) else " note"   # 등급(오더 2026.10.29-02): 새 차단 위반 block, 생성·원문 불변·대체 문서 참조 advisory
            print(f"  [{v['type']}]{tag} {v['file']} → {v['target']}{hint}")
        if baseline - current:
            print("  (고쳐진 항목이 있습니다 — --shrink-baseline 으로 기준선을 줄이세요)")
    return 1 if new else 0
