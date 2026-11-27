"""Pure-numpy helpers that turn per-step raw logits into word-level TokenInfo.
No torch import here so everything is unit-testable without a model."""
from __future__ import annotations
import unicodedata
from typing import Callable, List, Sequence, Tuple
import numpy as np

from core.interfaces import TokenInfo


def steps_from_logits(gen_ids: Sequence[int], logits: np.ndarray, null_id: int, k: int = 20
                      ) -> Tuple[np.ndarray, np.ndarray]:
    """gen_ids: emitted token id per step [T]; logits: RAW logits [T, V].
    Returns (topk [T,k], null [T]).

    topk[t,0] is ALWAYS the logit of the token actually emitted at step t. The
    remaining k-1 entries are the largest logits of the other tokens, descending.
    (If a logits-processor made the emitted token differ from the raw argmax,
    topk[t,0] < topk[t,1]; this is allowed and counted by validate_raw.)"""
    logits = np.asarray(logits, dtype=np.float32)
    T, V = logits.shape
    if len(gen_ids) != T:
        raise ValueError(f"{len(gen_ids)} ids vs {T} logit rows")
    if k > V:
        raise ValueError("k larger than vocabulary")
    topk = np.zeros((T, k), dtype=np.float32)
    for t in range(T):
        row = logits[t].copy()
        emitted = row[gen_ids[t]]
        row[gen_ids[t]] = -np.inf
        idx = np.argpartition(-row, k - 1)[: k - 1]
        rest = row[idx]
        rest = rest[np.argsort(-rest, kind="stable")]
        topk[t, 0] = emitted
        topk[t, 1:] = rest
    return topk, logits[:, null_id].copy()


def _is_punct_only(piece: str) -> bool:
    s = piece.strip()
    return bool(s) and all(unicodedata.category(c)[0] in ("P", "S") for c in s)


def _prob_of_first(z: np.ndarray) -> float:
    m = z.max()
    e = np.exp(z - m)
    return float(e[0] / e.sum())


def group_into_words(gen_ids: Sequence[int], topk: np.ndarray, null: np.ndarray,
                     decode: Callable[[Sequence[int]], str],
                     special_ids: set) -> List[TokenInfo]:
    """Group BPE tokens into words.

    A token starts a new word iff its own decoded text begins with a space (or it is
    the first non-special token). Special tokens are skipped. Punctuation-only
    subtokens are attached to the word text but IGNORED when choosing the
    confidence-carrying subtoken; a word made only of punctuation is dropped.
    The carrying subtoken is the one with the LOWEST raw top-probability, and its
    `topk_logits` / `null_logit` represent the word (CONTRACTS.md)."""
    groups: List[List[int]] = []
    for t, tid in enumerate(gen_ids):
        if tid in special_ids:
            continue
        piece = decode([tid])
        if not groups or piece.startswith(" "):
            groups.append([t])
        else:
            groups[-1].append(t)
    words: List[TokenInfo] = []
    for g in groups:
        text = decode([gen_ids[t] for t in g]).strip()
        carriers = [t for t in g if not _is_punct_only(decode([gen_ids[t]]))]
        if not text or not carriers:
            continue
        best = min(carriers, key=lambda t: _prob_of_first(topk[t]))
        words.append(TokenInfo(word=text, topk_logits=topk[best].astype(np.float32),
                               null_logit=float(null[best]), raw_conf=_prob_of_first(topk[best])))
    return words
