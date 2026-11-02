"""DEC-2026-10-29-20: embeddings are optional — kb search --hybrid falls back to FTS when the model cannot be imported."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

from kb import search


class HybridFallbackTest(unittest.TestCase):
    def test_import_error_falls_back_to_fts(self):
        args = SimpleNamespace(query="refund", hybrid=True, semantic=False, limit=5, include_history=False, category=None,
                               topic=None, status=None, project=None, section=None, json=False, content=False)
        with mock.patch.object(search, "_vector_rows", side_effect=ImportError(name="sentence_transformers")), \
             mock.patch.object(search.api, "fts_rows", return_value=[]) as fts:
            buf = io.StringIO()
            with redirect_stdout(buf):
                try:
                    search.cmd_search(mock.MagicMock(), args)
                except SystemExit:
                    pass
        fts.assert_called()


if __name__ == "__main__":
    unittest.main()
