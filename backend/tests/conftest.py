"""
Shared pytest fixtures for the real, working pipeline (build_local_index.py /
build_drive_index.py / pgvector_store.py / chat.py's quality gate).

Does NOT cover the old speculative modules under processing/, chunking/,
embedding/, discovery/scanner.py — those are dead code this project
deliberately bypassed in favor of ingestion_common.py; see the session
history / README for why.

Run from backend/: `pytest` (rootdir must be backend/ so `app.*` imports
resolve the same way uvicorn app.main:app does).
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _force_mock_embeddings(monkeypatch):
    """
    Every test gets mock embeddings and no real provider keys by default, so
    the suite never makes a real network call or spends real API quota.
    Tests that specifically want to exercise a real-provider code path
    should override this within the test itself.
    """
    monkeypatch.setenv("USE_MOCK_EMBEDDINGS", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)


@pytest.fixture
def tmp_index_path(tmp_path):
    return tmp_path / "test_enhanced_index.json"
