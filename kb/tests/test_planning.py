"""Planning bundles (planning/planning-stage acceptance 1~5, DEC-2026-11-01-04·05): the check finds rows without a
destination, rows counted twice and hand-offs the receiving bundle does not hold, rule rows with no axis, refined
documents over their limits and code or architecture expressions in refined documents only; knowledge search finds
refined documents but not source/ or audit/; the boundary command prints the exclusions and the injectable list."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import api, planning as P  # noqa: E402
from kb.providers import VaultScanner  # noqa: E402
from kb.store import SqliteStore  # noqa: E402


def w(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


FACTS = """---
title: 사실 목록
type: planning
category: audit
---
| # | 원천 위치 | 유형 | 내용 | 역할 | 축 | 하위 주제 |
|---|---|---|---|---|---|---|
| 1 | 2절 | 규칙 | 부분 환불은 결제 후 7일 안에만 된다 | 기획 | 시간 | 환불 |
| 2 | 2절 | 규칙 | 환불 금액은 사용한 만큼 뺀다 | 기획 |  | 환불 |
| 3 | 3절 | 데이터 | refund 테이블에 partial_amount 컬럼을 둔다 | 코드 |  | 환불 |
| 4 | 4절 | 규칙 | 정산은 다른 팀이 정한다 | 기획 | 충돌 | 정산 |
| 5 | 2절 | 규칙 | 7일 안에만 부분 환불 | 중복 | 시간 | 환불 |
| 6 | 5절 | 가정 | 환불 사유는 자유 입력이다 | 배경 |  | 환불 |
| 7 | 6절 | 규칙 | 환불 승인자는 운영자다 | 기획 | 해당 없음 | 환불 |
"""

COVERAGE = """---
title: 대조표
type: planning
category: audit
---
| 행# | 원천 위치 | 행선지 | 비고 |
|---|---|---|---|
| 1 | 2절 | prd R1 | |
| 2 | 2절 | prd R2 | |
| 2 | 2절 | 배경 | 두 번 셈 |
| 3 | 3절 | 코드 | |
| 4 | 4절 | 범위 밖:settlement | |
| 5 | 2절 | 중복:#1 | |
| 7 | 6절 | 결함:승인자 미정 | |
"""

PRD = """---
title: 부분 환불 PRD
type: planning
planning_doc: prd
---
# 부분 환불

- R1 결제 후 7일 안에만 부분 환불한다.
- R2 사용한 만큼 빼고 돌려준다.
"""


class BundleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        self.plan = self.vault / "projects" / "demo" / "planning"
        self.b = self.plan / "refund"
        w(self.b / "source" / "notion-refund.md", "---\ntitle: 원문\ntype: planning\n---\nrefund 테이블과 POST /api/refunds 를 쓴다\n")
        w(self.b / "audit" / "facts.md", FACTS)
        w(self.b / "audit" / "coverage.md", COVERAGE)
        w(self.b / "audit" / "defects.md", "| # | 종류 | 내용 | 처리 |\n|---|---|---|---|\n| 6 | 공백 | x | y |\n")
        w(self.b / "prd.md", PRD)
        w(self.plan / "settlement" / "audit" / "coverage.md", "| # | 원천 | 행선지 | 비고 |\n|---|---|---|---|\n| 9 | x | prd R1 | |\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_destinations_double_counts_and_handoffs_with_row_numbers(self):
        r = P.check(self.b)
        self.assertEqual(r["missing"], ["6"])                                   # row 6 has no destination
        self.assertEqual([x[0] for x in r["double"]], ["2"])
        self.assertEqual(r["handoff"], [("4", "settlement", "받는 쪽 대조표에 같은 행이 없음")])
        self.assertEqual(r["defect_unlisted"], ["7"])                           # defect destination, not in defects.md
        self.assertEqual(r["duplicate_target"], [])
        out = "\n".join(P.report(self.b, r))
        self.assertIn("행선지 없는 행: #6", out)
        self.assertIn("두 번 센 행 #2", out)
        self.assertIn("넘긴 행 #4 → settlement", out)
        # the receiving side takes the row: the hand-off problem disappears
        w(self.plan / "settlement" / "audit" / "coverage.md", "| # | 원천 | 행선지 | 비고 |\n|---|---|---|---|\n| 4 | 4절 | prd R1 | |\n")
        self.assertEqual(P.check(self.b)["handoff"], [])
        w(self.b / "audit" / "coverage.md", COVERAGE.replace("범위 밖:settlement", "범위 밖:nowhere"))
        self.assertEqual(P.check(self.b)["handoff"], [("4", "nowhere", "받는 묶음이 없음")])

    def test_rule_rows_without_axis_and_limits(self):
        r = P.check(self.b)
        self.assertEqual(r["axes"], ["2"])                                      # rule with empty axis; '해당 없음' counts as answered
        self.assertEqual(r["unanswered_axes"], ["동일성", "파생", "소멸"])
        self.assertEqual(r["limits"], [])
        rules = "\n".join(f"- R{i} 규칙 {i}" for i in range(1, 12))
        w(self.b / "prd.md", PRD + rules + "\n" + "말 " * 800)
        w(self.b / "logical-tech-spec.md", "---\ntitle: spec\ntype: planning\n---\n" + "보장 " * 1201)
        lim = P.check(self.b)["limits"]
        self.assertEqual([n for n, _ in lim], ["logical-tech-spec.md", "prd.md", "prd.md"])
        self.assertEqual(lim[0][1], "1201단어 (상한 1200)")
        self.assertTrue(lim[1][1].endswith("단어 (상한 800)"))
        self.assertEqual(lim[2][1], "규칙 11개 (상한 10)")

    def test_code_expressions_only_in_refined_documents(self):
        self.assertEqual(P.check(self.b)["code"], [])                           # source/ and audit/ name tables and APIs freely
        w(self.b / "prd.md", PRD + "\n환불 내역은 refund_history 테이블에 쌓는다.\nRefundService 가 POST /api/refunds 를 받고 HTTP 409 를 낸다.\n결제는 Stripe 로 한다.\n")
        hits = {ln: kinds for _, ln, kinds, _ in P.check(self.b)["code"]}
        self.assertEqual(hits[11], ["테이블·컬럼·스키마"])
        self.assertEqual(set(hits[12]), {"클래스·모듈·서비스명", "API 경로·HTTP 코드"})
        self.assertEqual(hits[13], ["프레임워크·라이브러리·벤더명"])
        self.assertNotIn(8, hits)                                               # plain rule lines are clean
        out = "\n".join(P.report(self.b, P.check(self.b)))
        self.assertIn("코드 표현 prd.md:11 [테이블·컬럼·스키마]", out)

    def test_cli_exit_codes(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(P.main(["check", str(self.b)]), 1)
        self.assertIn("refund: 사실 7행", buf.getvalue())
        self.assertEqual(P.main(["check", str(self.plan / "nope")]), 2)

    def test_axes_read_inside_free_text(self):
        self.assertEqual(P.axes_in("identity: order line; time: 14 days from payment"), {"identity", "time"})
        self.assertEqual(P.axes_in("시간, 소멸"), {"time", "expiry"})
        self.assertEqual(P.axes_in("timeline"), set())                         # word boundary for Latin names
        self.assertEqual(P.axes_in("n/a"), set())

    def test_layers(self):
        v = self.vault
        self.assertEqual(P.layer_of("projects/demo/planning/refund/source/notion-refund.md", {}, v), "source")
        self.assertEqual(P.layer_of("projects/demo/planning/refund/audit/facts.md", {}, v), "audit")
        self.assertEqual(P.layer_of("projects/demo/planning/refund/prd.md", {}, v), "refined")
        self.assertEqual(P.layer_of("projects/demo/planning/refund/raw.md", {"category": "source"}, v), "source")
        self.assertEqual(P.layer_of("projects/demo/planning/flat.md", {}, v), "original")
        self.assertEqual(P.layer_of("projects/demo/planning/intake/story.md", {}, v), "original")   # a folder without audit/
        self.assertEqual(P.layer_of("projects/demo/knowledge-base/x.md", {}, v), "")


class SearchAndBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        w(self.vault / "_meta" / "taxonomy.yaml", "version: '2'\ncategories:\n  guides:\n    order: 1\n")
        pl = self.vault / "projects" / "p" / "planning"
        w(pl / "flat.md", "---\ntitle: flat\ntype: planning\ncreated: 2026-01-01\n---\n## 원문\n오로라환불 원문 문서\n")
        w(pl / "refund" / "source" / "orig.md", "---\ntitle: orig\ntype: planning\ncreated: 2026-01-01\n---\n오로라환불 원천\n")
        w(pl / "refund" / "audit" / "facts.md", "---\ntitle: facts\ntype: planning\ncreated: 2026-01-01\n---\n| # | a |\n|---|---|\n| 1 | 오로라환불 사실 |\n")
        w(pl / "refund" / "tagged.md", "---\ntitle: tagged\ntype: planning\ncategory: audit\ncreated: 2026-01-01\n---\n오로라환불 격리\n")
        w(pl / "refund" / "prd.md", "---\ntitle: 환불 PRD\ntype: planning\nplanning_doc: prd\ncreated: 2026-01-01\n---\n## 규칙\n오로라환불 정리본\n")
        os.environ["STRATA_VAULT"] = str(self.vault)
        self.store = SqliteStore()
        self.store.rebuild([VaultScanner(self.vault)], kit_rev="t")

    def tearDown(self):
        self.tmp.cleanup()

    def test_knowledge_search_finds_refined_only(self):
        hits = api.search(self.store, "오로라환불")
        self.assertEqual([h["file_path"] for h in hits], ["projects/p/planning/refund/prd.md"])
        rows = self.store._fts_ranked("오로라환불", 20, None, None, knowledge_only=True)
        self.assertEqual({self.store.get(r[1]).path for r in rows}, {"projects/p/planning/refund/prd.md"})
        # history scope still reaches the evidence and the original
        everything = {h["file_path"] for h in api.search(self.store, "오로라환불", include_history=True, limit=20)}
        self.assertEqual(len(everything), 5)

    def test_original_planning_unchanged_when_no_bundle(self):
        self.assertEqual(self.store.get("doc:projects/p/planning/flat.md").payload["planning_layer"], "original")
        self.assertEqual(api.role_of(self.store.get("doc:projects/p/planning/flat.md")), "planning")

    def test_boundary_and_list(self):
        share = w(self.vault / "_meta" / "share.yaml", 'never:\n  - "projects/*/planning/**/source/**"\n')
        out = "\n".join(P.boundary_lines(share))
        self.assertIn("projects/*/planning/**/audit/**", out)
        self.assertIn('"projects/*/planning/**/source/**"   # 있음', out)
        self.assertIn('"projects/*/planning/**/audit/**"   # 없음', out)
        self.assertEqual(P.injectable(self.vault), ["projects/p/planning/refund/prd.md"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(P.main(["boundary", "--list", "--project", "p"]), 0)
        self.assertEqual(buf.getvalue().split(), ["projects/p/planning/refund/prd.md"])


if __name__ == "__main__":
    unittest.main()
