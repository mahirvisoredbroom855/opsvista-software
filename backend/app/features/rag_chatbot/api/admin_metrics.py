# backend/app/features/rag_chatbot/api/admin_metrics.py
"""
Observability/metrics API backing the logging dashboard. Reads from the
fact_query / bridge_query_citation / dim_document / fact_chunk tables
written by pgvector_store.py's dual-write + audit-logging paths.

Aggregation happens in Python rather than SQL (GROUP BY via Postgres
functions) — at this corpus/traffic scale that's simpler and just as fast;
same reasoning as skipping the ivfflat ANN index until the data actually
warrants it. Revisit with SQL-side aggregation if query volume grows large
enough that pulling raw rows becomes slow.

Auth: gated behind require_roles(["Owner", "Admin"]) — a plain authenticated
user without one of those two roles in their Supabase app_metadata gets a
403, not just a login prompt. Grant a role via
supabase.auth.admin.update_user_by_id(user_id, {"app_metadata": {"role": "Owner"}}).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth_deps import require_roles
from app.core.rate_limit import limiter

# ═══════════════════════════════════════════════════════════════════════
# MODULE: [OPS:ADMIN-002] — dashboard metrics API
#
# One endpoint (GET /metrics) that reads the audit-trail tables
# [OPS:PVEC-005] log_query() writes on every chat request, and aggregates
# them in Python (not SQL GROUP BY) into the shape the dashboard's
# charts/tables expect. Auth: [OPS:AUTH-004] require_roles — strict
# session required, no automation-token escape hatch (contrast with
# [OPS:ADMIN-001]'s reindex endpoint, which needs headless CI access).
# ═══════════════════════════════════════════════════════════════════════
_require_admin = require_roles(["Owner", "Admin"])

router = APIRouter(prefix="/api/rag/admin", tags=["Admin Metrics"])


def _service_client():
    from ..vector.pgvector_store import get_service_client

    return get_service_client()


# [OPS:ADMIN-002b] _percentile() — nearest-rank percentile (not
# interpolated), used for p95 latency. Fine for a dashboard metric where
# exact interpolation precision doesn't matter.
def _percentile(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, int(round(pct * (len(values) - 1))))
    return values[idx]


# ─────────────────────────────────────────────────────────────────────────
# [OPS:ADMIN-002a] GET /metrics — dashboard aggregation endpoint
#
# API/CALL: Supabase REST reads only (fact_query, bridge_query_citation,
#       dim_document, fact_chunk) — no LLM/embedding calls, this is
#       pure post-hoc analytics over what [OPS:PVEC-005] log_query()
#       already wrote.
# WHAT IT COMPUTES: summary (avg/p95 latency via [OPS:ADMIN-002b]
#       _percentile(), fallback rate, avg confidence, token totals),
#       a daily timeseries, top-cited documents/departments (by joining
#       bridge_query_citation → dim_document within the window), a
#       recent-queries log table (capped at 50 rows), and index
#       freshness (total docs/chunks + most recent ingestion time).
# WHY PYTHON AGGREGATION, NOT SQL: at current query volume (low
#       thousands/week) pulling up to 5000 raw rows and reducing them in
#       Python is simpler to reason about and just as fast as writing
#       Postgres-side GROUP BY functions — same "don't build for scale
#       you don't have yet" reasoning as skipping the ivfflat ANN index.
#       Revisit if query volume grows large enough that a 5000-row pull
#       becomes the bottleneck.
# NUANCE: citations_resp.in_("query_id", query_ids[:1000]) hard-caps at
#       1000 IDs — a PostgREST practical limit on IN-clause list size;
#       harmless today since this endpoint is capped at 90 days/window
#       and typical volume stays well under that.
# CALLED BY (frontend): dashboard/page.tsx [OPS:FE-DASH].
# RATE LIMIT: 60/minute.
# ─────────────────────────────────────────────────────────────────────────
@router.get("/metrics")
@limiter.limit("60/minute")
def get_metrics(
    request: Request,
    days: int = Query(7, ge=1, le=90),
    _user: Dict[str, Any] = Depends(_require_admin),
) -> Dict[str, Any]:
    client = _service_client()
    if client is None:
        return {"configured": False, "message": "Supabase not configured"}

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    queries_resp = (
        client.table("fact_query")
        .select("*")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(5000)
        .execute()
    )
    queries = queries_resp.data or []

    # --- Summary ---
    latencies = [q["processing_time_ms"] for q in queries if q.get("processing_time_ms") is not None]
    confidences = [float(q["retrieval_confidence"]) for q in queries if q.get("retrieval_confidence") is not None]
    total_tokens_list = [q["total_tokens"] for q in queries if q.get("total_tokens") is not None]
    fallback_count = sum(1 for q in queries if q.get("used_fallback"))

    summary = {
        "total_queries": len(queries),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "p95_latency_ms": _percentile(latencies, 0.95),
        "fallback_rate": round(fallback_count / len(queries), 4) if queries else 0.0,
        "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        "total_tokens": sum(total_tokens_list) if total_tokens_list else 0,
        "total_prompt_tokens": sum(q.get("prompt_tokens") or 0 for q in queries),
        "total_completion_tokens": sum(q.get("completion_tokens") or 0 for q in queries),
    }

    # --- Daily time series ---
    by_day: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"queries": 0, "fallback": 0, "tokens": 0, "latency_sum": 0, "latency_n": 0})
    for q in queries:
        day = q["created_at"][:10]
        bucket = by_day[day]
        bucket["queries"] += 1
        if q.get("used_fallback"):
            bucket["fallback"] += 1
        bucket["tokens"] += q.get("total_tokens") or 0
        if q.get("processing_time_ms") is not None:
            bucket["latency_sum"] += q["processing_time_ms"]
            bucket["latency_n"] += 1

    timeseries = []
    for day in sorted(by_day.keys()):
        b = by_day[day]
        timeseries.append(
            {
                "date": day,
                "queries": b["queries"],
                "fallback_count": b["fallback"],
                "tokens": b["tokens"],
                "avg_latency_ms": round(b["latency_sum"] / b["latency_n"], 1) if b["latency_n"] else None,
            }
        )

    # --- Top documents / departments (via citations in this window) ---
    query_ids = [q["query_id"] for q in queries]
    top_documents: List[Dict[str, Any]] = []
    top_departments: List[Dict[str, Any]] = []
    if query_ids:
        # PostgREST .in_() has practical limits on very large lists; fine at this scale.
        citations_resp = (
            client.table("bridge_query_citation")
            .select("document_id")
            .in_("query_id", query_ids[:1000])
            .execute()
        )
        citation_rows = citations_resp.data or []
        doc_counts: Dict[str, int] = defaultdict(int)
        for row in citation_rows:
            if row.get("document_id"):
                doc_counts[row["document_id"]] += 1

        if doc_counts:
            docs_resp = (
                client.table("dim_document")
                .select("document_id,title,department")
                .in_("document_id", list(doc_counts.keys()))
                .execute()
            )
            doc_lookup = {d["document_id"]: d for d in (docs_resp.data or [])}

            dept_counts: Dict[str, int] = defaultdict(int)
            for doc_id, count in doc_counts.items():
                doc = doc_lookup.get(doc_id, {})
                dept_counts[doc.get("department") or "Unknown"] += count

            top_documents = sorted(
                (
                    {"title": doc_lookup.get(doc_id, {}).get("title", "Unknown"), "department": doc_lookup.get(doc_id, {}).get("department"), "citations": count}
                    for doc_id, count in doc_counts.items()
                ),
                key=lambda d: d["citations"],
                reverse=True,
            )[:10]

            top_departments = sorted(
                ({"department": dept, "citations": count} for dept, count in dept_counts.items()),
                key=lambda d: d["citations"],
                reverse=True,
            )

    # --- Recent queries (for the log table) ---
    recent_queries = [
        {
            "query_id": q["query_id"],
            "query_text": q["query_text"],
            "created_at": q["created_at"],
            "processing_time_ms": q.get("processing_time_ms"),
            "used_fallback": q.get("used_fallback", False),
            "retrieval_confidence": q.get("retrieval_confidence"),
            "total_tokens": q.get("total_tokens"),
            "user_id": q.get("user_id"),
        }
        for q in queries[:50]
    ]

    # --- Index freshness ---
    docs_count_resp = client.table("dim_document").select("document_id", count="exact").limit(1).execute()
    chunks_count_resp = client.table("fact_chunk").select("chunk_id", count="exact").limit(1).execute()
    last_doc_resp = client.table("dim_document").select("discovered_at").order("discovered_at", desc=True).limit(1).execute()

    index_freshness = {
        "total_documents": docs_count_resp.count,
        "total_chunks": chunks_count_resp.count,
        "last_ingested_at": last_doc_resp.data[0]["discovered_at"] if last_doc_resp.data else None,
    }

    return {
        "configured": True,
        "window_days": days,
        "summary": summary,
        "timeseries": timeseries,
        "top_documents": top_documents,
        "top_departments": top_departments,
        "recent_queries": recent_queries,
        "index_freshness": index_freshness,
    }
