"""Glossary aliases for query expansion (MB-strata-kit-2026-056 step 2) — deterministic, no model.

The aliases are only what a glossary document already writes in its tables:
  | 집계행 / 활동데이터 | …      term cell 'A / B'      → {집계행, 활동데이터}
  | 협업자 (COLLABORATOR) | …   term cell 'A (B)'      → {협업자, COLLABORATOR}
  | 산정인자 | 배출계수, EF | …  a column headed 별칭 · 동의어 · alias(es) · synonym(s), split on , · ; ·
Members shorter than two characters are dropped ('존' would match 존재), and a group needs two members.

A query that names one member (at a word start, case-insensitive — '협업자를' names 협업자) gets the other members
added: OR'ed into the FTS expression, and named after the query text for the dense encoder.
"""
from __future__ import annotations

import re

ALIAS_HEADERS = {"별칭", "동의어", "alias", "aliases", "synonym", "synonyms"}
_SEP_ROW = re.compile(r"^\|?\s*:?-{3,}")
_ALIAS_SPLIT = re.compile(r"\s*[,·;]\s*")
_PAREN = re.compile(r"^(.*?)\s*[(（]([^)）]+)[)）]\s*$")


def _clean(cell: str) -> str:
    cell = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", r"\1", cell)
    return cell.replace("**", "").replace("`", "").strip()


def _cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _term_members(cell: str) -> list[str]:
    cell = _clean(cell)
    out: list[str] = []
    for part in re.split(r"\s+/\s+", cell):
        m = _PAREN.match(part)
        if m:
            out += [m.group(1).strip(), m.group(2).strip()]
        else:
            out.append(part.strip())
    return out


def parse_alias_groups(markdown: str) -> list[list[str]]:
    """Alias groups (ordered, de-duplicated) from every markdown table in the text."""
    groups: list[list[str]] = []
    header: list[str] | None = None
    prev_table = False
    for line in markdown.splitlines():
        is_row = line.strip().startswith("|")
        if not is_row:
            header, prev_table = None, False
            continue
        cells = _cells(line)
        if not prev_table:              # first row of a table is its header
            header, prev_table = [c.lower() for c in cells], True
            continue
        if _SEP_ROW.match(line.strip()):
            continue
        members = _term_members(cells[0]) if cells else []
        for i, h in enumerate(header or []):
            if i > 0 and h in ALIAS_HEADERS and i < len(cells):
                members += [_clean(a) for a in _ALIAS_SPLIT.split(cells[i]) if _clean(a)]
        seen, group = set(), []
        for m in members:
            if len(m) >= 2 and m.lower() not in seen:
                seen.add(m.lower())
                group.append(m)
        if len(group) >= 2:
            groups.append(group)
    return groups


class AliasIndex:
    def __init__(self, groups: list[list[str]] | None = None):
        self.groups = [list(g) for g in groups or []]
        self._pat = {m: re.compile(r"(?<!\w)" + re.escape(m), re.IGNORECASE) for g in self.groups for m in g}

    def __bool__(self) -> bool:
        return bool(self.groups)

    def _named(self, text: str, m: str) -> bool:
        return bool(self._pat[m].search(text))

    def expand(self, query: str) -> list[str]:
        """Members of the groups the query names that the query does not name yet, in glossary order."""
        out: list[str] = []
        for g in self.groups:
            if any(self._named(query, m) for m in g):
                out += [m for m in g if not self._named(query, m) and m not in out]
        return out

    def alternatives(self, word: str) -> list[str]:
        """For one query word: the other members of a group whose single-word member starts it."""
        out: list[str] = []
        for g in self.groups:
            hit = [m for m in g if " " not in m and word.lower().startswith(m.lower())]
            if hit:
                out += [m for m in g if m not in hit and m not in out]
        return out

    def dense_text(self, query: str) -> str:
        extra = self.expand(query)
        return f"{query} ({' · '.join(extra)})" if extra else query
