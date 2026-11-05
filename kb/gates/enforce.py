"""Per-project enforcement grades (DEC-2026-10-29-17, order 2026.10.29-14 task-08).

A project declares, per rule family, how hard the harness enforces it — in its placement manifest (Tier P
profile.yaml):

  enforcement:
    layers: advisory     # record violations, never stop the work
    naming: default      # fail unless gate-overrides.yaml covers it with a reason and an expiry
    rules: block         # fail

A family the manifest does not name is `block`: an existing checker keeps stopping work until the project says
otherwise. `coverage` is the exception (DEC-2026-10-31-31): undeclared, it only reports, because the gate counts every
gap that predates the project's baseline. `stages` — the checks of the newer stages (kb planning · design · taste · ideas ·
signals check) — is advisory when undeclared too (DEC-2026-11-01-18): run them as `kb enforce run --family stages -- …`.
`boundaries` — the three-boundary checks (kb boundaries check, the ArchUnit StrataBoundaryRulesTest) — starts advisory too
(DEC-2026-11-05-02).

`run` wraps any existing checker (hook, CI step, a project's run.sh) without changing it: the checker's non-zero
exit means violations; the grade decides what the wrapper returns, and every run — clean ones too (DEC-2026-10-31-23)
— is appended to the vault ledger projects/<p>/measurements/violations.yaml with the kit revision, so a family can be
promoted (advisory → default → block, each step a decision) once its numbers are known.

A checker that fails for another reason (cannot start, crashes, bad configuration) is not a violation: a run counts
as violations only when its exit code is one of --violation-exit (default 1) and, when --violation-pattern is
given, its output matches it. Any other failure fails at every grade and is recorded as a checker error
(DEC-2026-10-29-19) — advisory never hides a broken checker.

A warning-mode checker prints its violations and exits 0 (an ArchUnit `./gradlew archCheck` in warning mode). Put 0 in --violation-exit
and give --violation-pattern: an exit-0 run whose output matches is a violation, one that does not is clean. 0 without
a pattern is refused — every clean run would count (MB-strata-kit-2026-046).

A run that evaluated nothing is not clean either (MB-strata-kit-2026-057). Two signs mark it: the checker prints a
line `[strata] indeterminate: …` (kb boundaries check, kb check-layer --audit) or `[strata-arch] <family>
indeterminate: …` (the ArchUnit warning mode), or --expect-pattern is given and the output does not match it — a
Gradle run with -q hides the test output, exits 0 and would otherwise be recorded as clean. Such a run is recorded as
kind checker_error with `indeterminate: true` and its reason ('judgement impossible — the declaration does not match
the code'); the grade decides what it returns, like a violation (advisory passes with a warning, default and block
fail), because the checker itself did not break. A violation run that also printed indeterminate lines stays a
violation and carries them.

A checker that prints a coverage line — `[strata] coverage: … 82% (미대응 41파일 …)` (kb check-layer --audit, kb
boundaries check) or `[strata-arch] layers coverage: 82% of classes mapped (unmapped 41 of …)` (the ArchUnit layer
tests) — has it kept on the entry as `coverage: {percent, unmapped}`, so the ledger shows how much of the code the rule
saw next to what it found (MB-strata-kit-2026-057 step 2).

The ledger is append-only. A wrong entry is not rewritten: `correct` appends a correction that names it by time and
family and says what it was (violation with a count, clean, or void); readers use effective(), which applies them.

The grade binds the harness only. The agent rule (must card rec.architecture.no-layer-violation) holds at every
grade: write no new violation, and report one that was written.

  python3 -m kb enforce run --family layers [--project DIR] [--count-regex RE] [--violation-exit 1|1-255|1,3]
                           [--violation-pattern RE] [--expect-pattern RE] -- <checker> [args…]
  python3 -m kb enforce correct --family F --at <entry time> --as violation|clean|void [--count N] --reason R [--project DIR]
  python3 -m kb enforce show [--project DIR]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from kb import vault_root
from kb.gates.grades import GRADES, Finding, evaluate, load_overrides, render

KIT = Path(__file__).resolve().parents[2]
DEFAULT_GRADE = "block"
FAMILY_DEFAULTS = {"coverage": "advisory", "stages": "advisory",   # DEC-2026-10-31-31; stages (planning·design·taste·ideas·signals checks): DEC-2026-11-01-18
                   "boundaries": "advisory"}   # the three boundaries (kb boundaries check, StrataBoundaryRulesTest) start advisory: DEC-2026-11-05-02
TAIL = 15
COVERAGE_RE = re.compile(r"\[strata(?:-arch)?\]\s+(?:[\w.-]+\s+)?coverage:\D*?(\d+(?:\.\d+)?)%[^\n]*?(?:미대응|unmapped)\s*(\d+)")
INDETERMINATE_RE = re.compile(r"\[strata(?:-arch)?\]\s+(?:[\w.-]+\s+)?indeterminate:\s*(.*)")


def _tier(project: Path):
    from kb.legacy.strata_paths import resolve_tier_p
    try:
        return resolve_tier_p(project)
    except ValueError:
        return None


def manifest(project: Path) -> tuple[dict, Path | None]:
    import yaml
    tier = _tier(project)
    root = tier.root if tier else project / ".strata"
    p = root / "profile.yaml"
    return ((yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.is_file() else {}), root


def grades(project: Path) -> dict[str, str]:
    m, _ = manifest(project)
    out = {}
    for fam, g in ((m.get("enforcement") or {}) if isinstance(m.get("enforcement"), dict) else {}).items():
        if g not in GRADES:
            raise SystemExit(f"enforcement.{fam}: unknown grade {g!r} (one of {', '.join(GRADES)})")
        out[str(fam)] = g
    return out


def grade_of(project: Path, family: str) -> str:
    return grades(project).get(family, FAMILY_DEFAULTS.get(family, DEFAULT_GRADE))


def ledger_path(project: Path) -> Path | None:
    v = vault_root()
    m, _ = manifest(project)
    return v / "projects" / (m.get("project") or project.name) / "measurements" / "violations.yaml" if v else None


def _kit_rev() -> str:
    r = subprocess.run(["git", "-C", str(KIT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or "?"


def record(path: Path, entry: dict) -> None:
    """Append one entry as a one-line flow mapping (JSON is YAML): appends from different machines merge line by line."""
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text("# violations ledger (python3 -m kb enforce, DEC-2026-10-29-17) — append-only, generated\nentries:\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write("  - " + json.dumps(entry, ensure_ascii=False) + "\n")


def entries(path: Path | None) -> list[dict]:
    import yaml
    return ((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("entries") or []) if path and path.is_file() else []


def effective(raw: list[dict]) -> list[dict]:
    """The ledger as readers should count it: corrections applied to the entry they name (same `at` and family), the
    correction lines themselves dropped, a 'void' entry dropped (MB-strata-kit-2026-046)."""
    fix = {(c.get("corrects"), c.get("family")): c for c in raw if c.get("kind") == "correction"}
    out = []
    for e in raw:
        if e.get("kind") == "correction":
            continue
        c = fix.get((e.get("at"), e.get("family")))
        if c:
            if c.get("as") == "void":
                continue
            e = {**{k: v for k, v in e.items() if k != "count"}, "kind": c.get("as"),
                 **({"count": c["count"]} if c.get("count") is not None else {}),
                 "corrected_by": {"at": c.get("at"), "reason": c.get("reason")}}
        out.append(e)
    return out


def correct(project: Path, family: str, at: str, as_kind: str, reason: str, count: int | None = None) -> tuple[int, str]:
    lp = ledger_path(project)
    if not lp:
        return 2, "STRATA_VAULT 없음 — 기록부를 찾지 못함"
    if not any(e.get("at") == at and e.get("family") == family and e.get("kind") != "correction" for e in entries(lp)):
        return 2, f"정정할 기록 없음: {family} @ {at}"
    record(lp, {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "family": family, "kind": "correction",
                "corrects": at, "as": as_kind, **({"count": count} if count is not None else {}), "reason": reason,
                "kit_revision": _kit_rev()})
    return 0, f"정정 기록: {family} @ {at} → {as_kind}" + (f" ({count}건)" if count is not None else "")


def exit_codes(spec: str) -> set[int]:
    """'1' · '1-255' · '1,3' → the exit codes that mean 'the checker ran and found violations'."""
    out: set[int] = set()
    for part in str(spec).split(","):
        a, _, b = part.strip().partition("-")
        out |= set(range(int(a), int(b or a) + 1))
    return out


def coverage_of(output: str) -> dict | None:
    """The coverage line a checker printed (MB-strata-kit-2026-057 step 2) — '[strata] coverage: … 82% (미대응 41파일 …)'
    or '[strata-arch] layers coverage: 82% of classes mapped (unmapped 41 of …)'; the last one wins."""
    found = COVERAGE_RE.findall(output)
    if not found:
        return None
    pct, unmapped = found[-1]
    return {"percent": float(pct), "unmapped": int(unmapped)}


def _indeterminate(project: Path, family: str, grade: str, lp: Path | None, cmd: list[str], rc: int, output: str,
                   reason: str, today: str | None) -> tuple[int, list[str]]:
    """Record a run that evaluated nothing as a checker_error marked indeterminate; the grade decides the return."""
    if lp:
        record(lp, {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "family": family, "kind": "checker_error",
                    "indeterminate": True, "reason": reason, "grade": grade, "kit_revision": _kit_rev(),
                    **({"coverage": coverage_of(output)} if coverage_of(output) else {}),
                    "command": " ".join(cmd), "exit_code": rc, "tail": "\n".join(output.rstrip("\n").splitlines()[-TAIL:])})
    _, root = manifest(project)
    finding = Finding("enforce", family, grade, f"{family} 판정 불가 — 선언이 코드와 맞지 않음 (깨끗함이 아님): {reason}"
                      + (f" — 기록: {lp}" if lp else " — STRATA_VAULT 없음, 기록 안 함"))
    r = evaluate([finding], load_overrides(root / "gate-overrides.yaml") if root else [], today)
    return r["rc"], render(r)


def run(project: Path, family: str, cmd: list[str], count_regex: str | None = None, today: str | None = None,
        violation_exit: str = "1", violation_pattern: str | None = None,
        expect_pattern: str | None = None) -> tuple[int, list[str]]:
    codes = exit_codes(violation_exit)
    if 0 in codes and not violation_pattern:
        raise ValueError("--violation-exit 에 0 을 넣으면 --violation-pattern 이 필요하다 — 없으면 모든 정상 실행이 위반이 된다 (MB-strata-kit-2026-046)")
    try:
        proc = subprocess.run(cmd, cwd=project, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        rc, output = proc.returncode, proc.stdout
    except OSError as e:   # the checker could not even start
        rc, output = 127, f"{type(e).__name__}: {e}\n"
    sys.stdout.write(output)
    grade = grade_of(project, family)
    lp = ledger_path(project)
    hit = violation_pattern is not None and re.search(violation_pattern, output) is not None
    said = [m.group(1).strip() for m in INDETERMINATE_RE.finditer(output)]
    violation = rc in codes and (violation_pattern is None or hit)   # 0 in codes always comes with a pattern
    if not violation and said:
        return _indeterminate(project, family, grade, lp, cmd, rc, output, "; ".join(said), today)
    if not violation and rc == 0 and expect_pattern and re.search(expect_pattern, output) is None:
        return _indeterminate(project, family, grade, lp, cmd, rc, output,
                              f"출력에 기대한 표식 {expect_pattern!r} 이 없음 — 검사가 아무것도 평가하지 않았거나 출력이 숨겨짐(-q 등)", today)
    if rc == 0 and not (0 in codes and hit):
        # a clean run is evidence too: without it a checker that runs daily and finds nothing looks like one that never
        # ran (DEC-2026-10-31-23, doctor's run evidence)
        if lp:
            record(lp, {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "family": family, "kind": "clean",
                        "grade": grade, "kit_revision": _kit_rev(), "command": " ".join(cmd), "exit_code": 0,
                        **({"coverage": coverage_of(output)} if coverage_of(output) else {})})
        return 0, [f"enforce {family}: clean ({grade})"]
    if not violation:
        if lp:
            record(lp, {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "family": family, "kind": "checker_error",
                        "grade": grade, "kit_revision": _kit_rev(), "command": " ".join(cmd), "exit_code": rc,
                        "tail": "\n".join(output.rstrip("\n").splitlines()[-TAIL:])})
        return 2, [f"BLOCK  enforce {family} — 검사 실패(exit {rc}, 위반 종료 코드 {violation_exit}"
                   + (f"·표식 {violation_pattern!r}" if violation_pattern else "") + " 아님) — 등급과 무관하게 실패, 검사기를 고칠 것"]
    proc_stdout = output
    count = None
    if count_regex:
        m = re.search(count_regex, proc_stdout)
        count = int(m.group(1)) if m and m.groups() else len(re.findall(count_regex, proc_stdout))
    if lp:
        record(lp, {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "family": family, "kind": "violation", "grade": grade,
                    "kit_revision": _kit_rev(), "command": " ".join(cmd), "exit_code": rc,
                    **({"count": count} if count is not None else {}),
                    **({"indeterminate": said} if said else {}),
                    **({"coverage": coverage_of(output)} if coverage_of(output) else {}),
                    "tail": "\n".join(proc_stdout.rstrip("\n").splitlines()[-TAIL:])})
    _, root = manifest(project)
    finding = Finding("enforce", family, grade, f"{family} 위반 (exit {rc}" + (f", {count}건" if count is not None else "") + ")"
                      + (f" — 기록: {lp}" if lp else " — STRATA_VAULT 없음, 기록 안 함"))
    r = evaluate([finding], load_overrides(root / "gate-overrides.yaml") if root else [], today)
    return r["rc"], render(r)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd: list[str] = []
    if "--" in argv:
        i = argv.index("--"); argv, cmd = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(prog="kb enforce", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["run", "correct", "show"])
    ap.add_argument("--project", default=".")
    ap.add_argument("--family")
    ap.add_argument("--violation-exit", default="1", help="exit codes that mean violations were found: 1 · 1-255 · 1,3 (default 1)")
    ap.add_argument("--violation-pattern", help="regex the output must match for a failing run to count as violations")
    ap.add_argument("--expect-pattern", help="regex every completed run prints (e.g. the checker's summary line); a run "
                    "that exits 0 without it is indeterminate, not clean (MB-strata-kit-2026-057)")
    ap.add_argument("--count-regex", help="regex over the checker output: its first group is the count, or the number of matches")
    ap.add_argument("--at", help="correct: the time of the entry to correct, as the ledger shows it")
    ap.add_argument("--as", dest="as_kind", choices=["violation", "clean", "void"], help="correct: what the entry really was")
    ap.add_argument("--count", type=int, help="correct: the violation count")
    ap.add_argument("--reason", help="correct: why (required)")
    a = ap.parse_args(argv)
    project = Path(a.project).resolve()
    if a.action == "show":
        g = grades(project)
        print("enforcement: " + (", ".join(f"{k} {v}" for k, v in g.items()) or "none declared") + f" · undeclared families: {DEFAULT_GRADE} (coverage: advisory)")
        print(f"ledger: {ledger_path(project) or '(STRATA_VAULT not set)'}")
        return 0
    if a.action == "correct":
        if not (a.family and a.at and a.as_kind and (a.reason or "").strip()):
            ap.error("correct needs --family, --at, --as and --reason")
        rc, msg = correct(project, a.family, a.at, a.as_kind, a.reason.strip(), a.count)
        print(msg, file=sys.stderr if rc else sys.stdout)
        return rc
    if not a.family or not cmd:
        ap.error("run needs --family and -- <checker command>")
    if 0 in exit_codes(a.violation_exit) and not a.violation_pattern:
        ap.error("--violation-exit 에 0 을 넣으면 --violation-pattern 이 필요하다")
    rc, lines = run(project, a.family, cmd, a.count_regex, violation_exit=a.violation_exit, violation_pattern=a.violation_pattern,
                    expect_pattern=a.expect_pattern)
    for l in lines:
        print(l, file=sys.stderr)
    return rc
