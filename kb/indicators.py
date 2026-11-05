"""Product-flow indicators (DEC-2026-11-01-17): the core's operations stage shows indicators, it does not touch the
product's own flows (a QA ledger, coverage test cases). A project lists, in its Tier P `indicators.yaml`, read-only
commands that read those flows' outputs and print one number each; the kit runs them, keeps the history and compares.

  <Tier P>/indicators.yaml       (embedded: <repo>/.strata/, detached: $STRATA_VAULT/projects/<p>/strata/)
    indicators:
      - id: qa.recheck-pending                      # stable id, used in signal notes
        label: "다시 확인할 결함"
        command: "python3 scripts/qa_indicator.py recheck"   # read-only, run in the repository; prints a number,
                                                              # or YAML/JSON with `value:`
        better: lower                               # lower | higher
        threshold: 0.10                             # relative change counted as worse (default 0.10)
        nodes: [qa.recheck]                         # optional topic nodes — copied to the signal note, so the node
                                                    # page shows the indicator's signals

  python3 -m kb indicators collect --project P --repo DIR [--write]   run the commands; --write appends to the history
  python3 -m kb indicators show    --project P                        the latest values against the collection before
  python3 -m kb indicators read    json-count <file> --path K [--where F=V|V2]   items in a list or map, optionally filtered
  python3 -m kb indicators read    json-ratio <file> --path K --has F             % of items whose field F is non-empty
  python3 -m kb indicators read    jacoco <glob…>                                  line coverage % over JaCoCo XML reports
  python3 -m kb indicators read    junit  <glob…>                                  failures + errors over JUnit XML results

`read` is the kit's set of readers for common output formats, so a project's indicators.yaml can point at its own
files without writing a script: it prints one number, or exits 2 when nothing could be read.

The history is $STRATA_VAULT/projects/<p>/measurements/indicators.yaml (generated; the last HISTORY_MAX collections).
`kb signals candidates` reads it and offers a candidate when an indicator moved the worse way past its threshold.
A command that fails or prints no number is recorded as an error for that collection, never as zero, and `collect`
then exits 1 (after writing the history) so the librarian's run counts it in `failed N`.

Commands run with STRATA_KIT and STRATA_PYTHON in their environment (STRATA_PYTHON defaults to the python running the
collector). A kit command — one that names `$STRATA_KIT` or `-m kb` — written with a bare `python3` runs with
STRATA_PYTHON instead: under launchd a bare python3 is /usr/bin/python3 without PyYAML. Write new commands as
`"$STRATA_PYTHON" "$STRATA_KIT/kb" indicators read …`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

THRESHOLD = 0.10
HISTORY_MAX = 120
TIMEOUT = 120


def config_path(repo: Path) -> Path | None:
    from kb.legacy.strata_paths import resolve_tier_p
    try:
        tier = resolve_tier_p(repo)
    except ValueError:
        tier = None
    root = Path(tier.root) if tier else repo / ".strata"
    p = root / "indicators.yaml"
    return p if p.is_file() else None


def history_path(vault: Path, project: str) -> Path:
    return vault / "projects" / project / "measurements" / "indicators.yaml"


def load_config(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = []
    for it in data.get("indicators") or []:
        if not isinstance(it, dict) or not it.get("id") or not it.get("command"):
            continue
        better = str(it.get("better") or "lower")
        if better not in ("lower", "higher"):
            raise ValueError(f"{it['id']}: better {better!r} — lower 또는 higher")
        nodes = it.get("nodes") or []
        out.append({"id": str(it["id"]), "label": str(it.get("label") or it["id"]), "command": str(it["command"]),
                    "better": better, "threshold": float(it.get("threshold", THRESHOLD)),
                    "nodes": [str(n) for n in (nodes if isinstance(nodes, list) else [nodes])]})
    return out


def parse_value(stdout: str) -> float | None:
    s = stdout.strip()
    if not s:
        return None
    first = s.splitlines()[0].strip()
    try:
        return float(first)
    except ValueError:
        pass
    try:
        data = json.loads(s)
    except ValueError:
        try:
            data = yaml.safe_load(s)
        except yaml.YAMLError:
            return None
    if isinstance(data, dict) and isinstance(data.get("value"), (int, float)) and not isinstance(data.get("value"), bool):
        return float(data["value"])
    return None


KIT_ROOT = Path(__file__).resolve().parents[1]
_KIT_CMD = re.compile(r"\$\{?STRATA_KIT\}?|(?:^|\s)-m\s+kb\b")
_BARE_PY = re.compile(r"(^|[;&|(]\s*|&&\s*|\|\|\s*)python3?(?=\s)")


def resolve_kit_python(command: str, python: str) -> str:
    """A kit command's bare python3 (in command position) becomes `python`; other commands are left alone."""
    if not _KIT_CMD.search(command):
        return command
    return _BARE_PY.sub(lambda m: m.group(1) + shlex.quote(python), command)


def command_env() -> tuple[dict, str]:
    env = dict(os.environ)
    py = env.get("STRATA_PYTHON") or sys.executable
    env["STRATA_PYTHON"] = py
    env.setdefault("STRATA_KIT", str(KIT_ROOT))
    return env, py


def collect(indicators: list[dict], repo: Path, now: str | None = None) -> dict:
    values, errors = {}, {}
    env, py = command_env()
    for it in indicators:
        try:
            r = subprocess.run(resolve_kit_python(it["command"], py), shell=True, cwd=repo, capture_output=True,
                               text=True, timeout=TIMEOUT, env=env)
        except subprocess.TimeoutExpired:
            errors[it["id"]] = f"{TIMEOUT}초 넘음"
            continue
        v = parse_value(r.stdout) if r.returncode == 0 else None
        if v is None:
            errors[it["id"]] = f"exit {r.returncode}" + (f": {r.stderr.strip().splitlines()[-1][:160]}" if r.stderr.strip() else " — 숫자를 출력하지 않음")
        else:
            values[it["id"]] = int(v) if v.is_integer() else v
    return {"collected": now or datetime.now(timezone.utc).isoformat(timespec="seconds"), "values": values,
            **({"errors": errors} if errors else {})}


def merge(old: dict, row: dict, indicators: list[dict], project: str) -> dict:
    meta = {it["id"]: {k: it[k] for k in ("label", "better", "threshold", "nodes") if it.get(k) not in (None, [])} for it in indicators}
    return {"project": project, "indicators": {**(old.get("indicators") or {}), **meta},
            "history": ((old.get("history") or []) + [row])[-HISTORY_MAX:]}


def worse(meta: dict, before: float, now: float) -> float | None:
    """The relative change when the indicator moved the worse way past its threshold, else None. From 0, any worse
    move counts (reported as 1.0)."""
    sign = 1 if meta.get("better", "lower") == "lower" else -1
    delta = (now - before) * sign
    if delta <= 0:
        return None
    rel = delta / abs(before) if before else 1.0
    return rel if rel > float(meta.get("threshold", THRESHOLD)) else None


def show(data: dict) -> list[str]:
    hist = data.get("history") or []
    if not hist:
        return ["지표 이력 없음"]
    last, prev = hist[-1], (hist[-2] if len(hist) > 1 else {})
    lines = [f"지표 {len(data.get('indicators') or {})} · 수집 {last.get('collected')}" + (f" (앞 수집 {prev.get('collected')})" if prev else "")]
    for iid, meta in (data.get("indicators") or {}).items():
        now, before = last.get("values", {}).get(iid), prev.get("values", {}).get(iid) if prev else None
        err = (last.get("errors") or {}).get(iid)
        mark = ""
        if now is not None and before is not None and worse(meta, before, now) is not None:
            mark = " — 나빠짐"
        lines.append(f"  {iid} ({meta.get('label')}, {meta.get('better')} 이 좋음): "
                     + (f"오류 {err}" if err else f"{before if before is not None else '—'} → {now}") + mark)
    return lines


def _items(data, path: str) -> list:
    for key in [k for k in path.split(".") if k]:
        data = data.get(key) if isinstance(data, dict) else None
    if isinstance(data, dict):
        return list(data.values())
    return data if isinstance(data, list) else []


def read(kind: str, args: list[str], where: str | None = None, has: str | None = None, path: str = "") -> float:
    """One number from a common output format; raises ValueError when nothing could be read."""
    import glob
    import xml.etree.ElementTree as ET
    if kind in ("json-count", "json-ratio"):
        if len(args) != 1:
            raise ValueError("파일 하나")
        items = _items(json.loads(Path(args[0]).read_text(encoding="utf-8")), path)
        if kind == "json-count":
            if where:
                field, vals = where.split("=", 1)
                items = [i for i in items if isinstance(i, dict) and str(i.get(field)) in vals.split("|")]
            return float(len(items))
        if not has or not items:
            raise ValueError("--has 와 항목이 필요하다")
        return round(100.0 * sum(1 for i in items if isinstance(i, dict) and i.get(has)) / len(items), 1)
    files = sorted({f for g in args for f in glob.glob(g, recursive=True)})
    if not files:
        raise ValueError(f"일치하는 파일 없음: {' '.join(args)}")
    if kind == "jacoco":
        covered = missed = 0
        for f in files:
            for c in ET.parse(f).getroot().findall("counter"):
                if c.get("type") == "LINE":
                    covered += int(c.get("covered", 0)); missed += int(c.get("missed", 0))
        if not covered + missed:
            raise ValueError("LINE 카운터 없음")
        return round(100.0 * covered / (covered + missed), 1)
    if kind == "junit":
        n = 0
        for f in files:
            root = ET.parse(f).getroot()
            suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
            n += sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
        return float(n)
    raise ValueError(f"모르는 형식 {kind}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb indicators", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect"); c.add_argument("--project", required=True); c.add_argument("--repo", required=True)
    c.add_argument("--write", action="store_true"); c.add_argument("--config", help="indicators.yaml (default: the project's Tier P)")
    s = sub.add_parser("show"); s.add_argument("--project", required=True)
    r = sub.add_parser("read"); r.add_argument("kind", choices=["json-count", "json-ratio", "jacoco", "junit"]); r.add_argument("args", nargs="+")
    r.add_argument("--path", default=""); r.add_argument("--where"); r.add_argument("--has")
    a = ap.parse_args(argv)
    if a.cmd == "read":
        try:
            v = read(a.kind, a.args, a.where, a.has, a.path)
        except (ValueError, OSError, json.JSONDecodeError) as e:
            print(f"읽지 못함: {e}", file=sys.stderr)
            return 2
        print(int(v) if float(v).is_integer() else v)
        return 0
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    if a.cmd == "show":
        p = history_path(vault, a.project)
        print("\n".join(show(yaml.safe_load(p.read_text(encoding="utf-8")) or {} if p.is_file() else {})))
        return 0
    repo = Path(a.repo).resolve()
    cfg = Path(a.config) if a.config else config_path(repo)
    if not cfg or not cfg.is_file():
        print(f"지표 설정 없음 — {a.project} 의 Tier P 에 indicators.yaml 이 없다(제품 흐름 지표를 두지 않은 프로젝트)")
        return 0
    try:
        indicators = load_config(cfg)
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2
    row = collect(indicators, repo)
    print(f"지표 {len(indicators)} · 값 {len(row['values'])} · 오류 {len(row.get('errors') or {})} — {cfg}")
    for iid, v in row["values"].items():
        print(f"  {iid}: {v}")
    for iid, e in (row.get("errors") or {}).items():
        print(f"  {iid}: 오류 {e}")
    if a.write:
        hp = history_path(vault, a.project)
        hp.parent.mkdir(parents=True, exist_ok=True)
        old = yaml.safe_load(hp.read_text(encoding="utf-8")) or {} if hp.is_file() else {}
        hp.write_text("# product-flow indicators (kb indicators, DEC-2026-11-01-17) — generated, do not edit by hand\n"
                      + yaml.safe_dump(merge(old, row, indicators, a.project), allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
        print(f"  씀: {hp.relative_to(vault)}")
    return 1 if row.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
