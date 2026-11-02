"""Providers emit generated nodes, edges and chunks for the store (kb-engine.md § provider).

  VaultScanner     document · session · task · topic-node nodes, declared edges, heading chunks
  DecisionRecords  decision nodes from Tier P DEC-*.yaml records, supersedes · member_of · decisions_made
  Orders           order · task nodes from projects/*/tasks/**/_order.yaml and task-*.yaml
  CodeGraph        code nodes (dirs · files · type symbols) and imports · tests · member_of edges from each project repo (DEC-2026-10-28-05)

Declared edges carry confidence 'declared' and the frontmatter field (or record key) as source_ref.
Targets that do not resolve to a node are kept as 'ref:<name>' so gates can report them.
"""
from .code_graph import CodeGraph  # noqa: F401
from .decision_records import DecisionRecords  # noqa: F401
from .orders import Orders  # noqa: F401
from .vault_scanner import VaultScanner  # noqa: F401
