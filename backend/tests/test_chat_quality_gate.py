"""
Tests for the dual-path quality gate in api/chat.py — the logic deciding
when the pgvector fallback should activate, plus the token-budget
enforcement helper. Retrieval functions are monkeypatched so these run
without a real index file or Supabase connection.
"""
from __future__ import annotations

import pytest

from app.features.rag_chatbot.api import chat


def _doc(text: str, score: float, file_name: str = "doc.md") -> dict:
    return {"text": text, "score": score, "metadata": {"file_name": file_name}}


def test_retrieval_confidence_is_max_score():
    docs = [_doc("a", 0.2), _doc("b", 0.8), _doc("c", 0.5)]
    assert chat._retrieval_confidence(docs) == 0.8


def test_retrieval_confidence_empty_is_zero():
    assert chat._retrieval_confidence([]) == 0.0


def test_source_diversity_all_same_file():
    docs = [_doc("a", 0.9, "x.md"), _doc("b", 0.8, "x.md")]
    assert chat._source_diversity(docs) == 0.5


def test_source_diversity_all_different_files():
    docs = [_doc("a", 0.9, "x.md"), _doc("b", 0.8, "y.md")]
    assert chat._source_diversity(docs) == 1.0


def test_enforce_token_budget_keeps_everything_under_budget():
    texts = ["short text"] * 3
    kept, truncated = chat._enforce_token_budget(texts, max_tokens=1000)
    assert kept == texts
    assert truncated is False


def test_enforce_token_budget_drops_least_relevant_when_over():
    # Each ~250 chars ~= 62 tokens at the 4 chars/token estimate.
    texts = ["x" * 250 for _ in range(10)]
    kept, truncated = chat._enforce_token_budget(texts, max_tokens=100)
    assert truncated is True
    assert len(kept) < len(texts)


def test_enforce_token_budget_hard_truncates_oversized_single_chunk():
    huge = "x" * 10000
    kept, truncated = chat._enforce_token_budget([huge], max_tokens=50)
    assert truncated is True
    assert len(kept) == 1
    assert len(kept[0]) <= 50 * chat.CHARS_PER_TOKEN_ESTIMATE


@pytest.mark.asyncio
async def test_retrieve_with_trace_uses_primary_when_confident(monkeypatch):
    good_docs = [_doc("relevant answer", 0.9)]

    monkeypatch.setattr(chat, "_enhanced_retrieve", lambda q, k: (good_docs, {"impl": "enhanced_index"}))

    async def _should_not_be_called(q, k):
        raise AssertionError("pgvector fallback should not run when primary is confident")

    monkeypatch.setattr(chat, "_pgvector_retrieve", _should_not_be_called)

    docs, trace = await chat.retrieve_with_trace("some question", top_k=4)
    assert docs == good_docs
    assert trace["used_fallback"] is False
    assert trace["retrieval_confidence"] == 0.9


@pytest.mark.asyncio
async def test_retrieve_with_trace_falls_back_on_low_confidence(monkeypatch):
    weak_docs = [_doc("barely relevant", 0.1)]
    strong_fallback_docs = [_doc("actually relevant", 0.8)]

    monkeypatch.setattr(chat, "_enhanced_retrieve", lambda q, k: (weak_docs, {"impl": "enhanced_index"}))

    async def _fake_fallback(q, k):
        return strong_fallback_docs, {"impl": "pgvector", "method": "match_chunks"}

    monkeypatch.setattr(chat, "_pgvector_retrieve", _fake_fallback)

    docs, trace = await chat.retrieve_with_trace("some question", top_k=4)
    assert docs == strong_fallback_docs
    assert trace["used_fallback"] is True
    assert "fallback_reason" in trace


@pytest.mark.asyncio
async def test_retrieve_with_trace_reports_failed_fallback_attempt(monkeypatch):
    weak_docs = [_doc("barely relevant", 0.1)]

    monkeypatch.setattr(chat, "_enhanced_retrieve", lambda q, k: (weak_docs, {"impl": "enhanced_index"}))

    async def _empty_fallback(q, k):
        return [], {"impl": "pgvector", "error": "not configured"}

    monkeypatch.setattr(chat, "_pgvector_retrieve", _empty_fallback)

    docs, trace = await chat.retrieve_with_trace("some question", top_k=4)
    assert docs == weak_docs  # falls back to the weak primary results, not empty
    assert trace["fallback_attempted"] is True
