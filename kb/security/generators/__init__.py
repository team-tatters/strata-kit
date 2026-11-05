"""Inventory generators — each returns items with the six G1 values: name, version, environment, kind, source, identifier."""
from __future__ import annotations

SIX = ("name", "version", "environment", "kind", "source", "identifier")
ECOSYSTEM_SOURCE = {"npm": "osv", "pypi": "osv", "golang": "osv", "maven": "osv", "cratesio": "osv"}


def item(name: str, version: str, environment: str, kind: str, source: str, identifier: str, **extra) -> dict:
    d = {"name": name, "version": version, "environment": environment, "kind": kind, "source": source or "none",
         "identifier": identifier or "none"}
    d.update(extra)
    return d


def purl(ecosystem: str, name: str, version: str, namespace: str | None = None) -> str:
    if ecosystem == "npm" and name.startswith("@") and "/" in name:
        scope, rest = name[1:].split("/", 1)
        return f"pkg:npm/%40{scope}/{rest}@{version}"
    if ecosystem == "pypi":
        return f"pkg:pypi/{name.lower().replace('_', '-')}@{version}"
    if ecosystem == "maven":
        return f"pkg:maven/{namespace}/{name}@{version}" if namespace else f"pkg:maven/{name}@{version}"
    return f"pkg:{ecosystem}/{name}@{version}"
