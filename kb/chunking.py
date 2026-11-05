"""Split heading sections that do not fit the encoder window (MB-strata-kit-2026-056).

chunk_by_heading cuts a document at H2–H4. Most sections fit the embedder's 2,048-token window
(kb.embed.MAX_SEQ_LENGTH), but a few do not: the encoder silently drops everything past the window, so the
facts in the back half of a long section are never seen by dense search. split_over_tokens leaves every
section that fits exactly as it is (same text, same embedding cache hash) and cuts only the others:

  · at paragraph boundaries (blank lines); a paragraph that alone is too long at line boundaries; a line that
    alone is too long at a character position — into pieces of about TARGET_TOKENS tokens;
  · every later piece starts with '…', the last OVERLAP_CHARS characters of the previous piece (snapped to a
    word boundary when one is near) and a newline, so a sentence across a cut is found from either side;
  · every piece keeps the section's heading (the embedded text repeats it) and gets part = [i, n].

Token counts come from the bge-m3 tokenizer when transformers can load it from the local cache (never a
download); otherwise from a conservative character estimate, ceil(chars * FALLBACK_TOKENS_PER_CHAR) + 2.
Measured on the vault (2026-11-05), bge-m3 never produced more tokens than characters and at most 0.69 tokens
per character for texts over 200 characters, so the estimate (0.75) over-counts: without the tokenizer more
sections are split than strictly necessary, never fewer. The output is deterministic for a given counter, but
a store built with the tokenizer and one built without it cut long sections differently (different hashes):
build the store and embed it on the same machine.
"""
from __future__ import annotations

import math
from typing import Callable

from kb.embed import MAX_SEQ_LENGTH

TOKEN_LIMIT = MAX_SEQ_LENGTH      # embedded text above this many tokens is truncated by the encoder
TARGET_TOKENS = 1500              # size of each piece of a split section, heading and title included
OVERLAP_CHARS = 150               # characters of the previous piece repeated at the start of the next
FALLBACK_TOKENS_PER_CHAR = 0.75   # character estimate when the tokenizer is unavailable (measured max 0.69)
_SLACK = 60                       # tokens kept free in each piece for joins that tokenize differently

TokenCount = Callable[[str], int]


def estimate_tokens(text: str) -> int:
    """Conservative token estimate without a tokenizer."""
    return math.ceil(len(text) * FALLBACK_TOKENS_PER_CHAR) + 2


_COUNTER: tuple[TokenCount, str] | None = None


def token_counter() -> tuple[TokenCount, str]:
    """(count, source): the bge-m3 tokenizer from the local cache, else the character estimate."""
    global _COUNTER
    if _COUNTER is None:
        try:
            import logging
            from transformers import AutoTokenizer
            logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)  # "longer than 8192" note
            tok = AutoTokenizer.from_pretrained("BAAI/bge-m3", local_files_only=True)

            def count(text: str) -> int:
                return len(tok(text, add_special_tokens=True, truncation=False)["input_ids"])
            _COUNTER = (count, "bge-m3")
        except Exception:   # transformers missing, or the model never downloaded on this machine
            _COUNTER = (estimate_tokens, "chars")
    return _COUNTER


def _units(text: str, budget: int, count: TokenCount) -> list[tuple[str, str, int]]:
    """(separator before, text, tokens) units no larger than budget: paragraphs, else lines, else char cuts."""
    out: list[tuple[str, str, int]] = []
    for pi, para in enumerate(text.split("\n\n")):
        psep = "\n\n" if pi else ""
        n = count(para)
        if n <= budget:
            out.append((psep, para, n))
            continue
        for li, line in enumerate(para.split("\n")):
            sep = psep if li == 0 else "\n"
            n = count(line)
            while n > budget:   # one line longer than a piece: cut in proportion to its token density
                k = max(1, int(len(line) * budget / n * 0.95))
                head = line[:k]
                out.append((sep, head, count(head)))
                sep, line = "", line[k:]
                n = count(line)
            out.append((sep, line, n))
    return out


def _lead(prev: str, overlap: int) -> str:
    if overlap <= 0:
        return ""
    tail = prev[-overlap:]
    cut = tail.find(" ")
    if 0 <= cut < len(tail) // 2:   # start the overlap on a word boundary when one is near
        tail = tail[cut + 1:]
    return "…" + tail + "\n" if tail else ""


def split_text(text: str, prefix_tokens: int, count: TokenCount, target: int = TARGET_TOKENS,
               overlap: int = OVERLAP_CHARS) -> list[tuple[str, str]]:
    """Cut text into (lead, own text) pieces of about `target` tokens including a prefix of prefix_tokens."""
    lead_room = count("…" + "x" * overlap) if overlap > 0 else 0
    budget = max(32, target - prefix_tokens - lead_room - _SLACK)
    parts: list[str] = []
    cur, cur_n = "", 0
    for sep, u, n in _units(text, budget, count):
        if cur and cur_n + n > budget:
            parts.append(cur)
            cur, cur_n = u, n
        elif cur:
            cur, cur_n = cur + sep + u, cur_n + n + 1
        else:
            cur, cur_n = u, n
    if cur or not parts:
        parts.append(cur)
    return [("" if i == 0 else _lead(parts[i - 1], overlap), p) for i, p in enumerate(parts)]


def split_over_tokens(chunks: list[dict], embedded: Callable[[dict], str], count: TokenCount | None = None,
                      limit: int = TOKEN_LIMIT, target: int = TARGET_TOKENS, overlap: int = OVERLAP_CHARS) -> list[dict]:
    """chunk_by_heading output → the same chunks, except that one whose embedded text (embedded(chunk) — title,
    heading and content as the store embeds them) exceeds `limit` tokens becomes several, each with
    part = [i, n] and own_chars (its characters without the overlap lead)."""
    if count is None:
        count = token_counter()[0]
    out: list[dict] = []
    for c in chunks:
        full = embedded(c)
        if len(full) <= limit or count(full) <= limit:   # bge-m3 never yields more tokens than characters
            out.append(c)
            continue
        prefix_tokens = count(full[: len(full) - len(c["content"])]) if c["content"] else count(full)
        pieces = split_text(c["content"], prefix_tokens, count, target, overlap)
        if len(pieces) == 1:   # nothing to cut at (should not happen: units are at most a piece)
            out.append(c)
            continue
        for k, (lead, own) in enumerate(pieces):
            out.append({**c, "content": lead + own, "own_chars": len(own), "part": [k + 1, len(pieces)]})
    return out
