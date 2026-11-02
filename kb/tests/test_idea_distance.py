"""Facet distance between idea notes (planning/idea-facet-distance acceptance 1~3 and the neighbour half of 6):
same-name facets are compared by cosine similarity, empty facets are left out and shown as not measurable; near and
far are read against the quartiles of that facet's pair distribution, and relation kinds (alternative · exaptation ·
bundle · competition) carry the facet values they rest on; a neighbour bias line appears when every close neighbour
is close in one facet only. Vectors are fake and fixed so the numbers can be checked by hand."""
import hashlib
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT))

from kb import ideas as I  # noqa: E402

E = "비어 있음"


def note(d: Path, name: str, facets: dict):
    body = "".join(f"## {f}\n\n{facets.get(f, E)}\n\n" for f in I.FACETS)
    (d / f"{name}.md").write_text(f"---\ntitle: {name}\ntype: idea\ncreated: 2026-11-01\nnature: problem\nstatus: active\n---\n\n"
                                  f"# {name}\n\n{body}## 발전 기록\n\n", encoding="utf-8")


# text → unit vector; texts are short labels so the geometry is set by hand
AXES = {"p1": (1, 0, 0), "p1b": (0.96, 0.28, 0), "p2": (0, 1, 0), "m1": (1, 0, 0), "m1b": (0.96, 0.28, 0), "m2": (0, 0, 1),
        "o1": (1, 0, 0), "o2": (0, 1, 0), "s1": (1, 0, 0), "s2": (0, 0, 1), "g1": (1, 0, 0), "g2": (0, 1, 0)}


def fake_vectors(texts):
    import numpy as np
    out = {}
    for t in texts:
        v = np.asarray(AXES[t.strip()], dtype="float32")
        out[t] = v / np.linalg.norm(v)
    return out


class FacetDistanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        d = self.d = self.vault / "ideas"
        d.mkdir()
        # A is the centre. B: same problem, other method → alternative. C: same method, other problem → exaptation.
        # D: same outcome → competition; its meaning is empty (not measurable).
        note(d, "A", {"문제": "p1", "방법": "m1", "결과": "o1", "의미": "s1", "발단": "g1"})
        note(d, "B", {"문제": "p1b", "방법": "m2", "결과": "o2", "의미": "s2", "발단": "g2"})
        note(d, "C", {"문제": "p2", "방법": "m1b", "결과": "o2", "의미": "s2", "발단": "g2"})
        note(d, "D", {"문제": "p2", "방법": "m2", "결과": "o1", "발단": "g2"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_facets_are_left_out(self):
        ideas = I.all_ideas(self.vault)
        f = I.facet_texts(next(i for i in ideas if i.path.stem == "D"))
        self.assertNotIn("의미", f)
        self.assertEqual(f["문제"], "p2")

    def test_similarity_by_hand_and_not_measurable(self):
        r = I.near(I.all_ideas(self.vault), self.d / "A.md", fake_vectors)
        b = r["pairs"]["B"]
        self.assertAlmostEqual(b["문제"], 0.96, places=5)
        self.assertAlmostEqual(b["방법"], 0.0, places=5)
        self.assertIsNone(r["pairs"]["D"]["의미"])                     # empty on D's side
        text = "\n".join(I.near_lines(r))
        self.assertIn("의미 — 잴 수 없음: D", text)

    def test_relation_kinds_with_their_evidence(self):
        r = I.near(I.all_ideas(self.vault), self.d / "A.md", fake_vectors)
        kinds = {o: [k for k, _ in v] for o, v in r["relations"].items()}
        self.assertIn("대안", kinds["B"])
        self.assertIn("전용", kinds["C"])
        self.assertIn("경쟁", kinds["D"])
        ev = dict(r["relations"]["B"])["대안"]
        self.assertIn("문제 0.96", ev); self.assertIn("방법 0.00", ev)

    def test_neighbour_bias_when_close_in_one_facet_only(self):
        d = self.d
        for n in ("B", "C", "D"):
            (d / f"{n}.md").unlink()
        note(d, "B", {"문제": "p1b", "방법": "m2", "결과": "o2", "의미": "s2", "발단": "g2"})
        note(d, "C", {"문제": "p1", "방법": "m2", "결과": "o2", "의미": "s2", "발단": "g2"})
        note(d, "D", {"문제": "p2", "방법": "m2", "결과": "o2", "의미": "s2", "발단": "g2"})
        r = I.near(I.all_ideas(self.vault), d / "A.md", fake_vectors)
        self.assertEqual(r["bias"], ("문제", ["B", "C"]))
        self.assertIn("이웃 치우침: 가까운 이웃 2 이 모두 문제 에서만 가깝다", "\n".join(I.near_lines(r)))

    def test_no_bias_when_neighbours_differ(self):
        r = I.near(I.all_ideas(self.vault), self.d / "A.md", fake_vectors)
        self.assertIsNone(r["bias"])
        self.assertNotIn("이웃 치우침", "\n".join(I.near_lines(r)))

    def test_too_few_pairs_holds_judgement(self):
        for n in ("C", "D"):
            (self.d / f"{n}.md").unlink()
        r = I.near(I.all_ideas(self.vault), self.d / "A.md", fake_vectors)
        self.assertEqual(r["relations"], {})
        self.assertIn("판정 보류", "\n".join(I.near_lines(r)))

    def test_missing_vectors_are_reported_not_computed(self):
        calls = []
        lines = I.near_command(self.vault, self.d / "A.md", lookup=lambda texts: {}, embed=None, on_embed=calls.append)
        self.assertIn("임베딩 없는 속성", lines[0]); self.assertIn("--embed", lines[0])
        self.assertEqual(calls, [])
        lines = I.near_command(self.vault, self.d / "A.md", lookup=lambda texts: {}, embed=fake_vectors, on_embed=calls.append)
        self.assertEqual(len(calls), 1)                                # only the idea facets, once
        self.assertTrue(set(calls[0]) <= set(AXES))
        self.assertTrue(any("대안" in l for l in lines))


class CanvasMapTest(unittest.TestCase):
    """planning/idea-facet-distance acceptance 4: an Obsidian canvas with the chosen idea in the centre, radius in
    distance order, relation kinds as colour and label, a file per facet, notes untouched, rewritten on each run."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        d = self.d = self.vault / "ideas"
        d.mkdir()
        note(d, "A", {"문제": "p1", "방법": "m1", "결과": "o1", "의미": "s1", "발단": "g1"})
        note(d, "B", {"문제": "p1b", "방법": "m2", "결과": "o2", "의미": "s2", "발단": "g2"})
        note(d, "C", {"문제": "p2", "방법": "m1b", "결과": "o2", "의미": "s2", "발단": "g2"})
        note(d, "D", {"문제": "p2", "방법": "m2", "결과": "o1", "발단": "g2"})

    def tearDown(self):
        self.tmp.cleanup()

    def digest(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.d.glob("*.md")}

    def test_canvas_centre_radius_and_relations(self):
        import json, math
        before = self.digest()
        out = I.write_map(self.vault, self.d / "A.md", fake_vectors, facet="문제")
        self.assertEqual(out, self.vault / "outputs" / "ideas" / "A.문제.canvas")
        c = json.loads(out.read_text(encoding="utf-8"))
        nodes = {n["file"]: n for n in c["nodes"] if n["type"] == "file"}
        centre = nodes["ideas/A.md"]
        cx, cy = centre["x"] + centre["width"] / 2, centre["y"] + centre["height"] / 2
        r = {f.split("/")[1][0]: math.hypot(n["x"] + n["width"] / 2 - cx, n["y"] + n["height"] / 2 - cy)
             for f, n in nodes.items() if f != "ideas/A.md"}
        self.assertLess(r["B"], r["C"])                                 # 문제: B 0.96 is nearer than C 0.00
        self.assertAlmostEqual(r["C"], r["D"], delta=1)                 # equal similarity, equal radius
        edges = {e["toNode"]: e for e in c["edges"]}
        b = edges[nodes["ideas/B.md"]["id"]]
        self.assertIn("0.96", b["label"]); self.assertIn("대안", b["label"]); self.assertEqual(b["color"], I.REL_COLORS["대안"])
        self.assertEqual(self.digest(), before)                         # notes untouched

    def test_combined_map_and_unmeasurable_ring(self):
        import json
        out = I.write_map(self.vault, self.d / "A.md", fake_vectors)
        self.assertEqual(out.name, "A.canvas")
        c = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(sum(1 for n in c["nodes"] if n["type"] == "file"), 4)
        out2 = I.write_map(self.vault, self.d / "A.md", fake_vectors, facet="의미")
        c2 = json.loads(out2.read_text(encoding="utf-8"))
        d_edge = next(e for e in c2["edges"] if e["toNode"] == next(n["id"] for n in c2["nodes"] if n.get("file") == "ideas/D.md"))
        self.assertIn("잴 수 없음", d_edge["label"])

    def test_rerun_overwrites_same_file(self):
        a = I.write_map(self.vault, self.d / "A.md", fake_vectors).read_text()
        b = I.write_map(self.vault, self.d / "A.md", fake_vectors).read_text()
        self.assertEqual(a, b)
        self.assertEqual(len(list((self.vault / "outputs" / "ideas").glob("*.canvas"))), 1)


class LinksAndOverallBiasTest(unittest.TestCase):
    """planning/idea-facet-distance acceptance 5 and the overall half of 6: link candidates are printed, never
    written; `list` shows an overall bias line when open ideas are much more alike in one facet than the others."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        self.d = self.vault / "ideas"
        self.d.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_link_candidates_printed_not_written(self):
        d = self.d
        note(d, "A", {"문제": "p1", "방법": "m1", "결과": "o1", "의미": "s1", "발단": "g1"})
        note(d, "B", {"문제": "p1b", "방법": "m2", "결과": "o2", "의미": "s2", "발단": "g2"})
        note(d, "C", {"문제": "p2", "방법": "m1b", "결과": "o2", "의미": "s2", "발단": "g2"})
        note(d, "D", {"문제": "p2", "방법": "m2", "결과": "o1", "발단": "g2"})
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.glob("*.md")}
        text = "\n".join(I.near_lines(I.near(I.all_ideas(self.vault), d / "A.md", fake_vectors)))
        self.assertIn("링크 후보: [[B]] (대안)", text)
        self.assertIn("[[C]] (전용)", text)
        self.assertIn("ideas event", text)
        self.assertEqual({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.glob("*.md")}, before)

    def test_overall_bias_in_one_facet(self):
        d = self.d   # problems all alike (p1 · p1b), every other facet spread
        for n, p, m, o in (("A", "p1", "m1", "o1"), ("B", "p1b", "m2", "o2"), ("C", "p1", "m1b", "o2"), ("D", "p1b", "m2", "o1")):
            note(d, n, {"문제": p, "방법": m, "결과": o})
        line = I.overall_bias(I.all_ideas(self.vault), fake_vectors)
        self.assertIn("전체 치우침: 열린 아이디어 4 이 문제 에서 서로 너무 비슷하다", line)
        lines = I.listing(I.all_ideas(self.vault), date(2026, 11, 1), vectors=fake_vectors)
        self.assertTrue(any("전체 치우침" in l for l in lines))

    def test_no_overall_bias_when_spread(self):
        d = self.d
        for n, p, m, o in (("A", "p1", "m1", "o1"), ("B", "p2", "m2", "o2"), ("C", "p1b", "m1b", "o2"), ("D", "p2", "m2", "o1")):
            note(d, n, {"문제": p, "방법": m, "결과": o})
        self.assertIsNone(I.overall_bias(I.all_ideas(self.vault), fake_vectors))
        lines = I.listing(I.all_ideas(self.vault), date(2026, 11, 1), vectors=fake_vectors)
        self.assertFalse(any("전체 치우침" in l for l in lines))


if __name__ == "__main__":
    unittest.main()
