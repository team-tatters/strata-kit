"""The user skill layer (planning/user-skill-layer, DEC-2026-10-31-36).

One layer, two sources, under ~/.strata/skills (STRATA_USER_SKILLS overrides the path):

  packs/<pack>/registry.yaml   installed and updated by the kit (`kb skills install <pack>`); the user does not edit it
  local/registry.yaml          the user's own skills

Each registry lists routes like the core registry (skill, intent, triggers) plus `stage` and `kind`; a skill's
directory sits next to its registry under the skill's name, with a SKILL.md. Layers are read core → profile → user →
project. The user layer only adds: a name another layer already has is refused — except a user skill that names
the core skill it replaces with `overrides: <skill>`, which the session header then always shows. Skills are
classified by flow stage and kind, never by persona: what a person uses is what they installed.

  python3 -m kb skills check   [--project DIR]
  python3 -m kb skills install <pack> [--apply]
  python3 -m kb skills link    --harness claude|codex [--apply]
  python3 -m kb skills next    <skill> [--project DIR] [--standing AREA=decides|proposes ...]

`next` shows what may follow a skill (DEC-2026-10-31-37): the route's `next:` candidates ({skill, why, area,
on_proposes}), or the skill's entry in next.yaml beside the registry (the core keeps them there, DEC-2026-11-01-15), with their reasons, ordered by the project's optional `standing: {<area>: decides|proposes}` in its
profile.yaml (unset areas decide). A proposes area rewords a candidate with its on_proposes text, or moves it after the
others. "Do nothing" is always offered last. Nothing is blocked: the command always exits 0.
"""
from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[1]
STAGES = ("ideation", "planning", "design", "spec", "build", "verify", "review", "release", "operate", "retro")
KINDS = ("procedure", "check", "rule")
HARNESS_DIRS = {"claude": Path.home() / ".claude" / "skills", "codex": Path.home() / ".codex" / "skills"}


def user_root() -> Path:
    return Path(os.environ.get("STRATA_USER_SKILLS") or Path.home() / ".strata" / "skills")


@dataclass
class Entry:
    skill: str
    origin: str          # pack:<name> | local
    dir: Path
    stage: str = ""
    kind: str = ""
    overrides: str = ""
    problems: list[str] = field(default_factory=list)


def _routes(p: Path) -> list[dict]:
    try:
        return [r for r in ((yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("routes") or []) if isinstance(r, dict) and r.get("skill")]
    except (OSError, yaml.YAMLError):
        return []


def _next_file(registry: Path) -> dict:
    """{skill: [candidates]} from next.yaml beside a registry, or {} (DEC-2026-11-01-15)."""
    p = registry.parent / "next.yaml"
    try:
        data = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("next") if p.is_file() else None
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def user_entries(root: Path | None = None) -> list[Entry]:
    root = root or user_root()
    regs = [(f"pack:{p.parent.name}", p) for p in sorted((root / "packs").glob("*/registry.yaml"))]
    if (root / "local" / "registry.yaml").is_file():
        regs.append(("local", root / "local" / "registry.yaml"))
    out = []
    for origin, reg in regs:
        for r in _routes(reg):
            e = Entry(str(r["skill"]), origin, reg.parent / str(r["skill"]), str(r.get("stage") or ""), str(r.get("kind") or ""),
                      str(r.get("overrides") or ""))
            if e.stage not in STAGES:
                e.problems.append(f"stage {e.stage or '없음'} — {', '.join(STAGES)} 중 하나")
            if e.kind not in KINDS:
                e.problems.append(f"kind {e.kind or '없음'} — {', '.join(KINDS)} 중 하나")
            if not (e.dir / "SKILL.md").is_file():
                e.problems.append(f"SKILL.md 없음 — {e.dir}")
            out.append(e)
    return out


def resolve(core: list[str], profile: list[str], project: list[str], entries: list[Entry]) -> dict:
    """Accepted user skills, explicit core overrides, and refusals with their reason. The user layer only adds."""
    taken = {s: "core" for s in core}
    taken.update({s: "profile" for s in profile})
    taken.update({s: "project" for s in project})
    accepted, overrides, refused = [], [], []
    for e in [x for x in entries if x.origin != "local"] + [x for x in entries if x.origin == "local"]:
        if e.problems:
            refused.append((e, "; ".join(e.problems)))
            continue
        owner = taken.get(e.skill)
        if owner is None:
            taken[e.skill] = e.origin
            accepted.append(e)
        elif owner == "core" and e.overrides == e.skill and e.origin == "local":
            overrides.append(e)
            accepted.append(e)
            taken[e.skill] = e.origin
        else:
            why = f"{owner} 층에 같은 이름이 있다 — 사용자 층은 더하기만 한다"
            if owner == "core":
                why += f" (코어를 바꾸려면 local 스킬에 overrides: {e.skill} 을 적는다)"
            refused.append((e, why))
    return {"accepted": accepted, "overrides": overrides, "refused": refused}


def layer_status(core_reg: Path, profile_reg: Path | None, project_regs: list[Path], root: Path | None = None) -> dict:
    names = lambda ps: [str(r["skill"]) for p in ps if p and p.is_file() for r in _routes(p)]
    entries = user_entries(root)
    r = resolve(names([core_reg]), names([profile_reg]), names(project_regs), entries)
    r["packs"] = sorted({e.origin.split(":", 1)[1] for e in entries if e.origin.startswith("pack:")})
    r["local"] = sum(1 for e in entries if e.origin == "local")
    r["present"] = bool(entries)
    return r


def status_text(r: dict) -> str:
    """The header's user part: 'user absent' or 'user ok(packs a · local N · overrides: x · refused N)'."""
    if not r["present"]:
        return "user absent"
    bits = [f"packs {', '.join(r['packs'])}" if r["packs"] else "packs none", f"local {r['local']}"]
    if r["overrides"]:
        bits.append("overrides: " + ", ".join(e.skill for e in r["overrides"]))
    if r["refused"]:
        bits.append(f"refused {len(r['refused'])} (kb skills check)")
    return f"user ok({' · '.join(bits)})"


def install(pack: str, apply: bool = False, root: Path | None = None, today: str | None = None) -> list[str]:
    """Copy the kit's skills/packs/<pack>/ into the user layer. Files that would change are kept under .archive/ first;
    the user's local/ is never touched. Without apply, only says what it would do."""
    src = KIT / "skills" / "packs" / pack
    if not (src / "registry.yaml").is_file():
        raise ValueError(f"kit 에 팩 {pack} 없음 — {src}/registry.yaml")
    root = root or user_root()
    dst = root / "packs" / pack
    plan = []
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = f.relative_to(src)
        t = dst / rel
        if not t.exists():
            plan.append(("new", rel))
        elif not filecmp.cmp(f, t, shallow=False):
            plan.append(("update", rel))
    lines = [f"{'설치' if apply else '미리보기'}: {pack} → {dst}"] + [f"  {k} {rel}" for k, rel in plan] + ([] if plan else ["  바뀐 것 없음"])
    if apply:
        stamp = today or date.today().isoformat()
        for kind, rel in plan:
            t = dst / rel
            if kind == "update":
                keep = root / ".archive" / stamp / "packs" / pack / rel
                keep.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(t, keep)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / rel, t)
    return lines


def link(harness: str, apply: bool = False, root: Path | None = None, target: Path | None = None, project: Path | None = None) -> list[str]:
    """Link each accepted user-layer skill directory into the harness's user skill folder. Only links that point into
    the user layer are replaced; any other file or folder of the same name is left alone and reported."""
    root = (root or user_root()).resolve()
    target = target or HARNESS_DIRS[harness]
    r = layer_status(KIT / "skills" / "registry.yaml", None, [], root)
    lines = [f"{'연결' if apply else '미리보기'}: {harness} → {target}"]
    for e, why in r["refused"]:
        lines.append(f"  거부 {e.skill} ({e.origin}): {why}")
    for e in r["accepted"]:
        t = target / e.dir.name
        if t.is_symlink() and str(Path(os.readlink(t))).startswith(str(root)):
            state = "same" if Path(os.readlink(t)) == e.dir.resolve() else "relink"
        elif t.exists() or t.is_symlink():
            lines.append(f"  건너뜀 {e.skill}: {t} 이 이미 있다(kit 이 만든 링크가 아님)")
            continue
        else:
            state = "new"
        lines.append(f"  {state} {e.skill} ({e.origin}) → {e.dir}")
        if apply and state != "same":
            target.mkdir(parents=True, exist_ok=True)
            if t.is_symlink():
                t.unlink()   # only a link this layer made — the skill directory itself stays
            t.symlink_to(e.dir.resolve(), target_is_directory=True)
    return lines


STANDINGS = ("decides", "proposes")


def _text(v) -> str:
    if isinstance(v, dict):
        return str(v.get("ko") or v.get("en") or next(iter(v.values()), ""))
    return str(v or "")


def user_registries(root: Path | None = None) -> list[Path]:
    root = root or user_root()
    return sorted((root / "packs").glob("*/registry.yaml")) + [p for p in [root / "local" / "registry.yaml"] if p.is_file()]


def next_candidates(skill: str, registries: list[Path], standing: dict | None = None) -> list[str]:
    """The candidates that may follow `skill`, reasons attached, ordered by standing; never a command to proceed."""
    standing = {k: v for k, v in (standing or {}).items() if v in STANDINGS}
    route, cands = None, []
    for reg in registries:          # later layers win, as in routing
        for r in _routes(reg):
            if str(r["skill"]) == skill:
                route, cands = r, list(r.get("next") or [])
        side = _next_file(reg).get(skill)   # next.yaml beside the registry (DEC-2026-11-01-15)
        if side is not None:
            cands = list(side or [])
    if route is None:
        return [f"{skill}: 어느 층의 레지스트리에도 없다 — 후보 없음", "  1. 아무것도 안 함"]
    first, later = [], []
    for c in cands:
        if not isinstance(c, dict) or not c.get("skill"):
            continue
        area = str(c.get("area") or "")
        seat = standing.get(area, "decides") if area else "decides"
        why = _text(c.get("why"))
        if seat == "proposes" and c.get("on_proposes"):
            first.append(f"{c['skill']} — {_text(c['on_proposes'])} [{area}: proposes]")
        elif seat == "proposes":
            later.append(f"{c['skill']} — {why} (이 영역은 제안 자리 — 결정은 owner 에게) [{area}: proposes]")
        else:
            first.append(f"{c['skill']} — {why}" + (f" [{area}: decides]" if area else ""))
    items = first + later + ["아무것도 안 함 — 지금은 여기서 멈춘다"]
    return [f"{skill} 다음 후보 (고르는 것은 사용자, 안건마다 자리를 바꿔 고를 수 있다)"] + [f"  {n}. {x}" for n, x in enumerate(items, 1)]


def project_standing(project: Path) -> dict:
    sys.path.insert(0, str(KIT / "tools"))
    import wizard
    tier = wizard.tier_of(project)
    prof = (tier.root if tier else project / ".strata") / "profile.yaml"
    data = wizard.load_yaml(prof) or {} if prof.is_file() else {}
    return {str(k): str(v) for k, v in (data.get("standing") or {}).items()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb skills", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("--project", default=".")
    i = sub.add_parser("install"); i.add_argument("pack"); i.add_argument("--apply", action="store_true")
    ln = sub.add_parser("link"); ln.add_argument("--harness", choices=list(HARNESS_DIRS), required=True); ln.add_argument("--apply", action="store_true")
    nx = sub.add_parser("next"); nx.add_argument("skill"); nx.add_argument("--project", default=".")
    nx.add_argument("--standing", action="append", default=[], help="AREA=decides|proposes, for this agenda only")
    a = ap.parse_args(argv)
    if a.cmd == "next":
        project = Path(a.project).resolve()
        sys.path.insert(0, str(KIT / "tools"))
        import wizard
        tier = wizard.tier_of(project)
        standing = project_standing(project)
        standing.update(dict(x.split("=", 1) for x in a.standing if "=" in x))
        regs = [KIT / "skills" / "registry.yaml", *sorted((KIT / "skills" / "packs").glob("*/registry.yaml")),   # kit pack source, read even before install
                *user_registries(), *wizard.project_registries(project, tier)]
        print("\n".join(next_candidates(a.skill, regs, standing)))
        return 0
    if a.cmd == "install":
        try:
            print("\n".join(install(a.pack, a.apply)))
        except ValueError as e:
            print(f"오류: {e}", file=sys.stderr)
            return 2
        return 0
    if a.cmd == "link":
        print("\n".join(link(a.harness, a.apply)))
        return 0
    sys.path.insert(0, str(KIT / "tools"))
    import wizard
    project = Path(a.project).resolve()
    tier = wizard.tier_of(project)
    prof = (wizard.load_yaml((tier.root if tier else project / ".strata") / "profile.yaml") or {}).get("kit_profile") if (tier or (project / ".strata" / "profile.yaml").is_file()) else None
    r = layer_status(KIT / "skills" / "registry.yaml", KIT / "profiles" / str(prof) / "skills" / "registry.yaml" if prof else None,
                     wizard.project_registries(project, tier))
    print(f"사용자 층 — {user_root()}: {status_text(r)}")
    for e in r["accepted"]:
        print(f"  ok {e.skill} ({e.origin}, {e.stage}·{e.kind})" + (f" — 코어 {e.overrides} 를 덮어씀" if e in r["overrides"] else ""))
    for e, why in r["refused"]:
        print(f"  거부 {e.skill} ({e.origin}): {why}")
    return 2 if r["refused"] else 0


if __name__ == "__main__":
    sys.exit(main())
