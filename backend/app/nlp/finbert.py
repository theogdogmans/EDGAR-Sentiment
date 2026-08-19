from __future__ import annotations

import re
import threading
from typing import Any

import numpy as np

from ..config import FINBERT_MODEL

_lock = threading.Lock()
_tokenizer = None
_model = None

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
LABELS = ("positive", "negative", "neutral")


def _load():
    global _tokenizer, _model
    if _model is not None:
        return _tokenizer, _model
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    _tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL)
    _model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL)
    _model.eval()
    return _tokenizer, _model


def split_sentences(text: str) -> list[str]:
    parts = SENT_SPLIT.split(re.sub(r"\s+", " ", text).strip())
    out: list[str] = []
    for part in parts:
        s = part.strip()
        if len(s) < 40:
            continue
        words = s.split()
        if len(words) < 8:
            continue
        if sum(ch.isalpha() for ch in s) < 20:
            continue
        out.append(s)
    return out


def _select_sentences(sentences: list[str], limit: int = 220) -> list[str]:
    if len(sentences) <= limit:
        return sentences
    idx = np.linspace(0, len(sentences) - 1, limit, dtype=int)
    return [sentences[i] for i in idx]


def score_sentences(sentences: list[str], batch_size: int = 24) -> list[dict[str, Any]]:
    tokenizer, model = _load()
    import torch
    import torch.nn.functional as F

    results: list[dict[str, Any]] = []
    id2label = {int(k): v.lower() for k, v in getattr(model.config, "id2label", {}).items()}
    if not id2label:
        id2label = {0: "positive", 1: "negative", 2: "neutral"}

    with _lock:
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i : i + batch_size]
            encoded = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            with torch.no_grad():
                logits = model(**encoded).logits
                probs = F.softmax(logits, dim=-1).cpu().numpy()
            for text, dist in zip(batch, probs):
                by_label = {id2label.get(j, LABELS[j]): float(p) for j, p in enumerate(dist)}
                pos = by_label.get("positive", 0.0)
                neg = by_label.get("negative", 0.0)
                neu = by_label.get("neutral", 0.0)
                label = max(by_label, key=by_label.get)
                results.append(
                    {
                        "text": text,
                        "label": label,
                        "positive": pos,
                        "negative": neg,
                        "neutral": neu,
                        "score": pos - neg,
                    }
                )
    return results


def analyze_text(text: str) -> dict[str, Any]:
    sentences = _select_sentences(split_sentences(text))
    if not sentences:
        raise ValueError("No usable sentences in MD&A")
    scored = score_sentences(sentences)
    n = len(scored)
    pos_n = sum(1 for s in scored if s["label"] == "positive")
    neg_n = sum(1 for s in scored if s["label"] == "negative")
    neu_n = n - pos_n - neg_n
    mean_score = float(np.mean([s["score"] for s in scored]))
    # Keep polar examples plus leading narrative for the UI.
    ranked = sorted(scored, key=lambda s: abs(s["score"]), reverse=True)
    polar = ranked[:40]
    head = scored[:80]
    seen = set()
    display = []
    for item in head + polar:
        key = item["text"][:80]
        if key in seen:
            continue
        seen.add(key)
        display.append(item)
        if len(display) >= 120:
            break
    return {
        "score": mean_score,
        "positive_share": pos_n / n,
        "negative_share": neg_n / n,
        "neutral_share": neu_n / n,
        "sentence_count": n,
        "sentences": display,
    }
