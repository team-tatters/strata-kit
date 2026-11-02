"""Decision-record provider — Tier P DEC-*.yaml records → decision nodes and their declared edges.

Status comes from kb.decisions.derive_status (superseded is derived from the other records'
`supersedes`, never written into the superseded record). Edges:
  decision --supersedes--> decision        (record.supersedes)
  decision --member_of-->  topic node      (record.nodes)
  session  --decisions_made--> decision    (record.session, when that session file exists in the vault)
"""
from __future__ import annotations

import re
import hashlib
from pathlib import Path

from kb.decisions import _dec_ids, derive_status
from kb.legacy.gen_decision_notes import load_records
from kb.paths import resolve_tier_p
from kb.store import Chunk, Edge, Node, ProviderOutput


def decision_node_id(project: str, dec_id: str) -> str:
    return f"decision:{project}:{dec_id}"


class DecisionRecords:
    name = "decisions"

    def __init__(self, project_dirs: list[Path], vault: Path | None = None,
                 names: dict[str, str] | None = None):
        """project_dirs: repos (or detached project roots) whose Tier P holds the records.
        names: project_dir → vault project name (default: directory basename)."""
        self.project_dirs = [Path(p).resolve() for p in project_dirs]
        self.vault = Path(vault).resolve() if vault else None
        self.names = {Path(k).resolve(): v for k, v in (names or {}).items()}

    def _toc(self, project: str):
        if not self.vault:
            return None
        path = self.vault / "projects" / project / "_meta" / "toc.yaml"
        if not path.is_file():
            return None
        from kb.providers.vault_scanner import _Toc
        return _Toc(project, path)

    def collect(self) -> ProviderOutput:
        out = ProviderOutput()
        for pdir in self.project_dirs:
            tier = resolve_tier_p(pdir)
            if tier is None or not tier.decisions_dir.is_dir():
                continue
            project = self.names.get(pdir, pdir.name)
            toc = self._toc(project)
            records = list(load_records(tier.decisions_dir))
            derived = derive_status(records)
            for f, body in records:
                rid = str(body["id"])
                status, superseded_by = derived[rid]
                nid = decision_node_id(project, rid)
                try:
                    rel = str(f.relative_to(pdir))
                except ValueError:
                    rel = str(f)
                topic = str(body.get("topic") or body.get("title") or "").strip()
                out.nodes.append(Node(
                    id=nid, kind="decision", project=project, path=rel, title=topic, status=status,
                    updated=str(body.get("date") or ""), revision=hashlib.sha256(f.read_bytes()).hexdigest(),
                    payload={"summary": str(body.get("summary") or "").strip(), "session": str(body.get("session") or ""),
                             "verification_tier": str(body.get("verification_tier") or ""),
                             "affects": [str(a) for a in (body.get("affects") or [])],
                             "nodes": [str(n) for n in (body.get("nodes") or [])],
                             "supersedes": _dec_ids(body.get("supersedes")),
                             "superseded_by": superseded_by,
                             "mirror": f"projects/{project}/decisions/{rid}.md"}))
                for old in _dec_ids(body.get("supersedes")):
                    out.edges.append(Edge(nid, decision_node_id(project, old), "supersedes", source_ref="record.supersedes"))
                for n in body.get("nodes") or []:
                    target = toc.resolve(str(n)) if toc else str(n)   # toc aliases apply to records as to documents
                    out.edges.append(Edge(nid, f"node:{project}:{target}", "member_of", source_ref="record.nodes"))
                sess = str(body.get("session") or "").strip()
                if sess and self.vault and (self.vault / "projects" / project / "sessions" / f"{sess}.md").is_file():
                    out.edges.append(Edge(f"doc:projects/{project}/sessions/{sess}.md", nid, "decisions_made",
                                          source_ref="record.session"))
                seq = 0
                for key in ("summary", "decision", "reason", "context", "consequences"):
                    text = str(body.get(key) or "").strip()
                    if text:
                        head = topic if key == "summary" else key
                        out.chunks.append(Chunk(nid, seq, text, heading=head, title=topic))
                        seq += 1
        return out
