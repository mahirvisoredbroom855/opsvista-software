# Legacy / unused files

Everything in this folder is from earlier, abandoned attempts at the RAG
retrieval layer, before the app settled on the current design: a local
JSON index (`persisted_inmemory_search.py`) as the primary search, with
Supabase/pgvector (`pgvector_store.py`) as the backup search. Nothing the
running app actually imports lives in here.

Moved here (not deleted) on 2026-09-28 so `vector/` only shows the three
files that matter — `google_drive_service.py`, `persisted_inmemory_search.py`,
`pgvector_store.py` — plus this leftover history for anyone who wants to
dig through it. Some of these files import each other via relative imports
that assumed they still lived directly under `vector/`, so a few of them
won't import cleanly from here without fixing those paths first — that's
fine, since nothing calls them anyway.

Safe to delete this whole folder if the history isn't needed.
