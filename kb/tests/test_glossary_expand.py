"""Deterministic query expansion from glossary aliases (MB-strata-kit-2026-056 step 2). No model: the aliases are
what the glossary itself writes — 'A / B' and 'A (B)' in the term cell, or an alias column."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import api  # noqa: E402
from kb.glossary import AliasIndex, parse_alias_groups  # noqa: E402
from kb.store import Chunk, Node, SqliteStore, fts_query_expanded  # noqa: E402

GLOSSARY = """## 도메인 용어

| 용어 | 정의 | 프로젝트 |
|---|---|---|
| 집계행 / 활동데이터 | 배출량 v2 입력 단위 | api-server |
| 협업자 (COLLABORATOR) | 매직링크로 초대되는 외부 작업자 | api-server |
| 존(zone) | 배포 단위 | web-app |
| relay JWT | 다운스트림에 넘기는 JWT | api-server |

## 별칭 표

| 용어 | 별칭 | 정의 |
|---|---|---|
| 산정인자 | 배출계수, emission factor | 배출량 계산의 계수 |
"""


class ParseTest(unittest.TestCase):
    def test_groups_come_from_slash_parentheses_and_alias_column(self):
        groups = {frozenset(g) for g in parse_alias_groups(GLOSSARY)}
        self.assertIn(frozenset({"집계행", "활동데이터"}), groups)
        self.assertIn(frozenset({"협업자", "COLLABORATOR"}), groups)
        self.assertIn(frozenset({"산정인자", "배출계수", "emission factor"}), groups)
        # one-syllable members are too ambiguous to expand ('존' would match 존재); a group of one is no alias
        self.assertFalse(any("존" in g for g in groups))
        self.assertFalse(any("relay JWT" in g for g in groups))

    def test_header_and_separator_rows_are_not_terms(self):
        terms = set().union(*parse_alias_groups(GLOSSARY))
        self.assertNotIn("용어", terms)
        self.assertFalse(any(t.startswith("---") for t in terms))


class ExpandTest(unittest.TestCase):
    def setUp(self):
        self.ix = AliasIndex(parse_alias_groups(GLOSSARY))

    def test_expand_adds_the_other_members_only(self):
        self.assertEqual(self.ix.expand("배출계수 관리 정책"), ["산정인자", "emission factor"])
        self.assertEqual(self.ix.expand("배출계수와 산정인자"), ["emission factor"])     # present members are not repeated
        self.assertEqual(self.ix.expand("collaborator 초대"), ["협업자"])                 # case-insensitive
        self.assertEqual(self.ix.expand("협업자를 초대하는 API"), ["COLLABORATOR"])       # a particle does not hide the term
        self.assertEqual(self.ix.expand("배출량 입력"), [])

    def test_fts_any_terms_appends_aliases(self):
        self.assertEqual(fts_query_expanded("배출계수 정책", True, self.ix), '"배출계수" OR "정책" OR "산정인자" OR "emission factor"')

    def test_fts_all_terms_offers_the_alias_in_place(self):
        self.assertEqual(fts_query_expanded("배출계수 정책", False, self.ix), '("배출계수" OR "산정인자" OR "emission factor") AND "정책"')
        self.assertEqual(fts_query_expanded("정책 결정", False, self.ix), '"정책" "결정"')        # nothing to expand: unchanged
        self.assertEqual(fts_query_expanded("배출계수 AND 정책", True, self.ix), '("배출계수" OR "산정인자" OR "emission factor") AND "정책"')

    def test_no_index_is_plain_fts_query(self):
        self.assertEqual(fts_query_expanded("배출계수 정책", True, None), '"배출계수" OR "정책"')

    def test_dense_text_names_the_aliases(self):
        self.assertEqual(self.ix.dense_text("배출계수 관리 정책"), "배출계수 관리 정책 (산정인자 · emission factor)")
        self.assertEqual(self.ix.dense_text("배출량 입력"), "배출량 입력")


class StoreAliasTest(unittest.TestCase):
    def setUp(self):
        self.s = SqliteStore()
        self.s.put_nodes([Node("doc:_index/glossary.md", "doc", path="_index/glossary.md", payload={"type": "glossary", "indexed": True}),
                          Node("doc:f", "doc", path="projects/p/knowledge-base/formula.md", payload={"type": "specification", "indexed": True})])
        self.s.put_chunks([Chunk("doc:_index/glossary.md", 0, GLOSSARY, heading="도메인 용어"),
                           Chunk("doc:f", 0, "산정인자 세트는 버전을 고정한다")])

    def test_expanded_expressions_are_valid_fts5(self):
        for q in ("배출계수 정책", "배출계수 AND 정책", "정책 배출계수*", "협업자 초대 메일", "relay JWT"):
            for any_terms in (False, True):
                self.s.search_text(q)
                api.fts_rows(self.s, q, any_terms=any_terms)

    def test_store_reads_aliases_from_glossary_documents(self):
        self.assertEqual(self.s.query_aliases().expand("배출계수"), ["산정인자", "emission factor"])

    def test_search_finds_a_document_through_its_alias(self):
        self.assertIn("doc:f", [h.node.id for h in self.s.search_text("배출계수")])    # the document only says 산정인자
        self.assertIn("doc:f", [r["node"].id for r in api.fts_rows(self.s, "배출계수 관리 정책", any_terms=True)])

    def test_rebuild_drops_the_cached_aliases(self):
        self.s.query_aliases()
        self.s.rebuild([])
        self.assertEqual(self.s.query_aliases().expand("배출계수"), [])


if __name__ == "__main__":
    unittest.main()
