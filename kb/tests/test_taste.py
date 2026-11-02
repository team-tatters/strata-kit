"""kb taste (planning/design-stage acceptance 1·2·3·7·8·9, DEC-2026-11-01-10 · 11): taste notes live per project or
brand with four sections, inferences stay marked, a tag from three different briefs is a promotion candidate and
only a promoted line with three briefs of evidence is a taste line; expression notes reference primitives by name and
their relations are computed (OKLCH lightness, WCAG 2 contrast)."""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import design as D  # noqa: E402
from kb import taste as T  # noqa: E402

KIT = Path(__file__).resolve().parents[2]
EXAMPLE = KIT / "skills" / "packs" / "design" / "design.taste" / "data" / "example-expression.md"


def w(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def taste_note(scope="project", owner="acme", taste="", signals="", infer="", reject="") -> str:
    return (f"---\ntype: design-taste\nscope: {scope}\nowner: {owner}\nstatus: active\n---\n\n# 취향\n\n"
            f"## 취향\n\n{taste}\n## 신호\n\n{signals}\n## 추론\n\n{infer}\n## 거절\n\n{reject}")


SIG3 = ('- 2026-10-01 반응 #여백 [[brief-a]] — "숨 쉴 데가 있어서 좋다"\n'
        '- 2026-10-05 고름 #여백 [[brief-b]] — "이게 덜 답답해"\n')
REJ = '- 2026-10-09 #여백 [[brief-c]] — "꽉 찬 건 싫다" — 이유: 정보가 한꺼번에 들어온다\n'


def expr_note(primitives: str, technique: str) -> str:
    return (f"---\ntype: design-expression\nscope: project\nowner: acme\n---\n\n## 원값\n\n바탕과 글자.\n\n```yaml\n"
            f"primitives:\n{primitives}```\n\n## 기법: 시험\n\n시험 기법.\n\n```yaml\n{technique}```\n")


PRIMS = '  color.page: "#ffffff"\n  color.ink: "#000000"\n  color.mid: "#777777"\n  opacity.half: 0.5\n  radius.r: 8px\n'


class ColourTest(unittest.TestCase):
    def test_contrast_black_white_is_21(self):
        self.assertAlmostEqual(T.contrast(T.Color.parse("#000"), T.Color.parse("#fff")), 21.0, places=6)

    def test_contrast_777_on_white(self):           # hand value: (1.05)/(0.18447+0.05) = 4.478
        self.assertAlmostEqual(T.contrast(T.Color.parse("#777777"), T.Color.parse("#ffffff")), 4.478, places=2)

    def test_oklch_lightness_of_grey_is_cube_root_of_linear(self):
        # for a neutral grey OKLab L = cbrt(linear value); L = 0.5 → linear 0.125 → sRGB 0.3886 → #636363
        self.assertAlmostEqual(T.lightness(T.Color.parse("#ffffff")), 1.0, places=4)
        self.assertEqual(T.shift(T.Color.parse("#000000"), 0.5).hex(), "#636363")

    def test_darken_moves_lightness_down_by_d(self):
        c = T.Color.parse("#3b6ef5")
        self.assertAlmostEqual(T.lightness(T.shift(c, -0.1)), T.lightness(c) - 0.1, places=2)

    def test_alpha_composites_over_background(self):
        half_black = T.Color(0, 0, 0, 0.5)
        self.assertEqual(T.over(half_black, T.Color.parse("#ffffff")).hex(), "#808080")


class TasteCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        self.path = self.vault / "projects" / "acme" / "design" / "taste.md"

    def tearDown(self):
        self.tmp.cleanup()

    def kinds(self, path=None):
        probs, cands = T.check_taste(path or self.path, self.vault)
        return [k for k, _ in probs], cands

    def test_clean_note_and_candidate_from_three_briefs(self):
        w(self.path, taste_note(signals=SIG3, reject=REJ))
        kinds, cands = self.kinds()
        self.assertEqual(kinds, [])
        self.assertEqual(len(cands), 1)
        self.assertIn("#여백", cands[0])

    def test_repeats_in_one_brief_count_once(self):
        sig = "".join(f'- 2026-10-0{i} 반응 #둥글게 [[brief-a]] — "둥근 게 좋다"\n' for i in range(1, 5))
        w(self.path, taste_note(signals=sig))
        self.assertEqual(self.kinds(), ([], []))

    def test_promoted_line_with_three_briefs_passes_and_is_no_longer_a_candidate(self):
        taste = "- #여백 요소 사이를 넉넉히 둔다 — 승격 2026-10-10 · 근거 [[brief-a]] [[brief-b]] [[brief-c]]\n"
        w(self.path, taste_note(taste=taste, signals=SIG3, reject=REJ))
        self.assertEqual(self.kinds(), ([], []))

    def test_promoted_from_one_signal_is_thin(self):
        taste = "- #여백 요소 사이를 넉넉히 둔다 — 승격 2026-10-02 · 근거 [[brief-a]]\n"
        w(self.path, taste_note(taste=taste, signals=SIG3))
        self.assertIn("thin-taste", self.kinds()[0])

    def test_taste_line_without_promotion_date_is_malformed(self):
        w(self.path, taste_note(taste="- #여백 넉넉한 여백\n", signals=SIG3, reject=REJ))
        self.assertIn("bad-taste", self.kinds()[0])

    def test_inference_outside_its_section_leaks(self):
        taste = "- [추론] #차분 차분한 색을 좋아한다 — 2026-10-03\n"
        w(self.path, taste_note(taste=taste, signals=SIG3))
        self.assertIn("infer-leak", self.kinds()[0])

    def test_inference_line_needs_mark_and_date(self):
        w(self.path, taste_note(infer="- #차분 차분한 색\n"))
        self.assertIn("bad-infer", self.kinds()[0])
        w(self.path, taste_note(infer="- [추론] #차분 차분한 색을 좋아하는 듯 — 2026-10-03\n"))
        self.assertEqual(self.kinds()[0], [])

    def test_signal_without_quoted_words_and_rejection_without_reason(self):
        w(self.path, taste_note(signals="- 2026-10-01 반응 #여백 [[brief-a]] — 여백이 좋음\n",
                                reject='- 2026-10-09 #여백 [[brief-c]] — "꽉 찬 건 싫다"\n'))
        kinds = self.kinds()[0]
        self.assertIn("bad-signal", kinds)
        self.assertIn("bad-reject", kinds)

    def test_sections_must_be_the_four(self):
        w(self.path, "---\ntype: design-taste\nscope: project\nowner: acme\n---\n\n## 취향\n\n## 신호\n")
        self.assertIn("sections", self.kinds()[0])

    def test_person_level_note_is_refused(self):
        p = w(self.vault / "people" / "alice" / "taste.md", taste_note())
        self.assertIn("place", self.kinds(p)[0])
        self.assertIn(p, T.vault_taste_notes(self.vault))

    def test_brand_place_and_scope_mismatch(self):
        p = w(self.vault / "designs" / "moonlight" / "taste.md", taste_note(scope="brand", owner="moonlight"))
        self.assertEqual(self.kinds(p)[0], [])
        w(p, taste_note(scope="project", owner="moonlight"))
        self.assertIn("scope", self.kinds(p)[0])


class ExpressionCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def kinds(self, technique: str, prims: str = PRIMS):
        p = w(self.dir / "expression.md", expr_note(prims, technique))
        probs, comp = T.check_expression(p)
        return [k for k, _ in probs], comp

    def test_example_note_has_four_techniques_and_passes(self):
        probs, comp = T.check_expression(EXAMPLE)
        self.assertEqual(probs, [])
        self.assertEqual(len(comp), 4)          # glass, neumorphism, stacked borders, roles

    def test_relations_pass_and_values_are_computed(self):
        kinds, comp = self.kinds("derive:\n  t.fill: alpha(color.ink, opacity.half)\n"
                                 "layers:\n  - {fill: t.fill, radius: radius.r}\n"
                                 "relations:\n  - contrast(color.ink, color.page) >= 21\n")
        self.assertEqual(kinds, [])
        self.assertEqual(comp["기법: 시험"]["t.fill"].hex(), "#00000080")

    def test_relation_that_does_not_hold(self):
        kinds, _ = self.kinds("relations:\n  - contrast(color.mid, color.page) >= 4.5\n")
        self.assertEqual(kinds, ["relation-fails"])

    def test_translucent_colour_is_composited_over_on(self):
        kinds, _ = self.kinds("derive:\n  t.veil: alpha(color.ink, opacity.half)\n"
                              "relations:\n  - contrast(t.veil, color.page, color.page) < 5\n")
        self.assertEqual(kinds, [])                    # #808080 on white ≈ 3.95

    def test_raw_values_in_technique(self):
        kinds, _ = self.kinds("derive:\n  t.x: lighten(#123456, 0.1)\n"
                              "layers:\n  - {fill: \"#ff0000\", blur: 12px}\n"
                              "relations:\n  - lightness(t.x) > 0\n")
        self.assertEqual(kinds.count("raw-value"), 3)

    def test_unknown_reference_and_cycle(self):
        kinds, _ = self.kinds("derive:\n  a.x: lighten(a.y, 0.1)\n  a.y: darken(a.x, 0.1)\n  a.z: lighten(color.none, 0.1)\n"
                              "relations:\n  - lightness(color.ink) < 1\n")
        self.assertIn("cycle", kinds)
        self.assertIn("unknown-ref", kinds)

    def test_technique_without_relations(self):
        kinds, _ = self.kinds("layers:\n  - {fill: color.page}\n")
        self.assertEqual(kinds, ["no-relations"])

    def test_opacity_out_of_range(self):
        kinds, _ = self.kinds("relations:\n  - lightness(color.ink) < 1\n", PRIMS + "  opacity.bad: 1.4\n")
        self.assertIn("bad-opacity", kinds)
        kinds, _ = self.kinds("derive:\n  t.x: alpha(color.ink, 2)\nrelations:\n  - lightness(color.ink) < 1\n")
        self.assertIn("bad-expr", kinds)

    def test_section_without_block_or_text(self):
        p = w(self.dir / "e.md", "---\ntype: design-expression\n---\n\n## 원값\n\n```yaml\nprimitives: {color.a: \"#fff\"}\n```\n\n## 기법: 빈\n\n설명만.\n")
        kinds = [k for k, _ in T.check_expression(p)[0]]
        self.assertIn("no-text", kinds)
        self.assertIn("no-block", kinds)


class BoundaryTest(unittest.TestCase):
    """acceptance 9: neither side reads the other's files."""

    def test_taste_check_does_not_read_task_files(self):
        with tempfile.TemporaryDirectory() as d:
            task = w(Path(d) / "task-ui.yaml", "task:\n  id: x\ninputs:\n  design_ref: {kind: none}\n")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = T.main(["check", str(task)])
            self.assertEqual(rc, 0)
            self.assertIn("취향 노트 0", out.getvalue())

    def test_design_check_does_not_read_taste_notes(self):
        with tempfile.TemporaryDirectory() as d:
            note = w(Path(d) / "design" / "taste.md", taste_note(taste="- bad\n"))
            out = io.StringIO()
            with redirect_stdout(out):
                rc = D.main(["check", str(note), str(note.parent)])
            self.assertEqual(rc, 0)
            self.assertIn("태스크 0", out.getvalue())


if __name__ == "__main__":
    unittest.main()
