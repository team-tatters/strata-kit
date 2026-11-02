"""build-index — the store is the only index (order 2026.10.28-07, replaces kb.legacy.build_kb_index).

One run rebuilds the store from the providers and then derives every generated view: validation warnings
(block → exit 2), the review inbox (.kb/review-candidates.json + _index/review-needed.md), node pages, Obsidian
sortspecs and .kb/manifest.json, in the formats the session-end channel reads.

--project limits what is reported (warnings, add/update lines) to that project, like the legacy partial build;
the store itself is always rebuilt whole (1–2 s) so no view ever sees a partial store.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from kb import vault_root
from kb.engine import build_store, default_project_dirs
from kb.store import SCHEMA_VERSION, Node, SqliteStore
from kb.taxonomy import load_taxonomy
from kb.views.node_pages import generate_all

REVIEW_INBOX_JSON = "review-candidates.json"
REVIEW_INBOX_MOC = Path("_index") / "review-needed.md"
GENERATOR = "python3 -m kb build-index"
DOC_KINDS = ("doc", "session", "task")


# ---------------------------------------------------------------- store views

def discovered_docs(store: SqliteStore, project: str | None = None) -> list[Node]:
    """Documents the scanner discovered (the legacy manifest set), in discovery order."""
    docs = [n for n in store.query() if n.kind in DOC_KINDS and n.payload.get("discovered")]
    if project:
        docs = [n for n in docs if n.path.startswith(f"projects/{project}/")]
    docs.sort(key=lambda n: n.payload.get("doc_seq", 0))
    return docs


def indexed(n: Node) -> bool:
    return bool(n.payload.get("indexed"))


def _link_target(value) -> str:
    s = str(value).strip()
    m = re.match(r"^\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]$", s)
    return (m.group(1) if m else s.split("#", 1)[0]).strip()


def check_supersedes_symmetry(docs: list[Node], taxonomy: dict | None) -> list[tuple]:
    """A.supersedes=B ⇔ B.superseded_by=A (taxonomy validation.supersedes_symmetry_check). Same messages and
    order as the legacy check over document_links. Returns (severity, path, message, action)."""
    if not taxonomy:
        return []
    check = taxonomy.get("validation", {}).get("supersedes_symmetry_check", {})
    if not check.get("enabled"):
        return []
    sev, act = check.get("severity", "warning"), check.get("action", "warn")
    idx = [d for d in docs if indexed(d)]

    def doc_keys(d: Node) -> set[str]:
        fp, sid = d.path, str(d.payload.get("stable_id") or "")
        return {sid, Path(fp).stem, fp, fp[:-3] if fp.endswith(".md") else fp}

    keys: dict[str, Node] = {}
    for d in idx:
        for k in doc_keys(d):
            if k:
                keys.setdefault(k, d)
    out = []
    for src in idx:
        for target in (src.payload.get("supersedes") or []):
            target = _link_target(target)
            tgt = keys.get(target) or keys.get(Path(target).stem)
            sid = str(src.payload.get("stable_id") or "")
            if tgt is None:
                out.append((sev, src.path, f"supersedes 대상을 찾을 수 없음: '{target}'", act))
                continue
            if tgt.status != "superseded":
                out.append((sev, tgt.path, f"'{sid or src.path}' 가 이 문서를 supersedes 하지만 status 가 superseded 가 아님 ({tgt.status})", act))
            back = {_link_target(b) for b in (tgt.payload.get("superseded_by") or [])}
            src_keys = doc_keys(src)
            if not (back & src_keys) and not any(Path(b).stem in src_keys for b in back):
                out.append((sev, tgt.path, f"superseded_by 가 '{sid or Path(src.path).stem}' 를 가리키지 않음 (대칭 깨짐)", act))
    return out


def review_candidates(docs: list[Node], taxonomy: dict | None, today: date | None = None) -> list[tuple]:
    """(file_path, days, basis) for active Knowledge documents older than review_policy.default_review_days.
    updated is the basis; fallback_to_created makes documents without updated judged by created (DEC-2026-09-08-01)."""
    if not taxonomy:
        return []
    policy = taxonomy.get("lifecycle", {}).get("review_policy", {})
    if not policy.get("auto_flag"):
        return []
    review_days = policy.get("default_review_days", 90)
    exempt = set(policy.get("exempt_types", []))
    fallback = bool(policy.get("fallback_to_created", False))
    today = today or date.today()
    out = []
    for d in docs:
        pl = d.payload
        if not indexed(d) or d.status not in ("active", "") or pl.get("category") == "archive" or pl.get("type") in exempt:
            continue
        basis, stamp = "updated", str(pl.get("updated_fm") or "")
        if not stamp and fallback:
            basis, stamp = "created", str(pl.get("created") or "")
        if not stamp:
            continue
        try:
            stamp_date = date.fromisoformat(stamp[:10])
        except (ValueError, TypeError):
            continue
        days = (today - stamp_date).days
        if days >= review_days:
            out.append((d.path, days, basis))
    return out


def write_review_inbox(vault: Path, candidates: list, review_days: int) -> bool:
    """`.kb/review-candidates.json` (machine) + `_index/review-needed.md` (people, Index layer). The builder never edits
    canonical documents; the status transition is --apply-review or the session-end gate."""
    kb_dir = vault / ".kb"
    kb_dir.mkdir(exist_ok=True)
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "review_days": review_days,
        "candidates": [{"file_path": fp, "days": days, "basis": basis} for fp, days, basis in sorted(candidates, key=lambda x: -x[1])],
    }
    (kb_dir / REVIEW_INBOX_JSON).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    by_proj: dict = {}
    for fp, days, basis in candidates:
        parts = Path(fp).parts
        proj = parts[1] if len(parts) > 2 and parts[0] == "projects" else "vault"
        by_proj.setdefault(proj, []).append((days, fp, basis))
    lines = ["---", 'title: "리뷰 필요 후보"', "id: moc-vault-review-needed", "type: moc", f"created: {date.today().isoformat()}",
             "status: active", "---", "",
             "> GENERATED — 편집 금지. KB 색인 빌더가 review_policy 로 생성. status 전이는 색인 빌더의 `--apply-review` 또는 세션 종료 게이트가 수행한다.",
             "", f"기준: {review_days}일 경과 (updated, 없으면 created). 총 {len(candidates)}건.", ""]
    for proj in sorted(by_proj):
        lines.append(f"## {proj} ({len(by_proj[proj])})")
        for days, fp, basis in sorted(by_proj[proj], key=lambda x: -x[0]):
            lines.append(f"- [[{Path(fp).stem}]] — {days}일 ({basis}) `{fp}`")
        lines.append("")
    text = "\n".join(lines)
    out = vault / REVIEW_INBOX_MOC
    out.parent.mkdir(exist_ok=True)
    if out.exists() and out.read_text(encoding="utf-8").split("\n", 6)[6:] == text.split("\n", 6)[6:]:
        return False  # only the created date would change
    out.write_text(text + "\n", encoding="utf-8")
    return True


_STATUS_LINE_RE = re.compile(r"^status:\s*.*$", re.M)
_TYPE_LINE_RE = re.compile(r"^type:\s*.*$", re.M)
_FM_BLOCK_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(\r?\n|\Z)", re.S)


def apply_review(vault: Path) -> int:
    """Transition the inbox candidates to frontmatter `status: review-needed` (explicit command). Only active or
    status-less documents change; no other line is touched. Returns the number of documents changed."""
    src = vault / ".kb" / REVIEW_INBOX_JSON
    if not src.exists():
        print("  review 후보 파일 없음 — 먼저 빌드가 필요")
        return 0
    payload = json.loads(src.read_text(encoding="utf-8"))
    changed = 0
    for item in payload.get("candidates", []):
        path = vault / item["file_path"]
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        m = _FM_BLOCK_RE.match(text)
        if not m:
            continue
        fm_text = m.group(1)
        sm = _STATUS_LINE_RE.search(fm_text)
        if sm:
            current = sm.group(0).split(":", 1)[1].split("#", 1)[0].strip().strip("'\"")
            if current not in ("active", ""):
                continue
            new_fm = fm_text[: sm.start()] + "status: review-needed" + fm_text[sm.end():]
        else:
            tm = _TYPE_LINE_RE.search(fm_text)
            insert_at = tm.end() if tm else len(fm_text)
            new_fm = fm_text[:insert_at] + "\nstatus: review-needed" + fm_text[insert_at:]
        path.write_text(text[: m.start(1)] + new_fm + text[m.end(1):], encoding="utf-8")
        changed += 1
        print(f"  → review-needed: {item['file_path']} ({item['days']}일, {item['basis']})")
    return changed


def generate_sortspecs(docs: list[Node], vault: Path) -> int:
    """Obsidian Custom Sort sortspec.md per project KB root: page_order → file name within each target folder.
    Generated only (sortspec.md is never indexed). Rewritten only when it changes."""
    by_proj: dict = {}
    for d in sorted((d for d in docs if indexed(d) and d.payload.get("category") != "archive"), key=lambda d: d.path):
        p = Path(d.path)
        if "knowledge-base" not in p.parts or p.name == "_index.md":
            continue
        order = d.payload.get("page_order")
        by_proj.setdefault(p.parts[1], {}).setdefault(str(p.parent), []).append((order if order is not None else 99, p.stem))
    written = 0
    for proj, dirs in by_proj.items():
        sections = []
        for folder in sorted(dirs):
            entries = sorted(dirs[folder])
            if len(entries) < 2:
                continue
            sections.append(f"  target-folder: {folder}")
            sections.extend(f"  {stem}" for _, stem in entries)
        if not sections:
            continue
        out = vault / "projects" / proj / "knowledge-base" / "sortspec.md"
        if not out.parent.exists():
            continue
        text = "\n".join(["---", "sorting-spec: |", *sections, "---", "",
                          "<!-- GENERATED — build-kb-index.py가 page_order에서 생성. 손편집 금지 -->", ""])
        if not out.exists() or out.read_text(encoding="utf-8") != text:
            out.write_text(text, encoding="utf-8")
            written += 1
    return written


def manifest_entries(store: SqliteStore, docs: list[Node]) -> dict:
    """The legacy manifest `files` map: sha256 · title · chunk count · updated per discovered document."""
    counts = {r[0]: r[1] for r in store.conn.execute("SELECT node_id, COUNT(*) FROM chunks GROUP BY node_id")}
    files = {}
    for d in docs:
        if not indexed(d):
            files[d.path] = {"sha256": d.revision, "title": "(skipped)", "chunks": 0, "updated": ""}
            continue
        pl = d.payload
        files[d.path] = {"sha256": d.revision, "title": d.title, "chunks": counts.get(d.id, 0),
                         "updated": str(pl.get("updated_fm") or pl.get("created") or "")}
    return files


def load_manifest(vault: Path) -> dict:
    mf = vault / ".kb" / "manifest.json"
    if mf.is_file():
        try:
            return json.loads(mf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"version": "1.0", "files": {}}


# ---------------------------------------------------------------- the build

def build(vault: Path, store_path: Path | None = None, project: str | None = None,
          project_dirs: list[Path] | None = None, force: bool = False) -> int:
    """Rebuild the store, then every generated view. Returns the exit code (2 on a block violation).
    force forgets the previous manifest, so every document is reported as added (legacy --force)."""
    vault = Path(vault).resolve()
    store_path = Path(store_path) if store_path else vault / ".kb" / "store.sqlite"
    (vault / ".kb").mkdir(parents=True, exist_ok=True)
    taxonomy = load_taxonomy(vault, project)
    if taxonomy:
        print(f"  Taxonomy: v{taxonomy.get('version', '?')} ({', '.join(taxonomy.get('categories', {}).keys())})")
    else:
        print("  Taxonomy: 없음 (legacy NN-section 모드)")
    old_files = {} if force else load_manifest(vault).get("files", {})

    dirs = project_dirs if project_dirs is not None else default_project_dirs(vault)
    store = build_store(vault, store_path, None, dirs)
    try:
        all_docs = discovered_docs(store)
        scope = discovered_docs(store, project) if project else all_docs
        scope_prefix = f"projects/{project}/" if project else None

        added = updated = unchanged = skipped = removed = 0
        warnings: list[tuple] = []
        for d in scope:
            old = old_files.get(d.path)
            for sev, act, msg in (d.payload.get("diagnostics") or []):
                warnings.append((sev, d.path, msg, act))
            if not indexed(d) and not d.payload.get("diagnostics"):
                skipped += 1
                continue
            n_chunks = 0 if not indexed(d) else len(store.chunks_of(d.id))
            if old and old.get("sha256") == d.revision:
                unchanged += 1
            elif old:
                updated += 1
                print(f"  ↻ 갱신: {d.path} ({n_chunks} chunks)")
            else:
                added += 1
                print(f"  + 추가: {d.path} ({n_chunks} chunks)")
        current = {d.path for d in all_docs}
        for old_path in old_files:
            if scope_prefix and not old_path.startswith(scope_prefix):
                continue
            if old_path not in current:
                removed += 1
                print(f"  - 제거: {old_path}")

        warnings.extend(check_supersedes_symmetry(scope, taxonomy))

        candidates = review_candidates(all_docs, taxonomy)
        if taxonomy and taxonomy.get("lifecycle", {}).get("review_policy", {}).get("auto_flag"):
            review_days = taxonomy["lifecycle"]["review_policy"].get("default_review_days", 90)
            if write_review_inbox(vault, candidates, review_days):
                print(f"  리뷰 Inbox 갱신: {REVIEW_INBOX_MOC} ({len(candidates)}건)")

        try:
            w, u, r, n = generate_all(vault, store, project, quiet=True)
            if w or r:
                print(f"  노드 페이지: 작성 {w} / 변경없음 {u} / 제거 {r} (프로젝트 {n})")
        except Exception as e:  # noqa: BLE001 — node pages never block the build (legacy behaviour)
            print(f"  ⚠ 노드 페이지 생성 실패: {e}")

        n_sort = generate_sortspecs(all_docs, vault)
        if n_sort:
            print(f"  sortspec 생성/갱신: {n_sort}개 프로젝트")

        files = manifest_entries(store, all_docs)
        doc_count = sum(1 for d in all_docs if indexed(d))
        chunk_count = sum(f["chunks"] for f in files.values())
        ids = [d.id for d in all_docs if indexed(d)]
        total_chars = 0
        for i in range(0, len(ids), 500):   # document chunks only — order/task provider chunks are not index chunks
            marks = ",".join("?" * len(ids[i:i + 500]))
            total_chars += store.conn.execute(f"SELECT COALESCE(SUM(json_extract(meta_json, '$.char_count')), 0) FROM chunks WHERE node_id IN ({marks})", ids[i:i + 500]).fetchone()[0] or 0
        manifest = {"version": "1.0", "schema_version": f"store-{SCHEMA_VERSION}", "files": files,
                    "generated": datetime.now(timezone.utc).isoformat(), "generator": GENERATOR,
                    "stats": {"documents": doc_count, "chunks": chunk_count, "total_chars": total_chars}}
        (vault / ".kb" / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    finally:
        store.close()

    errors = [(p, m) for s, p, m, a in warnings if s == "error"]
    warns = [(p, m) for s, p, m, a in warnings if s == "warning"]
    if warns:
        print(f"\n=== 검증 경고: {len(warns)}건 ===")
        for path, msg in warns[:20]:
            print(f"  W {path}: {msg}")
        if len(warns) > 20:
            print(f"  ... 외 {len(warns) - 20}건")
    if errors:
        print(f"\n=== 검증 에러: {len(errors)}건 ===")
        for path, msg in errors:
            print(f"  E {path}: {msg}")
    if candidates:
        print(f"\n=== 리뷰 필요 후보: {len(candidates)}건 (전이는 --apply-review) ===")
        for path, days, basis in sorted(candidates, key=lambda x: -x[1])[:10]:
            print(f"  ? {path} ({days}일 경과, {basis} 기준)")
        if len(candidates) > 10:
            print(f"  ... 외 {len(candidates) - 10}건 — 전체: .kb/{REVIEW_INBOX_JSON}")

    print("\n=== KB 색인 빌드 완료 ===")
    print(f"  문서: {doc_count}개")
    print(f"  청크: {chunk_count}개")
    print(f"  총 문자: {total_chars:,}")
    parts = [f"추가: {added}", f"갱신: {updated}", f"변경없음: {unchanged}", f"제거: {removed}"]
    if skipped:
        parts.append(f"제외: {skipped}")
    print(f"  {' / '.join(parts)}")
    if taxonomy:
        print(f"  검증: 경고 {len(warns)} / 에러 {len(errors)}")
    print(f"  Store: {store_path}")
    print(f"  Manifest: {vault / '.kb' / 'manifest.json'}")

    block = [(p, m) for s, p, m, a in warnings if a == "block"]
    if block:
        print(f"\n=== BLOCK 위반: {len(block)}건 — 빌드 실패(exit 2) ===")
        for path, msg in block[:10]:
            print(f"  ✗ {path}: {msg}")
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb build-index", description="Strata KB 색인 빌드 — store 재생성 + 생성 뷰(노드 페이지·sortspec·리뷰 Inbox·manifest)")
    ap.add_argument("--vault", default=None, help="vault root (default $STRATA_VAULT)")
    ap.add_argument("--store", default=None, help="store file (default <vault>/.kb/store.sqlite)")
    ap.add_argument("--project", help="보고 범위를 한 프로젝트로 (store 는 항상 전체 재생성)")
    ap.add_argument("--project-dir", action="append", default=None, help="Tier P 레코드가 있는 repo (반복; 기본 자동)")
    ap.add_argument("--force", action="store_true", help="호환용 — store 는 매번 전체를 다시 만든다")
    ap.add_argument("--apply-review", action="store_true",
                    help="빌드 후 리뷰 후보(.kb/review-candidates.json)를 frontmatter status: review-needed 로 전이하고 다시 빌드")
    args = ap.parse_args(argv)
    vault = Path(args.vault).resolve() if args.vault else vault_root()
    if vault is None:
        print("ERROR: STRATA_VAULT 환경 변수가 설정되지 않았습니다.", file=sys.stderr)
        return 2
    if not (vault / "projects").is_dir():
        print(f"projects/ 없음 — vault 가 아님: {vault}", file=sys.stderr)
        return 2
    store_path = Path(args.store).resolve() if args.store else None
    dirs = [Path(d) for d in args.project_dir] if args.project_dir else None
    print(f"Strata KB Index Builder (store v{SCHEMA_VERSION})")
    print(f"  Vault: {vault}")
    if args.project:
        print(f"  Project: {args.project}")
    print()
    rc = build(vault, store_path, args.project, dirs, force=args.force)
    if args.apply_review:
        print("\n=== 리뷰 전이 (--apply-review) ===")
        n = apply_review(vault)
        print(f"  전이: {n}건")
        if n:
            print("\n전이된 문서 재색인:")
            rc = build(vault, store_path, args.project, dirs) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
