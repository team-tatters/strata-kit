#!/usr/bin/env python3
"""Continuous measurement of strata-kit in use (DEC-2026-10-29-16, order 2026.10.29-14 task-07).

Collects, per project, numbers that already exist as a side effect of working, and keys them by the kit revision
that was current when each session started, so that kit revisions can be compared over time:

  revision  wizard verify of the project now: always-loaded bytes, inherited total, entry path bytes, must cards
  sessions  Claude Code transcripts (~/.claude/projects/<encoded project path>/*.jsonl), one row per session:
            duration, assistant turns, context of the first turn (what the session loaded before acting), tokens
            and turns before the first file edit (resume cost), tool calls, approvals by a person, denials by kind,
            tool errors, lines added/removed, skills invoked, cost
  evidence  .strata/local/verify/*.yaml: commands recorded, failed, unstable
  handoffs  vault projects/<p>/sessions/*.md: pending items (lines with 'blocker:')
  violations kb enforce ledger: runs with violations per family and grade, the last count
  git       commits and reverts in the project since the first collected session
  history   one summary per collection (evidence, handoffs, violations, git), so a collection can be compared with
            the one before it (kb signals candidates)

The transcript format is Claude Code's own and undocumented: unknown shapes are skipped, never guessed, and a
field that could not be read is absent rather than zero. Transcripts are deleted by Claude Code after its cleanup
period (30 days by default), so run this at least weekly; rows already in the vault file are kept.

Trends only compare kit revisions with each other. Whether strata helps at all is the baseline comparison:
the same fixed tasks run with tools/evals/run_isolated.sh (no guidance, no plugin) and with the strata plugin;
`session <transcript>` reads either output (stream-json or a saved session) with the same counters.

The kit revision of a session is read from the SessionStart header in its transcript (generated guidance, adapter
and kit revision as loaded); only a session without the header falls back to the kit commit current at its start.

Limits: a file edit made through Bash is not seen as an edit (only Edit/Write/MultiEdit/NotebookEdit are), so
turns_before_first_edit is high for sessions that edit with scripts; injection accuracy is not measured.

Usage:
  python3 tools/metrics.py collect <project> [--write]      # print (default) or merge into the vault measurement file
  python3 tools/metrics.py summary <project>                # medians per kit revision from the vault file
  python3 tools/metrics.py session <transcript.jsonl>       # one transcript's row (baseline runs, debugging)
"""
from __future__ import annotations
import argparse, json, os, re, statistics, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[1]
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
REVERT = re.compile(r"^(Revert\b|되돌림)")
# the SessionStart header line (tools/wizard.py header): what this session actually loaded (DEC-2026-10-29-19)
HEADER_REV = re.compile(r"core revision: (\S+) · adapter revision: (\S+) \(kit now: ([^)\\]+)\)")


def transcript_dir(project: Path, home: Path | None = None) -> Path:
    """Claude Code keys a project's transcripts by its absolute path with every non-alphanumeric character as '-'."""
    return (home or Path.home()) / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(project.resolve()))


def _ts(v) -> datetime | None:
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def session_row(path: Path) -> dict:
    """Counters for one transcript. Assistant lines repeat their usage once per content block: count each message id once."""
    row: dict = {"tool_calls": 0, "approvals_by_person": 0, "denials": {}, "tool_errors": 0, "skills": {}}
    seen, first_ts, last_ts, session_id = set(), None, None, None
    turns = out_tok = ctx_tok = 0
    edited = False
    for line in path.open(encoding="utf-8", errors="replace"):
        if "loaded" not in row and "core revision: " in line:
            h = HEADER_REV.search(line)
            if not h:   # a writer that escaped non-ASCII (\u00b7): search the decoded text
                try: h = HEADER_REV.search(json.dumps(json.loads(line), ensure_ascii=False))
                except ValueError: h = None
            if h: row["loaded"] = {"guidance_revision": h.group(1), "adapter_revision": h.group(2), "kit_revision": h.group(3)}
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        session_id = session_id or d.get("sessionId") or d.get("session_id")
        ts = _ts(d.get("timestamp"))
        if ts:
            first_ts = first_ts or ts; last_ts = ts
        t, m = d.get("type"), d.get("message") if isinstance(d.get("message"), dict) else {}
        if t == "assistant" and not d.get("isSidechain"):
            mid = m.get("id")
            u = m.get("usage") or {}
            if mid and mid not in seen and u:
                seen.add(mid); turns += 1
                ctx = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                if turns == 1: row["first_turn_context_tokens"] = ctx
                out_tok += int(u.get("output_tokens") or 0); ctx_tok += ctx
            for c in m.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    row["tool_calls"] += 1
                    if c.get("name") == "Skill":
                        s = str((c.get("input") or {}).get("skill", "?")); row["skills"][s] = row["skills"].get(s, 0) + 1
                    if c.get("name") in EDIT_TOOLS and not edited:
                        edited = True
                        row["turns_before_first_edit"] = turns; row["output_tokens_before_first_edit"] = out_tok
        elif t == "user":
            pd = d.get("permissionDecision")
            if isinstance(pd, dict) and str(pd.get("source", "")).startswith("user") and pd.get("decision") == "accept":
                row["approvals_by_person"] += 1
            kind = d.get("toolDenialKind")
            if kind:
                row["denials"][kind] = row["denials"].get(kind, 0) + 1
            for c in (m.get("content") if isinstance(m.get("content"), list) else []):
                if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error"):
                    row["tool_errors"] += 1
        elif t == "result":   # headless stream-json (baseline runs): totals for the whole run
            if d.get("total_cost_usd") is not None: row["cost_usd"] = round(d["total_cost_usd"], 4)
            if d.get("duration_ms") is not None: row["minutes"] = round(d["duration_ms"] / 60000, 1)
            if d.get("is_error") is not None: row["run_error"] = bool(d["is_error"])
        elif t == "cost-state":
            for src, dst in (("totalCostUSD", "cost_usd"), ("totalLinesAdded", "lines_added"), ("totalLinesRemoved", "lines_removed")):
                if d.get(src) is not None: row[dst] = round(d[src], 4) if isinstance(d[src], float) else d[src]
    row.update({"session": session_id or path.stem, "assistant_turns": turns, "output_tokens": out_tok, "context_tokens": ctx_tok,
                "edited": edited})
    if first_ts:
        row["start"] = first_ts.isoformat(timespec="seconds")
        row.setdefault("minutes", round((last_ts - first_ts).total_seconds() / 60, 1))
    return row


def kit_revision_at(ts: str | None, kit: Path = KIT) -> str | None:
    """The kit commit that was current at a session's start (the newest commit not after it)."""
    if not ts:
        return None
    r = subprocess.run(["git", "-C", str(kit), "log", "-1", f"--before={ts}", "--format=%h"], capture_output=True, text=True)
    return r.stdout.strip() or None


def revision_row(project: Path, kit: Path = KIT) -> dict:
    sys.path.insert(0, str(kit / "tools"))
    import wizard
    _, rep = wizard.verify(project, kit)
    const = wizard.load_yaml(kit / "core" / "constitution" / "constitution.yaml").get("constitution", {})
    return {"date": datetime.now(timezone.utc).date().isoformat(), "constitution": const.get("version"),
            "always_loaded_bytes": rep.get("always_loaded_total"), "loaded_with_inherited_bytes": rep.get("loaded_total"),
            "entry_path_bytes": rep.get("entry_path_total"), "verify": rep.get("grades")}


def evidence_counts(project: Path) -> dict:
    n = failed = unstable = 0
    for f in sorted((project / ".strata" / "local" / "verify").glob("*.yaml")):
        for e in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("entries", []):
            n += 1; failed += e.get("exit_code") != 0; unstable += bool(e.get("unstable"))
    return {"entries": n, "failed": failed, "unstable": unstable}


def handoff_counts(project_id: str, vault: Path | None) -> dict | None:
    d = vault / "projects" / project_id / "sessions" if vault else None
    if not d or not d.is_dir():
        return None
    files = [f for f in d.glob("session-*.md")]
    pending = [sum(1 for l in f.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip().startswith("blocker:")) for f in files]
    return {"handoffs": len(files), "pending_items": sum(pending), "with_pending": sum(1 for p in pending if p)}


def violation_counts(project_id: str, vault: Path | None) -> dict | None:
    """kb enforce ledger (DEC-2026-10-29-17): runs with violations per family and grade, last count when the checker gave one."""
    p = vault / "projects" / project_id / "measurements" / "violations.yaml" if vault else None
    if not p or not p.is_file():
        return None
    out: dict = {}
    if str(KIT) not in sys.path:
        sys.path.insert(0, str(KIT))   # the kit's kb package, when metrics runs from another directory
    from kb.gates.enforce import effective, entries
    for e in effective(entries(p)):   # corrections applied (MB-strata-kit-2026-046)
        r = out.setdefault(f"{e.get('family')}:{e.get('kind', 'violation')}:{e.get('grade')}", {"runs": 0})
        r["runs"] += 1
        if e.get("count") is not None: r["last_count"] = e["count"]; r["last_at"] = e.get("at")
    return out


def git_counts(project: Path, since: str | None) -> dict | None:
    if not since or not (project / ".git").exists():
        return None
    r = subprocess.run(["git", "-C", str(project), "log", f"--since={since}", "--format=%s"], capture_output=True, text=True)
    subjects = [s for s in r.stdout.splitlines() if s]
    # a revert is a subject that starts with git's "Revert" or with "되돌림" — the word inside a longer subject (a feature
    # that counts reverts, say) is not one
    return {"since": since, "commits": len(subjects), "reverts": sum(1 for s in subjects if REVERT.match(s))}


def project_id(project: Path) -> str:
    sys.path.insert(0, str(KIT / "tools"))
    import wizard
    tier = wizard.tier_of(project)
    m = wizard.load_yaml((tier.root if tier else project / ".strata") / "profile.yaml") or {}
    return m.get("project") or project.name


def collect(project: Path, home: Path | None = None, vault: Path | None = None) -> dict:
    sessions = {}
    for f in sorted(transcript_dir(project, home).glob("*.jsonl")):
        row = session_row(f)
        if row["assistant_turns"]:
            # the revision the header says was loaded; the commit current at the session start only when there was no header
            loaded = row.get("loaded") or {}
            row["kit_revision"] = loaded.get("kit_revision") or kit_revision_at(row.get("start"))
            row["revision_source"] = "header" if loaded else "start-time"
            sessions[row.pop("session")] = row
    since = min((r["start"] for r in sessions.values() if r.get("start")), default=None)
    pid = project_id(project)
    return {"project": pid, "collected": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "revisions": {subprocess.run(["git", "-C", str(KIT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip(): revision_row(project)},
            "sessions": sessions, "evidence": evidence_counts(project), "handoffs": handoff_counts(pid, vault),
            "violations": violation_counts(pid, vault), "git": git_counts(project, since)}


def store_path(vault: Path, pid: str) -> Path:
    return vault / "projects" / pid / "measurements" / "strata-metrics.yaml"


SNAPSHOT_KEYS = ("evidence", "handoffs", "violations", "git")
HISTORY_MAX = 120   # about four months of daily collections


def snapshot(data: dict) -> dict:
    """The per-collection summary kept in `history`, so a reader can compare a collection with the one before it
    (kb signals candidates, planning/operations-signal). A key the collection did not have stays absent."""
    return {"collected": data.get("collected"), **{k: data[k] for k in SNAPSHOT_KEYS if data.get(k) is not None}}


def merge(old: dict, new: dict) -> dict:
    """Sessions and revisions accumulate (a transcript Claude Code has deleted keeps its row); the top-level counts are
    the latest, and every collection's counts are appended to `history` (a file written before history existed seeds
    it with its own last collection)."""
    out = {**old, **{k: v for k, v in new.items() if k not in ("sessions", "revisions", "history")}}
    # a revision collected again moves to the end, so the table's order is the order of the latest collections
    out["revisions"] = {**{k: v for k, v in (old.get("revisions") or {}).items() if k not in new["revisions"]}, **new["revisions"]}
    out["sessions"] = {**(old.get("sessions") or {}), **new["sessions"]}
    hist = list(old.get("history") or ([snapshot(old)] if old.get("collected") else []))
    out["history"] = (hist + [snapshot(new)])[-HISTORY_MAX:]
    return out


def summary(data: dict) -> dict:
    by: dict[str, list] = {}
    for r in (data.get("sessions") or {}).values():
        by.setdefault(r.get("kit_revision") or "?", []).append(r)
    med = lambda rows, k: statistics.median([r[k] for r in rows if r.get(k) is not None]) if any(r.get(k) is not None for r in rows) else None
    return {rev: {"sessions": len(rows), "first_turn_context_tokens": med(rows, "first_turn_context_tokens"),
                  "turns_before_first_edit": med(rows, "turns_before_first_edit"), "approvals_by_person": med(rows, "approvals_by_person"),
                  "denials": sum(sum(r.get("denials", {}).values()) for r in rows), "tool_errors": med(rows, "tool_errors"),
                  "minutes": med(rows, "minutes")} for rev, rows in sorted(by.items())}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["collect", "summary", "session"]); ap.add_argument("target")
    ap.add_argument("--write", action="store_true", help="collect: merge into the vault measurement file")
    a = ap.parse_args(argv)
    dump = lambda d: print(yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=1000), end="")
    if a.cmd == "session":
        dump(session_row(Path(a.target))); return 0
    project = Path(a.target).resolve()
    vault = Path(os.environ["STRATA_VAULT"]) if os.environ.get("STRATA_VAULT") else None
    if a.cmd == "summary":
        p = store_path(vault, project_id(project)) if vault else None
        if not p or not p.is_file(): raise SystemExit(f"no measurement file: {p}")
        dump(summary(yaml.safe_load(p.read_text(encoding="utf-8")) or {})); return 0
    data = collect(project, vault=vault)
    if not a.write:
        dump(data); return 0
    if not vault: raise SystemExit("STRATA_VAULT is not set")
    p = store_path(vault, data["project"]); p.parent.mkdir(parents=True, exist_ok=True)
    old = yaml.safe_load(p.read_text(encoding="utf-8")) if p.is_file() else {}
    merged = merge(old or {}, data)
    p.write_text("# strata-kit measurement (tools/metrics.py, DEC-2026-10-29-16) — generated, do not edit by hand\n"
                 + yaml.safe_dump(merged, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    print(f"metrics: {p} — {len(merged['sessions'])} sessions, {len(merged['revisions'])} revisions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
