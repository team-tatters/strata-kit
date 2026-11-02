#!/usr/bin/env python3
"""doctor — is strata actually running in this project? (planning/doctor, DEC-2026-10-31-22~29)

  python3 tools/doctor.py <project> [--since YYYY-MM-DD] [--json] [--librarian-log PATH] [--librarian-label LABEL]

Runs the existing checks against one project and groups everything under one grade vocabulary (kb/gates/grades.py):
the wizard's verify and the coverage gate keep their own grades; link check (new blocking violations outside the
baseline → default), embedded decision records left uncommitted (default) and the hygiene report (advisory) are
graded here. Four checks nobody ran before start as advisory (DEC-2026-10-31-22): checker installation and run
evidence, solo decisions that changed core sources or profiles, generated guidance behind the kit, and the
librarian's last run (a machine item). Every item carries its evidence and the command or skill that fixes it; what
doctor cannot find is shown as unknown or "no evidence", never counted as a pass.

Read-only. It never rebuilds the store (an old store is opened as it is and its age is an item, DEC-2026-10-31-25),
never mirrors the link baseline, never runs a checker and never writes a file. One check failing shows as a check
failure (default) and the others still run. Exit code: 2 when something blocks or a default item has no live
override in the Tier P gate-overrides.yaml, else 0 — the same rule as the wizard's verify.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sqlite3
import subprocess
import sys
import traceback
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "tools"))

import yaml  # noqa: E402

from kb.gates.grades import Finding, evaluate, load_overrides  # noqa: E402

CORE_SOURCES = ("core/rules", "layer-rules", "naming-convention", "task-spec-schema", "agent-roles")
GUIDANCE_PATHS = ("core", "profiles", "adapters", "skills")
GROUPS = (("block", "막는 것"), ("default", "사유와 기한이 필요한 것(default)"), ("advisory", "참고"), ("machine", "기계 상태"))


@dataclass
class Item:
    check: str
    key: str
    grade: str          # block | default | advisory
    message: str
    evidence: str
    fix: str
    machine: bool = False
    status: str = ""    # filled after overrides: blocked | unresolved | overridden | expired | advisory
    override: dict = field(default_factory=dict)


# ---------------------------------------------------------------- project facts

def tier_of(project: Path):
    from kb.legacy.strata_paths import resolve_tier_p
    try:
        return resolve_tier_p(project)
    except ValueError:
        return None


def manifest(project: Path) -> dict:
    t = tier_of(project)
    p = (t.root if t else project / ".strata") / "profile.yaml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.is_file() else {}


def project_id(project: Path) -> str:
    return str(manifest(project).get("project") or project.name)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


# ---------------------------------------------------------------- store (opened as it is)

def open_store(vault: Path | None):
    """(store or None, items). Never rebuilds: an old store is used and its age reported; another schema is not opened
    at all, because SqliteStore would discard it."""
    from kb.store import SCHEMA_VERSION, SqliteStore
    if vault is None:
        return None, [Item("store", "store", "advisory", "STRATA_VAULT 가 없어 vault 점검을 하지 못했습니다", "환경 변수 STRATA_VAULT 없음",
                           "STRATA_VAULT 를 vault 체크아웃으로 정한다")]
    path = vault / ".kb" / "store.sqlite"
    if not path.is_file():
        return None, [Item("store", "store", "advisory", "store 가 없어 커버리지·위생·링크 점검을 하지 못했습니다", str(path),
                           "python3 -m kb build-store")]
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        row = c.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        c.close()
    except sqlite3.Error as e:
        row = None
        err = str(e)
    else:
        err = ""
    if not row or row[0] != SCHEMA_VERSION:
        return None, [Item("store", "store", "advisory", "store 형식이 kit 과 달라 열지 않았습니다(열면 지워진다)",
                           f"{path} schema {row[0] if row else err or '없음'} ≠ {SCHEMA_VERSION}", "python3 -m kb build-store")]
    store = SqliteStore(path)
    items = []
    rev = store.revision()
    if rev is not None:
        from kb.engine import _source_mtime, default_project_dirs
        built = datetime.fromisoformat(rev.built_at)
        newest = _source_mtime(vault, default_project_dirs(vault))
        lag = newest - built.timestamp()
        if lag > 0:
            items.append(Item("store", "store_age", "advisory",
                              f"store 가 소스보다 {lag / 3600:.1f}시간 낡았습니다 — 커버리지·위생·링크 결과는 이 store 기준입니다",
                              f"built_at {rev.built_at}, 가장 새 소스 {datetime.fromtimestamp(newest, timezone.utc).isoformat(timespec='seconds')}",
                              "python3 -m kb build-store"))
    return store, items


# ---------------------------------------------------------------- existing checks

def check_verify(project: Path, **_) -> list[Item]:
    import wizard
    _, rep = wizard.verify(project, KIT)
    return [Item("verify", f.key, f.grade, f.message, f"wizard verify — {f.key}", "strata.init-wizard (recommend → generate → verify)")
            for f in rep.get("_findings", [])]


def check_coverage(project: Path, store=None, since: str | None = None, stale: bool = False, **_) -> list[Item]:
    if store is None:
        return []
    from kb.gates import coverage as cov
    t = tier_of(project)
    r = cov.run_gate(str(project), {}, None, since or date.today().isoformat(), store=store)
    pol = cov.load_coverage_policy(t.root if t else None)
    note = " (낡은 store 기준)" if stale else ""
    out = [Item("coverage", f"new_spec:{m}", pol["grade"], f"소유 명세 없는 변경 {len(fs)}개{note}", f"since {r['since']} — " + ", ".join(fs[:3]) + (" …" if len(fs) > 3 else ""),
                "strata.kb-update — 명세를 쓰거나 Tier P gate-overrides.yaml 에 사유·기한")
           for m, fs in sorted(r["new_spec_needed"].items())] if pol["grade"] in ("default", "block") else []
    if pol["grade"] in ("default", "block"):   # unjudged implemented plans whose specification's code changed (DEC-2026-11-02-05)
        for plan in sorted({d["planning"] for d in r.get("desired_shape") or [] if d.get("action") == "recheck"}):
            rows = [d for d in r["desired_shape"] if d["planning"] == plan and d["action"] == "recheck"]
            out.append(Item("coverage", f"desired:{Path(plan).stem}", pol["grade"], f"구현됨 기획 {Path(plan).stem} 의 명세가 맡은 코드가 바뀜 — 판정 전{note}",
                            f"since {r['since']} — 명세 " + ", ".join(sorted({Path(d['spec']).stem for d in rows})) + " · "
                            + ", ".join(sorted({x for d in rows for x in d['paths']})[:3]),
                            "kb divergence add·judge 로 대조해 판정한다, 또는 Tier P gate-overrides.yaml 에 사유·기한"))
    if r["changed"]:
        out.append(Item("coverage", "summary", "advisory", r["summary_line"] + note, f"since {r['since']}, 경고 {len(r['warnings'])}건",
                        f"python3 -m kb coverage-gate --project-dir {project} --since {r['since']}"))
    return out


def check_hygiene(project: Path, store=None, vault: Path | None = None, stale: bool = False, **_) -> list[Item]:
    if store is None:
        return []
    from kb.gates.hygiene import report
    pid = project_id(project)
    s = report(store, vault, pid)["summary"]
    note = " (낡은 store 기준)" if stale else ""
    fix = f"python3 -m kb hygiene --project {pid}"
    out = []
    broken = sum((s.get("broken") or {}).values())
    for key, n, what in (("broken_references", broken, "깨진 참조"),
                         ("state_docs_without_covers", s.get("state_docs_without_covers", 0), "covers 없는 최종형상 문서"),
                         ("status_outside_taxonomy", s.get("history_status_values_outside_taxonomy", 0), "taxonomy 밖 이력 상태값")):
        if n:
            out.append(Item("hygiene", key, "advisory", f"{what} {n}{note}", f"위생 리포트 summary.{key} = {n}", fix))
    return out


def check_links(project: Path, store=None, vault: Path | None = None, stale: bool = False, **_) -> list[Item]:
    if store is None:
        return []
    from kb.gates.links import blocking, check, key_of
    pid = project_id(project)
    bp = vault / ".kb" / "link-baseline.json"
    base = set(json.loads(bp.read_text(encoding="utf-8")).get("violations", [])) if bp.is_file() else set()
    new = sorted({key_of(v) for v in check(store, pid) if blocking(v)} - base)
    if not new:
        return []
    return [Item("links", "new_violations", "default", f"기준선 밖 새 링크 위반 {len(new)}건" + (" (낡은 store 기준)" if stale else ""),
                 ", ".join(new[:3]) + (" …" if len(new) > 3 else ""), f"python3 -m kb link-check --project {pid}")]


def check_uncommitted(project: Path, **_) -> list[Item]:
    from kb.legacy.decision import uncommitted_records
    paths = uncommitted_records(str(project))
    if not paths:
        return []
    return [Item("decisions", "uncommitted", "default", f"커밋하지 않은 결정 레코드 {len(paths)}건(embedded — push 전까지 다른 기계에 안 보임)",
                 ", ".join(paths[:3]) + (" …" if len(paths) > 3 else ""), "결정 레코드를 커밋한다 (strata.handoff 게시 단계)")]


# ---------------------------------------------------------------- new checks (advisory, DEC-2026-10-31-22)

def enforcement_templates(profile: str) -> list[str]:
    d = KIT / "profiles" / profile / "enforcement"
    return sorted(p.name[:-len(".template")] for p in d.glob("*.template")) if d.is_dir() else []


def check_enforcement(project: Path, vault: Path | None = None, **_) -> list[Item]:
    m = manifest(project)
    prof = str(m.get("kit_profile") or "")
    kp = KIT / "profiles" / prof / "profile.yaml"
    pstatus = str(((yaml.safe_load(kp.read_text(encoding="utf-8")) or {}).get("profile") or {}).get("status") or "") if kp.is_file() else ""
    want = enforcement_templates(prof)
    pid = project_id(project)
    out = []
    from kb.gates.enforce import effective, entries as ledger_entries
    led = vault / "projects" / pid / "measurements" / "violations.yaml" if vault else None
    entries = effective(ledger_entries(led))   # corrections applied (MB-strata-kit-2026-046)
    # a project's own checker run through kb enforce is installed too (MB-strata-kit-2026-047) — a run that finished
    # (clean or violation) proves it, a checker_error does not
    ran = sorted({str(e.get("family")) for e in entries if e.get("kind") in ("clean", "violation")})
    if not want:
        out.append(Item("enforcement", "install", "advisory", f"프로필 {prof or '?'} 에는 검사기 템플릿이 없어 설치를 판정할 기준이 없습니다",
                        f"{KIT.name}/profiles/{prof}/enforcement/*.template 없음", "프로필에 검사기 템플릿을 둔다 (strata.init-wizard 로 프로필 확인)"))
    else:
        t = tier_of(project)
        have = {p.name for p in ((t.root / "enforcement").glob("*") if t and (t.root / "enforcement").is_dir() else [])}
        have |= {Path(f).name for f in _git(project, "ls-files").stdout.splitlines()}
        missing = [w for w in want if w not in have]
        state = "설치됨" if not missing else ("설치 안 됨" if len(missing) == len(want) else "설치 불완전")
        if len(missing) == len(want) and ran:
            out.append(Item("enforcement", "install", "advisory", f"검사기 설치됨 — 템플릿 대신 프로젝트의 검사기({', '.join(ran)})",
                            f"프로필 {prof} 템플릿은 없고, kb enforce 실행 기록이 {', '.join(ran)} 묶음에 있음",
                            "그대로 kb enforce run 으로 감싸 돌린다 — 템플릿 설치는 선택"))
        else:
            out.append(Item("enforcement", "install", "advisory", f"검사기 {state}" + (f" — 빠짐: {', '.join(missing)}" if missing and len(missing) < len(want) else ""),
                            f"프로필 {prof} 템플릿 {len(want)}개 중 {len(want) - len(missing)}개를 Tier P enforcement/ 또는 저장소에서 찾음",
                            f"{KIT.name}/profiles/{prof}/enforcement/README.md 대로 설치, 또는 프로젝트의 검사기를 kb enforce run 으로 감싼다"))
    if entries:
        last = max(entries, key=lambda e: str(e.get("at", "")))
        out.append(Item("enforcement", "run", "advisory", f"마지막 검사기 실행 {str(last.get('at'))[:10]} — {last.get('kind')} ({last.get('family')})",
                        f"{led.relative_to(vault)} 기록 {len(entries)}건, kit {last.get('kit_revision')}",
                        "python3 -m kb enforce run --family <묶음> -- <검사기 명령> 로 계속 돌린다"))
    elif want:
        out.append(Item("enforcement", "run", "advisory", "검사기 실행 증거 없음 — 직접 돌린 실행(run.sh 등)은 기록되지 않습니다",
                        f"{(led.relative_to(vault) if led else 'projects/' + pid + '/measurements/violations.yaml')} 없음",
                        "python3 -m kb enforce run --family <묶음> -- <검사기 명령> 으로 감싼다 (DEC-2026-10-31-24)"))
        if pstatus == "active":
            out.append(Item("enforcement", "active_without_evidence", "advisory", f"프로필 {prof} 은 active 인데 이 프로젝트에 실행 증거가 없습니다",
                            f"{KIT.name}/profiles/{prof}/profile.yaml status active, 기록 없음 (DEC-2026-10-30-04 의 기준)",
                            "검사기를 kb enforce run 으로 감싸 기록을 남기거나 active 판정을 다시 본다"))
    return out


def check_solo_decisions(project: Path, **_) -> list[Item]:
    t = tier_of(project)
    if t is None or not t.decisions_dir.is_dir():
        return []
    from kb.legacy.decision import derive_status
    recs = []
    for f in sorted(t.decisions_dir.glob("DEC-*.yaml")):
        body = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("decision")
        if isinstance(body, dict) and body.get("id"):
            recs.append((f, body))
    status = derive_status(recs)
    out = []
    for f, b in recs:
        if str(b.get("verification_tier") or "solo") != "solo" or status.get(str(b["id"]), ("active",))[0] != "active":
            continue
        aff = " ".join(map(str, b.get("affects") or []))
        core = [c for c in CORE_SOURCES if c in aff]
        prof = "profiles" in aff
        if not (core or prof):
            continue
        weight = "핵심 원천 — cross_verified 필수" if core else "프로필 문서 — cross_verified 권장"
        out.append(Item("solo_decisions", f"solo:{b['id']}", "advisory", f"{b['id']} 은 solo 검증으로 {weight}",
                        f"affects 경로 조각 {', '.join(core) or 'profiles'} (자유 문장을 조각으로 찾음 — 놓치거나 잘못 잡을 수 있음)",
                        "strata.review 로 다른 벤더 교차 리뷰 → strata.decision 으로 레코드 갱신 또는 대체"))
    return out


def check_guidance_lag(project: Path, **_) -> list[Item]:
    seen: dict[str, list[str]] = {}
    for n in ("AGENTS.md", "CLAUDE.md"):
        p = project / n
        if p.is_file():
            m = re.search(r"core_revision:\s*([0-9a-f]+)(\+dirty)?", (p.read_text(encoding="utf-8").splitlines() or [""])[0])
            if m:
                seen.setdefault(m.group(1) + (m.group(2) or ""), []).append(n)
    out = []
    for raw, files in seen.items():
        rev, dirty = raw.replace("+dirty", ""), raw.endswith("+dirty")
        tag = " (더러운 작업 트리에서 생성됨)" if dirty else ""
        if _git(KIT, "cat-file", "-e", f"{rev}^{{commit}}").returncode != 0:
            out.append(Item("guidance", "lag", "advisory", f"생성 지침 리비전 {rev} 이 kit 이력에 없어 비교 불가{tag}", f"{', '.join(files)} 머리말",
                            "strata.init-wizard (recommend → generate → verify)"))
            continue
        total = int(_git(KIT, "rev-list", "--count", f"{rev}..HEAD").stdout.strip() or 0)
        impact = int(_git(KIT, "rev-list", "--count", f"{rev}..HEAD", "--", *GUIDANCE_PATHS).stdout.strip() or 0)
        if impact or dirty:   # any commit touching what the guidance is generated from (DEC-2026-10-31-27)
            out.append(Item("guidance", "lag", "advisory", f"생성 지침이 kit 보다 {total}커밋 뒤, 그중 지침에 영향 주는 커밋 {impact}{tag}",
                            f"{', '.join(files)} 머리말 core_revision {rev}, kit HEAD {_git(KIT, 'rev-parse', '--short=12', 'HEAD').stdout.strip()}, 경로 {'·'.join(GUIDANCE_PATHS)}",
                            "strata.init-wizard (recommend → generate → verify)"))
    return out


def check_librarian(log: Path, label: str, launchctl: str = "launchctl", **_) -> list[Item]:
    fix = "core/templates/librarian/README.md 대로 다시 설치하고 로그의 마지막 실행 구간을 본다"
    out = []
    if not log.is_file():
        return [Item("librarian", "log", "advisory", "librarian 로그가 없어 확인할 수 없습니다", str(log), fix, machine=True)]
    text = log.read_text(encoding="utf-8", errors="replace")
    starts = [m.start() for m in re.finditer(r"^=== strata-librarian start .*$", text, re.M)]
    seg = text[starts[-1]:] if starts else text
    errors = [l for l in seg.splitlines() if re.search(r"Traceback|오류:|librarian step failed|Error\b", l)]
    end = re.search(r"^=== strata-librarian end .* failed (\d+).*$", seg, re.M)
    when = datetime.fromtimestamp(log.stat().st_mtime).isoformat(timespec="minutes")
    seg_note = "마지막 실행 구간" if starts else "실행 구분 없음(옛 설치) — 로그 전체"
    out.append(Item("librarian", "log", "advisory",
                    (f"librarian 마지막 실행에 오류 줄 {len(errors)}개" if errors else "librarian 마지막 실행에 오류 줄 없음")
                    + ("" if starts else " — 실행 구분이 없는 옛 설치"),
                    f"{log} 수정 {when}, {seg_note}" + (f", 끝 줄 failed {end.group(1)}" if end else "") + (f", 첫 오류: {errors[0][:120]}" if errors else ""),
                    fix, machine=True))
    try:
        r = subprocess.run([launchctl, "print", f"gui/{os.getuid()}/{label}"], capture_output=True, text=True)
    except OSError:
        r = None
    if r is None or r.returncode != 0:
        out.append(Item("librarian", "launchd", "advisory", f"launchd 작업 {label} 을 확인할 수 없습니다", (r.stderr.strip()[:120] if r else "launchctl 없음") or "등록되지 않음", fix, machine=True))
    else:
        runs = re.search(r"\bruns = (\d+)", r.stdout)
        code = re.search(r"last exit code = (-?\d+)", r.stdout)
        out.append(Item("librarian", "launchd", "advisory", f"launchd 작업 {label}: 마지막 종료 코드 {code.group(1) if code else '?'}",
                        f"launchctl print — runs {runs.group(1) if runs else '?'}", fix, machine=True))
    return out


# ---------------------------------------------------------------- run

PROJECT_CHECKS = (("verify", check_verify), ("coverage", check_coverage), ("hygiene", check_hygiene), ("links", check_links),
                  ("decisions", check_uncommitted), ("enforcement", check_enforcement), ("solo_decisions", check_solo_decisions),
                  ("guidance", check_guidance_lag))


def run(project: Path, since: str | None = None, librarian_log: Path | None = None, librarian_label: str | None = None,
        launchctl: str = "launchctl", vault: Path | None = None, checks=PROJECT_CHECKS, today: str | None = None) -> dict:
    os.environ["KB_NO_REFRESH"] = "1"   # anything nested that opens the store opens it as it is
    from kb import vault_root
    vault = vault or vault_root()
    items: list[Item] = []
    store, sitems = open_store(vault)
    items += sitems
    stale = any(i.key == "store_age" for i in sitems)
    ctx = {"store": store, "vault": vault, "since": since, "stale": stale}
    for name, fn in checks:
        try:
            items += fn(project, **ctx)
        except Exception as e:  # noqa: BLE001 — one check never stops the others, and a failure is not a pass
            items.append(Item(name, f"check_failed:{name}", "default", f"점검 실패: {type(e).__name__}: {e}",
                              traceback.format_exc().strip().splitlines()[-1][:200], f"tools/doctor.py 의 {name} 점검을 고친다"))
    if store is not None:
        store.close()
    log = librarian_log or Path(os.environ.get("STRATA_LIBRARIAN_LOG") or Path.home() / "Library" / "Logs" / "strata-librarian.log")
    label = librarian_label or os.environ.get("STRATA_LIBRARIAN_LABEL") or f"com.{getpass.getuser()}.strata-librarian"
    try:
        items += check_librarian(log, label, launchctl)
    except Exception as e:  # noqa: BLE001
        items.append(Item("librarian", "check_failed:librarian", "advisory", f"점검 실패: {type(e).__name__}: {e}", "기계 상태라 종료 코드에 넣지 않음",
                          "tools/doctor.py 의 librarian 점검을 고친다", machine=True))
    t = tier_of(project)
    ov = (t.root if t else project / ".strata") / "gate-overrides.yaml"
    graded = [i for i in items if not i.machine]
    by_key = {(i.check, i.key): i for i in graded}
    r = evaluate([Finding(i.check, i.key, i.grade, i.message) for i in graded], load_overrides(ov), today)
    for f in r["blocked"]: by_key[(f.check, f.key)].status = "blocked"
    for f in r["unresolved"]: by_key[(f.check, f.key)].status = "unresolved"
    for f in r["advisory"]: by_key[(f.check, f.key)].status = "advisory"
    for f, o in r["overridden"]:
        by_key[(f.check, f.key)].status = "overridden"; by_key[(f.check, f.key)].override = {"reason": o.get("reason"), "until": o.get("until")}
    for f, o in r["expired"]:
        by_key[(f.check, f.key)].override = {"expired": True, "reason": o.get("reason"), "until": o.get("until")}
    for i in items:
        if i.machine: i.status = "machine"
    return {"project": str(project), "vault": str(vault) if vault else None, "rc": r["rc"], "overrides_file": str(ov),
            "items": [asdict(i) for i in items]}


def render(res: dict) -> str:
    L = [f"doctor — {res['project']} (rc {res['rc']})"]
    items = res["items"]
    sel = {"block": lambda i: i["status"] == "blocked",
           "default": lambda i: i["grade"] == "default" and not i["machine"],
           "advisory": lambda i: i["grade"] == "advisory" and not i["machine"],
           "machine": lambda i: i["machine"]}
    for g, title in GROUPS:
        rows = [i for i in items if sel[g](i)]
        L.append(f"\n## {title} ({len(rows)})")
        for i in rows:
            tag = {"overridden": f" — 덮어씀: {i['override'].get('reason')} (~{i['override'].get('until')})", "unresolved": ""}.get(i["status"], "")
            if i["override"].get("expired"):
                tag += f" — 기한 지난 덮어쓰기: {i['override'].get('reason')} (~{i['override'].get('until')})"
            L += [f"- [{i['check']}] {i['message']}{tag}", f"    근거: {i['evidence']}", f"    고칠 방법: {i['fix']}"]
    L.append(f"\n덮어쓰기 파일: {res['overrides_file']}")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tools/doctor.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--since", help="커버리지 게이트 기간 시작일 YYYY-MM-DD (기본 오늘)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--librarian-log", help="기본 $STRATA_LIBRARIAN_LOG 또는 ~/Library/Logs/strata-librarian.log")
    ap.add_argument("--librarian-label", help="기본 $STRATA_LIBRARIAN_LABEL 또는 com.<사용자>.strata-librarian")
    a = ap.parse_args(argv)
    res = run(Path(a.project).resolve(), a.since, Path(a.librarian_log).expanduser() if a.librarian_log else None, a.librarian_label)
    print(json.dumps(res, ensure_ascii=False, indent=2) if a.json else render(res), end="" if not a.json else "\n")
    return res["rc"]


if __name__ == "__main__":
    sys.exit(main())
