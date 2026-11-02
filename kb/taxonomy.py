"""Taxonomy views for the MCP server (moved from strata-mcp). Loading reuses the index builder's merge rules
(kb.docrules) so every consumer sees the same taxonomy."""
from __future__ import annotations

from pathlib import Path

from kb import docrules


def load_taxonomy(vault: Path, project: str | None = None) -> dict | None:
    return docrules.load_taxonomy(Path(vault), project)


def category_info(taxonomy: dict | None) -> list[dict]:
    if not taxonomy:
        return []
    cats = taxonomy.get("categories", {})
    return sorted(
        [{"name": name, "label": cat.get("label", name), "order": cat.get("order", 99),
          "depth_limit": cat.get("depth_limit", 3),
          "allowed_types": (cat.get("defaults") or {}).get("allowed_types", []),
          "children": list((cat.get("children") or {}).keys())} for name, cat in cats.items()],
        key=lambda x: x["order"])


def document_types(taxonomy: dict | None) -> list[dict]:
    if not taxonomy:
        return []
    return [{"name": name, "label": t.get("label", name), "required_fields": t.get("required_fields", []),
             "max_lines": t.get("max_lines"), "indexed": t.get("indexed", True)}
            for name, t in (taxonomy.get("document_types") or {}).items()]
