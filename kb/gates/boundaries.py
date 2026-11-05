"""Three-boundary checker from Liquibase changelogs and entity mappings (DEC-2026-11-05-02, MB-strata-kit-2026-051).

The boundaries a layer cannot cover (core/docs/<locale>/architecture/prepaid-structure.md): data ownership,
cross-domain writes, cross-domain reads. Their rule ids and check ids are declared in core/rules/layer-rules.yaml
`boundaries:`. This module runs the checks that read the schema history rather than the bytecode:

  boundary.data_ownership.changelog       a table (or view) created by more than one module of the same database,
                                          or a module's changelog altering / writing a table another module of the
                                          same database owns
  boundary.data_ownership.entity_mapping  an @Table/@Entity in one module mapping a table another module of the same
                                          database owns
  boundary.cross_domain_read.fdw_window   foreign tables (postgres_fdw) are read windows, never ownership; they are
                                          listed per consumer → provider database, and judged only when the project has
                                          decided the canonical window for that pair (`read_windows`)

The two bytecode checks (direct DataSource construction, Feign writes outside listeners) live in the ArchUnit
template profiles/backend.kotlin-spring-cqrs/enforcement/StrataBoundaryRulesTest.kt.template.

Project input is the `boundaries:` section of the project layer map, found like the edit hooks find it:
repo .strata/layer-map.yaml → repo archunit/layer-map.yaml → Tier P layer-map.yaml (or --map FILE).

  boundaries:
    modules:                      # build module directory (repo-relative, or a unique directory name) → database
      domain/order-entity: orders
      domain/billing-entity: { db: billing, changelogs: [src/main/resources/db/changelog-master.yaml] }
    fdw_servers: { orders_fdw: orders }   # foreign server → database it reads, when the DDL uses a placeholder
    read_windows:                 # a person's decision per consumer db → provider db: feign | fdw (absent = undecided)
      billing: { orders: null }
    default_schema: public
    exemptions:
      - id: BX-2026-11-05-01
        rule: boundary.data_ownership.changelog   # a check id, or a boundary id that covers its checks
        table: audit_logs                         # any of table · module · path (substring of the file path); all given must match
        reason: "..."
        decision: DEC-…                           # or sunset: 2026-12-31 (a past ISO date is no longer honoured) / a condition
        status: active                            # retired = ignored

The layer map's top-level `excluded:` (code being replaced — the same paths the layer check and the ArchUnit boundary
template leave out) applies here too: a finding whose file path matches an excluded path is not listed or counted as a
finding; it is counted per module under `excluded_by_module`. That is separate from exemptions, which waive a finding a
person has decided to allow. Paths match like the edit hook: substring, with a source path's src/main/kotlin/ matched
piece by piece.

A declaration that evaluates nothing is not clean (MB-strata-kit-2026-057): a module whose directory is not there, a
module with no changelog, an explicit changelog path that does not resolve, or no table found in any module is listed
under `indeterminate` and printed as `[strata] indeterminate: …` lines ('judgement impossible — the declaration does
not match the code').

Every run also prints the coverage line: the share of build modules with a changelog that boundaries.modules names
("경계 대응표가 덮는 비율 67% (미대응 1모듈 …)") — a module the map does not name is not judged at all.

Exit code: 0 clean, 1 findings (not exempted, not excluded), 2 configuration error, 3 no findings but part of the
declaration evaluated nothing (indeterminate). The harness grade is applied by the wrapper:
`python3 -m kb enforce run --family boundaries -- python3 -m kb boundaries check` (family default advisory).

  python3 -m kb boundaries check [--project DIR] [--map FILE] [--json]
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

BOUNDARIES = ("boundary.data_ownership", "boundary.cross_domain_write", "boundary.cross_domain_read")
CHECK_CHANGELOG = "boundary.data_ownership.changelog"
CHECK_ENTITY = "boundary.data_ownership.entity_mapping"
CHECK_FDW = "boundary.cross_domain_read.fdw_window"
KNOWN_CHECKS = (CHECK_CHANGELOG, CHECK_ENTITY, CHECK_FDW,
                "boundary.data_ownership.direct_datasource", "boundary.cross_domain_write.feign_write")
WINDOWS = ("feign", "fdw")
REPO_LAYER_MAPS = (Path(".strata") / "layer-map.yaml", Path("archunit") / "layer-map.yaml")   # same order as the edit hooks
SKIP_DIRS = {".git", "build", "out", "target", "node_modules", ".gradle", ".idea"}
CHANGELOG_EXT = (".sql", ".yml", ".yaml", ".xml")
MASTER_RE = re.compile(r"(^|[._-])changelog[._-]?master|^db\.changelog\.|^changelog\.(ya?ml|xml)$", re.I)


# ---------------------------------------------------------------- configuration

def find_map(project: Path) -> Path | None:
    for rel in REPO_LAYER_MAPS:
        if (project / rel).is_file():
            return project / rel
    try:
        from kb.legacy.strata_paths import resolve_tier_p
        tier = resolve_tier_p(project)
    except (ValueError, ImportError):
        tier = None
    if tier is not None and (Path(tier.root) / "layer-map.yaml").is_file():
        return Path(tier.root) / "layer-map.yaml"
    return None


@dataclass
class Module:
    key: str
    rel: str          # repo-relative directory
    db: str
    changelogs: list[str] = field(default_factory=list)


@dataclass
class Exemption:
    id: str
    rule: str
    table: str | None
    module: str | None
    path: str | None

    def covers(self, check: str, table: str | None, module: str | None, path: str | None) -> bool:
        if not (check == self.rule or check.startswith(self.rule + ".")):
            return False
        if self.table is not None and self.table != table:
            return False
        if self.module is not None and self.module != module:
            return False
        if self.path is not None and self.path not in (path or ""):
            return False
        return True


@dataclass
class Config:
    modules: list[Module]
    fdw_servers: dict[str, str]
    read_windows: dict[str, dict[str, str | None]]
    default_schema: str
    exemptions: list[Exemption]
    problems: list[str]
    missing: list[str] = field(default_factory=list)    # module keys whose directory was not found


def _module_dirs(project: Path) -> dict[str, list[str]]:
    """Directory name → repo-relative directories that look like build modules (have src/)."""
    out: dict[str, list[str]] = {}
    for root, dirs, _ in os.walk(project):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".") and d != "src"]
        if (Path(root) / "src").is_dir() and Path(root) != project:
            out.setdefault(Path(root).name, []).append(Path(root).relative_to(project).as_posix())
    return out


def _module_dir(project: Path, key: str, index: dict[str, list[str]] | None) -> str | None:
    if "/" in key.strip("/"):
        return key.strip("/") if (project / key).is_dir() else None
    hits = (index or {}).get(key, [])
    return hits[0] if len(hits) == 1 else None


def load_config(project: Path, raw: dict, today: date | None = None) -> Config:
    today = today or date.today()
    b = raw.get("boundaries") if isinstance(raw, dict) else None
    problems: list[str] = []
    if not isinstance(b, dict):
        return Config([], {}, {}, "public", [], ["layer map has no boundaries: section"])
    modules, missing = [], []
    index = _module_dirs(project) if any("/" not in str(k).strip("/") for k in (b.get("modules") or {})) else None
    for key, v in (b.get("modules") or {}).items():
        db, cls = (v, []) if isinstance(v, str) else ((v or {}).get("db"), list((v or {}).get("changelogs") or []))
        if not isinstance(db, str) or not db:
            problems.append(f"boundaries.modules.{key}: no database")
            continue
        rel = _module_dir(project, str(key), index)
        if rel is None:
            problems.append(f"boundaries.modules.{key}: module directory not found (or not unique)")
            missing.append(str(key))
            continue
        modules.append(Module(str(key), rel, db, cls))
    windows = {}
    for consumer, per in (b.get("read_windows") or {}).items():
        windows[str(consumer)] = {}
        for provider, w in (per or {}).items():
            if w is not None and w not in WINDOWS:
                problems.append(f"boundaries.read_windows.{consumer}.{provider}: {w!r} is not one of {', '.join(WINDOWS)} — treated as undecided")
                w = None
            windows[str(consumer)][str(provider)] = w
    exemptions = []
    for i, e in enumerate(b.get("exemptions") or []):
        if not isinstance(e, dict):
            problems.append(f"boundaries.exemptions[{i}]: not a mapping")
            continue
        eid = str(e.get("id") or f"#{i}")
        if e.get("status") == "retired":
            continue
        rule = e.get("rule")
        if rule not in BOUNDARIES and rule not in KNOWN_CHECKS:
            problems.append(f"exemption {eid}: rule {rule!r} is not a boundary or check id — not honoured")
            continue
        if not str(e.get("reason") or "").strip():
            problems.append(f"exemption {eid}: no reason — not honoured")
            continue
        if not (e.get("decision") or e.get("sunset")):
            problems.append(f"exemption {eid}: needs decision or sunset — not honoured")
            continue
        sunset = e.get("sunset")
        if not e.get("decision") and sunset is not None:
            d = sunset if isinstance(sunset, date) else None
            if d is None and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(sunset)):
                d = date.fromisoformat(str(sunset))
            if d is not None and d < today:
                problems.append(f"exemption {eid}: sunset {d} has passed — not honoured")
                continue
        if not any(e.get(k) for k in ("table", "module", "path")):
            problems.append(f"exemption {eid}: names no table, module or path — not honoured")
            continue
        exemptions.append(Exemption(eid, rule, _norm_name(str(e["table"]), str(b.get("default_schema") or "public")) if e.get("table") else None,
                                    e.get("module"), e.get("path")))
    return Config(modules, {str(k): str(v) for k, v in (b.get("fdw_servers") or {}).items()}, windows,
                  str(b.get("default_schema") or "public"), exemptions, problems, missing)


# ---------------------------------------------------------------- SQL parsing

IDENT = r'(?:"[^"]+"|[A-Za-z_][\w$]*)'
QNAME = rf"{IDENT}(?:\s*\.\s*{IDENT})?"


def _unquote(part: str) -> str:
    part = part.strip()
    return part[1:-1] if part.startswith('"') and part.endswith('"') else part.lower()


def _norm_name(name: str, default_schema: str) -> str:
    parts = [_unquote(p) for p in re.findall(IDENT, name)]
    if len(parts) == 2 and parts[0] == default_schema.lower():
        parts = parts[1:]
    return ".".join(parts)


_TOKEN_RX = re.compile(r"'(?:[^']|'')*'|--[^\n]*|/\*.*?\*/", re.S)


def _strip_comments(sql: str) -> str:
    """Remove -- and /* */ comments (Liquibase --changeset/--rollback lines too) keeping string literals and line numbers."""
    def keep(m: re.Match) -> str:
        t = m.group(0)
        if t.startswith("'"):
            return t
        return "\n" * t.count("\n") if t.startswith("/*") else ""
    return _TOKEN_RX.sub(keep, sql)


@dataclass
class Event:
    kind: str          # create | create_view | drop | rename | alter | dml | foreign | server
    name: str
    file: str
    line: int
    new: str | None = None
    server: str | None = None
    remote: str | None = None


DML_STOP = {"set", "only", "cascade", "restrict", "no", "of", "nowait", "skip"}
_SQL_PATTERNS = [
    ("foreign", re.compile(rf"\bcreate\s+foreign\s+table\s+(?:if\s+not\s+exists\s+)?(?P<n>{QNAME})(?P<rest>.*?)(?:;|$)", re.I | re.S)),
    ("create", re.compile(rf"\bcreate\s+(?:(?:global|local)\s+)?(?P<tmp>temp\s+|temporary\s+)?(?:unlogged\s+)?table\s+(?:if\s+not\s+exists\s+)?(?P<n>{QNAME})", re.I)),
    ("create_view", re.compile(rf"\bcreate\s+(?:or\s+replace\s+)?(?:materialized\s+)?(?:recursive\s+)?view\s+(?:if\s+not\s+exists\s+)?(?P<n>{QNAME})", re.I)),
    ("rename", re.compile(rf"\balter\s+(?:materialized\s+view|view|table)\s+(?:if\s+exists\s+)?(?:only\s+)?(?P<n>{QNAME})\s+rename\s+to\s+(?P<new>{IDENT})", re.I)),
    ("alter", re.compile(rf"\balter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?(?P<n>{QNAME})", re.I)),
    ("drop", re.compile(rf"\bdrop\s+(?:foreign\s+table|materialized\s+view|view|table)\s+(?:if\s+exists\s+)?(?P<list>{QNAME}(?:\s*,\s*{QNAME})*)", re.I)),
    ("dml", re.compile(rf"(?:^|[;(]|\bthen\b|\bbegin\b|\bas\b)\s*(?:insert\s+into|update|delete\s+from)\s+(?:only\s+)?(?P<n>{QNAME})", re.I | re.M)),
    ("import", re.compile(rf"\bimport\s+foreign\s+schema\s+(?P<remote>{IDENT})\s+(?:limit\s+to\s*\((?P<lim>[^)]*)\)\s*)?(?:except\s*\([^)]*\)\s*)?from\s+server\s+(?P<srv>{IDENT})\s+into\s+(?P<local>{IDENT})", re.I)),
    ("server", re.compile(rf"\bcreate\s+server\s+(?:if\s+not\s+exists\s+)?(?P<n>{IDENT})(?P<rest>.*?)(?:;|$)", re.I | re.S)),
]


_STRING_RX = re.compile(r"'(?:[^']|'')*'")


def _mask_strings(sql: str) -> str:
    """Blank string literal contents (same length, newlines kept) so statements are only matched in code."""
    return _STRING_RX.sub(lambda m: "'" + re.sub(r"[^\n]", "_", m.group(0)[1:-1]) + "'", sql)


def parse_sql(text: str, file: str, default_schema: str, base_line: int = 1) -> list[Event]:
    original = _strip_comments(text)
    sql = _mask_strings(original)   # statements are matched here; option values ('…') are read from `original`
    found: list[tuple[int, Event]] = []

    starts = [m.end() for m in re.finditer(r"\n", sql)]

    def line_of(pos: int) -> int:
        return base_line + bisect.bisect_right(starts, pos)

    for kind, rx in _SQL_PATTERNS:
        for m in rx.finditer(sql):
            if "${" in m.group(0)[:200] and kind not in ("server", "foreign"):
                continue
            ln = line_of(m.start())
            if kind == "foreign":
                rest = original[m.start("rest"):m.end("rest")]
                srv = re.search(rf"\bserver\s+(?P<s>{IDENT})", rest, re.I)
                remote = re.search(r"\btable_name\s+'([^']+)'", rest, re.I)
                found.append((m.start(), Event("foreign", _norm_name(m.group("n"), default_schema), file, ln,
                                               server=_unquote(srv.group("s")) if srv else None,
                                               remote=remote.group(1) if remote else None)))
            elif kind == "create":
                if m.group("tmp"):
                    continue
                found.append((m.start(), Event("create", _norm_name(m.group("n"), default_schema), file, ln)))
            elif kind == "create_view":
                found.append((m.start(), Event("create_view", _norm_name(m.group("n"), default_schema), file, ln)))
            elif kind == "rename":
                old = _norm_name(m.group("n"), default_schema)
                new = _unquote(m.group("new"))
                if "." in old:
                    new = old.rsplit(".", 1)[0] + "." + new
                found.append((m.start(), Event("rename", old, file, ln, new=new)))
            elif kind == "alter":
                if re.match(r"\s+rename\s+to\b", sql[m.end():m.end() + 40], re.I):
                    continue
                found.append((m.start(), Event("alter", _norm_name(m.group("n"), default_schema), file, ln)))
            elif kind == "drop":
                for part in re.findall(QNAME, m.group("list")):
                    if part.lower() in ("cascade", "restrict"):
                        continue
                    found.append((m.start(), Event("drop", _norm_name(part, default_schema), file, ln)))
            elif kind == "dml":
                name = m.group("n")
                if name.lower() in DML_STOP:
                    continue
                found.append((m.start(), Event("dml", _norm_name(name, default_schema), file, ln)))
            elif kind == "import":
                srv = _unquote(m.group("srv"))
                names = [_unquote(x) for x in re.findall(IDENT, m.group("lim") or "")] or ["*"]
                for t in names:
                    found.append((m.start(), Event("foreign", _norm_name(t, default_schema) if t != "*" else f"{_unquote(m.group('local'))}.*",
                                                   file, ln, server=srv, remote=f"{_unquote(m.group('remote'))}.{t}")))
            elif kind == "server":
                db = re.search(r"\bdbname\s+'([^']+)'", original[m.start("rest"):m.end("rest")], re.I)
                found.append((m.start(), Event("server", _unquote(m.group("n")), file, ln,
                                               remote=db.group(1) if db and "${" not in db.group(1) else None)))
    # dynamic SQL with a literal statement (EXECUTE 'DROP TABLE …' in a DO block) runs like the statement itself
    for m in re.finditer(r"\bexecute\s+('(?:[^']|'')*')", sql, re.I):
        inner = original[m.start(1) + 1:m.end(1) - 1].replace("''", "'")
        found += [(m.start(), e) for e in parse_sql(inner, file, default_schema, line_of(m.start(1)))]
    found.sort(key=lambda x: x[0])
    return [e for _, e in found]


# ---------------------------------------------------------------- Liquibase changelog walking

def _candidates(ref: str, module_dir: Path, here: Path, relative: bool) -> list[Path]:
    """Liquibase paths: relative to the changelog file, to the module (gradle working directory) or to the classpath root
    (src/main/resources; a leading / or classpath: means the classpath)."""
    ref = ref.strip()
    if ref.startswith("classpath:"):
        ref = ref[len("classpath:"):]
    bare = ref.lstrip("/")
    res = module_dir / "src" / "main" / "resources"
    cands = [here.parent / bare] if relative else []
    if ref.startswith("/"):
        cands.append(Path(ref))
    return cands + [module_dir / bare, res / bare, here.parent / bare]


def _resolve(ref: str, module_dir: Path, here: Path, relative: bool) -> Path | None:
    return next((c.resolve() for c in _candidates(ref, module_dir, here, relative) if c.is_file()), None) if ref else None


def _resolve_dir(ref: str, module_dir: Path, here: Path, relative: bool) -> Path | None:
    return next((c.resolve() for c in _candidates(ref, module_dir, here, relative) if c.is_dir()), None) if ref else None


class Walker:
    """Follows a module's changelog masters in Liquibase order; each physical file is read once."""

    def __init__(self, module_dir: Path, project: Path, default_schema: str):
        self.module_dir, self.project, self.default_schema = module_dir, project, default_schema
        self.seen: set[Path] = set()
        self.events: list[Event] = []
        self.problems: list[str] = []

    def rel(self, p: Path) -> str:
        try:
            return p.resolve().relative_to(self.project.resolve()).as_posix()
        except ValueError:
            return p.as_posix()

    def visit(self, path: Path) -> None:
        path = path.resolve()
        if path in self.seen:
            return
        self.seen.add(path)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            self.problems.append(f"{self.rel(path)}: {e}")
            return
        suffix = path.suffix.lower()
        if suffix == ".sql":
            self.events += parse_sql(text, self.rel(path), self.default_schema)
        elif suffix in (".yml", ".yaml"):
            self._yaml(path, text)
        elif suffix == ".xml":
            self._xml(path, text)

    def _include_all(self, d: Path) -> None:
        for p in sorted(x for x in d.rglob("*") if x.is_file() and x.suffix.lower() in CHANGELOG_EXT):
            self.visit(p)

    def _yaml(self, path: Path, text: str) -> None:
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as e:
            self.problems.append(f"{self.rel(path)}: YAML {str(e).splitlines()[0]}")
            return
        items = (doc or {}).get("databaseChangeLog") if isinstance(doc, dict) else None
        if not isinstance(items, list):
            return
        lines = text.splitlines()
        for it in items:
            if not isinstance(it, dict):
                continue
            if isinstance(it.get("include"), dict):
                inc = it["include"]
                p = _resolve(str(inc.get("file") or ""), self.module_dir, path, bool(inc.get("relativeToChangelogFile")))
                if p:
                    self.visit(p)
                else:
                    self.problems.append(f"{self.rel(path)}: include {inc.get('file')!r} not found")
            elif isinstance(it.get("includeAll"), dict):
                inc = it["includeAll"]
                d = _resolve_dir(str(inc.get("path") or ""), self.module_dir, path, bool(inc.get("relativeToChangelogFile")))
                if d:
                    self._include_all(d)
            elif isinstance(it.get("changeSet"), dict):
                for ch in it["changeSet"].get("changes") or []:
                    if isinstance(ch, dict):
                        for ctype, body in ch.items():
                            self._change(path, ctype, body if isinstance(body, dict) else {}, lines)

    def _xml(self, path: Path, text: str) -> None:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            self.problems.append(f"{self.rel(path)}: XML {e}")
            return
        lines = text.splitlines()
        for el in root.iter():
            tag = el.tag.rsplit("}", 1)[-1]
            rel = el.get("relativeToChangelogFile") == "true"
            if tag == "include":
                p = _resolve(el.get("file") or "", self.module_dir, path, rel)
                if p:
                    self.visit(p)
                else:
                    self.problems.append(f"{self.rel(path)}: include {el.get('file')!r} not found")
            elif tag == "includeAll":
                d = _resolve_dir(el.get("path") or "", self.module_dir, path, rel)
                if d:
                    self._include_all(d)
            elif tag == "sql":
                self.events += parse_sql(el.text or "", self.rel(path), self.default_schema, _line_hint(lines, (el.text or "").strip()[:40]))
            else:
                self._change(path, tag, dict(el.attrib), lines)

    def _change(self, path: Path, ctype: str, body: dict, lines: list[str]) -> None:
        def name(key: str) -> str | None:
            v = body.get(key)
            if not v:
                return None
            s = body.get("schemaName")
            return _norm_name(f'"{s}"."{v}"' if s else f'"{v}"', self.default_schema)

        f = self.rel(path)
        if ctype == "sqlFile":
            p = _resolve(str(body.get("path") or ""), self.module_dir, path, bool(body.get("relativeToChangelogFile")))
            if p:
                self.visit(p)
            else:
                self.problems.append(f"{f}: sqlFile {body.get('path')!r} not found")
        elif ctype == "sql":
            sql = body.get("sql") if isinstance(body.get("sql"), str) else ""
            self.events += parse_sql(sql, f, self.default_schema, _line_hint(lines, sql.strip()[:40]))
        elif ctype == "createTable" and name("tableName"):
            self.events.append(Event("create", name("tableName"), f, _line_hint(lines, str(body["tableName"]))))
        elif ctype == "createView" and name("viewName"):
            self.events.append(Event("create_view", name("viewName"), f, _line_hint(lines, str(body["viewName"]))))
        elif ctype in ("dropTable", "dropView") and name("tableName" if ctype == "dropTable" else "viewName"):
            n = name("tableName" if ctype == "dropTable" else "viewName")
            self.events.append(Event("drop", n, f, _line_hint(lines, n.split(".")[-1])))
        elif ctype in ("renameTable", "renameView"):
            old, new = ("oldTableName", "newTableName") if ctype == "renameTable" else ("oldViewName", "newViewName")
            if name(old) and body.get(new):
                o = name(old)
                n = str(body[new])
                self.events.append(Event("rename", o, f, _line_hint(lines, str(body[old])),
                                         new=(o.rsplit(".", 1)[0] + "." + n) if "." in o else n))
        elif ctype in ("addColumn", "dropColumn", "renameColumn", "modifyDataType", "addForeignKeyConstraint",
                       "addUniqueConstraint", "createIndex", "addNotNullConstraint", "addPrimaryKey") and name("tableName" if "tableName" in body else "baseTableName"):
            n = name("tableName" if "tableName" in body else "baseTableName")
            self.events.append(Event("alter", n, f, _line_hint(lines, n.split(".")[-1])))
        elif ctype in ("insert", "update", "delete", "loadData", "loadUpdateData") and name("tableName"):
            self.events.append(Event("dml", name("tableName"), f, _line_hint(lines, str(body["tableName"]))))


def _line_hint(lines: list[str], needle: str) -> int:
    if needle:
        for i, ln in enumerate(lines, 1):
            if needle in ln:
                return i
    return 1


def changelog_files(module_dir: Path) -> list[Path]:
    res = module_dir / "src" / "main" / "resources"
    if not res.is_dir():
        return []
    out = []
    for root, dirs, files in os.walk(res):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        if not re.search(r"liquibase|changelog", root.replace(str(res), ""), re.I):
            continue
        out += [Path(root) / f for f in sorted(files) if f.lower().endswith(CHANGELOG_EXT)]
    return out


def module_events(project: Path, mod: Module, default_schema: str, missing: list[str] | None = None
                  ) -> tuple[list[Event], list[str], list[str]]:
    """(events in Liquibase order, problems, changelog files no master reached). `missing`, when given, receives the
    explicit changelog paths that do not resolve."""
    mdir = project / mod.rel
    w = Walker(mdir, project, default_schema)
    files = changelog_files(mdir)
    if mod.changelogs:
        resolved = [(c, _resolve(c, mdir, mdir / "x", False)) for c in mod.changelogs]
        if missing is not None:
            missing += [c for c, r in resolved if r is None]
        roots = [r for _, r in resolved]
    else:
        roots = sorted((p for p in files if MASTER_RE.search(p.name)), key=lambda p: (len(p.name), p.as_posix()))
    roots = [r for r in roots if r]
    if roots:
        for r in roots:
            w.visit(r)
        unreached = [w.rel(p) for p in files if p.resolve() not in w.seen and p.suffix.lower() == ".sql"]
    else:
        for p in files:
            w.visit(p)
        unreached = []
    return w.events, w.problems, unreached


@dataclass
class Owned:
    kind: str     # table | view
    file: str
    line: int


def replay(events: list[Event]) -> tuple[dict[str, Owned], list[Event], dict[str, str | None]]:
    """End state of one module: owned objects, foreign tables (read windows), servers → database."""
    owned: dict[str, Owned] = {}
    foreign: dict[str, Event] = {}
    servers: dict[str, str | None] = {}
    for e in events:
        if e.kind in ("create", "create_view"):
            owned.setdefault(e.name, Owned("table" if e.kind == "create" else "view", e.file, e.line))
        elif e.kind == "foreign":
            foreign[e.name] = e
        elif e.kind == "drop":
            owned.pop(e.name, None)
            foreign.pop(e.name, None)
        elif e.kind == "rename" and e.new:
            if e.name in owned:
                owned[e.new] = owned.pop(e.name)
            elif e.name in foreign:
                foreign[e.new] = foreign.pop(e.name)
        elif e.kind == "server":
            servers[e.name] = e.remote or servers.get(e.name)
    return owned, list(foreign.values()), servers


# ---------------------------------------------------------------- entity mappings

ENTITY_RX = re.compile(r"@(?:jakarta\.persistence\.|javax\.persistence\.)?Entity\b")
TABLE_RX = re.compile(r"@(?:[\w.]+\.)?Table\s*(?:\((?P<args>[^)]*)\))?")
CLASS_RX = re.compile(r"\b(?:data\s+|open\s+|abstract\s+|sealed\s+|final\s+|public\s+)*class\s+(?P<c>\w+)")


def _snake(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()


@dataclass
class Mapping:
    table: str
    file: str
    line: int
    derived: bool


def entity_mappings(project: Path, mod: Module, default_schema: str) -> list[Mapping]:
    out = []
    for lang in ("kotlin", "java"):
        src = project / mod.rel / "src" / "main" / lang
        if not src.is_dir():
            continue
        for p in sorted(src.rglob("*.kt" if lang == "kotlin" else "*.java")):
            text = p.read_text(encoding="utf-8", errors="ignore")
            if "Table" not in text and "Entity" not in text:
                continue
            rel = p.relative_to(project).as_posix()
            for cm in CLASS_RX.finditer(text):
                head = text[max(0, cm.start() - 600):cm.start()]
                # only the annotations directly above this class (stop at the previous class or closing brace)
                head = re.split(r"\bclass\s+\w+|^\}", head, flags=re.M)[-1]
                tm = None
                for m in TABLE_RX.finditer(head):
                    tm = m
                line = text.count("\n", 0, cm.start()) + 1
                if tm is not None:
                    args = tm.group("args") or ""
                    nm = re.search(r'\b(?:name|value)\s*=\s*"([^"]+)"', args) or re.match(r'\s*"([^"]+)"', args)
                    sch = re.search(r'\bschema\s*=\s*"([^"]+)"', args)
                    if nm:
                        q = f'"{sch.group(1)}"."{nm.group(1)}"' if sch else nm.group(1)
                        out.append(Mapping(_norm_name(q, default_schema), rel, line, False))
                        continue
                    if ENTITY_RX.search(head) or "@Table" in head:
                        out.append(Mapping(_snake(cm.group("c")), rel, line, True))
                elif ENTITY_RX.search(head):
                    out.append(Mapping(_snake(cm.group("c")), rel, line, True))
    return out


# ---------------------------------------------------------------- the check

@dataclass
class Finding:
    check: str
    message: str
    table: str | None
    module: str
    path: str
    line: int
    exempted_by: str | None = None
    excluded: bool = False


def excluded_path(path: str, excluded: list[str]) -> bool:
    """A file path under a layer map `excluded:` entry — the fragments around src/main/kotlin/ appear in order (the hook's
    and the ArchUnit templates' matching)."""
    for entry in excluded:
        frags = [f for f in str(entry).split("src/main/kotlin/") if f]
        cursor, ok = 0, bool(frags)
        for f in frags:
            i = path.find(f, cursor)
            if i < 0:
                ok = False
                break
            cursor = i + len(f)
        if ok:
            return True
    return False


def check(project: Path, raw_map: dict, today: date | None = None) -> dict:
    cfg = load_config(project, raw_map, today)
    per_mod = {}
    problems = list(cfg.problems)
    unreached_all = {}
    servers: dict[str, str | None] = dict(cfg.fdw_servers)
    indeterminate = [f"boundaries.modules.{k}: module directory not found — its ownership is not judged" for k in cfg.missing]
    for mod in cfg.modules:
        missing_cl: list[str] = []
        events, probs, unreached = module_events(project, mod, cfg.default_schema, missing_cl)
        indeterminate += [f"{mod.key}: changelog {c} not found — not read" for c in missing_cl]
        if not mod.changelogs and not changelog_files(project / mod.rel):
            indeterminate.append(f"{mod.key}: no changelog under src/main/resources (liquibase/changelog directory) — its ownership is not judged")
        problems += [f"{mod.key}: {p}" for p in probs]
        if unreached:
            unreached_all[mod.key] = unreached
        owned, foreign, srv = replay(events)
        for k, v in srv.items():
            servers.setdefault(k, v)
            if servers[k] is None:
                servers[k] = v
        per_mod[mod.key] = (mod, events, owned, foreign, entity_mappings(project, mod, cfg.default_schema))

    owners: dict[tuple[str, str], list[str]] = {}
    for key, (mod, _e, owned, _f, _m) in per_mod.items():
        for t in owned:
            owners.setdefault((mod.db, t), []).append(key)

    findings: list[Finding] = []
    for (db, t), mods in sorted(owners.items()):
        if len(mods) > 1:
            for k in mods:
                o = per_mod[k][2][t]
                findings.append(Finding(CHECK_CHANGELOG, f"{o.kind} {t} (db {db}) is created by {len(mods)} modules: {', '.join(mods)}",
                                        t, k, o.file, o.line))
    for key, (mod, events, owned, foreign, maps) in per_mod.items():
        foreign_names = {f.name for f in foreign}
        seen = set()
        for e in events:
            if e.kind not in ("alter", "dml") or e.name in owned or e.name in foreign_names:
                continue
            others = [m for m in owners.get((mod.db, e.name), []) if m != key]
            if others and (e.name, e.kind) not in seen:
                seen.add((e.name, e.kind))
                what = "alters" if e.kind == "alter" else "writes rows of"
                findings.append(Finding(CHECK_CHANGELOG, f"changelog of {key} {what} {e.name}, owned by {', '.join(others)} (db {mod.db})",
                                        e.name, key, e.file, e.line))
        for m in maps:
            if m.table in owned or m.table in foreign_names:
                continue
            others = [x for x in owners.get((mod.db, m.table), []) if x != key]
            if others:
                findings.append(Finding(CHECK_ENTITY, f"{key} maps {m.table}{' (name from the class)' if m.derived else ''}, owned by {', '.join(others)} (db {mod.db})",
                                        m.table, key, m.file, m.line))

    windows = []
    for key, (mod, _e, _o, foreign, _m) in per_mod.items():
        for f in foreign:
            provider = servers.get(f.server or "") if f.server else None
            decided = cfg.read_windows.get(mod.db, {}).get(provider) if provider else None
            windows.append({"consumer_module": key, "consumer_db": mod.db, "foreign_table": f.name, "server": f.server,
                            "provider_db": provider, "remote": f.remote, "file": f.file, "line": f.line, "canonical": decided})
            if decided == "feign":
                findings.append(Finding(CHECK_FDW, f"{key} reads {provider} through foreign table {f.name} (server {f.server}); "
                                        f"the canonical window for {mod.db} → {provider} is feign", f.name, key, f.file, f.line))
    for w in windows:
        if w["provider_db"] is None:
            problems.append(f"{w['consumer_module']}: foreign server {w['server']!r} has no database (add boundaries.fdw_servers)")
    problems = list(dict.fromkeys(problems))
    if per_mod and not any(v[2] for v in per_mod.values()):
        indeterminate.append("어느 모듈의 changelog 에서도 테이블을 찾지 못함 — 소유 판정 대상이 없음")

    excluded = [str(x) for x in (raw_map.get("excluded") or []) if x] if isinstance(raw_map.get("excluded"), list) else []
    excluded_by_module: dict[str, int] = {}
    for f in findings:
        if excluded and excluded_path(f.path, excluded):
            f.excluded = True
            excluded_by_module[f.module] = excluded_by_module.get(f.module, 0) + 1
            continue
        for ex in cfg.exemptions:
            if ex.covers(f.check, f.table, f.module, f.path):
                f.exempted_by = ex.id
                break

    unowned = {}
    for key, (mod, _e, owned, foreign, maps) in per_mod.items():
        fn = {f.name for f in foreign}
        miss = sorted({m.table for m in maps if not m.derived and m.table not in owned and m.table not in fn and not owners.get((mod.db, m.table))})
        if miss:
            unowned[key] = miss
    pairs = {}
    for w in windows:
        pairs.setdefault((w["consumer_db"], w["provider_db"]), set()).add(w["consumer_module"])
    undecided = sorted(f"{c} → {p}" for (c, p) in pairs if p and cfg.read_windows.get(c, {}).get(p) is None)
    return {
        "coverage": coverage(project, [m.rel for m in cfg.modules], excluded),
        "modules": {k: {"db": v[0].db, "dir": v[0].rel, "owned": len(v[2]), "foreign": len(v[3]), "mappings": len(v[4])} for k, v in per_mod.items()},
        "findings": [f.__dict__ for f in findings],
        "excluded_by_module": dict(sorted(excluded_by_module.items())),
        "read_windows": windows,
        "undecided_read_windows": undecided,
        "mapped_without_owner": unowned,
        "unreached_changelogs": unreached_all,
        "problems": problems,
        "indeterminate": indeterminate,
    }


def coverage(project: Path, declared: list[str], excluded: list[str] | None = None) -> dict:
    """Share of the build modules that have a changelog which boundaries.modules names (MB-strata-kit-2026-057 step 2).
    A module with a changelog the map does not name is not judged at all; one under the layer map's excluded: is counted
    apart."""
    with_cl, excl = [], []
    for rels in _module_dirs(project).values():
        for rel in rels:
            if not changelog_files(project / rel):
                continue
            (excl if excluded and excluded_path(rel + "/", excluded) else with_cl).append(rel)
    declared_set = set(declared)
    unmapped = sorted(r for r in with_cl if r not in declared_set)
    n = len(with_cl)
    return {"modules_with_changelog": n, "mapped": n - len(unmapped), "unmapped": len(unmapped), "excluded": len(excl),
            "unmapped_modules": unmapped, "percent": round(100.0 * (n - len(unmapped)) / n, 1) if n else 0.0}


def coverage_line(cov: dict) -> str:
    tail = f": {', '.join(cov['unmapped_modules'][:8])}{' …' if len(cov['unmapped_modules']) > 8 else ''}" if cov["unmapped_modules"] else ""
    return (f"[strata] coverage: 경계 대응표가 덮는 비율 {cov['percent']:.0f}% (미대응 {cov['unmapped']}모듈{tail} · "
            f"changelog 가 있는 모듈 {cov['modules_with_changelog']}개 중 {cov['mapped']}개"
            + (f", 제외 범위 {cov['excluded']}개 따로" if cov["excluded"] else "") + ")")


def render(report: dict) -> str:
    out = []
    live = [f for f in report["findings"] if not f["exempted_by"] and not f.get("excluded")]
    ex = [f for f in report["findings"] if f["exempted_by"]]
    excl = report.get("excluded_by_module") or {}
    out.append(f"boundaries: {len(live)} finding(s), {len(ex)} exempted, {sum(excl.values())} in excluded scope — modules {len(report['modules'])}")
    if report.get("coverage"):
        out.append(coverage_line(report["coverage"]))
    for k, m in report["modules"].items():
        out.append(f"  {k:<28} db {m['db']:<14} owned {m['owned']:>4}  foreign {m['foreign']:>3}  mappings {m['mappings']:>4}")
    for title, rows in (("findings", live), ("exempted", ex)):
        if rows:
            out.append(f"== {title}")
            for f in rows:
                tail = f"  [exempted by {f['exempted_by']}]" if f["exempted_by"] else ""
                out.append(f"  {f['check']}  {f['message']}\n      {f['path']}:{f['line']}{tail}")
    if excl:
        out.append("== excluded scope (layer map excluded: — counted, not listed): "
                   + ", ".join(f"{k} {v}" for k, v in excl.items()))
    if report["read_windows"]:
        out.append("== read windows (foreign tables — reads, not ownership)")
        for w in report["read_windows"]:
            canon = w["canonical"] or "undecided"
            out.append(f"  {w['consumer_module']} ({w['consumer_db']}) → {w['provider_db'] or '?'}: {w['foreign_table']} "
                       f"via {w['server']} [{canon}]  {w['file']}:{w['line']}")
    if report["undecided_read_windows"]:
        out.append("== read window pairs with no canonical choice (boundaries.read_windows — a person decides): "
                   + ", ".join(report["undecided_read_windows"]))
    if report["mapped_without_owner"]:
        n = sum(len(v) for v in report["mapped_without_owner"].values())
        out.append(f"== info: {n} mapped table(s) no changelog of the same database creates")
        for k, v in report["mapped_without_owner"].items():
            out.append(f"  {k}: {', '.join(v[:10])}{' …' if len(v) > 10 else ''}")
    if report["unreached_changelogs"]:
        n = sum(len(v) for v in report["unreached_changelogs"].values())
        out.append(f"== info: {n} SQL file(s) under a changelog directory no master includes (not read)")
        for k, v in report["unreached_changelogs"].items():
            out.append(f"  {k}: {', '.join(x.rsplit('/', 1)[-1] for x in v[:6])}{' …' if len(v) > 6 else ''}")
    if report["problems"]:
        out.append("== configuration")
        out += [f"  {p}" for p in report["problems"]]
    if report.get("indeterminate"):
        out.append("== 판정 불가 — 선언이 코드와 맞지 않음 (깨끗함이 아님)")
        out += [f"[strata] indeterminate: {x}" for x in report["indeterminate"]]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kb boundaries", description=__doc__.split("\n\n")[0])
    ap.add_argument("action", choices=["check"])
    ap.add_argument("--project", default=".")
    ap.add_argument("--map", help="layer map file with a boundaries: section (default: the hook lookup order)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    project = Path(a.project).resolve()
    mp = Path(a.map) if a.map else find_map(project)
    if mp is None or not mp.is_file():
        print("boundaries: no layer map (.strata/layer-map.yaml, archunit/layer-map.yaml or Tier P) — nothing to check", file=sys.stderr)
        return 2
    raw = yaml.safe_load(mp.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict) or not isinstance(raw.get("boundaries"), dict):
        print(f"boundaries: {mp} has no boundaries: section", file=sys.stderr)
        return 2
    report = check(project, raw)
    report["map"] = str(mp)
    print(json.dumps(report, ensure_ascii=False, indent=2) if a.json else render(report))
    if not report["modules"]:
        return 2
    if any(not f["exempted_by"] and not f["excluded"] for f in report["findings"]):
        return 1
    return 3 if report["indeterminate"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
