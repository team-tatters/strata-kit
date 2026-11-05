"""Cross-encoder rerank — opt-in second pass over the first search hits (default off).

Model BAAI/bge-reranker-v2-m3 through sentence-transformers CrossEncoder on the local device (Apple MPS in fp16
when available), loaded on first use and kept per process. Only the first TOP_N candidates are rescored, each
(query, chunk) pair cut at MAX_LENGTH tokens; the candidates below TOP_N keep their order after them.

Measured 2026-11-05 on the vault query set: hybrid recall@5/@10 .887/.897 → .917/.926 with top_n 30 and
max_length 384, about +1.25 s per query (median), +1.1–2.2 GB GPU memory, 3–4 s cold start. Hence off by default.

When sentence-transformers/torch or the model is not available, callers keep the un-reranked order and say so
(RerankUnavailable), like the embedding fallback (DEC-2026-10-29-20).
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"
TOP_N = 30
MAX_LENGTH = 384

Scorer = Callable[[str, Sequence[str]], Sequence[float]]


class RerankUnavailable(RuntimeError):
    """The rerank model or its packages could not be loaded; the reason is the message."""


class Reranker:
    def __init__(self, model: str = DEFAULT_MODEL, device: str | None = None, max_length: int = MAX_LENGTH):
        self.model_name = model
        self._device = device
        self.max_length = max_length
        self._model = None

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as e:
                raise RerankUnavailable(f"rerank model unavailable: {e.name or e}") from e
            device = self._device
            if device is None:
                try:
                    import torch
                    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
                except Exception:  # noqa: BLE001
                    device = "cpu"
            kwargs: dict[str, Any] = {}
            if device in ("mps", "cuda"):
                import torch
                kwargs["model_kwargs"] = {"torch_dtype": torch.float16}
            try:
                self._model = CrossEncoder(self.model_name, device=device, max_length=self.max_length, **kwargs)
            except (OSError, ValueError) as e:      # not cached and no network, or a bad model name
                raise RerankUnavailable(f"rerank model unavailable: {self.model_name} ({type(e).__name__})") from e
        return self._model

    def __call__(self, query: str, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        scores = self.model.predict([(query, t) for t in texts], batch_size=8, show_progress_bar=False)
        return [float(s) for s in scores]


_rerankers: dict[str, Reranker] = {}


def get_reranker(model: str = DEFAULT_MODEL) -> Reranker:
    """One reranker per model per process (the MCP server is long-lived; loading takes seconds)."""
    if model not in _rerankers:
        _rerankers[model] = Reranker(model)
    return _rerankers[model]


def rerank(query: str, items: list, text_of: Callable[[Any], str], *, top_n: int = TOP_N,
           scorer: Scorer | None = None) -> tuple[list, list[float]]:
    """Reorder the first top_n items by cross-encoder score (highest first, ties keep their order); the rest follow
    unchanged. Returns (items, scores of the reordered head). Raises RerankUnavailable when the model cannot load."""
    head, tail = items[:top_n], items[top_n:]
    if not head:
        return list(items), []
    score = scorer or get_reranker()
    scores = list(score(query, [text_of(x) for x in head]))
    order = sorted(range(len(head)), key=lambda i: -scores[i])
    return [head[i] for i in order] + tail, [scores[i] for i in order]


def chunk_text(heading: str | None, text: str | None) -> str:
    """What the cross-encoder reads for one chunk: its heading, then its text."""
    heading, text = (heading or "").strip(), text or ""
    return f"{heading}\n{text}" if heading and heading != "(intro)" else text
