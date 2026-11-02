"""Embedder provider — local dense vectors for the store (DEC-2026-10-28-09).

Default model BAAI/bge-m3 (1024 dims, 8192 tokens, Korean·English) through sentence-transformers on the local
device (Apple MPS when available). Vectors are normalized, cached in the store's embeddings table by text hash
and attached to chunks; a rebuilt store reattaches them without recomputing.

  python3 -m kb embed [--model M] [--batch 16] [--max N]      embed chunks the cache does not cover yet
"""
from __future__ import annotations

import sys
import time

DEFAULT_MODEL = "BAAI/bge-m3"


MAX_SEQ_LENGTH = 2048   # bge-m3 accepts 8192, but attention memory grows with the square of the length: 2048 keeps
                        # a batch of long sections within a few GB on a laptop; only ~1% of chunks are longer


class Embedder:
    def __init__(self, model: str = DEFAULT_MODEL, device: str | None = None, max_seq_length: int = MAX_SEQ_LENGTH):
        self.model_name = model
        self._device = device
        self._model = None
        self.max_seq_length = max_seq_length

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            device = self._device
            if device is None:
                try:
                    import torch
                    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
                except Exception:  # noqa: BLE001
                    device = "cpu"
            kwargs = {}
            if device in ("mps", "cuda"):
                import torch
                kwargs["model_kwargs"] = {"torch_dtype": torch.float16}   # half the weight memory (≈1.1GB instead of 2.3GB)
            self._model = SentenceTransformer(self.model_name, device=device, **kwargs)
            self._model.max_seq_length = self.max_seq_length
        return self._model

    def encode(self, texts: list[str], batch_size: int = 16):
        import numpy as np
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        return self.model.encode(texts, batch_size=batch_size, normalize_embeddings=True, convert_to_numpy=True,
                                 show_progress_bar=False).astype("float32")

    def encode_query(self, text: str):
        return self.encode([text])[0]


def embed_store(store, model: str = DEFAULT_MODEL, batch_size: int = 4, max_chunks: int | None = None,
                log=print) -> dict:
    """Compute vectors for chunks whose text hash is not cached for `model`, store them, attach to chunks."""
    missing = store.missing_embeddings(model)
    if max_chunks is not None:
        missing = missing[:max_chunks]
    stats = {"model": model, "missing": len(missing), "embedded": 0, "seconds": 0.0}
    if not missing:
        with_vec, total = store.embedding_coverage()
        stats["coverage"] = f"{with_vec}/{total}"
        return stats
    emb = Embedder(model)
    t0 = time.time()
    log(f"embedding {len(missing)} chunks with {model} on {emb.model.device} (max {emb.max_seq_length} tokens, batch {batch_size}) …")
    # shortest first: batches stay homogeneous in length, so padding and peak memory stay small
    missing.sort(key=lambda m: len(m[3]))
    step = batch_size * 8
    for i in range(0, len(missing), step):
        part = missing[i:i + step]
        bs = batch_size if len(part[-1][3]) < 3000 else max(1, batch_size // 4)
        vecs = emb.encode([m[3] for m in part], batch_size=bs)
        store.put_embeddings(model, [(m[2], v) for m, v in zip(part, vecs)])
        stats["embedded"] += len(part)
        if log and (i // step) % 10 == 0:
            log(f"  {stats['embedded']}/{len(missing)}  {time.time() - t0:.0f}s")
    stats["seconds"] = round(time.time() - t0, 1)
    with_vec, total = store.embedding_coverage()
    stats["coverage"] = f"{with_vec}/{total}"
    return stats


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python3 -m kb embed", description="embed store chunks with a local model")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--max-seq", type=int, default=MAX_SEQ_LENGTH, help="토큰 상한 (기본 2048 — 메모리 보호)")
    ap.add_argument("--max", type=int, default=None, help="embed at most N chunks (smoke test)")
    ap.add_argument("--vault", default=None)
    ap.add_argument("--store", default=None)
    args = ap.parse_args(argv)
    from pathlib import Path
    from kb import vault_root
    from kb.engine import ensure_fresh_store
    store = ensure_fresh_store(Path(args.store) if args.store else None, Path(args.vault) if args.vault else vault_root())
    import kb.embed as _self
    _self.MAX_SEQ_LENGTH = args.max_seq
    stats = embed_store(store, args.model, args.batch, args.max)
    print(f"embedded {stats['embedded']} (missing {stats['missing']}) in {stats['seconds']}s · coverage {stats.get('coverage')} · model {stats['model']}")
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
