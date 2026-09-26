"""
Tests for pgvector_store.py that don't require a real Supabase connection —
config-detection and pure helper logic only. Real end-to-end pgvector
behavior (upsert/search against an actual Postgres instance) was verified
manually against the live project; it isn't re-mocked here since faking the
whole PostgREST/RPC surface would test the mock, not the code.
"""
from __future__ import annotations

from app.features.rag_chatbot.vector.pgvector_store import _document_source_path, is_configured


def test_is_configured_false_without_credentials(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert is_configured() is False


def test_is_configured_false_with_placeholder_url(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://placeholder.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "some-key")
    assert is_configured() is False


def test_document_source_path_prefers_drive_file_id():
    meta = {"drive_file_id": "abc123", "owner_folder": "HR", "file_name": "policy.md"}
    assert _document_source_path(meta) == "abc123"


def test_document_source_path_falls_back_to_folder_and_filename():
    meta = {"owner_folder": "HR", "file_name": "policy.md"}
    assert _document_source_path(meta) == "HR/policy.md"
