"""Order/task provider — projects/<p>/tasks/<date>/<nn>-<slug>/_order.yaml (or an older _order.md whose frontmatter
holds the same `order:` block) and task-*.yaml → nodes.

  order:<project>:<order.id>              kind order   (title, status, date; payload: goal, tasks, decisions)
  task:<project>:<order.id>/<task-NN>     kind task    (title, status; payload: layer, repo, files)
Edges (declared): task --member_of--> order, order --decisions_made--> decision:<project>:<DEC>,
                  task --decisions_made--> decision when a task names decisions.
Sessions already point at orders through their `orders:` frontmatter (vault scanner), so this provider
turns those dangling targets into nodes. Task markdown files under tasks/ are doc nodes of kind task
from the scanner and are left alone here.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from kb.store import Chunk, Edge, Node, ProviderOutput

DEC_RE = re.compile(r"DEC-\d{4}-\d{2}-\d{2}-\d{2}")


FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(\r?\n|\Z)", re.S)


def _load(path: Path) -> dict:
    """A YAML file, or the frontmatter of a markdown file (older orders were written as _order.md)."""
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            m = FM_RE.match(text)
            text = m.group(1) if m else ""
        data = yaml.safe_load(text)
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def order_files(tasks_dir: Path) -> list[Path]:
    """_order.yaml per folder; _order.md only where no yaml exists."""
    files = {f.parent: f for f in tasks_dir.rglob("_order.md")}
    files.update({f.parent: f for f in tasks_dir.rglob("_order.yaml")})
    return [files[k] for k in sorted(files)]


def _decisions(values) -> list[str]:
    out = []
    for v in values or []:
        m = DEC_RE.search(str(v))
        if m:
            out.append(m.group(0))
    return out


class Orders:
    name = "orders"

    def __init__(self, vault: Path, project: str | None = None):
        self.vault = Path(vault).resolve()
        self.project = project

    def collect(self) -> ProviderOutput:
        out = ProviderOutput()
        projects_dir = self.vault / "projects"
        if not projects_dir.is_dir():
            return out
        for pdir in sorted(d for d in projects_dir.iterdir() if d.is_dir()):
            if self.project and pdir.name != self.project:
                continue
            project = pdir.name
            for order_file in order_files(pdir / "tasks"):
                order = _load(order_file).get("order") or {}
                folder = order_file.parent
                oid = str(order.get("id") or f"{folder.parent.name}-{folder.name[:2]}")
                rel = str(order_file.relative_to(self.vault))
                onid = f"order:{project}:{oid}"
                tasks_meta = order.get("tasks") if isinstance(order.get("tasks"), list) else []
                out.nodes.append(Node(
                    id=onid, kind="order", project=project, path=rel, title=str(order.get("title") or folder.name),
                    status=str(order.get("status") or "unknown"), updated=str(order.get("date") or ""),
                    revision=hashlib.sha256(order_file.read_bytes()).hexdigest(),
                    payload={"mode": str(order.get("mode") or ""), "inline": bool(order.get("inline")),
                             "goal": str(order.get("goal") or "").strip(),
                             "tasks": [str(t.get("id") if isinstance(t, dict) else t) for t in tasks_meta],
                             "decisions": _decisions(order.get("decisions")),
                             "related_projects": [str(x) for x in (order.get("related_projects") or [])]}))
                for dec in _decisions(order.get("decisions")):
                    out.edges.append(Edge(onid, f"decision:{project}:{dec}", "decisions_made", source_ref="order.decisions"))
                text = "\n".join(x for x in (str(order.get("title") or ""), str(order.get("goal") or "").strip()) if x)
                if text:
                    out.chunks.append(Chunk(onid, 0, text, heading=str(order.get("title") or "")))
                for task_file in sorted(folder.glob("task-*.yaml")):
                    task = _load(task_file)
                    meta = task.get("task") if isinstance(task.get("task"), dict) else {}
                    tid_raw = str(meta.get("id") or task_file.stem)
                    tid = tid_raw.rsplit("/", 1)[-1] if "/" in tid_raw else tid_raw
                    tid = re.match(r"task-\d+", tid).group(0) if re.match(r"task-\d+", tid) else tid
                    tnid = f"task:{project}:{oid}/{tid}"
                    scope = task.get("scope") if isinstance(task.get("scope"), dict) else {}
                    out.nodes.append(Node(
                        id=tnid, kind="task", project=project, path=str(task_file.relative_to(self.vault)),
                        title=str(meta.get("title") or task_file.stem), status=str(task.get("status") or "unknown"),
                        updated=str(order.get("date") or ""), revision=hashlib.sha256(task_file.read_bytes()).hexdigest(),
                        payload={"order": oid, "layer": str(task.get("layer") or scope.get("module") or ""),
                                 "repo": str(scope.get("repo") or ""), "files": [str(f) for f in (task.get("files") or [])],
                                 "decisions": _decisions(task.get("decisions"))}))
                    out.edges.append(Edge(tnid, onid, "member_of", source_ref="task.order_ref"))
                    for dec in _decisions(task.get("decisions")):
                        out.edges.append(Edge(tnid, f"decision:{project}:{dec}", "decisions_made", source_ref="task.decisions"))
                    ttext = "\n".join(x for x in (str(meta.get("title") or ""), str((task.get("inputs") or {}).get("requirements") or "").strip()
                                                  if isinstance(task.get("inputs"), dict) else "") if x)
                    if ttext:
                        out.chunks.append(Chunk(tnid, 0, ttext, heading=str(meta.get("title") or "")))
        return out
