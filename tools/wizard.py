#!/usr/bin/env python3
"""strata-kit guidance wizard — the deterministic half of skills/strata.init-wizard.

Subcommands — each prints its result and writes nothing unless --apply (into <project>/.strata/kit/) or --out DIR:
  diagnose  <project> [--apply|--out DIR]  detect profiles from files, measure budget, list open questions
                                           (writes diagnosis.yaml)
  recommend <project> --profile <id>       build a proposal: must cards + profile should cards (+ waivers)
            [--waive card=reason ...] [--locale xx] [--domain work|personal] [--apply|--out DIR]
                                           (writes proposal.yaml; an approved proposal.yaml is never replaced —
                                           the new one goes to proposal.next.yaml for the person to review)
  generate  <project> [--apply|--out DIR]  write adapters listed in the approved .strata/kit/proposal.yaml
  verify    <project>                      budget, revision headers, registry, trigger samples (read-only)

Previous answers (opt-in adoption, facts) are read from the last proposal: for a detached project the vault's Tier P
kit/proposal.yaml first (the repo copy can be stale), then <project>/.strata/kit/proposal.yaml. An answer given on the
command line wins. The kit root is this file's grandparent unless --kit is given.
"""
from __future__ import annotations
import argparse, fnmatch, hashlib, json, os, re, subprocess, sys, time
from datetime import date
from pathlib import Path
try:
    import yaml
except ImportError:  # pragma: no cover
    print("PyYAML is required", file=sys.stderr); sys.exit(1)

KIT = Path(__file__).resolve().parents[1]
LOCALES = ["en", "ko", "ja", "zh", "es", "fr"]
LOADED_BUDGET_BYTES = 14 * 1024   # total incl. inherited guidance — lower only, raising needs a decision (DEC-2026-10-29-07)
BUDGET_BYTES = 12 * 1024          # CB-1: always-loaded set (AGENTS.md + CLAUDE.md); diagnose also counts a legacy embedded T0 (registry, decisions index)
LAYER_EXAMPLES = 2                 # paths shown per layer in AGENTS.md; the full map is linked (file-granular maps run long)
REGISTRY_SUMMARY_BYTES = 2 * 1024  # the constraint summary rendered into AGENTS.md (the full registry is linked)
LAYER_MAP_LINES = 30
if str(KIT) not in sys.path: sys.path.insert(0, str(KIT))
try:
    from kb.legacy.strata_paths import resolve_tier_p   # placement: embedded (.strata in the repo) or detached (vault/projects/<n>/strata)
except Exception:  # pragma: no cover
    resolve_tier_p = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime_env  # noqa: E402  — the runtime environment step (MB-strata-kit-2026-058)

# interview answers recommend keeps in the proposal (--answer key=value, --because key=reason) and carries to the next
INTERVIEW_KEYS = ("team_size", "lifetime", "cross_domain_writes", "shared_envs", "runtime", "strata_python")
RUNTIME_FILES = ("env.sh", "claude-settings.json", "mcp.json", "launchd-environment.plist.xml")

def tier_of(project: Path):
    """TierP for the project (profile 'embedded' | 'detached', root with decisions/ · layer-map · registry) or None."""
    if resolve_tier_p is None: return None
    try: return resolve_tier_p(project)
    except ValueError: return None

def vault_root() -> Path | None:
    v = os.environ.get("STRATA_VAULT")
    return Path(os.path.expanduser(v)).resolve() if v else None

def show_path(p) -> str:
    """Render a path for the adapters: inside the vault as $STRATA_VAULT/…, never a machine-specific absolute path."""
    p = Path(p); v = vault_root()
    if v:
        try: return "$STRATA_VAULT/" + p.resolve().relative_to(v).as_posix()
        except ValueError: pass
    for repo in p.resolve().parents:   # embedded Tier P: relative to the repository the adapter sits in
        if (repo / ".git").exists():
            return p.resolve().relative_to(repo).as_posix()
    return str(p)

def t(m, locale: str) -> str:
    """pick a localized string with the LOCALES.md fallback order."""
    if isinstance(m, str): return m
    if not isinstance(m, dict): return str(m)
    return m.get(locale) or m.get("en") or m.get("ko") or next(iter(m.values()), "")

def load_yaml(p: Path):
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}

def kit_revision(kit: Path) -> str:
    try:
        rev = subprocess.run(["git", "-C", str(kit), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(kit), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
        return (rev or "unborn") + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"

def cards(kit: Path) -> dict:
    out = {}
    for p in sorted((kit / "core" / "cards").glob("*.yaml")):
        c = load_yaml(p).get("card", {})
        if c.get("id"): out[c["id"]] = c
    return out

def profiles(kit: Path) -> dict:
    out = {}
    for p in sorted((kit / "profiles").glob("*/profile.yaml")):
        pr = load_yaml(p).get("profile", {})
        if pr.get("id"): out[pr["id"]] = pr
    return out

# ---------- diagnose ----------
def _match_profile(project: Path, pr: dict) -> list[str]:
    hits = []
    d = pr.get("detect", {}) or {}
    def candidates(pattern: str):
        # the project root first, then one and two levels down (pnpm/turbo/gradle monorepos keep apps under apps/*, services/*)
        for depth in ("", "*/", "*/*/"):
            for x in sorted(project.glob(depth + pattern)):
                if "node_modules" in x.parts or ".git" in x.parts: continue
                yield x
    for f in d.get("any_files", []) or []:
        hit = next(candidates(f), None)
        if hit: hits.append(f"file:{hit.relative_to(project).as_posix()}")
    for g in d.get("any_glob", []) or []:
        if any(fnmatch.fnmatch(x.name, g) for x in project.iterdir()): hits.append(f"glob:{g}")
    for pat, needle in d.get("any_content", []) or []:
        for x in candidates(pat):
            try:
                if needle in x.read_text(encoding="utf-8", errors="ignore"): hits.append(f"content:{x.relative_to(project).as_posix()}~{needle}"); break
            except Exception: pass
    return hits

def always_loaded(project: Path) -> dict[str, int]:
    """What a session here loads every time: AGENTS.md + CLAUDE.md (DEC-2026-10-29-02). The constraint registry and the
    decision index are linked and read on demand in both placements — diagnose and verify count the same files
    (MB-strata-kit-2026-031: diagnose used to add them for embedded projects and reported a budget verify passed)."""
    return {n: (project / n).stat().st_size for n in ("AGENTS.md", "CLAUDE.md") if (project / n).is_file()}

def diagnose(project: Path, kit: Path) -> dict:
    prs = profiles(kit)
    matched = {pid: h for pid, pr in prs.items() if (h := _match_profile(project, pr))}
    tier = tier_of(project)
    always = always_loaded(project)
    manifest = (tier.root / "profile.yaml") if tier else (project / ".strata" / "profile.yaml")
    existing = load_yaml(manifest) if manifest.is_file() else {}
    questions = [
        {"key": "domain", "en": "Is this work (company) or personal? It decides where handoffs and knowledge go.", "ko": "업무(회사) 프로젝트입니까, 개인 프로젝트입니까? 핸드오프와 지식이 갈 곳이 정해집니다."},
        {"key": "team_size", "en": "How many people work on this project?", "ko": "이 프로젝트에 몇 명이 함께 일합니까?"},
        {"key": "lifetime", "en": "Expected lifetime: months, years, or one-off?", "ko": "예상 수명은 몇 달, 몇 년, 아니면 일회성입니까?"},
        {"key": "cross_domain_writes", "en": "How many domains write into each other's data?", "ko": "서로의 데이터를 쓰는 도메인 경계가 몇 개입니까?"},
        {"key": "shared_envs", "en": "Which shared environments exist (dev, stage, prod)?", "ko": "공유 환경(dev·stage·prod)은 무엇이 있습니까?"},
        {"key": "harnesses", "en": "Which harnesses run here (Claude Code, Codex, Quilt)?", "ko": "어떤 하네스를 씁니까(Claude Code, Codex, Quilt)?"},
        {"key": "runtime", "en": "Which python should the kit run on, the same in every execution path? Options: " + ", ".join(runtime_env.OPTIONS) + f" (default {runtime_env.DEFAULT_CHOICE}: {runtime_env.DEFAULT_REASON['en']}).",
         "ko": "kit 이 모든 실행 경로에서 같은 python 으로 돌게 무엇을 쓸까요? 선택지: " + ", ".join(runtime_env.OPTIONS) + f" (기본 {runtime_env.DEFAULT_CHOICE}: {runtime_env.DEFAULT_REASON['ko']})."},
    ]
    try:
        runtime = runtime_env.detect(project, kit)
        runtime["findings"] = runtime_env.findings(runtime)
    except Exception as e:  # noqa: BLE001 — a failed measurement is reported, never a silent pass
        runtime = {"error": f"{type(e).__name__}: {e}"}
    if len(matched) > 1:
        questions.insert(0, {"key": "profile_choice", "en": f"Several profiles match ({', '.join(matched)}). Which one is primary?", "ko": f"프로필이 여럿 맞습니다({', '.join(matched)}). 어느 것이 주 프로필입니까?"})
    return {
        "project": str(project), "kit_revision": kit_revision(kit), "date": str(date.today()),
        "existing_manifest": existing or None,
        "placement": (tier.profile if tier else "none"), "tier_p_root": (str(tier.root) if tier else None),
        "matched_profiles": matched,
        "always_loaded_bytes": always, "always_loaded_total": sum(always.values()), "budget_bytes": BUDGET_BYTES,
        "budget_ok": sum(always.values()) <= BUDGET_BYTES,
        "runtime": runtime,
        "open_questions": questions, "answers": {},
    }

# ---------- recommend ----------
def user_adopt_list() -> list[str]:
    """The user's layer for opt-in must cards (DEC-2026-10-29-14): wizard.adopt_cards in ~/.strata/config.yaml
    (STRATA_USER_CONFIG overrides the path). Cards named here are proposed already adopted in every project."""
    p = Path(os.environ.get("STRATA_USER_CONFIG") or Path.home() / ".strata" / "config.yaml")
    try:
        return list(((load_yaml(p) or {}).get("wizard") or {}).get("adopt_cards") or []) if p.is_file() else []
    except Exception:
        return []


RESTART_LINES = {"restart_tokens": 400_000, "restart_limit": 600_000}   # DEC-2026-10-31-33: starting values, unmeasured


def restart_lines() -> tuple[int, int]:
    """The conversation sizes for a new session (DEC-2026-10-31-09·33): past the warning line the agent wraps up the unit
    and splits at the next task boundary, before the limit at the latest. session.restart_tokens and
    session.restart_limit in ~/.strata/config.yaml (STRATA_USER_CONFIG overrides the path), else 400,000 and 600,000."""
    p = Path(os.environ.get("STRATA_USER_CONFIG") or Path.home() / ".strata" / "config.yaml")
    try:
        cfg = ((load_yaml(p) or {}).get("session") or {}) if p.is_file() else {}
    except Exception:
        cfg = {}
    out = []
    for k, d in RESTART_LINES.items():
        try:
            out.append(int(cfg.get(k) or d))
        except (TypeError, ValueError):
            out.append(d)
    return out[0], out[1]


ADOPT_Q = {"en": "Adopt “{title}” as a must card in this project? {claim}", "ko": "“{title}” 카드를 이 프로젝트의 must 로 채택합니까? {claim}"}


ENFORCE_FAMILIES = ("layers", "naming", "rules", "coverage", "links", "stages")   # coverage·links: DEC-2026-10-30-01, stages: DEC-2026-11-01-18   # rule families a project grades (DEC-2026-10-29-17); others may be added
ENFORCE_GRADES = ("advisory", "default", "block")


def previous_proposal(project: Path) -> tuple[Path | None, dict]:
    """The last proposal a person answered: a detached project's vault copy (Tier P kit/proposal.yaml) first — the repo
    copy can be stale — then the repo's .strata/kit/proposal.yaml. (None, {}) when there is none."""
    tier = tier_of(project)
    cands = ([tier.root / "kit" / "proposal.yaml"] if tier and tier.profile == "detached" else []) + [project / ".strata" / "kit" / "proposal.yaml"]
    for c in cands:
        if c.is_file():
            try:
                return c, load_yaml(c) or {}
            except Exception:
                continue
    return None, {}


def previous_answers(project: Path) -> tuple[dict, str | None]:
    """Opt-in adoption answers a person gave in the last proposal: {card id: True | (False, reason)}, and where from."""
    path, prev = previous_proposal(project)
    out = {}
    for a in prev.get("adoption") or []:
        if isinstance(a, dict) and a.get("id") and a.get("answered"):
            out[a["id"]] = True if a.get("adopted") else (False, a.get("declined_reason"))
    return out, (show_path(path) if path else None)


def interview_answers(project: Path, given: dict | None = None) -> dict:
    """{key: {value, reason}}: the last proposal's answers, then the ones given now (which win). Unknown keys refuse."""
    prev = previous_proposal(project)[1].get("answers") or {}
    out = {k: v for k, v in prev.items() if k in INTERVIEW_KEYS and isinstance(v, dict) and "value" in v}
    for k, v in (given or {}).items():
        if k not in INTERVIEW_KEYS:
            raise SystemExit(f"unknown answer {k!r} (one of {', '.join(INTERVIEW_KEYS)})")
        out[k] = {"value": v.get("value"), "reason": v.get("reason")}
    return out


def runtime_section(project: Path, kit: Path, answers: dict, locale: str) -> dict:
    """The runtime step's proposal part: the options with pros and cons and the default; once answered, the choice,
    the one STRATA_PYTHON it means here (an explicit strata_python answer wins) and the setup steps."""
    lang = "ko" if locale == "ko" else "en"
    sec = {"choice": None, "default": runtime_env.DEFAULT_CHOICE, "default_reason": runtime_env.DEFAULT_REASON[lang],
           "options": {k: v[lang] for k, v in runtime_env.OPTIONS.items()},
           **runtime_env.layers_advice(runtime_env.managers(Path.home(), os.environ.get("PATH")),
                                       runtime_env.version_files([project, kit, Path.home()]), lang)}
    ans = (answers.get("runtime") or {}).get("value")
    if not ans:
        return sec
    if ans not in runtime_env.OPTIONS:
        raise SystemExit(f"runtime: unknown choice {ans!r} (one of {', '.join(runtime_env.OPTIONS)})")
    home = Path.home()
    explicit = (answers.get("strata_python") or {}).get("value")
    if explicit:
        py = os.path.expanduser(str(explicit))
    else:
        try:
            py = runtime_env.python_for(ans, kit, {"version_files": runtime_env.version_files([project, kit, home])}, home)
        except ValueError as e:
            raise SystemExit(str(e))
    shown = "~/" + Path(py).relative_to(home).as_posix() if Path(py).is_relative_to(home) else py
    sec.update({"choice": ans, "reason": (answers.get("runtime") or {}).get("reason"), "strata_python": shown,
                "setup": runtime_env.setup_steps(ans, py)})
    return sec


def project_facts(project: Path, domain: str, given: dict | None = None) -> dict:
    """Facts that decide conditional must cards and opt-in defaults (DEC-2026-10-30-01): the answers given now, else
    what the last proposal recorded, else what the environment shows. domain_work always follows the domain answer."""
    prev = previous_proposal(project)[1].get("facts") or {}
    v = vault_root()
    facts = {"uses_vault": prev.get("uses_vault", bool(v and v.is_dir())), "uses_quilt": prev.get("uses_quilt", False)}
    facts.update({k: bool(x) for k, x in (given or {}).items() if x is not None})
    facts["domain_work"] = domain == "work"
    return facts


def recommend(project: Path, kit: Path, profile_id: str, waivers: dict, locale: str, domain: str,
              answers: dict | None = None, enforcement: dict | None = None, facts: dict | None = None,
              interview: dict | None = None) -> dict:
    """answers: {card id: True | False | (False, reason)} for opt-in must cards (--adopt / --decline id=reason);
    unanswered ones default to the user's adopt list, then the profile's cards_default, then the card's default_when
    fact, else off. Conditional must cards load whenever their condition fact holds, without a question."""
    answers = answers or {}
    carried, carried_from = previous_answers(project)
    given_ids = set(answers)
    answers = {**{k: v for k, v in carried.items() if k not in given_ids}, **answers}
    facts = project_facts(project, domain, facts)
    cs, prs = cards(kit), profiles(kit)
    if profile_id not in prs: raise SystemExit(f"unknown profile: {profile_id} (have {', '.join(prs)})")
    const = load_yaml(kit / "core" / "constitution" / "constitution.yaml").get("constitution", {})
    chosen, waived, problems = [], [], []
    for cid in const.get("articles", []):
        c = cs.get(cid)
        if not c: problems.append(f"constitution lists missing card {cid}"); continue
        if cid in waivers: problems.append(f"must card {cid} cannot be waived; pushback recorded as counter_example candidate")
        chosen.append(_card_view(c, locale))
    core_should = [cid for cid, c in cs.items() if c.get("strength") == "should" and not c.get("profiles") and c.get("status") == "active"]
    excluded = set(prs[profile_id].get("cards_excluded", []) or [])
    prof_default = list(prs[profile_id].get("cards_default", []) or [])
    for cid in core_should + prof_default:
        c = cs.get(cid)
        if not c: problems.append(f"profile lists missing card {cid}"); continue
        if cid in excluded or c.get("adoption"): continue   # opt-in must cards are asked below
        if cid in waivers: waived.append({"id": cid, "waived_reason": waivers[cid]})
        else: chosen.append(_card_view(c, locale))
    # conditional must cards (DEC-2026-10-30-01): loaded without a question whenever the condition fact holds
    conditional = []
    for cid, c in sorted(cs.items()):
        if c.get("adoption") != "conditional" or c.get("status") != "active" or cid in excluded: continue
        on = bool(facts.get(c.get("condition")))
        conditional.append({"id": cid, "condition": c.get("condition"), "on": on})
        if on: chosen.append(_card_view(c, locale))
    # opt-in must cards (DEC-2026-10-29-14): every one is asked; the default says where it came from
    adoption, user, warnings = [], set(user_adopt_list()), []
    for cid, c in sorted(cs.items()):
        if c.get("adoption") != "opt_in" or c.get("status") != "active" or cid in excluded: continue
        default_from = ("user" if cid in user else "profile" if cid in prof_default
                        else f"fact:{c['default_when']}" if c.get("default_when") and facts.get(c["default_when"]) else None)
        ans = answers.get(cid)
        on, reason = (ans if isinstance(ans, tuple) else (ans, None)) if cid in answers else (default_from is not None, None)
        entry = {"id": cid, "adopted": bool(on), "answered": cid in answers, "default_from": default_from,
                 "question": (ADOPT_Q.get(locale) or ADOPT_Q["en"]).format(title=t(c.get("title"), locale), claim=t(c.get("short_claim") or c.get("claim"), locale))}
        if cid in answers and cid not in given_ids:
            entry["answer_from"] = f"previous proposal {carried_from}"
        if cid in answers and not on:
            entry["declined_reason"] = reason
            if not reason: warnings.append(f"{cid}: declined without a reason (--decline {cid}=<reason>)")
        adoption.append(entry)
        if on: chosen.append(_card_view(c, locale))
    # enforcement grades (DEC-2026-10-29-17): what the manifest already says, then the answers; undeclared stays block
    tier_now = tier_of(project)
    old = load_yaml((tier_now.root if tier_now else project / ".strata") / "profile.yaml") if ((tier_now.root if tier_now else project / ".strata") / "profile.yaml").is_file() else {}
    grades = {**((old or {}).get("enforcement") or {}), **(enforcement or {})}
    for fam, g in grades.items():
        if g not in ENFORCE_GRADES: problems.append(f"enforcement {fam}: unknown grade {g} (one of {', '.join(ENFORCE_GRADES)})")
    pushback = [{"card": cid, "note": reason} for cid, reason in waivers.items() if cid in const.get("articles", [])]
    said = interview_answers(project, interview)
    runtime = runtime_section(project, kit, said, locale)
    return {
        "project": project.name, "domain": domain, "profile": profile_id, "locale": locale,
        "kit_revision": kit_revision(kit), "constitution_version": const.get("version"),
        "facts": facts, "answers": said, "runtime": runtime, "cards": chosen, "conditional": conditional, "adoption": adoption, "warnings": warnings, "enforcement": grades, "waived": waived, "counter_example_candidates": pushback, "problems": problems,
        "placement": (tier_of(project).profile if tier_of(project) else "embedded"),
        "write_paths": ([] if (tier_of(project) and tier_of(project).profile == "detached") else [".strata/profile.yaml"])
                       + ["AGENTS.md", "CLAUDE.md", ".strata/kit/registry.yaml", f".strata/kit/quilt-charter.{locale}.md", f".strata/kit/quilt-piece.{locale}.md"]
                       + ([f".strata/kit/runtime/{n}" for n in (*RUNTIME_FILES, f"README.{locale}.md")] if runtime.get("choice") else []),
        "approved": False,
    }

def _card_view(c: dict, locale: str) -> dict:
    return {"id": c["id"], "strength": c.get("strength"), "title": t(c.get("title"), locale), "claim": t(c.get("claim"), locale),
            "evidence": [f"{e.get('kind')}: {e.get('ref')}" for e in c.get("evidence", [])],
            "counter_examples": [t(x, locale) for x in c.get("counter_examples", [])],
            "verification": t(c.get("verification"), locale)}

# ---------- generate ----------
GENERATED_MARKS = ("<!-- generated by strata-kit wizard", "# placement profile manifest", "# project skill registry layer")


def _handwritten(target: Path) -> bool:
    """An existing file the wizard did not write (no generated marker at its head)."""
    if not target.is_file(): return False
    head = target.read_text(encoding="utf-8", errors="replace").lstrip()[:200]
    return not head.startswith(GENERATED_MARKS)


def generate(project: Path, kit: Path, apply: bool, out: Path | None = None) -> list[str]:
    """apply=False prints sizes only; out=<dir> writes the files there instead of the project (review copy)."""
    pp = project / ".strata" / "kit" / "proposal.yaml"
    if not pp.is_file(): raise SystemExit("no proposal: run recommend first")
    prop = load_yaml(pp)
    if not prop.get("approved") and not out: raise SystemExit("proposal.yaml is not approved (set approved: true after the user reviews it); use --out <dir> for a review copy")
    core_ver = load_yaml(kit / "core" / "constitution" / "constitution.yaml").get("constitution", {}).get("version")
    if prop.get("constitution_version") != core_ver:   # DEC-2026-10-29-13: the proposal's must set is as old as its version
        raise SystemExit(f"proposal is stale: constitution {prop.get('constitution_version')} ≠ core {core_ver}; re-run recommend (same waivers) and approve again")
    locale = prop.get("locale", "en")
    rev, arev = kit_revision(kit), _adapter_revision(prop)   # the kit as it is now, not as it was when the proposal was written
    header = f"<!-- generated by strata-kit wizard | core_revision: {rev} | adapter_revision: {arev} | profile: {prop['profile']} | {date.today()} -->"
    musts = [c for c in prop["cards"] if c["strength"] == "must"]; shoulds = [c for c in prop["cards"] if c["strength"] != "must"]
    agents = [header, f"# {project.name} — Agent Harness (strata-kit)", "",
              f"Profile: `{prop['profile']}` · Domain: `{prop.get('domain','work')}` · Constitution: {prop.get('constitution_version')}", "",
              "## Entry", "", "Every session starts with the `using-strata` skill. It prints the context header and routes the task.", "",
              "## Must cards (never waived; full text in `$STRATA_KIT/core/cards/`)", ""]
    # entry-view budget (rec.context.entry-view-budget): must cards carry their claim; should cards are named with their
    # title only — the full card (claim, evidence, verification) is one read away in strata-kit/core/cards
    # MB-strata-kit-2026-016: the entry view carries each must card's one-line short_claim, read from the kit card at
    # generate time (the proposal keeps the full claim for review); a card without short_claim falls back to title + claim
    kit_cards = cards(kit)
    for c in musts:
        short = t((kit_cards.get(c["id"]) or {}).get("short_claim"), locale) if (kit_cards.get(c["id"]) or {}).get("short_claim") else None
        agents += [f"- **{c['id']}** — {short}" if short else f"- **{c['id']}** — {c['title']}. {c['claim']}"]
    if shoulds:
        agents += ["", "## Should cards (on by default; full text in `$STRATA_KIT/core/cards/`)", ""]
        agents += [" · ".join(f"`{c['id']}`" for c in shoulds)]   # ids only — the title is one read away (DEC-2026-11-02-01)
    if prop.get("waived"):
        agents += ["", "## Waived (with reasons)", ""]
        for w in prop["waived"]: agents += [f"- {w['id']}: {w['waived_reason']}"]
    tier = tier_of(project); prs = profiles(kit); pr = prs.get(prop["profile"], {})
    waived_ids = {w["id"] for w in prop.get("waived", [])}
    if any(cid in waived_ids for cid in (pr.get("cards_default") or [])) and not (tier and (tier.root / "layer-map.yaml").is_file()):
        pr = {**pr, "layers": None, "enforcement": None}   # the profile's layer card is waived and no map is declared: say so instead of listing layers
    agents += _layers_section(pr, tier, locale, prop.get("enforcement") or {})
    agents += _constraints_section(tier, locale)
    agents += _where_section(project, tier, locale)
    agents += _checklist_section(kit, locale)
    agents += _notes_section(project, locale)
    claude = [header, f"# {project.name}", "", "Read `AGENTS.md` first; it is the contract. This file is an index only.", "",
              f"- Profile: {prop['profile']}", "- Entry skill: using-strata", "- Must cards: " + ", ".join(c["id"] for c in musts), ""]
    claude += _claude_kb_section(project, tier, locale)
    claude += _claude_hooks_section(project, locale)
    manifest = f"# placement profile manifest — embedded (git tracked)\nprofile: embedded\nproject: {project.name}\nkit_profile: {prop['profile']}\ndomain: {prop.get('domain','work')}\n" + _enforcement_yaml(prop)
    registry = {"version": "0.1", "layer": "project", "core_revision": rev, "adapter_revision": arev,
                "constitution_version": prop.get("constitution_version"), "must_cards": [c["id"] for c in musts],
                "adopted": [a["id"] for a in prop.get("adoption", []) if a.get("adopted")],
                "conditional": [c["id"] for c in prop.get("conditional", []) if c.get("on")],
                "declined": [{"id": a["id"], "reason": a.get("declined_reason")} for a in prop.get("adoption", []) if a.get("answered") and not a.get("adopted")],
                "facts": prop.get("facts", {}),
                "answers": prop.get("answers") or {},
                **({"runtime": {k: prop["runtime"].get(k) for k in ("choice", "reason", "strata_python")}} if (prop.get("runtime") or {}).get("choice") else {}),
                "waivers": prop.get("waived", []), "routes": []}
    # Quilt texts: hub charter paragraph and piece instructions (Quilt reads these; roles come from core/roles)
    roles = load_yaml(kit / "core" / "roles" / "agent-roles.yaml").get("roles", [])
    charter = [header, f"# Quilt charter — {project.name}", "",
               f"Domain: {prop.get('domain','work')}. Profile: {prop['profile']}. Constitution {prop.get('constitution_version')} with {len(musts)} must cards: " + ", ".join(c["id"] for c in musts) + ".", "",
               "- Every session starts with `using-strata`; it prints the strata header and routes the task.",
               "- State changes ask first (gate policy per role under adapters/quilt/policies). Commits, pushes and worktrees are the person's.",
               "- Relays carry a packet: level (0-4), decision anchor, evidence as path:lines, one bounded request. One round trip per packet.",
               "- Session end is three steps: record (handoff), verify (gates), publish (listed paths only).",
               "- Roles and who hands to whom come from core/roles/agent-roles.yaml: " + ", ".join(f"{r['id']}→{r['quilt_role']}" for r in roles) + ".", ""]
    piece = [header, f"# Piece instructions — {project.name}", "",
             f"Profile `{prop['profile']}`. Should cards in force: " + (", ".join(c["id"] for c in shoulds) or "none") + ".",
             ("Waived: " + "; ".join(f"{w['id']} ({w['waived_reason']})" for w in prop.get("waived", []))) if prop.get("waived") else "Waived: none.", "",
             "- Read AGENTS.md (the contract) and the latest handoff before acting; if the handoff cannot be reached, say so and read the repository's traces (notes, git log, branches). Keep session state in .strata/local/.",
             "- Spec-first from the KB piece: kb_spec for the owning document, kb_propose for changes; never edit knowledge documents directly from a piece.",
             "- Report completion with evidence (rec.verify.evidence-not-impression).", ""]
    files = {"AGENTS.md": "\n".join(agents), "CLAUDE.md": "\n".join(claude), ".strata/profile.yaml": manifest,
             ".strata/kit/registry.yaml": "# project skill registry layer — routes added here override the profile and core layers\n" + yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
             f".strata/kit/quilt-charter.{locale}.md": "\n".join(charter), f".strata/kit/quilt-piece.{locale}.md": "\n".join(piece)}
    rt = prop.get("runtime") or {}
    if rt.get("choice") and rt.get("strata_python"):
        # one STRATA_PYTHON for every execution path, as snippets the person applies — home files are never edited here
        v = vault_root()
        for n, body in runtime_env.snippets(os.path.expanduser(rt["strata_python"]), str(kit), str(v) if v else None, str(project), locale).items():
            files[f".strata/kit/runtime/{n}"] = body
    allowed = set(prop.get("write_paths", []))
    # MB-strata-kit-2026-010: a hand-written file is never replaced unless the proposal names it here
    # (move its text to .strata/kit/notes.<locale>.md first, so the generated file carries it as project notes)
    overwrite = set(prop.get("overwrite_handwritten", []))
    written = []
    if tier and tier.profile == "detached":
        # the placement manifest lives in the vault (Tier P); add the kit fields there instead of creating an embedded one
        vm = tier.root / "profile.yaml"
        if vm.is_file():
            text = vm.read_text(encoding="utf-8"); add = []
            if "kit_profile:" not in text: add.append(f"kit_profile: {prop['profile']}")
            if "domain:" not in text: add.append(f"domain: {prop.get('domain','work')}")
            if prop.get("enforcement") and (load_yaml(vm) or {}).get("enforcement") != prop["enforcement"]:
                text = re.sub(r"(?m)^enforcement:.*\n(?:[ \t]+.*\n?)*", "", text)   # replaced as a whole block
                add.append(_enforcement_yaml(prop).rstrip("\n"))
            if add and apply and not out:
                vm.write_text(text.rstrip("\n") + "\n" + "\n".join(add) + "\n", encoding="utf-8"); written.append(f"updated detached manifest {vm}: {', '.join(add)}")
            elif add:
                written.append(f"would update detached manifest {vm}: {', '.join(add)}")
    # rec.placement.minimal-strata-in-code-repo: in the work domain, adapters stay out of the shared repository.
    # Root files are kept local through .git/info/exclude (never a committed .gitignore); .strata/profile.yaml may be tracked.
    if apply and not out and prop.get("domain", "work") == "work" and (project / ".git").exists():
        tracked = subprocess.run(["git", "-C", str(project), "ls-files", "--", "AGENTS.md", "CLAUDE.md", ".strata"], capture_output=True, text=True).stdout.split()
        tracked = [t for t in tracked if t != ".strata/profile.yaml"]
        if tracked:
            written.append(f"warning: {', '.join(tracked)} are tracked by this repository; leaving them tracked (team adoption must be recorded as a decision)")
        else:
            excl = project / ".git" / "info" / "exclude"; excl.parent.mkdir(parents=True, exist_ok=True)
            have = excl.read_text(encoding="utf-8") if excl.is_file() else ""
            add = [l for l in ("# strata-kit adapters stay local (rec.placement.minimal-strata-in-code-repo)", "AGENTS.md", "CLAUDE.md", ".strata/*", "!.strata/profile.yaml") if l not in have.splitlines()]
            if add:
                excl.write_text(have.rstrip("\n") + ("\n" if have else "") + "\n".join(add) + "\n", encoding="utf-8")
                written.append("updated .git/info/exclude (local only): AGENTS.md, CLAUDE.md, .strata/* except profile.yaml")
    for rel, body in files.items():
        if rel not in allowed: continue
        target = (out or project) / rel
        if not out and rel not in overwrite and (_handwritten(project / rel) or
                                                 (tier and tier.profile == "detached" and rel in ("AGENTS.md", "CLAUDE.md") and _handwritten(tier.root / rel))):
            written.append(f"kept hand-written {rel} (no generated marker; name it in proposal overwrite_handwritten to replace it)")
            continue
        if apply or out:
            target.parent.mkdir(parents=True, exist_ok=True); target.write_text(body, encoding="utf-8"); written.append(f"wrote {target if out else rel} ({len(body.encode())} B)")
        else:
            written.append(f"would write {rel} ({len(body.encode())} B)")
        if tier and tier.profile == "detached" and rel in ("AGENTS.md", "CLAUDE.md"):
            notes = project / ".strata" / "kit" / f"notes.{locale}.md"
            if rel == "AGENTS.md" and notes.is_file() and apply and not out:
                (tier.root / "kit").mkdir(parents=True, exist_ok=True); (tier.root / "kit" / notes.name).write_text(notes.read_text(encoding="utf-8"), encoding="utf-8")
                written.append(f"wrote canonical {show_path(tier.root / 'kit' / notes.name)}")
            canon = tier.root / rel   # detached: the vault copy is canonical (a new machine restores the repo copy from it)
            if apply and not out:
                canon.write_text(body, encoding="utf-8"); written.append(f"wrote canonical {show_path(canon)}")
            else:
                written.append(f"would write canonical {show_path(canon)}")
    return written

def _enforcement_yaml(prop: dict) -> str:
    g = prop.get("enforcement") or {}
    return ("enforcement:   # per rule family: advisory | default | block; undeclared = block (DEC-2026-10-29-17)\n"
            + "".join(f"  {k}: {v}\n" for k, v in g.items())) if g else ""


def _layers_section(pr: dict, tier, locale: str, enforcement: dict | None = None) -> list[str]:
    L = ["", "## Layers" if locale == "en" else "## 레이어", ""]
    if pr.get("layers"):
        L.append(("- Profile layers: " if locale == "en" else "- 프로필 레이어: ") + f"`{pr['layers']}`"
                 + ((" · enforcement: " if locale == "en" else " · 집행: ") + ", ".join(pr.get("enforcement") or []) if pr.get("enforcement") else ""))
    lm = (tier.root / "layer-map.yaml") if tier else None
    if lm and lm.is_file():
        m = load_yaml(lm); rows = [(str(x.get("path")), str(x.get("layer"))) for x in (m.get("mappings") or []) if isinstance(x, dict)]
        L.append(("- Project layer map (" if locale == "en" else "- 프로젝트 레이어 맵 (") + f"`{show_path(lm)}`" + (", ordered, first match wins; grouped here by layer):" if locale == "en" else ", 순서 있음·먼저 맞는 것; 여기서는 레이어별로 묶음):"))
        groups: dict[str, list[str]] = {}
        for path, layer in rows: groups.setdefault(layer, []).append(f"`{path}`")
        skipped = [l for l in groups if l.startswith("_")]   # _test · _story · _infrastructure …: excluded from layer checks, named only
        for layer, paths in groups.items():
            if layer.startswith("_"): continue
            shown = paths[:LAYER_EXAMPLES]; more = len(paths) - len(shown)
            L.append(f"  - {layer}: " + ", ".join(shown) + (f" … +{more}" if more > 0 else ""))
        if skipped: L.append(("  - excluded from checks: " if locale == "en" else "  - 검사 제외: ") + ", ".join(skipped))
    elif not pr.get("layers"):
        L.append("- (no layer map declared)" if locale == "en" else "- (선언된 레이어 맵 없음)")
    run = (tier.root / "enforcement" / "run.sh") if tier else None
    if run and run.is_file():
        L.append(("- Enforcement script: " if locale == "en" else "- 집행 스크립트: ") + f"`sh {show_path(run)} layers` · `sh {show_path(run)} diff --staged`"
                 + (" (local only, outside the team CI)" if locale == "en" else " (로컬 전용, 팀 CI 밖)"))
    if enforcement:
        grades = ", ".join(f"{k} {v}" for k, v in enforcement.items())
        L.append((f"- Enforcement grades: {grades} (undeclared: block; checkers run through `kb enforce run --family <f> -- <checker>`). "
                  "The agent rule does not change with the grade: write no new violation, report one that was written.") if locale == "en" else
                 (f"- 집행 등급: {grades} (선언 안 한 묶음은 block, 검사기는 `kb enforce run --family <f> -- <검사기>` 로 감싼다). "
                  "에이전트 규칙은 등급과 무관하다: 새 위반을 쓰지 않고, 쓰게 되면 보고한다."))
    return L

def _constraints_section(tier, locale: str) -> list[str]:
    reg = (tier.root / "constraint-registry.yaml") if tier else None
    if not reg or not reg.is_file(): return []
    cons = [c for c in (load_yaml(reg).get("constraints") or []) if isinstance(c, dict) and c.get("status", "active") == "active"]
    L = ["", "## Project constraints" if locale == "en" else "## 프로젝트 제약", "",
         (f"Summary of `{show_path(reg)}` ({len(cons)} active). Read the file for scope and rationale." if locale == "en"
          else f"`{show_path(reg)}` 요약 ({len(cons)}건 active). 범위·근거는 파일에서 읽는다.")]
    used = 0
    for c in cons:
        layers = ", ".join(c.get("scope", {}).get("layers") or []) if isinstance(c.get("scope"), dict) else ""
        line = f"- **{c.get('id')}** ({c.get('severity', '-')}) {str(c.get('rule') or '').strip()}"
        if used + len(line.encode()) > REGISTRY_SUMMARY_BYTES:
            L.append(("- … remaining entries in the file" if locale == "en" else "- … 나머지는 파일에서")); break
        L.append(line); used += len(line.encode())
    return L

TIER_P_FILES = ("decisions/", "constraint-registry.yaml", "layer-map.yaml")


def tier_files(root: Path) -> list[str]:
    """The Tier P entries that exist under root — generated guidance names only these (order 2026.10.29-11)."""
    return [n for n in TIER_P_FILES if (root / n.rstrip("/")).exists()]


def _where_section(project: Path, tier, locale: str) -> list[str]:
    name = project.name; vault = vault_root(); vp = f"$STRATA_VAULT/projects/{name}"
    placement = tier.profile if tier else "embedded"
    L = ["", "## Where things live" if locale == "en" else "## 파일 자리", ""]
    if placement == "detached":
        L.append((f"- Placement `detached`: Tier P (decisions · constraint registry · layer map) = `{show_path(tier.root)}`; the repo keeps `.strata/local/` and `.strata/kit/` only."
                  if locale == "en" else f"- 배치 `detached`: Tier P(결정·제약·레이어 맵) = `{show_path(tier.root)}`, 저장소에는 `.strata/local/`·`.strata/kit/` 만."))
        L.append(("- Decisions: `python3 \"$STRATA_KIT/kb\" decision add --project-dir <repo>` writes the record there (index and vault notes generated)."
                  if locale == "en" else "- 결정: `python3 \"$STRATA_KIT/kb\" decision add --project-dir <repo>` 가 거기 레코드를 쓴다(인덱스·vault 노트는 생성)."))
        if (project / ".strata" / "layer-map.yaml").is_symlink():
            L.append("- `.strata/layer-map.yaml` is a symlink to the vault copy (checkers read it there)." if locale == "en" else "- `.strata/layer-map.yaml` 은 vault 사본의 심링크다(검사기가 그 경로로 읽는다).")
        L.append(("- Repo AGENTS.md·CLAUDE.md are git-excluded local copies; canonical copies live in Tier P."
                  if locale == "en" else "- 저장소의 AGENTS.md·CLAUDE.md 는 git 제외 로컬 사본, 정본은 Tier P."))
    else:
        names = tier_files(project / ".strata")
        notes = {"decisions/": (" (records, index generated)", "(레코드, 인덱스는 생성)")}
        if names:
            en = ", ".join(f"`.strata/{n}`{notes.get(n, ('', ''))[0]}" for n in names)
            ko = "·".join(f"`.strata/{n}`{notes.get(n, ('', ''))[1]}" for n in names)
            L.append(f"- Placement `embedded`: {en} tracked in this repository." if locale == "en" else f"- 배치 `embedded`: {ko} 이 이 저장소에 있다.")
        else:
            L.append("- Placement `embedded`: no Tier P files yet (`.strata/decisions/` appears with the first decision)." if locale == "en"
                     else "- 배치 `embedded`: Tier P 파일은 아직 없다(첫 결정을 기록하면 `.strata/decisions/` 가 생긴다).")
    L += [("- Session state: `.strata/local/` (not tracked). Handoffs, tasks and history: the vault." if locale == "en" else "- 세션 상태: `.strata/local/`(미추적). 핸드오프·태스크·이력은 vault."),
          (f"- Knowledge: `{vp}/knowledge-base/` · sessions `{vp}/sessions/` · tasks `{vp}/tasks/` · decision notes `{vp}/decisions/` (generated) · node pages `{vp}/nodes/` (generated)"
           if locale == "en" else f"- 지식: `{vp}/knowledge-base/` · 세션 `{vp}/sessions/` · 태스크 `{vp}/tasks/` · 결정 노트 `{vp}/decisions/`(생성) · 노드 페이지 `{vp}/nodes/`(생성)"),
          ("- Skill registry layers: strata-kit → profile → `.strata/kit/registry.yaml` (+ Tier P `skills/registry.yaml` for skill packs)." if locale == "en" else "- 스킬 레지스트리 층: strata-kit → 프로필 → `.strata/kit/registry.yaml`(스킬 팩은 Tier P `skills/registry.yaml`).")]
    return L

def _notes_section(project: Path, locale: str) -> list[str]:
    """Hand-written project specifics (zones, stack, commands, reading order) kept in .strata/kit/notes.<locale>.md
    or notes.md; the wizard never rewrites that file, only includes it."""
    tier = tier_of(project)
    roots = [project / ".strata" / "kit"] + ([tier.root / "kit"] if tier and tier.profile == "detached" else [])
    for root in roots:   # repo copy first; for detached projects the vault Tier P copy is the canonical one
        for name in (f"notes.{locale}.md", "notes.md"):
            n = root / name
            if n.is_file():
                body = n.read_text(encoding="utf-8").strip()
                return ["", "## Project notes" if locale == "en" else "## 프로젝트 메모", "",
                        (f"<!-- from {show_path(n) if root != project / '.strata' / 'kit' else '.strata/kit/' + name} — edit that file, not this section -->"), body] if body else []
    return []

def _skill_validation(kit: Path, skill: str) -> list[str]:
    text = (kit / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    import re
    m = re.search(r"```yaml\n(.*?)```", text, re.S)
    if not m: return []
    return [str(x) for x in ((yaml.safe_load(m.group(1)) or {}).get("skill", {}).get("validation") or [])]

def _checklist_section(kit: Path, locale: str) -> list[str]:
    # one pointer, not the items: the skills carry their own validation list and load when called, so copying it here
    # paid ~1 KB every session for text read again at the moment it matters (DEC-2026-11-02-01, MB-strata-kit-2026-045)
    skills = [s for s in ("strata.verify", "strata.handoff") if _skill_validation(kit, s)]
    if not skills:
        return []
    names = " · ".join(f"`{s}`" for s in skills)
    return ["", "## Completion checklist" if locale == "en" else "## 완료 체크리스트", "",
            (f"Before any 'done' report and at session end, call {names} and check every validation item of that skill." if locale == "en"
             else f"완료 보고 전과 세션 종료에 {names} 를 부르고 그 스킬의 검증 항목을 모두 확인한다.")]

def _claude_kb_section(project: Path, tier, locale: str) -> list[str]:
    vp = f"$STRATA_VAULT/projects/{project.name}"
    L = ["## Knowledge base" if locale == "en" else "## 지식 기반", "",
         f"- {('Project knowledge' if locale == 'en' else '프로젝트 지식')}: `{vp}/`"]   # plain paths, never @imports (MB-strata-kit-2026-004)
    v = vault_root()   # name the KB index only where it exists (or the vault is not known on this machine)
    if v is None or (v / "projects" / project.name / "knowledge-base" / "_index.md").is_file():
        L.append(f"- {('KB index' if locale == 'en' else 'KB 인덱스')}: `{vp}/knowledge-base/_index.md`")
    L += [
         f"- {('Latest handoff' if locale == 'en' else '최신 핸드오프')}: {vp}/sessions/latest.md" + (
             " — if it cannot be read (variable unset, tool denied, no file), say so, then look for traces in this repository"
             " (notes, `git log`, branches) before asking" if locale == "en" else
             " — 읽을 수 없으면(변수 미설정·도구 거부·파일 없음) 그렇다고 말하고, 묻기 전에 이 저장소의 흔적(노트·`git log`·브랜치)을 본다"),
         f"- {('Decision notes' if locale == 'en' else '결정 노트')}: {vp}/decisions/ · {('tasks' if locale == 'en' else '태스크')}: {vp}/tasks/"]
    if tier:
        names = tier_files(tier.root)
        L.append(f"- Tier P ({tier.profile}): `{show_path(tier.root)}`" + (" — " + " · ".join(names) if names else ""))
    return L + [""]

def _claude_hooks_section(project: Path, locale: str) -> list[str]:
    mapping = [("session.start", "SessionStart"), ("before.file.write", "PreToolUse:Write|Edit"), ("after.file.change", "PostToolUse:Write|Edit"),
               ("before.context.compact", "PreCompact"), ("task.complete", "(manual: tests + strata.verify)"), ("session.end", "Stop / SessionEnd → strata.handoff")]
    L = ["## Harness events (Claude Code)" if locale == "en" else "## 하네스 이벤트 (Claude Code)", "", "| Strata event | Claude Code hook | " + ("installed hooks" if locale == "en" else "설치된 훅") + " |", "|---|---|---|"]
    installed: dict[str, list[str]] = {}
    for sp in (project / ".claude" / "settings.json", project / ".claude" / "settings.local.json"):
        if not sp.is_file(): continue
        try:
            for ev, items in (json.loads(sp.read_text(encoding="utf-8")).get("hooks") or {}).items():
                for it in items:
                    for h in it.get("hooks") or []:
                        toks = [t.strip("\"'") for t in str(h.get("command") or "").split()]
                        script = next((t for t in toks if "." in t and t.rsplit(".", 1)[-1] in ("py", "sh", "js") and not t.startswith("-")), toks[0] if toks else "")
                        base = script.split("/")[-1]
                        kb_at = next((i for i, t in enumerate(toks) if t.rstrip("/").endswith("/kb") or t == "kb"), None)
                        if kb_at is not None and kb_at + 1 < len(toks):   # kit CLI hook: `python3 "$STRATA_KIT/kb" check-layer`
                            base = f"kb {toks[kb_at + 1]}"
                        if base and base not in ("atom-notify.py", "echo", "true", "sh", "bash"): installed.setdefault(ev, []).append(base + (f" [{str(it.get('matcher')).replace('|', '\\|')}]" if it.get("matcher") else ""))
        except ValueError: pass
    # the strata-kit Claude plugin is the kit's Claude adapter: its hooks are listed from the generator, not from this
    # machine's settings, so the generated guidance is the same on every machine
    if str(Path(__file__).resolve().parent) not in sys.path: sys.path.insert(0, str(Path(__file__).resolve().parent))
    from gen_claude_plugin import PLUGIN_HOOKS
    for ev, label in PLUGIN_HOOKS.items(): installed.setdefault(ev, []).append(label)
    for ev, hook in mapping:
        key = hook.split(":")[0].split(" ")[0]
        L.append(f"| `{ev}` | `{hook.replace('|', '\\|')}` | {', '.join(sorted(set(installed.get(key, [])))) or '-'} |")
    extra = {k: v for k, v in installed.items() if k not in {h.split(':')[0].split(' ')[0] for _, h in mapping}}
    for ev, cmds in sorted(extra.items()): L.append(f"| - | `{ev}` | {', '.join(sorted(set(cmds)))} |")
    return L + [""]

def _adapter_revision(prop: dict) -> str:
    h = hashlib.sha256(json.dumps({k: prop.get(k) for k in ("profile", "cards", "waived", "locale")}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return h[:12]

# ---------- verify ----------
IMPORT_RE = re.compile(r"(?:^|(?<=\s))@((?:~|\$\w+|\.{0,2}/|\w)[^\s`)]*)")


def _imports(path: Path, expand_env: bool = False) -> list[Path]:
    """Files a CLAUDE.md pulls in with @path (code spans skipped, ~ expanded, directories ignored). Paths with $VARS are
    followed only with expand_env — Claude Code documents relative, absolute and ~ imports, not environment variables."""
    text = re.sub(r"```.*?```|`[^`\n]*`", "", path.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    out = []
    for m in IMPORT_RE.finditer(text):
        raw = m.group(1).rstrip(".,;:")
        if "$" in raw and not expand_env: continue
        p = Path(os.path.expandvars(os.path.expanduser(raw)))
        p = p if p.is_absolute() else path.parent / p
        if p.is_file(): out.append(p.resolve())
    return out


def env_imports(project: Path, chain) -> list[str]:
    """@imports with $VARS in the chain or the project's CLAUDE.md — not counted, reported so they can be made plain paths."""
    out = []
    for f in [*chain, project / "CLAUDE.md"]:
        if Path(f).is_file():
            text = re.sub(r"```.*?```|`[^`\n]*`", "", Path(f).read_text(encoding="utf-8", errors="replace"), flags=re.S)
            out += [m.group(1) for m in IMPORT_RE.finditer(text) if "$" in m.group(1)]
    return out


def inherited_chain(project: Path, home: Path | None = None) -> dict[Path, int]:
    """What every session in the project loads besides the project's own AGENTS.md and CLAUDE.md
    (MB-strata-kit-2026-004): the user's global CLAUDE.md, each ancestor directory's CLAUDE.md, and the files these and
    the project's CLAUDE.md import with @path (depth 5, each file once)."""
    home = home or Path.home()
    project = project.resolve()
    roots = [home / ".claude" / "CLAUDE.md"] + [d / n for d in reversed(project.parents) for n in ("CLAUDE.md", "CLAUDE.local.md")]
    chain: dict[Path, int] = {}
    own = {(project / n).resolve() for n in ("AGENTS.md", "CLAUDE.md")}
    def add(p: Path, depth: int):
        p = p.resolve()
        if p in chain or p in own or not p.is_file(): return
        chain[p] = p.stat().st_size
        if depth < 5:
            for q in _imports(p): add(q, depth + 1)
    for r in roots: add(r, 0)
    if (project / "CLAUDE.md").is_file():
        for q in _imports(project / "CLAUDE.md"): add(q, 1)
    return chain


ENTRY_PATH = lambda kit: [kit / "skills" / "using-strata" / "SKILL.md", kit / "skills" / "registry.yaml",
                          kit / "core" / "constitution" / "constitution.yaml"]
MUST_LINE = re.compile(r"^- \*\*(rec\.[^*]+)\*\*")


def guidance_musts(project: Path) -> dict[str, tuple[str | None, list[str]]]:
    """Constitution version and must card ids as the generated AGENTS.md and CLAUDE.md state them (hand-written files are skipped)."""
    out = {}
    a, c = project / "AGENTS.md", project / "CLAUDE.md"
    if a.is_file() and not _handwritten(a):
        text = a.read_text(encoding="utf-8")
        ver = re.search(r"Constitution: (\S+)", text)
        sec = text.split("## Must cards", 1)[1].split("\n## ", 1)[0] if "## Must cards" in text else ""
        out["AGENTS.md"] = (ver.group(1) if ver else None, [m.group(1) for l in sec.splitlines() if (m := MUST_LINE.match(l))])
    if c.is_file() and not _handwritten(c):
        line = next((l for l in c.read_text(encoding="utf-8").splitlines() if l.startswith("- Must cards:")), "")
        out["CLAUDE.md"] = (None, [x.strip() for x in line.split(":", 1)[1].split(",") if x.strip()] if line else [])
    return out


CLOSING_COMMAND = re.compile(r"^(handoff|wrap-?up|session-?(end|close)|(end|close)-?session)", re.I)


def verify(project: Path, kit: Path) -> tuple[int, dict]:
    """Graded (order 2026.10.29-02): budgets and trigger samples are default (a reasoned, dated override in the Tier P
    gate-overrides.yaml lets them pass), a missing revision header or project registry blocks."""
    from kb.gates.grades import Finding, evaluate, load_overrides, render
    report, found = {}, []
    tier = tier_of(project)
    # what a generated adapter actually loads every session: AGENTS.md + CLAUDE.md. The constraint registry is linked and
    # summarised (REGISTRY_SUMMARY_BYTES) in AGENTS.md, read on demand in both placements (rec.context.entry-view-budget)
    always = always_loaded(project)
    report["placement"] = tier.profile if tier else "none"
    total = sum(always.values()); report["always_loaded"] = always; report["always_loaded_total"] = total; report["budget_bytes"] = BUDGET_BYTES
    report["budget"] = "FAIL" if total > BUDGET_BYTES else "ok"
    if total > BUDGET_BYTES: found.append(Finding("verify", "budget", "default", f"AGENTS.md+CLAUDE.md {total:,} B > {BUDGET_BYTES:,} B"))
    # MB-strata-kit-2026-004: the same budget over everything a session here loads — global, ancestor and @imported guidance too
    chain = inherited_chain(project)
    report["inherited"] = {show_path(k): v for k, v in chain.items()}
    report["loaded_total"] = total + sum(chain.values())
    envs = env_imports(project, chain)
    if envs: report["env_imports_not_counted"] = envs   # make these plain paths: either they load nothing or a whole index
    report["loaded_budget_bytes"] = LOADED_BUDGET_BYTES
    report["budget_with_inherited"] = "FAIL" if report["loaded_total"] > LOADED_BUDGET_BYTES else "ok"
    if report["loaded_total"] > LOADED_BUDGET_BYTES:
        found.append(Finding("verify", "budget_with_inherited", "default", f"상속 포함 {report['loaded_total']:,} B > {LOADED_BUDGET_BYTES:,} B"))
    for n in ("AGENTS.md", "CLAUDE.md"):
        p = project / n
        if p.is_file():
            first = p.read_text(encoding="utf-8").splitlines()[:1]
            ok = bool(first) and "core_revision:" in first[0]
            report[f"revision_header:{n}"] = "ok" if ok else "MISSING"
            if not ok: found.append(Finding("verify", f"revision_header:{n}", "block", "생성본 머리말(core_revision) 없음"))
    # DEC-2026-10-29-13·19: the generated guidance carries the approved policy set — every constitution article and
    # every must card the project adopted (the registry's must_cards, written by generate from the approved proposal)
    const = load_yaml(kit / "core" / "constitution" / "constitution.yaml").get("constitution", {})
    approved = list(const.get("articles", []))
    for reg in project_registries(project, tier):
        approved += [c for c in (load_yaml(reg) or {}).get("must_cards") or [] if c not in approved]
    report["approved_musts"] = len(approved)
    for n, (ver, ids) in guidance_musts(project).items():
        miss = [c for c in approved if c not in ids]
        bad = ([f"constitution {ver} ≠ core {const.get('version')}"] if ver is not None and ver != const.get("version") else []) \
              + ([f"must 누락 {len(miss)}: " + ", ".join(miss)] if miss else [])
        report[f"constitution:{n}"] = "; ".join(bad) or "ok"
        if bad: found.append(Finding("verify", f"constitution:{n}", "default", f"{n} 이 승인된 정책 집합과 다름 — " + "; ".join(bad) + " (recommend → generate 로 재생성)"))
    # what using-strata makes a session read besides the guidance files — reported, not budgeted yet (DEC-2026-10-29-13)
    entry = {show_path(f): f.stat().st_size for f in ENTRY_PATH(kit) if f.is_file()}
    report["entry_path"] = entry; report["entry_path_total"] = sum(entry.values())
    # DEC-2026-10-29-19: with the SessionStart header the skill body is all using-strata reads; the registry and the
    # constitution are opened only without it. Both routes are reported; neither has a ceiling yet.
    report["entry_path_with_header"] = entry.get(show_path(ENTRY_PATH(kit)[0]), 0)
    # the harness loads the memory index at every start: shown and warned over the kit budget, never failed (DEC-2026-10-31-19)
    sys.path.insert(0, str(kit)); from kb.gates.memory_hygiene import INDEX_BUDGET, memory_dir_for
    mi = memory_dir_for(project) / "MEMORY.md"
    report["memory_index_bytes"] = mi.stat().st_size if mi.is_file() else 0
    if report["memory_index_bytes"] > INDEX_BUDGET:
        report["memory_index"] = f"warning: {report['memory_index_bytes']:,} B > {INDEX_BUDGET:,} B — kb hygiene --memory 로 정리 후보를 본다"
    regs = project_registries(project, tier)   # same layer as the header (MB-strata-kit-2026-001)
    report["project_registry"] = ("ok: " + ", ".join(show_path(p) for p in regs)) if regs else "MISSING"
    if not regs: found.append(Finding("verify", "project_registry", "block", "프로젝트 스킬 레지스트리 없음"))
    # a project command named like a closing step wins over the plugin skill when typed (/handoff): it must route to
    # strata.handoff or its steps (memory check, decision records) are skipped whenever it is used (MB-strata-kit-2026-042)
    closing = [c for c in sorted((project / ".claude" / "commands").glob("*.md")) if CLOSING_COMMAND.search(c.stem)] \
        if (project / ".claude" / "commands").is_dir() else []
    off = [c.stem for c in closing if not re.search(r"strata[.-]handoff", c.read_text(encoding="utf-8", errors="replace"))]
    if closing:
        report["closing_commands"] = ("ok: " if not off else "off the kit handoff: ") + ", ".join("/" + s for s in (off or [c.stem for c in closing]))
    for name in off:
        found.append(Finding("verify", f"closing_command:{name}", "advisory",
                             f".claude/commands/{name}.md 가 strata.handoff 를 거치지 않음 — 본문을 strata-kit:strata-handoff 로 넘기고 프로젝트 고유 단계만 남긴다"))
    core = load_yaml(kit / "skills" / "registry.yaml")
    samples = [("set up guidance for this project", "strata.init-wizard"), ("write the acceptance criteria", "strata.spec"),
               ("handoff", "strata.handoff"), ("is it done? verify", "strata.verify"), ("we decided to split the service", "strata.decision"),
               ("let's do a retrospective of last week", "strata.retro"),
               ("turn this into a planning document", "strata.planning"),
               ("an indicator got worse this week", "strata.signal")]
    hits = 0
    for text, expect in samples:
        got = _route(core, text)
        hits += got == expect
        report[f"sample:{text}"] = f"{got} (expected {expect})"
    report["trigger_samples"] = f"{hits}/{len(samples)}"
    if hits < len(samples): found.append(Finding("verify", "trigger_samples", "default", f"트리거 표본 {hits}/{len(samples)}"))
    ov_path = (tier.root if tier else project / ".strata") / "gate-overrides.yaml"
    report["_findings"] = found   # the raw findings, for tools/doctor.py (dropped before printing)
    r = evaluate(found, load_overrides(ov_path))
    report["grades"] = render(r) or ["ok"]
    report["overrides_file"] = show_path(ov_path)
    return r["rc"], report

def _route(reg: dict, text: str) -> str | None:
    low = text.lower(); best, score = None, 0
    for r in reg.get("routes", []):
        for loc, phrases in (r.get("triggers") or {}).items():
            for ph in phrases:
                if ph.lower() in low and len(ph) > score: best, score = r["skill"], len(ph)
    return best

# ---------- header (using-strata step 3, deterministic) ----------
def _next_of(a: dict) -> str | None:
    """next action across the active-file shapes in use: flat next_action, session.next, state.next_action."""
    d = lambda v: v if isinstance(v, dict) else {}   # session: may be the id string (order 2026.10.29-14)
    for v in (a.get("next_action"), d(a.get("session")).get("next"), d(a.get("state")).get("next_action"),
              a.get("next"), a.get("task"), a.get("title")):
        if v: return " ".join(str(v).split())
    return None

def active_next(project: Path, session_id: str | None = None, source: str | None = None) -> str:
    """This session's per-session file (kb/legacy/active_session.py): by name or harness_session_id; on compaction
    only this session's, otherwise the newest file, named; the legacy active-task.yaml only when no per-session file exists."""
    from kb.legacy.active_session import pick
    p = pick(project / ".strata" / "local", session_id, source)
    if p.path is None:
        if p.label == "no active file":
            return "(no active task file — read-only, or a state-changing session that has not written one)"
        return f"({p.label})"
    try:
        a = load_yaml(p.path)
    except Exception:
        return f"(unreadable: {p.label})"
    a = a if isinstance(a, dict) else {}
    mode = a.get("mode") or (a.get("session") if isinstance(a.get("session"), dict) else {}).get("mode")
    return f"{_next_of(a) or '(active task present)'} [{p.label}]" + (f" · mode {mode}" if mode else "")

def handoff_next(project_id: str) -> str | None:
    """The latest handoff's next_session (front matter, as the ledger close writes it) with its path; None when the
    vault or the handoff is not here (DEC-2026-10-31-08)."""
    v = vault_root()
    f = v / "projects" / project_id / "sessions" / "latest.md" if v else None
    if not f or not f.is_file():
        return None
    t = f.read_text(encoding="utf-8")
    fm = t.split("---", 2)[1] if t.startswith("---") and t.count("---") >= 2 else ""
    try:
        nxt = (yaml.safe_load(fm) or {}).get("next_session")
    except Exception:
        return None
    if not nxt:
        return None
    return " ".join(str(nxt).split()) + f" [sessions/{f.resolve().name}]"

def machine_lines(project_id: str) -> tuple[list[str], str | None]:
    """'machine: <alias> (…)' and, when the latest handoff leaves work tied to other machines, one line naming it
    (MB-strata-kit-2026-049). Never blocks; an error names itself."""
    try:
        from kb import machine as mc
        alias, note = mc.current_alias()
        v = vault_root()
        out = [mc.header_line(mc.load_registry(v), alias, mc.current_fingerprint(), note)]
        f = v / "projects" / project_id / "sessions" / "latest.md" if v else None
        if f and f.is_file():
            here, others = mc.pending_by_machine(f.read_text(encoding="utf-8"), alias)
            if others:
                out.append("latest handoff pending for other machines: " + " · ".join(
                    f"{a} {len(d)} ({'; '.join(d[:2])}{' …' if len(d) > 2 else ''})" for a, d in others.items())
                    + f" — not this machine's work ({here} here or any)")
        return out, alias
    except Exception as e:   # the header never dies on one source
        return [f"machine: (error {type(e).__name__}: {e})"], None

def resume_trace_line(project_id: str) -> str:
    """No active file and no handoff: where the handoff was looked for, and the in-repository traces to read before
    asking (MB-strata-kit-2026-043 — the guidance pointed only at the vault and blocked discovery)."""
    v = vault_root()
    where = f"no handoff at {v / 'projects' / project_id / 'sessions' / 'latest.md'}" if v else "STRATA_VAULT unset, no handoff read"
    return (f"resume: {where} and no active file — before asking, look in this repository: NOTES/HANDOFF/TODO-like files, "
            "git log -10, git branch")

def hook_input(stream=None, wait: float = 1.0) -> dict:
    """The SessionStart hook's JSON on stdin (session_id, source, ...). A hand run (stdin a terminal, empty, left open
    with nothing written — an agent's shell — or not SessionStart JSON) gives {} and the header stays as it was."""
    import select
    import io
    stream = stream or sys.stdin
    try:
        if stream.isatty():
            return {}
        try:
            stream.fileno()
            waitable = True
        except (OSError, io.UnsupportedOperation):   # an in-memory stream: nothing to wait on
            waitable = False
        if waitable and not select.select([stream], [], [], wait)[0]:
            return {}
        d = json.loads(stream.read() or "{}")
    except Exception:
        return {}
    return d if isinstance(d, dict) and d.get("hook_event_name") == "SessionStart" else {}

def project_registries(project: Path, tier) -> list[Path]:
    """The project's skill registry layer: .strata/kit/registry.yaml (generated) and Tier P skills/registry.yaml
    (where a detached project keeps its own skills, e.g. a project-layer qa.* pack), whichever exist."""
    cands = [project / ".strata" / "kit" / "registry.yaml"] + ([tier.root / "skills" / "registry.yaml"] if tier else [])
    return [p for p in cands if p.is_file()]


def _routes(p: Path) -> int:
    return len((load_yaml(p) or {}).get("routes") or [])


def registry_line(project: Path, kit: Path, profile_id: str, tier) -> str:
    """'skill registry: core ok(N routes) · profile <id> ok(N)|absent · project ok(N routes, paths)|absent' (MB-strata-kit-2026-001)."""
    core = kit / "skills" / "registry.yaml"
    prof = kit / "profiles" / profile_id / "skills" / "registry.yaml"
    parts = [f"core ok({_routes(core)} routes)" if core.is_file() else "core absent",
             f"profile {profile_id} ok({_routes(prof)} routes)" if prof.is_file() else f"profile {profile_id} absent"]
    regs = project_registries(project, tier)
    try:   # the user layer sits between profile and project and only adds (DEC-2026-10-31-36)
        from kb.skills_layer import layer_status, status_text
        parts.append(status_text(layer_status(core, prof if prof.is_file() else None, regs)))
    except Exception as e:   # the header never dies on one layer
        parts.append(f"user error ({type(e).__name__}: {e})")
    parts.append(f"project ok({sum(_routes(p) for p in regs)} routes, " + ", ".join(show_path(p) for p in regs) + ")" if regs else "project absent")
    return "skill registry: " + " · ".join(parts)


STALE_HOURS = 6


def vault_sync(vault: Path | None, stale_hours: float = STALE_HOURS) -> str | None:
    """One header line when the shared vault checkout is out of step (MB-strata-kit-2026-008), else None: commits not
    pushed or not pulled, uncommitted files the remote also changed (they block the session-start pull), and uncommitted
    files left for hours (work no session owns any more). Reads the last fetch; never blocks."""
    if not vault or not (vault / ".git").exists():
        return None
    def g(*a):
        return subprocess.run(["git", "-C", str(vault), *a], capture_output=True, text=True)
    if g("rev-parse", "--abbrev-ref", "@{u}").returncode:
        return None
    counts = g("rev-list", "--left-right", "--count", "HEAD...@{u}").stdout.split()
    ahead, behind = (int(counts[0]), int(counts[1])) if len(counts) == 2 else (0, 0)
    dirty = [l[3:].split(" -> ")[-1].strip('"') for l in g("status", "--porcelain").stdout.splitlines() if l.strip()]
    remote = set(g("diff", "--name-only", "HEAD...@{u}").stdout.split()) if behind else set()
    overlap = [p for p in dirty if p in remote]
    cutoff = time.time() - stale_hours * 3600
    stale = [p for p in dirty if (vault / p).is_file() and (vault / p).stat().st_mtime < cutoff]
    if not (ahead or behind or overlap or stale):
        return None
    head = lambda xs: ", ".join(xs[:3]) + (" …" if len(xs) > 3 else "")
    parts = [f"ahead {ahead} · behind {behind}"]
    if overlap: parts.append(f"uncommitted the remote also changed {len(overlap)} ({head(overlap)})")
    if stale: parts.append(f"uncommitted for over {stale_hours:g}h {len(stale)} ({head(stale)})")
    return "vault out of step: " + " · ".join(parts) + " → settle before writing to the vault (owner sessions commit; generated files regenerate)"


def musts_line(reg: dict, const: dict) -> str:
    """The project's must cards as generated (constitution articles + adopted opt-in cards); the constitution alone
    when the registry predates DEC-2026-10-29-14. Articles the generated set lacks are named — regenerate."""
    arts = const.get("articles", [])
    ids = reg.get("must_cards") or arts
    miss = [a for a in arts if a not in ids]
    adopted = [i for i in ids if i not in arts]
    cond = set(reg.get("conditional") or [])
    adopted_only = [i for i in adopted if i not in cond]
    line = (f"must cards ({len(ids)}): " + ", ".join(ids) + (f" · adopted: {', '.join(adopted_only)}" if adopted_only else "")
            + (f" · conditional: {', '.join(i for i in adopted if i in cond)}" if cond & set(adopted) else ""))
    return line + (f" · MISSING from generated guidance: {', '.join(miss)} → re-run the wizard" if miss else "")


def header(project: Path, kit: Path, locale: str, hook: dict | None = None) -> str:
    """The session header. hook is the SessionStart input: its session_id picks this session's active file, and on
    source compact the header shrinks to a restore note — this session's next action and the latest handoff's, each
    with its path (DEC-2026-10-31-08) — so it never refills what compaction just cut and stays shorter than the header."""
    hook = hook or {}
    sid, source = hook.get("session_id"), hook.get("source")
    tier = tier_of(project)
    manifest = (tier.root / "profile.yaml") if tier else (project / ".strata" / "profile.yaml")
    if not manifest.is_file():
        return "strata: no .strata/profile.yaml here → run strata.init-wizard first"
    m = load_yaml(manifest)
    reg = project / ".strata" / "kit" / "registry.yaml"
    r = load_yaml(reg) if reg.is_file() else {}
    const = load_yaml(kit / "core" / "constitution" / "constitution.yaml").get("constitution", {})
    try:
        nxt = active_next(project, sid, source)
    except Exception as e:   # the header never dies on one unreadable source; it names the error instead
        nxt = f"(active file error: {type(e).__name__}: {e})"
    waivers = ", ".join(f"{w['id']} ({w['waived_reason']})" for w in r.get("waivers", [])) or "none"
    first = f"strata · project {m.get('project')} · profile {m.get('kit_profile', '?')} · domain {m.get('domain', 'work')}"
    if source == "compact":
        # must cards are left out: the project CLAUDE.md, reloaded after compaction, lists them (measured 2026-10-31)
        lines = [first + " · restored after compaction", f"next action: {nxt}"]
        hn = handoff_next(str(m.get("project") or project.name))
        if hn: lines.append(f"latest handoff next: {hn}")
        return "\n".join(lines)
    lines = [
        first,
        musts_line(r, const),
        f"waived should cards: {waivers}",
        "restart signal: past about {}K tokens (limit {}K), or two failures on one hypothesis → wrap up, hand off, new session (rec.session.split-at-task-boundary)".format(*(n // 1000 for n in restart_lines())),
        f"core revision: {r.get('core_revision', '?')} · adapter revision: {r.get('adapter_revision', '?')} (kit now: {kit_revision(kit)})",
        f"next action: {nxt}",
    ]
    pid = str(m.get("project") or project.name)
    mach, alias = machine_lines(pid)
    lines.extend(mach)
    hn = handoff_next(pid)
    if hn:
        lines.append(f"latest handoff next: {hn}")
    elif nxt.startswith("(no active"):   # nothing in files: say where we looked and where else to look (MB-strata-kit-2026-043)
        lines.append(resume_trace_line(pid))
    lines.append(registry_line(project, kit, m.get("kit_profile", "?"), tier))
    sync = vault_sync(vault_root())
    if sync: lines.append(sync)
    return "\n".join(lines)

# ---------- cli ----------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["diagnose", "recommend", "generate", "verify", "header"])
    ap.add_argument("project"); ap.add_argument("--kit", default=str(KIT))
    ap.add_argument("--profile"); ap.add_argument("--waive", action="append", default=[], help="card=reason")
    ap.add_argument("--enforce", action="append", default=[], help="family=grade (advisory|default|block)")
    ap.add_argument("--adopt", action="append", default=[], help="opt-in must card to adopt")
    ap.add_argument("--decline", action="append", default=[], help="opt-in must card to decline: id=reason")
    ap.add_argument("--uses-vault", choices=["yes", "no"], help="the project keeps knowledge in the vault (conditional cards)")
    ap.add_argument("--harness", help="harnesses here, comma separated (claude,codex,quilt); quilt turns on uses_quilt")
    ap.add_argument("--locale", default="en", choices=LOCALES); ap.add_argument("--domain", default="work", choices=["work", "personal"])
    ap.add_argument("--answer", action="append", default=[], help="interview answer key=value (" + ", ".join(INTERVIEW_KEYS) + "); runtime=" + "|".join(runtime_env.OPTIONS))
    ap.add_argument("--because", action="append", default=[], help="the reason for an answer: key=reason")
    ap.add_argument("--apply", action="store_true", help="diagnose·recommend·generate: write into the project (.strata/kit/, adapters)")
    ap.add_argument("--out", help="diagnose·recommend·generate: write into this directory instead of the project (review copy)")
    a = ap.parse_args()
    project, kit = Path(a.project).resolve(), Path(a.kit).resolve()
    outdir = Path(a.out).resolve() if a.out else project / ".strata" / "kit"
    writes = bool(a.apply or a.out)
    if a.cmd == "diagnose":
        d = diagnose(project, kit)
        print(yaml.safe_dump({k: d[k] for k in ("matched_profiles", "always_loaded_total", "budget_ok", "open_questions")}, allow_unicode=True, sort_keys=False))
        if writes:
            outdir.mkdir(parents=True, exist_ok=True)
            (outdir / "diagnosis.yaml").write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
            print(f"wrote {outdir / 'diagnosis.yaml'}")
        else:
            print("not written (read-only): --apply writes .strata/kit/diagnosis.yaml, --out DIR writes a copy there")
        return 0
    if a.cmd == "recommend":
        if not a.profile: raise SystemExit("--profile required")
        waivers = dict(w.split("=", 1) for w in a.waive)
        answers = {**{c: True for c in a.adopt}, **{d.split("=", 1)[0]: (False, d.split("=", 1)[1] if "=" in d else None) for d in a.decline}}
        given = {"uses_vault": None if a.uses_vault is None else a.uses_vault == "yes",
                 "uses_quilt": None if a.harness is None else "quilt" in [h.strip() for h in a.harness.split(",")]}
        bad = [x for x in a.answer + a.because if "=" not in x]
        if bad: raise SystemExit(f"--answer/--because need key=value: {', '.join(bad)}")
        reasons = dict(x.split("=", 1) for x in a.because)
        interview = {k: {"value": v, "reason": reasons.get(k)} for k, v in (x.split("=", 1) for x in a.answer)}
        for k in set(reasons) - set(interview):
            raise SystemExit(f"--because {k}: no --answer {k}=… given with it")
        p = recommend(project, kit, a.profile, waivers, a.locale, a.domain, answers, dict(e.split("=", 1) for e in a.enforce), given, interview)
        target = outdir / "proposal.yaml"
        note = ""
        if writes and target.is_file() and (load_yaml(target) or {}).get("approved"):
            target, note = outdir / "proposal.next.yaml", f" — {outdir / 'proposal.yaml'} is approved and kept; review proposal.next.yaml, then replace it and set approved: true"
        if writes:
            outdir.mkdir(parents=True, exist_ok=True)
            target.write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
        print(f"proposal: {len(p['cards'])} cards ({sum(c['strength']=='must' for c in p['cards'])} must), {len(p['waived'])} waived, {len(p['problems'])} problems → "
              + (f"{target}{note}" if writes else "not written (read-only): --apply writes .strata/kit/proposal.yaml, --out DIR writes a copy there"))
        print("  facts: " + ", ".join(f"{k} {v}" for k, v in p["facts"].items()))
        for c in p["conditional"]: print(f"  = {c['id']}: {'loaded' if c['on'] else 'not loaded'} (condition {c['condition']})")
        for w in p["warnings"]: print("  !", w)
        for ad in p["adoption"]: print(f"  ? {ad['id']}: {'adopted' if ad['adopted'] else 'not adopted'}" + (f" (default from {ad['default_from']})" if ad["default_from"] and not ad["answered"] else "") + (f" (answer from {ad['answer_from']})" if ad.get("answer_from") else "") + f" — {ad['question']}")
        print("  ? enforcement: " + (", ".join(f"{k} {v}" for k, v in p["enforcement"].items()) or "none declared") + f" — undeclared families are block (coverage, stages: advisory); --enforce family=advisory|default|block ({', '.join(ENFORCE_FAMILIES)})")
        for k, v in p["answers"].items(): print(f"  = answer {k}: {v['value']}" + (f" ({v['reason']})" if v.get("reason") else " (no reason given: --because)"))
        rt = p["runtime"]
        if rt.get("choice"):
            print(f"  = runtime: {rt['choice']} → STRATA_PYTHON {rt['strata_python']}; setup: " + " ; ".join(rt["setup"]))
        else:
            print(f"  ? runtime: which python should the kit run on in every path? --answer runtime=<choice> --because runtime=<reason> (default {rt['default']}: {rt['default_reason']})")
            for k, o in rt["options"].items(): print(f"      {k}: {o['label']} — + {o['pros']} / - {o['cons']}")
            ko = getattr(a, "locale", "en") == "ko"
            print("    " + ("권장 — 언어 런타임과 kit 실행 환경을 나눠서:" if ko else "recommended — split language runtimes from the kit env:"))
            names = {"languages": "언어 런타임" if ko else "language runtimes", "uv": "uv 자체" if ko else "uv itself", "kit": "kit 실행 환경" if ko else "kit env"}
            for x in rt.get("layers", []): print(f"      {names[x['layer']]}: {x['tool']} — {x['why']}")
            if rt.get("asdf_python_fits_when"): print("      " + ("예외: " if ko else "exception: ") + rt["asdf_python_fits_when"])
        for k in INTERVIEW_KEYS[:4]:
            if k not in p["answers"]: print(f"  ? {k}: not answered (--answer {k}=…)")
        for pr in p["problems"]: print("  !", pr)
        return 0
    if a.cmd == "generate":
        for line in generate(project, kit, a.apply, Path(a.out).resolve() if a.out else None): print(line)
        return 0
    if a.cmd == "header":
        print(header(project, kit, a.locale, hook_input())); return 0
    rc, rep = verify(project, kit); rep.pop("_findings", None); print(yaml.safe_dump(rep, allow_unicode=True, sort_keys=False)); return rc

if __name__ == "__main__":
    sys.exit(main())
