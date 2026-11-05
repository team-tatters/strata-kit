"""Vault scanner provider — frontmatter + taxonomy → doc/session/task/node nodes, declared edges, chunks.

Discovery, frontmatter parsing, heading chunking, path classification and taxonomy validation are the
index builder's rules (kb.docrules, moved verbatim from the retired legacy builder), so the store answers
exactly as the FTS index did.
"""
from __future__ import annotations

import os
import re
import urllib.parse
from pathlib import Path

try:
    import yaml
except ImportError as e:  # pragma: no cover
    raise SystemExit("PyYAML required") from e

from kb import docrules as rules
from kb.chunking import split_over_tokens
from kb.store import Chunk, Edge, Node, ProviderOutput, embed_text

DEC_RE = re.compile(r"^DEC-\d{4}-\d{2}-\d{2}-\d{2}$")
PROJECT_DEC_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s+(DEC-\d{4}-\d{2}-\d{2}-\d{2})$")
# body links (same patterns as the legacy kb-link-check.py — DEC-2026-10-28-07)
SKIP_DIRS = {".git", ".obsidian", ".kb", ".local", "_outbox", "_inbox", ".trash"}
HISTORY_DIRS = ("sessions", "tasks", "relays", "planning", "reviews", "signals")
GENERATED_DIRS = ("decisions", "nodes", "planning")
OUTSIDE_LINK_GATE = ("outputs/retro/",)   # regenerable retro bundles (DEC-2026-10-30-05): no doc node, still resolvable
FENCE_RE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
BODY_WIKI_RE = re.compile(r"!?\[\[([^\]\n]+?)\]\]")
MD_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
LINK_FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
# frontmatter field → edge kind (only fields in the store's edge vocabulary)
FIELD_EDGES = {
    "kb_updates": "kb_updates",
    "orders": "orders",
    "decisions_made": "decisions_made",
    "decisions": "decisions_made",
    "supersedes": "supersedes",
}


def doc_node_id(rel_path: str) -> str:
    return f"doc:{rel_path}"


def node_node_id(project: str, nid: str) -> str:
    return f"node:{project}:{nid}"


def decision_node_id(project: str, dec_id: str) -> str:
    return f"decision:{project}:{dec_id}"


ORDER_ID_RE = re.compile(r"\d{4}\.\d{2}\.\d{2}-\d{2}")
ORDER_FOLDER_RE = re.compile(r"(\d{4}\.\d{2}\.\d{2})/(\d{2})-")


def order_id(raw: str) -> str:
    """Session `orders:` entries are written many ways — "2026.09.30-04", "[[2026.08.28-04]] slug (note)",
    "[[path/_order|2026.09.30-04]]", "tasks/2026.09.15/01-slug" (the order folder). The declared target is the
    order id inside; a folder path maps to <date>-<nn> by the task-spec naming rule; else the raw text."""
    m = ORDER_ID_RE.search(raw)
    if m:
        return m.group(0)
    f = ORDER_FOLDER_RE.search(raw)
    if f:
        return f"{f.group(1)}-{f.group(2)}"
    return raw.strip()


def _kind_for(rel_path: str) -> str:
    parts = rel_path.split("/")
    if len(parts) > 2 and parts[0] == "projects":
        if parts[2] == "sessions":
            return "session"
        if parts[2] == "tasks":
            return "task"
    return "doc"


def _as_list(v) -> list:
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def _links_raw(legacy, fm: dict, body: str) -> list[str]:
    """Link targets in the order the legacy index stored document_links: typed frontmatter fields, then body."""
    out: list[str] = []
    for field in legacy.TYPED_LINK_FIELDS:
        vals = fm.get(field)
        if vals is None:
            continue
        for v in (vals if isinstance(vals, list) else [vals]):
            target = legacy._link_target(v)
            if target:
                out.append(target)
    out.extend(legacy.extract_links(body))
    return out


def _implementation_reviewed(fm: dict) -> str:
    impl = fm.get("implementation")
    return str(impl.get("reviewed") or "")[:10] if isinstance(impl, dict) else ""


def _implementation(fm: dict) -> tuple[str, list[str]]:
    """A planning document's implementation block: (status, spec links). `implementation: not-started` is a bare status."""
    impl = fm.get("implementation")
    if isinstance(impl, dict):
        return str(impl.get("status") or ""), [str(x).strip() for x in _as_list(impl.get("spec")) if str(x).strip()]
    return (str(impl), []) if impl else ("", [])


def strip_code(body: str) -> str:
    return INLINE_CODE_RE.sub("", FENCE_RE.sub("", body))


def body_link_target(raw: str) -> str:
    """'[[a\\|b]]' in tables escapes the pipe — the trailing backslash is not part of the name."""
    return raw.split("|", 1)[0].split("#", 1)[0].strip().rstrip("\\").strip()


def is_history(path: str) -> bool:
    parts = path.split("/")
    return len(parts) > 2 and parts[0] == "projects" and parts[2] in HISTORY_DIRS


def _is_free_text(raw: str) -> bool:
    """A frontmatter value with spaces and nothing path- or id-like names no document."""
    return " " in raw and "/" not in raw and "[[" not in raw and ".md" not in raw and "DEC-" not in raw


def is_origin_immutable(payload: dict) -> bool:
    """A planning original exported from an external system (source: notion:…) is kept verbatim; its outbound
    links point into that system and are references, not vault links to repair."""
    return str(payload.get("origin") or "").lower().startswith("notion")


def is_generated(path: str) -> bool:
    parts = path.split("/")
    if path.startswith("_index/") or parts[-1] == "_generated-index.md":
        return True
    return len(parts) > 2 and parts[0] == "projects" and parts[2] in GENERATED_DIRS


class _Files:
    """Every file in the vault (minus SKIP_DIRS): the resolution tables the legacy link check built."""

    def __init__(self, vault: Path):
        self.vault = vault
        self.by_path: set[str] = set()
        self.by_stem: dict[str, list[str]] = {}
        self.md: list[str] = []
        for dirpath, dirnames, filenames in os.walk(vault):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for fn in sorted(filenames):
                r = (Path(dirpath) / fn).relative_to(vault).as_posix()
                self.by_path.add(r)
                if fn.endswith(".md"):
                    self.by_path.add(r[:-3])
                    self.by_stem.setdefault(fn[:-3], []).append(r)
                    self.md.append(r)
                else:
                    self.by_stem.setdefault(fn, []).append(r)
        self.by_id: dict[str, str] = {}
        self.by_alias: dict[str, str] = {}

    def register(self, rel: str, fm: dict) -> None:
        if fm.get("id"):
            self.by_id.setdefault(str(fm["id"]), rel)
        for a in fm.get("aliases") or []:
            self.by_alias.setdefault(str(a), rel)

    def resolve(self, target: str, src: str | None = None) -> tuple[str, str | None]:
        """(kind, file) — kind: file | id | alias | none. Same rules as kb-link-check.py Index.resolve."""
        if target.startswith(".") and src:
            try:
                target = Path(os.path.normpath((self.vault / src).parent / target)).relative_to(self.vault).as_posix()
            except ValueError:
                return "none", None
        t = target.strip().lstrip("/")
        if t.endswith(".md"):
            t = t[:-3]
        if t in self.by_path or f"{t}.md" in self.by_path:
            return "file", f"{t}.md" if f"{t}.md" in self.by_path else t
        stem = t.rsplit("/", 1)[-1]
        cands = self.by_stem.get(stem) or self.by_stem.get(f"{stem}.md") or []
        if "/" in t:
            cands = [c for c in cands if c[:-3].endswith(t) or c.endswith(t)]
        if cands:
            if src and len(cands) > 1 and src.startswith("projects/"):
                proj = "/".join(src.split("/")[:2]) + "/"
                same = [c for c in cands if c.startswith(proj)]
                if same:
                    return "file", same[0]
            return "file", cands[0]
        if t in self.by_id:
            return "id", self.by_id[t]
        if t in self.by_alias:
            return "alias", self.by_alias[t]
        return "none", None


def _split_body(text: str) -> tuple[dict, str]:
    """Frontmatter and body with the link check's strict frontmatter rule (--- on its own lines)."""
    m = LINK_FM_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return (fm if isinstance(fm, dict) else {}), text[m.end():]


def body_link_edges(vault: Path, files: _Files, rel: str, body: str) -> list[Edge]:
    """doc --links--> target for each body wikilink and vault-internal markdown link (code excluded)."""
    src = doc_node_id(rel)
    out: list[Edge] = []
    clean = strip_code(body)
    for m in BODY_WIKI_RE.finditer(clean):
        target = body_link_target(m.group(1))
        if not target:
            continue
        kind, dst = files.resolve(target, rel)
        if kind == "none":
            node = f"ref:{target}"
        elif dst.endswith(".md"):
            node = doc_node_id(dst)
        else:
            node = f"file:{dst}"
        out.append(Edge(src, node, "links", source_ref=f"wiki:{kind}:{target}"))
    for m in MD_LINK_RE.finditer(clean):
        href = m.group(1)
        if re.match(r"^[a-z]+:", href) or href.startswith("#"):
            continue
        path = urllib.parse.unquote(href.split("#", 1)[0])
        if not path or ("/" not in path and "." not in path):
            continue   # "reviewers[...](순서대로)" — a bare word in prose is not a link to a vault file
        try:
            dst_rel = Path(os.path.normpath((vault / rel).parent / path)).relative_to(vault).as_posix()
        except ValueError:
            continue
        how = "file" if dst_rel in files.by_path else ("dir" if (vault / dst_rel).is_dir() else "none")
        node = doc_node_id(dst_rel) if dst_rel.endswith(".md") else f"file:{dst_rel}"
        out.append(Edge(src, node, "links", source_ref=f"md:{how}:{href}"))
    return out


class _Toc:
    """One project's topic-node tree: id set, alias → id, and nodes/edges to emit."""

    def __init__(self, project: str, toc_path: Path):
        self.project, self.alias, self.nodes, self.edges = project, {}, [], []
        try:
            toc = yaml.safe_load(toc_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            toc = {}
        rel = str(toc_path)
        self._walk(toc.get("nodes") or {}, "", None, 1, rel)

    def _walk(self, tree: dict, prefix: str, parent: str | None, depth: int, rel: str):
        for key, spec in (tree or {}).items():
            nid = f"{prefix}.{key}" if prefix else str(key)
            spec = spec if isinstance(spec, dict) else {}
            self.alias[nid] = nid
            for a in spec.get("aliases") or []:
                self.alias[str(a)] = nid
            self.nodes.append(Node(
                id=node_node_id(self.project, nid), kind="node", project=self.project, path=rel,
                title=str(spec.get("label") or key), status=str(spec.get("status") or "active"),
                payload={"aliases": [str(a) for a in (spec.get("aliases") or [])], "summary": str(spec.get("summary") or ""),
                         "order": spec.get("order"), "depth": depth}))
            if parent:
                self.edges.append(Edge(node_node_id(self.project, nid), node_node_id(self.project, parent), "member_of",
                                       source_ref="toc"))
            self._walk(spec.get("children") or {}, nid, nid, depth + 1, rel)

    def resolve(self, raw: str) -> str:
        return self.alias.get(raw, raw)


class VaultScanner:
    name = "vault"

    def __init__(self, vault: Path, project: str | None = None):
        self.vault = Path(vault).resolve()
        self.project = project

    def collect(self) -> ProviderOutput:
        legacy = rules   # the index builder's rules; the local name is kept so the comments below still read true
        legacy._TOC_CACHE.clear()   # toc node ids are cached per project name; another vault in the same process must not reuse them
        out = ProviderOutput()
        files = legacy.discover_kb_files(self.vault, self.project)
        # taxonomy per project (global + projects/<p>/_meta/taxonomy.yaml), exactly as the legacy full build does
        tax_cache: dict[str, dict | None] = {}

        def taxonomy_for(project: str):
            key = self.project or project
            if key not in tax_cache:
                tax_cache[key] = legacy.load_taxonomy(self.vault, key)
            return tax_cache[key]
        allf = _Files(self.vault)
        bodies: dict[str, str] = {}   # rel → body text, for the links pass

        # pass 1 — parse, emit nodes and chunks, gather the name → node maps used to resolve links
        docs: list[tuple[str, str, dict, str]] = []  # (node_id, project, fm, rel)
        by_name: dict[str, list[str]] = {}
        for doc_seq, (abs_path, rel, project) in enumerate(files):
            try:
                raw = Path(abs_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            fm, body = legacy.parse_frontmatter(raw)
            if not isinstance(fm, dict):
                fm = {}
            bodies[rel] = _split_body(raw)[1]
            allf.register(rel, fm)
            taxonomy = taxonomy_for(project)
            info = dict(legacy.parse_kb_path(rel, taxonomy) or {})
            # --- the legacy index builder's rules, kept identical so the store answers like the index ---
            parts = rel.split("/")
            is_archive = len(parts) > 2 and parts[0] == "projects" and parts[2] in ("sessions", "tasks", "signals")   # signals: DEC-2026-11-01-14
            is_planning = len(parts) > 2 and parts[0] == "projects" and parts[2] == "planning"
            if is_archive:
                info.update({"category": "archive", "topic": parts[2], "category_order": 99, "topic_order": 99})
                meta_bits = [f"{key}: {fm.get(key)}" for key in ("topic", "orders", "kb_updates", "decisions_made", "session_id", "nodes", "doc_change") if fm.get(key)]
                head = "\n".join(body.splitlines()[:40])
                body = ("\n".join(meta_bits) + "\n\n" + head) if meta_bits else head
            elif is_planning:
                info.update({"category": "planning", "topic": parts[3] if len(parts) > 4 else "", "category_order": 98, "topic_order": 99})
                from kb.planning import layer_of   # original · refined · source · audit (DEC-2026-11-01-04·05)
                info["planning_layer"] = layer_of(rel, fm, self.vault)
            elif len(parts) > 2 and parts[0] == "projects" and parts[2] == "reviews":
                info.update({"category": "review", "topic": "", "category_order": 98, "topic_order": 99})
            doc_type = fm.get("type", "unknown")
            indexed = True
            if taxonomy and not is_archive:
                if ((taxonomy.get("document_types") or {}).get(doc_type) or {}).get("indexed") is False:
                    indexed = False
            # taxonomy validation, exactly as the legacy index builder ran it per file: archive gets the node checks only
            node_ids = legacy.load_toc_node_ids(self.vault, project)
            if is_archive:
                diagnostics = legacy.validate_node_fields(taxonomy, fm, node_ids)
            else:
                diagnostics = legacy.validate_document(taxonomy, fm, info, rel, line_count=len(raw.splitlines()), node_ids=node_ids)
            nid = doc_node_id(rel)
            stem = Path(rel).stem
            title = str(fm.get("title", Path(abs_path).name))
            tags_raw = fm.get("tags", [])
            node = Node(
                id=nid, kind=_kind_for(rel), project=project, path=rel, title=title,
                status=str(fm.get("status", "active")),
                updated=str(fm.get("updated") or fm.get("created") or ""),
                revision=legacy.file_sha256(Path(abs_path)),
                payload={
                    "type": str(doc_type), "stable_id": str(fm.get("id") or ""),
                    "updated_fm": str(fm.get("updated") or ""),   # frontmatter `updated` alone; Node.updated falls back to created
                    "created": str(fm.get("created", "")),
                    "tags": tags_raw if isinstance(tags_raw, list) else [str(tags_raw)] if tags_raw else [],
                    "nodes": [str(n) for n in _as_list(fm.get("nodes"))],
                    "covers": fm.get("covers") if isinstance(fm.get("covers"), dict) else {},
                    "implementation_status": _implementation(fm)[0],
                    "implementation_reviewed": _implementation_reviewed(fm),
                    "doc_change": str(fm.get("doc_change") or ""),
                    "category": str(info.get("category") or ""), "topic": str(info.get("topic") or ""),
                    "planning_layer": str(info.get("planning_layer") or ""),
                    "subtopic": str(info.get("subtopic") or ""), "section_name": str(info.get("section_name") or ""),
                    "category_order": info.get("category_order", 99), "topic_order": info.get("topic_order", 99),
                    "section_order": info.get("section_order", 0), "page_order": fm.get("page_order", 99),
                    "doc_seq": doc_seq, "links_raw": _links_raw(legacy, fm, body if indexed else ""),
                    "sources": [legacy._link_target(s) for s in _as_list(fm.get("sources"))],
                    "origin": str(fm.get("source") or ""),
                    "related": [legacy._link_target(s) for s in _as_list(fm.get("related"))],
                    "supersedes": [body_link_target(str(s).strip("[]")) for s in _as_list(fm.get("supersedes"))],
                    "superseded_by": [body_link_target(str(s).strip("[]")) for s in _as_list(fm.get("superseded_by"))],
                    "superseded_by_raw": fm.get("superseded_by") if isinstance(fm.get("superseded_by"), (str, list)) else None,
                    "aliases": [str(a) for a in _as_list(fm.get("aliases"))],
                    "indexed": indexed, "generated": is_generated(rel), "history": is_history(rel),
                    "discovered": True, "diagnostics": [list(d) for d in diagnostics],
                    "status_declared": "status" in fm,   # Node.status defaults to active when the frontmatter has no status
                },
            )
            out.nodes.append(node)
            docs.append((nid, project, fm, rel))
            for name in {stem, str(fm.get("id") or ""), *[str(a) for a in _as_list(fm.get("aliases"))]}:
                if name:
                    by_name.setdefault(name, []).append(nid)
            if indexed:
                locale = str(fm.get("locale") or "")
                doc_title = str(fm.get("title", ""))
                doc_tags = " ".join(str(x) for x in tags_raw) if isinstance(tags_raw, list) else str(tags_raw or "")
                # a section over the encoder window is cut into parts; every other section is kept as is (MB-strata-kit-2026-056)
                sections = split_over_tokens(legacy.chunk_by_heading(body),
                                             lambda ch: embed_text(doc_title, ch["heading"], ch["content"]))
                for i, ch in enumerate(sections):
                    meta = {"heading_level": ch["heading_level"], "line_start": ch["line_start"],
                            "line_end": ch["line_end"], "char_count": len(ch["content"])}
                    if "part" in ch:
                        meta.update(part=ch["part"], own_chars=ch["own_chars"])
                    out.chunks.append(Chunk(nid, i, ch["content"], locale, heading=ch["heading"], title=doc_title, tags=doc_tags,
                                            meta=meta))

        # every other markdown file in the vault is a doc node too (link gate scope), without chunks
        discovered = {rel for _, rel, _ in files}
        for rel in allf.md:
            if rel in discovered or rel.startswith(OUTSIDE_LINK_GATE) or (self.project and not rel.startswith(f"projects/{self.project}/")):
                continue
            try:
                raw = (self.vault / rel).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            fm, body = _split_body(raw)
            bodies[rel] = body
            allf.register(rel, fm)
            parts = rel.split("/")
            project = parts[1] if parts[0] == "projects" and len(parts) > 2 else "vault"
            for name in {Path(rel).stem, str(fm.get("id") or ""), *[str(a) for a in _as_list(fm.get("aliases"))]}:
                if name:
                    by_name.setdefault(name, []).append(doc_node_id(rel))
            out.nodes.append(Node(
                id=doc_node_id(rel), kind=_kind_for(rel), project=project, path=rel,
                title=str(fm.get("title") or Path(rel).stem), status=str(fm.get("status") or "active"),
                updated=str(fm.get("updated") or fm.get("created") or ""), revision=legacy.file_sha256(self.vault / rel),
                payload={"type": str(fm.get("type") or ""), "stable_id": str(fm.get("id") or ""),
                         "updated_fm": str(fm.get("updated") or ""), "origin": str(fm.get("source") or ""),
                         "tags": [], "nodes": [], "covers": {}, "doc_change": "",
                         "category": "", "topic": "", "sources": [], "related": [],
                         "supersedes": [body_link_target(str(s).strip("[]")) for s in _as_list(fm.get("supersedes"))],
                         "superseded_by": [body_link_target(str(s).strip("[]")) for s in _as_list(fm.get("superseded_by"))],
                         "superseded_by_raw": fm.get("superseded_by") if isinstance(fm.get("superseded_by"), (str, list)) else None,
                         "aliases": [str(a) for a in _as_list(fm.get("aliases"))],
                         "indexed": False, "generated": is_generated(rel), "history": is_history(rel),
                         "discovered": False, "diagnostics": []}))
        for rel in sorted(bodies):
            out.edges.extend(body_link_edges(self.vault, allf, rel, bodies[rel]))

        # topic nodes per project (toc.yaml is a vault source)
        tocs: dict[str, _Toc] = {}
        projects = sorted({p for _, p, _, _ in docs} | ({self.project} if self.project else set()))
        for project in projects:
            toc_path = self.vault / "projects" / project / "_meta" / "toc.yaml"
            if toc_path.is_file():
                t = _Toc(project, toc_path)
                tocs[project] = t
                out.nodes.extend(t.nodes)
                out.edges.extend(t.edges)

        def resolve(name: str, project: str) -> str:
            # "[[target]] (annotation)" is common in kb_updates — the author declared the link, keep it
            m = WIKILINK_RE.search(name)
            name = m.group(1).strip() if m else legacy._link_target(name)
            # "tasks/x/design.md (note)", "guides/runbook.md §6" — a path with a remark still names one document
            # "TRACK_BOARD.md B8·B9" — a board row id after the path is a remark too
            name = re.sub(r"\s+(\(.*\)|§.*|[A-Z]\d+(?:·[A-Z]\d+)*)$", "", name).strip()
            if DEC_RE.match(name):
                return decision_node_id(project, name)
            if "/" in name and not name.endswith(".md"):
                # "tasks/x/reconcile.sql", "knowledge-base/guides/secret-ledger.yaml" — a non-markdown file the session produced
                for base in (self.vault / "projects" / project, self.vault):
                    if (base / name).is_file():
                        return f"file:{(base / name).relative_to(self.vault).as_posix()}"
            pm = PROJECT_DEC_RE.match(name)   # "shop-web DEC-2026-10-21-01": a decision recorded in another project
            if pm:
                return decision_node_id(pm.group(1), pm.group(2))
            hits = by_name.get(name) or []
            if not hits and ("/" in name or name.endswith(".md")):
                hits = by_name.get(Path(name).stem) or []
            same = [h for h in hits if h.startswith(f"doc:projects/{project}/")]
            if same:
                return same[0]
            if len(hits) == 1:
                return hits[0]
            return f"ref:{name}"

        # pass 2 — declared edges
        for nid, project, fm, rel in docs:
            toc = tocs.get(project)
            for raw in _as_list(fm.get("nodes")):
                target = toc.resolve(str(raw)) if toc else str(raw)
                out.edges.append(Edge(nid, node_node_id(project, target), "member_of", source_ref="nodes"))
            for field, kind in FIELD_EDGES.items():
                for raw in _as_list(fm.get(field)):
                    raw = str(raw).strip()
                    if not raw:
                        continue
                    if field == "orders":
                        dst = f"order:{project}:{order_id(raw)}"
                    else:
                        dst = resolve(raw, project)
                        if dst.startswith("ref:") and _is_free_text(raw):
                            continue   # "신규 KB 11건 + 패턴 3건" — an unresolved note, not a reference
                    out.edges.append(Edge(nid, dst, kind, source_ref=field))
            for raw in _as_list(fm.get("superseded_by")):
                raw = str(raw).strip()
                if raw:
                    out.edges.append(Edge(resolve(raw, project), nid, "supersedes", source_ref="superseded_by"))
            for raw in _implementation(fm)[1]:   # planning → the as-built spec it is realised in (DEC-2026-10-29-09)
                dst = resolve(raw, project)
                if not (dst.startswith("ref:") and _is_free_text(raw)):
                    out.edges.append(Edge(nid, dst, "implementation", source_ref="implementation.spec"))
            covers = fm.get("covers") if isinstance(fm.get("covers"), dict) else {}
            for ckind in legacy.COVERS_KINDS:
                for pattern in _as_list(covers.get(ckind)):
                    out.edges.append(Edge(nid, f"code:{project}:{ckind}:{pattern}", "covers", source_ref=f"covers.{ckind}"))
        return out
