"""Code graph provider — the kit's own thin import/definition provider (strata DEC-2026-10-28-05).

For every reachable project repo it emits code nodes for source directories, files and type-level symbols, and
edges with a confidence: file→dir and symbol→file `member_of` (extracted), file→file `imports` (extracted; a
wildcard or package-level import is `inferred` and points at the directory), test-file→file `tests` (inferred).
This is what resolves the vault's `covers` targets (`code:<project>:paths:<dir>/`, `code:<project>:symbols:<Name>`)
and answers two of the four graph questions cheaply: deps(file) and impact(files). tests_for(file) is the inferred
`tests` edge; flow(request) stays with an external adapter. No external tool is required; languages: Kotlin · Java ·
TypeScript/JavaScript · Python. Only git-tracked files are read.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path, PurePosixPath

from kb.store import Edge, Node, ProviderOutput

SOURCE_EXT = {".kt": "kotlin", ".kts": "kotlin", ".java": "java", ".ts": "ts", ".tsx": "ts", ".js": "js", ".jsx": "js",
              ".mjs": "js", ".cjs": "js", ".py": "python", ".go": "go", ".rs": "rust"}
SKIP_PARTS = {"node_modules", "build", "dist", ".next", "out", "coverage", "target", ".gradle", "generated", "__pycache__", ".venv", "vendor"}
TS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

JVM_DEF_RE = re.compile(r"^\s*(?:(?:public|internal|private|protected|abstract|open|sealed|data|enum|annotation|value|inline|final|static|inner|expect|actual)\s+)*"
                        r"(class|interface|object|typealias|record)\s+(\w+)", re.M)
JVM_PKG_RE = re.compile(r"^\s*package\s+([\w.]+)", re.M)
JVM_IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?(\w+(?:\.\w+)*)(\.\*)?", re.M)
TS_DEF_RE = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?(?:(?:async\s+)?function\*?|class|interface|type|enum|const|let|var)\s+(\w+)", re.M)   # module-scope declarations, exported or not
TS_IMPORT_RE = re.compile(r"(?:^|\n)\s*(?:import|export)\s+(?:[^'\"\n;]*?\s+from\s+)?['\"]([^'\"\n]+)['\"]|\bimport\(\s*['\"]([^'\"\n]+)['\"]\s*\)|\brequire\(\s*['\"]([^'\"\n]+)['\"]\s*\)")
PY_DEF_RE = re.compile(r"^(class|def)\s+(\w+)", re.M)
PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import\s+([\w*, ]+)|import\s+([\w.]+))", re.M)


def code_id(project: str, kind: str, key: str) -> str:
    return f"code:{project}:{kind}:{key}"


def is_test_path(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    stem = name.rsplit(".", 1)[0]
    return ("test" in parts or "tests" in parts or "__tests__" in parts or ".test." in name or ".spec." in name
            or stem.startswith("test_") or stem.endswith(("_test", "Test", "Tests", "IT", "Spec")))


def tracked_source_files(repo: Path) -> list[str]:
    try:
        out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    files = []
    for raw in out.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "replace")
        if PurePosixPath(rel).suffix not in SOURCE_EXT:
            continue
        if any(p in SKIP_PARTS for p in rel.split("/")[:-1]):
            continue
        files.append(rel)
    return sorted(files)


class _Repo:
    """One repository's tracked source files, their text, package roots and name maps."""

    def __init__(self, project: str, root: Path):
        self.project, self.root = project, root
        self.files = tracked_source_files(root)
        self.fileset = set(self.files)
        self.text: dict[str, str] = {}
        self.lang = {f: SOURCE_EXT[PurePosixPath(f).suffix] for f in self.files}
        # JVM: package → files, FQN(type) → file
        self.pkg_files: dict[str, list[str]] = defaultdict(list)
        self.fqn: dict[str, list[str]] = defaultdict(list)                        # a multi-module repo may define one FQN in several modules
        self.pkg_symbols: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))   # package → type name → files (same-package references need no import)
        # TS: workspace package name → dir, package roots (dirs with package.json)
        self.pkg_dirs: dict[str, str] = {}
        self.pkg_roots: set[str] = set()
        self.defs: dict[str, list[tuple[str, int, str]]] = defaultdict(list)   # symbol → [(file, line, type)]
        self._load()

    def _load(self) -> None:
        for rel in self.files:
            try:
                self.text[rel] = (self.root / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                self.text[rel] = ""
        for rel in self._tracked("package.json"):
            d = str(PurePosixPath(rel).parent)
            d = "" if d == "." else d
            self.pkg_roots.add(d)
            try:
                name = json.loads((self.root / rel).read_text(encoding="utf-8")).get("name")
            except (OSError, ValueError):
                name = None
            if name and isinstance(name, str):
                self.pkg_dirs.setdefault(name, d)
        for rel, text in self.text.items():
            lang = self.lang[rel]
            if lang in ("kotlin", "java"):
                m = JVM_PKG_RE.search(text)
                pkg = m.group(1) if m else ""
                self.pkg_files[pkg].append(rel)
                for dm in JVM_DEF_RE.finditer(text):
                    name = dm.group(2)
                    self.defs[name].append((rel, text.count("\n", 0, dm.start()) + 1, dm.group(1)))
                    self.fqn[f"{pkg}.{name}" if pkg else name].append(rel)
                    self.pkg_symbols[pkg][name].append(rel)
            elif lang in ("ts", "js"):
                for dm in TS_DEF_RE.finditer(text):
                    self.defs[dm.group(1)].append((rel, text.count("\n", 0, dm.start()) + 1, "export"))
            elif lang == "python":
                for dm in PY_DEF_RE.finditer(text):
                    self.defs[dm.group(2)].append((rel, text.count("\n", 0, dm.start()) + 1, dm.group(1)))

    def _tracked(self, basename: str) -> list[str]:
        try:
            out = subprocess.run(["git", "-C", str(self.root), "ls-files", "-z", "--", f"*{basename}", basename],
                                 capture_output=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            return []
        return [r.decode("utf-8", "replace") for r in out.split(b"\0") if r and r.decode("utf-8", "replace").split("/")[-1] == basename
                and not any(p in SKIP_PARTS for p in r.decode("utf-8", "replace").split("/")[:-1])]

    # -- resolution ----------------------------------------------------------
    def _file_candidates(self, base: str) -> str | None:
        """base without extension (or a dir) → the tracked file it names, if any."""
        base = os.path.normpath(base).replace("\\", "/")
        if base.startswith("./"):
            base = base[2:]
        if base in self.fileset:
            return base
        for ext in TS_EXTS:
            if base + ext in self.fileset:
                return base + ext
        for ext in TS_EXTS:
            if f"{base}/index{ext}" in self.fileset:
                return f"{base}/index{ext}"
        return None

    def package_root_of(self, rel: str) -> str:
        d = str(PurePosixPath(rel).parent)
        d = "" if d == "." else d
        while True:
            if d in self.pkg_roots:
                return d
            if not d:
                return ""
            d = str(PurePosixPath(d).parent)
            d = "" if d == "." else d

    def resolve_ts(self, rel: str, spec: str) -> tuple[str, str] | None:
        """(target id key, confidence): a file (extracted) or a package/dir (inferred). None = external."""
        if spec.startswith("."):
            f = self._file_candidates(str(PurePosixPath(rel).parent / spec))
            return (f, "extracted") if f else None
        root = self.package_root_of(rel)
        if spec.startswith("src/"):   # tsconfig "src/*" alias of the app
            f = self._file_candidates(f"{root}/{spec}" if root else spec)
            return (f, "extracted") if f else None
        parts = spec.split("/")
        for n in (2, 1):   # scoped name has two parts
            name = "/".join(parts[:n])
            if name in self.pkg_dirs:
                d = self.pkg_dirs[name]
                sub = "/".join(parts[n:])
                for cand in ([f"{d}/{sub}", f"{d}/src/{sub}"] if sub else [f"{d}/index", f"{d}/src/index"]):
                    f = self._file_candidates(cand)
                    if f:
                        return f, "extracted"
                return (d + "/" if d else ""), "inferred"
        return None

    @staticmethod
    def closest(rel: str, candidates: list[str]) -> str:
        """The candidate sharing the longest path prefix with rel — the same gradle/npm module wins when a
        package or FQN exists in several modules."""
        if len(candidates) == 1:
            return candidates[0]
        parts = rel.split("/")

        def common(c: str) -> int:
            n = 0
            for a, b in zip(parts, c.split("/")):
                if a != b:
                    break
                n += 1
            return n
        return max(candidates, key=lambda c: (common(c), -len(c), c))

    def resolve_jvm(self, rel: str, fqn: str, wildcard: bool) -> tuple[str, str] | None:
        if wildcard:
            files = self.pkg_files.get(fqn)
            if not files:
                return None
            d = str(PurePosixPath(self.closest(rel, files)).parent)
            return (d + "/", "inferred")
        probe = fqn
        while probe:
            if probe in self.fqn:
                return self.closest(rel, self.fqn[probe]), "extracted"
            if "." not in probe:
                break
            probe = probe.rsplit(".", 1)[0]
        return None

    def resolve_py(self, rel: str, module: str, names: list[str]) -> list[tuple[str, str]]:
        out = []
        bases = [""]
        d = str(PurePosixPath(rel).parent)
        if d != ".":
            bases.append(d)
        mod = module.lstrip(".")
        dots = len(module) - len(mod)
        if dots:
            up = d if d != "." else ""
            for _ in range(dots - 1):
                up = str(PurePosixPath(up).parent) if up else ""
                up = "" if up == "." else up
            bases = [up]
        path = mod.replace(".", "/")
        for base in bases:
            prefix = f"{base}/" if base else ""
            for cand in ([f"{prefix}{path}.py", f"{prefix}{path}/__init__.py"] if path else []):
                if cand in self.fileset:
                    out.append((cand, "extracted"))
                    break
            for name in names:
                cand = f"{prefix}{path}/{name}.py" if path else f"{prefix}{name}.py"
                if cand in self.fileset:
                    out.append((cand, "extracted"))
            if out:
                break
        return out

    def imports_of(self, rel: str) -> list[tuple[str, str]]:
        text, lang = self.text[rel], self.lang[rel]
        found: list[tuple[str, str]] = []
        if lang in ("kotlin", "java"):
            for m in JVM_IMPORT_RE.finditer(text):
                r = self.resolve_jvm(rel, m.group(1), bool(m.group(2)))
                if r:
                    found.append(r)
            # same-package types are visible without an import: a word match is an inferred dependency
            m = JVM_PKG_RE.search(text)
            pkg = m.group(1) if m else ""
            for name, targets in self.pkg_symbols.get(pkg, {}).items():
                target = self.closest(rel, targets)
                if target != rel and re.search(rf"\b{re.escape(name)}\b", text):
                    found.append((target, "inferred"))
        elif lang in ("ts", "js"):
            for m in TS_IMPORT_RE.finditer(text):
                spec = m.group(1) or m.group(2) or m.group(3)
                if not spec:
                    continue
                r = self.resolve_ts(rel, spec)
                if r:
                    found.append(r)
        elif lang == "python":
            for m in PY_IMPORT_RE.finditer(text):
                if m.group(3):
                    found.extend(self.resolve_py(rel, m.group(3), []))
                else:
                    names = [n.strip() for n in m.group(2).split(",") if n.strip() and n.strip() != "*"]
                    found.extend(self.resolve_py(rel, m.group(1), names))
        return [(t, c) for t, c in found if t != rel]


class CodeGraph:
    """Provider: code nodes and edges for every project dir with a git checkout."""
    name = "code"

    def __init__(self, project_dirs: list[Path]):
        self.project_dirs = [Path(d) for d in project_dirs]

    def collect(self) -> ProviderOutput:
        out = ProviderOutput()
        for d in self.project_dirs:
            if not (d / ".git").exists():
                continue
            self._collect_repo(_Repo(d.name, d.resolve()), out)
        return out

    def _collect_repo(self, repo: _Repo, out: ProviderOutput) -> None:
        p = repo.project
        dirs: dict[str, int] = defaultdict(int)
        edges: set[Edge] = set()
        for rel in repo.files:
            parent = str(PurePosixPath(rel).parent)
            parent = "" if parent == "." else parent
            if parent:
                dirs[parent] += 1
                d = parent
                while d:
                    up = str(PurePosixPath(d).parent)
                    up = "" if up == "." else up
                    if up:
                        dirs.setdefault(up, 0)
                        edges.add(Edge(code_id(p, "paths", d + "/"), code_id(p, "paths", up + "/"), "member_of", "extracted", "fs"))
                    d = up
            text = repo.text[rel]
            out.nodes.append(Node(
                id=code_id(p, "paths", rel), kind="code", project=p, path=rel, title=rel.split("/")[-1], status="active",
                revision=hashlib.sha256(text.encode("utf-8", "replace")).hexdigest(),
                payload={"kind": "file", "lang": repo.lang[rel], "test": is_test_path(rel), "lines": text.count("\n") + 1}))
            if parent:
                edges.add(Edge(code_id(p, "paths", rel), code_id(p, "paths", parent + "/"), "member_of", "extracted", "fs"))
            for target, conf in repo.imports_of(rel):
                key = target if not target.endswith("/") else target
                dst = code_id(p, "paths", key)
                edges.add(Edge(code_id(p, "paths", rel), dst, "imports", conf, "import"))
                if is_test_path(rel) and not target.endswith("/") and not is_test_path(target):
                    edges.add(Edge(code_id(p, "paths", rel), dst, "tests", "inferred", "import"))
        for d, n in dirs.items():
            out.nodes.append(Node(id=code_id(p, "paths", d + "/"), kind="code", project=p, path=d + "/", title=d.split("/")[-1],
                                  status="active", payload={"kind": "dir", "files": n}))
        for name, defs in repo.defs.items():
            files = sorted({f for f, _, _ in defs})
            out.nodes.append(Node(id=code_id(p, "symbols", name), kind="code", project=p, path=files[0], title=name, status="active",
                                  payload={"kind": "symbol", "files": files, "defs": [{"file": f, "line": ln, "type": t} for f, ln, t in defs][:20]}))
            for f in files:
                edges.add(Edge(code_id(p, "symbols", name), code_id(p, "paths", f), "member_of", "extracted", "def"))
        out.edges.extend(sorted(edges, key=lambda e: (e.src, e.dst, e.kind, e.source_ref)))
