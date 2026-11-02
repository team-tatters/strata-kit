"""Idea notes of the ideation pack (planning/ideation-pack acceptance 4~8, DEC-2026-10-31-38 · DEC-2026-11-01-01·02):
list shows remaining weight, the load of thought and idle days, counting only confirmed weights; tidy offers ideas idle
for more than 30 days and with --apply changes the status only; an event reopens an archived note; check reports
format problems but not empty facets; draw takes records outside the idea's projects first, the constraint list when
records run short, with a source on every item; the next-flow candidates are ordered by standing and never block."""
import hashlib
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "tools"))

from kb import ideas as I  # noqa: E402
from kb import skills_layer as sl  # noqa: E402

TODAY = date(2026, 11, 1)


def note(d: Path, name: str, *, status="active", created="2026-10-01", log="", weight=True, extra="", facets=I.FACETS,
         projects="[strata-kit]"):
    fm = [f"title: {name}", "type: idea", f"created: {created}", "nature: problem", f"status: {status}", f"projects: {projects}",
          "conditions:", "  - {text: a, met: true}", "  - {text: b, met: false}", "orders_expected: 3", "orders_done: 1"]
    if weight:
        fm.append("weight_confirmed: 2026-10-02")
    body = "\n".join(f"## {f}\n\n{'비어 있음' if f == '의미' else '사용자의 말'}\n" for f in facets)
    text = "---\n" + "\n".join(fm) + extra + "\n---\n\n# " + name + "\n\n" + body + "\n## 소거한 사례\n\n## 발전 기록\n\n" + log
    p = d / f"{name}.md"
    p.write_text(text, encoding="utf-8")
    return p


def digest(d: Path) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.glob("*.md"))}


class IdeasTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        self.d = self.vault / "ideas"
        self.d.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_counts_only_confirmed_weight(self):
        note(self.d, "a", log="- 2026-10-25 facet — 문제\n")          # unmet 1 + orders left 2 = 3
        note(self.d, "b", weight=False)
        note(self.d, "c", status="archived")
        out = I.listing(I.all_ideas(self.vault), TODAY)
        self.assertIn("열린 아이디어 2 · 고민의 총량 3 (무게 미확인 1 은 합에 넣지 않음) · 아카이브 1", out[0])
        a = next(l for l in out if l.strip().startswith("a.md"))
        self.assertIn("무게 3", a); self.assertIn("마지막 발전 7일 전", a); self.assertIn("빈칸 의미", a)
        self.assertIn("무게 미확인", next(l for l in out if l.strip().startswith("b.md")))
        self.assertFalse(any(l.strip().startswith("c.md") for l in out))

    def test_tidy_previews_then_changes_status_only(self):
        note(self.d, "old", created="2026-09-01", log="- 2026-09-20 link — x\n")
        note(self.d, "fresh", created="2026-10-20")
        before, bodies = digest(self.d), {p.name: I.split(p.read_text())[2] for p in self.d.glob("*.md")}
        out = I.tidy(I.all_ideas(self.vault), TODAY)
        self.assertIn("열린 아이디어 1", out[0]); self.assertIn("old.md", out[1])
        self.assertEqual(digest(self.d), before)                       # preview writes nothing
        I.tidy(I.all_ideas(self.vault), TODAY, apply=True)
        self.assertEqual(sorted(p.name for p in self.d.glob("*.md")), ["fresh.md", "old.md"])   # nothing moved or deleted
        old = I.load(self.d / "old.md")
        self.assertEqual(old.status, "archived")
        self.assertEqual(old.fm["archived"], {"date": "2026-11-01", "reason": "발전 없음 42일"})
        self.assertEqual(old.body, bodies["old.md"])                   # body byte for byte
        self.assertEqual(digest(self.d)["fresh.md"], before["fresh.md"])

    def test_event_appends_and_reopens(self):
        p = note(self.d, "arch", status="archived", extra="\narchived: {date: '2026-10-20', reason: x}", log="- 2026-09-01 facet — 발단\n")
        out = I.add_event(p, "use", "planning/ideation-pack 에서 씀", TODAY)
        self.assertIn("다시 열림", out[1])
        i = I.load(p)
        self.assertEqual(i.status, "active"); self.assertNotIn("archived", i.fm); self.assertEqual(i.fm["reopened"], "2026-11-01")
        self.assertEqual(i.events()[-1], ("2026-11-01", "use"))
        self.assertEqual(i.last_growth(), TODAY)
        with self.assertRaises(ValueError):
            I.add_event(p, "mood", "x", TODAY)

    def test_check_reports_format_but_allows_empty_facets(self):
        note(self.d, "ok")
        note(self.d, "bad", status="done", facets=("발단", "문제"), log="- 2026-10-02 mood — x\n")
        ideas = {i.path.name: i for i in I.all_ideas(self.vault)}
        self.assertEqual(ideas["ok.md"].problems, [])
        why = " | ".join(ideas["bad.md"].problems)
        self.assertIn("status done", why); self.assertIn("속성 절 없음: 방법, 결과, 의미", why); self.assertIn("사건 종류 mood", why)

    def test_draw_records_outside_projects_first_then_constraints(self):
        for proj, n in (("strata-kit", 2), ("shop-api", 2)):
            dd = self.vault / "projects" / proj / "decisions"; dd.mkdir(parents=True)
            for k in range(n):
                (dd / f"DEC-{k}.md").write_text(f"---\ntitle: {proj} 결정 {k}\ntype: decision\n---\n본문\n")
        p = note(self.d, "seed")
        out = I.draw(self.vault, p, count=3, seed=7)
        recs = [l for l in out if l.strip().startswith("기록")]
        self.assertEqual(len(recs), 2)
        self.assertTrue(all("shop-api" in l for l in recs))      # the idea's own project is left out, work projects quoted
        self.assertEqual(sum(1 for l in out if l.strip().startswith("제약")), 1)
        self.assertTrue(all("— " in l for l in out[1:-1]))             # every item names its source
        self.assertEqual(out, I.draw(self.vault, p, count=3, seed=7))  # same seed, same draw
        self.assertIn("재료일 뿐", out[-1])


class NextCandidatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = Path(self.tmp.name) / "registry.yaml"
        self.reg.write_text("routes:\n- skill: x.shape\n  stage: ideation\n  kind: procedure\n  next:\n"
                            "  - {skill: strata.spec, area: planning, why: {ko: 기획으로}, on_proposes: {ko: 제안 초안으로}}\n"
                            "  - {skill: strata.decision, area: architecture, why: {ko: 결정으로}}\n"
                            "  - {skill: x.shape, why: {ko: 더 키운다}}\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_decides_by_default_and_do_nothing_last(self):
        out = sl.next_candidates("x.shape", [self.reg])
        self.assertIn("1. strata.spec — 기획으로 [planning: decides]", out[1])
        self.assertIn("2. strata.decision — 결정으로", out[2])
        self.assertIn("4. 아무것도 안 함", out[-1])

    def test_proposes_rewords_or_moves_after(self):
        out = sl.next_candidates("x.shape", [self.reg], {"planning": "proposes", "architecture": "proposes", "bogus": "blocks"})
        self.assertIn("1. strata.spec — 제안 초안으로 [planning: proposes]", out[1])
        self.assertIn("2. x.shape — 더 키운다", out[2])
        self.assertIn("3. strata.decision — 결정으로 (이 영역은 제안 자리", out[3])
        self.assertIn("아무것도 안 함", out[-1])

    def test_unknown_skill_still_offers_do_nothing(self):
        out = sl.next_candidates("nope", [self.reg])
        self.assertIn("후보 없음", out[0]); self.assertIn("아무것도 안 함", out[-1])

    def test_kit_pack_installs_and_classifies(self):
        root = Path(self.tmp.name) / "user"
        sl.install("ideation", apply=True, root=root)
        r = sl.layer_status(KIT / "skills" / "registry.yaml", None, [], root)
        self.assertEqual([(e.skill, e.stage, e.kind) for e in r["accepted"]], [("ideation.shape", "ideation", "procedure")])
        self.assertEqual(r["refused"], [])
        out = sl.next_candidates("ideation.shape", sl.user_registries(root))
        self.assertIn("strata.planning", out[1]); self.assertIn("strata.spec", out[2])   # idea → planning → spec (planning-stage)
        self.assertIn("아무것도 안 함", out[-1])
        self.assertEqual(sl.main(["next", "nope"]), 0)


if __name__ == "__main__":
    unittest.main()
