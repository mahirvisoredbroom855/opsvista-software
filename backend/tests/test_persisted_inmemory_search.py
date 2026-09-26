"""
Tests for PersistedInMemorySearch — the primary (JSON, in-memory) retrieval
path. Uses mock embeddings throughout (see conftest.py's autouse fixture),
so these are pure unit tests with no network calls.
"""
from __future__ import annotations

from app.features.rag_chatbot.vector.persisted_inmemory_search import PersistedInMemorySearch


def _sample_documents():
    return [
        {
            "id": "doc_1",
            "text": "Casual leave entitlement is 10 days per year for permanent employees.",
            "metadata": {"file_name": "leave_policy.md", "department": "HR"},
        },
        {
            "id": "doc_2",
            "text": "Machine downtime is logged whenever a knitting machine stops unexpectedly.",
            "metadata": {"file_name": "maintenance_log.md", "department": "Maintenance"},
        },
        {
            "id": "doc_3",
            "text": "Total revenue for Q3 2026 was 55,050,000 BDT across export and domestic sales.",
            "metadata": {"file_name": "pnl.xlsx", "department": "Finance"},
        },
    ]


def test_ingest_and_search_round_trip(tmp_index_path):
    index = PersistedInMemorySearch(index_path=tmp_index_path)
    index.ingest_documents(_sample_documents())

    assert tmp_index_path.exists()
    assert len(index.items) == 3
    assert index.dim == 384  # mock embedding dimension

    results = index.search("How many days of casual leave do employees get?", top_k=2)
    assert len(results) == 2
    assert all("score" in r and "text" in r and "metadata" in r for r in results)
    # Every result must be scored, and scores must be sorted descending.
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_on_empty_index_returns_nothing(tmp_index_path):
    index = PersistedInMemorySearch(index_path=tmp_index_path)
    assert index.search("anything", top_k=4) == []


def test_index_persists_and_reloads(tmp_index_path):
    index = PersistedInMemorySearch(index_path=tmp_index_path)
    index.ingest_documents(_sample_documents())

    reloaded = PersistedInMemorySearch(index_path=tmp_index_path)
    assert len(reloaded.items) == 3
    assert reloaded.dim == 384


def test_get_stats_reports_mock_embeddings(tmp_index_path):
    index = PersistedInMemorySearch(index_path=tmp_index_path)
    index.ingest_documents(_sample_documents())

    stats = index.get_stats()
    assert stats["total_documents"] == 3
    assert stats["using_mock_embeddings"] is True
