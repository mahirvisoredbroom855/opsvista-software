# backend/app/features/finance/router.py
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse

# --- Auth / Clients ---------------------------------------------------------
# Your project already exposes these:
#   - app.core.auth_deps.get_current_user
#   - app.core.supabase_client.supabase / service_supabase
try:
    from app.core.auth_deps import get_current_user
except Exception as e:
    # Keep import errors readable during early bring-up
    raise RuntimeError(f"finance.router: auth import failed: {e}")

try:
    from app.core.supabase_client import supabase, service_supabase
except Exception as e:
    raise RuntimeError(f"finance.router: supabase client import failed: {e}")

# --- Optional schemas: prefer your existing ones; define minimal fallbacks ---
try:
    from .schemas import (
        FinanceTransactionCreateRequest,
        FinanceTransactionResponse,
        FinanceQueryRequest,
        PaginatedFinanceResponse,
        DashboardMetricsResponse,
        FileProcessingTriggerRequest,
        FileProcessingStatusResponse,
        ManualSyncRequest,
        HealthCheckResponse,
    )
except Exception:
    # Fallback minimal Pydantic models so imports never explode
    from pydantic import BaseModel, Field
    class FinanceTransactionCreateRequest(BaseModel):
        transaction_date: date
        transaction_type: str
        amount_bdt: Optional[float] = None
        amount_usd: Optional[float] = None
        party_name: Optional[str] = None
        vendor_supplier: Optional[str] = None
        description: Optional[str] = None
        transaction_category: Optional[str] = None
        bill_reference: Optional[str] = None

    class FinanceTransactionResponse(BaseModel):
        finance_id: uuid.UUID
        transaction_date: date
        transaction_type: str
        amount_bdt: Optional[float] = None
        amount_usd: Optional[float] = None
        amount_original: Optional[float] = None
        currency_original: Optional[str] = None
        party_name: Optional[str] = None
        vendor_supplier: Optional[str] = None
        bill_reference: Optional[str] = None
        transaction_category: Optional[str] = None
        description: Optional[str] = None
        amount_due: Optional[float] = None
        is_active: bool = True
        created_by: Optional[str] = None
        loaded_at: Optional[datetime] = None
        updated_at: Optional[datetime] = None

    class FinanceQueryRequest(BaseModel):
        start_date: Optional[date] = None
        end_date: Optional[date] = None
        transaction_type: Optional[str] = None
        party_name: Optional[str] = None
        limit: int = 100
        offset: int = 0

    class PaginatedFinanceResponse(BaseModel):
        data: List[FinanceTransactionResponse]
        total_count: int
        page_size: int
        current_offset: int
        has_next: bool
        has_previous: bool

    class DashboardMetricsResponse(BaseModel):
        today_cash_received: float
        today_expenses: float
        today_net_flow: float
        month_cash_received: float
        month_expenses: float
        month_net_flow: float
        prev_month_cash_received: float
        prev_month_expenses: float
        month_cash_growth_percent: float
        month_expense_growth_percent: float
        days_in_month: int
        days_passed: int
        days_remaining: int
        month_progress_percent: float
        year_revenue: float
        year_expenditure: float
        year_profit_loss: float
        total_outstanding_bills: float
        recent_file_count: int
        processing_errors_count: int
        last_sync_time: Optional[datetime] = None

    class FileProcessingTriggerRequest(BaseModel):
        file_name: str
        file_type: Optional[str] = "unknown"
        force_reprocess: bool = False

    class FileProcessingStatusResponse(BaseModel):
        id: Optional[int] = None
        source_file: str
        file_type: str = "unknown"
        status: str = "pending"
        rows_processed: Optional[int] = 0
        rows_successful: Optional[int] = 0
        rows_failed: Optional[int] = 0
        processing_started: Optional[datetime] = None
        processing_completed: Optional[datetime] = None
        created_at: Optional[datetime] = None

    class ManualSyncRequest(BaseModel):
        sync_type: str = Field("full", pattern="^(full|incremental)$")

    class HealthCheckResponse(BaseModel):
        status: str
        database_connection: bool
        google_drive_connection: bool
        services: Dict[str, bool]
        last_sync_time: Optional[datetime] = None
        pending_files: int = 0
        processing_errors: int = 0

# --- Env / feature gating ---------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
FINANCE_ENABLED = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)

router = APIRouter(prefix="/api/v1/finance", tags=["Finance"])

def _require_finance() -> None:
    if not FINANCE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Finance API disabled: set SUPABASE_URL and SUPABASE_SERVICE_KEY."
        )

def _supabase_table(name: str):
    # Prefer service client for writes; user client for reads would also work.
    return service_supabase.table(name)

# ============================================================================
# Health
# ============================================================================
@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    db_ok = False
    pending = 0
    errors = 0
    last_sync: Optional[datetime] = None

    if FINANCE_ENABLED:
        try:
            # cheap “ping”: count exact with limit 1
            _ = _supabase_table("fact_finance").select("finance_id", count="exact").limit(1).execute()
            db_ok = True
        except Exception:
            db_ok = False

        try:
            res = _supabase_table("finance_file_processing").select(
                "status,processing_completed,created_at", count="exact"
            ).order("created_at", desc=True).limit(200).execute()

            rows = res.data or []
            pending = sum(1 for r in rows if (r.get("status") or "").lower() == "pending")
            errors = sum(1 for r in rows if (r.get("status") or "").lower() == "failed")
            # find the last completed timestamp
            comp = [r.get("processing_completed") for r in rows if (r.get("status") or "").lower() == "completed"]
            if comp:
                # supabase returns iso strings
                last_sync = datetime.fromisoformat(comp[0].replace("Z", "+00:00"))
        except Exception:
            pass

    return HealthCheckResponse(
        status="healthy" if db_ok else "unhealthy",
        database_connection=db_ok,
        google_drive_connection=True,  # you can wire a real check later
        services={"database": db_ok, "google_drive": True, "background_tasks": True},
        last_sync_time=last_sync,
        pending_files=pending,
        processing_errors=errors,
    )

# ============================================================================
# Transactions (Supabase)
# ============================================================================
@router.post("/transactions", response_model=FinanceTransactionResponse)
async def create_transaction(
    request: FinanceTransactionCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_finance()
    try:
        payload = {
            "transaction_date": request.transaction_date.isoformat(),
            "transaction_type": request.transaction_type,
            "amount_bdt": request.amount_bdt,
            "amount_usd": request.amount_usd,
            "amount_original": request.amount_bdt or request.amount_usd,
            "currency_original": "BDT" if request.amount_bdt else ("USD" if request.amount_usd else None),
            "party_name": request.party_name,
            "vendor_supplier": request.vendor_supplier,
            "description": request.description,
            "transaction_category": request.transaction_category,
            "bill_reference": request.bill_reference,
            "created_by": current_user.get("email") or "system",
            "is_active": True,
        }
        res = _supabase_table("fact_finance").insert(payload).execute()
        if not res.data:
            raise RuntimeError("Insert returned no data")
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create: {e}")

@router.get("/transactions", response_model=PaginatedFinanceResponse)
async def get_transactions(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    transaction_type: Optional[str] = Query(None),
    party_name: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    _require_finance()
    try:
        q = _supabase_table("fact_finance").select("*", count="exact").eq("is_active", True)

        if start_date:
            q = q.gte("transaction_date", start_date.isoformat())
        if end_date:
            q = q.lte("transaction_date", end_date.isoformat())
        if transaction_type:
            q = q.eq("transaction_type", transaction_type)
        if party_name:
            # ILIKE available via PostgREST filter
            q = q.ilike("party_name", f"%{party_name}%")

        q = q.order("transaction_date", desc=True).range(offset, offset + limit - 1)
        res = q.execute()
        data = res.data or []
        total = res.count or 0

        return {
            "data": data,
            "total_count": total,
            "page_size": limit,
            "current_offset": offset,
            "has_next": (offset + limit) < total,
            "has_previous": offset > 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch: {e}")

@router.get("/transactions/{transaction_id}", response_model=FinanceTransactionResponse)
async def get_transaction(transaction_id: uuid.UUID):
    _require_finance()
    try:
        res = _supabase_table("fact_finance").select("*").eq("finance_id", str(transaction_id)).limit(1).execute()
        rows = (res.data or [])
        if not rows:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return rows[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch: {e}")

@router.put("/transactions/{transaction_id}", response_model=FinanceTransactionResponse)
async def update_transaction(
    transaction_id: uuid.UUID,
    request: FinanceTransactionCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_finance()
    try:
        payload = {
            "transaction_date": request.transaction_date.isoformat(),
            "transaction_type": request.transaction_type,
            "amount_bdt": request.amount_bdt,
            "amount_usd": request.amount_usd,
            "party_name": request.party_name,
            "vendor_supplier": request.vendor_supplier,
            "description": request.description,
            "transaction_category": request.transaction_category,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        res = _supabase_table("fact_finance").update(payload).eq("finance_id", str(transaction_id)).execute()
        rows = res.data or []
        if not rows:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return rows[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update: {e}")

@router.delete("/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: uuid.UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_finance()
    try:
        res = _supabase_table("fact_finance").update({"is_active": False}).eq("finance_id", str(transaction_id)).execute()
        if not (res.data or []):
            raise HTTPException(status_code=404, detail="Transaction not found")
        return {"message": "Transaction deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete: {e}")

# ============================================================================
# Dashboard / metrics (Supabase aggregation)
# ============================================================================
@router.get("/dashboard/metrics", response_model=DashboardMetricsResponse)
async def dashboard_metrics():
    _require_finance()
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    def _sum_between(kind: str, start: date, end: date) -> float:
        q = (
            _supabase_table("fact_finance")
            .select("amount_bdt", count="exact")
            .eq("is_active", True)
            .eq("transaction_type", kind)
            .gte("transaction_date", start.isoformat())
            .lte("transaction_date", end.isoformat())
        )
        res = q.execute()
        vals = [row.get("amount_bdt") or 0 for row in (res.data or [])]
        return float(sum(vals))

    def _sum_today(kind: str) -> float:
        return _sum_between(kind, today, today)

    def _sum_outstanding_due() -> float:
        res = (
            _supabase_table("fact_finance")
            .select("amount_due", count="exact")
            .eq("is_active", True)
            .eq("transaction_type", "due_bill")
            .gt("amount_due", 0)
            .execute()
        )
        vals = [row.get("amount_due") or 0 for row in (res.data or [])]
        return float(sum(vals))

    # today
    today_cash = _sum_today("cash_receipt")
    today_exp = _sum_today("expense")

    # month
    month_cash = _sum_between("cash_receipt", month_start, today)
    month_exp = _sum_between("expense", month_start, today)

    # prev month window
    if today.month == 1:
        prev_start = date(today.year - 1, 12, 1)
        prev_end = date(today.year - 1, 12, 31)
    else:
        prev_start = date(today.year, today.month - 1, 1)
        prev_end = month_start - timedelta(days=1)

    prev_cash = _sum_between("cash_receipt", prev_start, prev_end)
    prev_exp = _sum_between("expense", prev_start, prev_end)

    # year
    year_rev = _sum_between("cash_receipt", year_start, today)
    year_exp = _sum_between("expense", year_start, today)

    # month progress
    import calendar
    dim = calendar.monthrange(today.year, today.month)[1]
    passed = today.day
    remaining = dim - passed

    cash_growth = ((month_cash - prev_cash) / prev_cash * 100.0) if prev_cash > 0 else 0.0
    exp_growth = ((month_exp - prev_exp) / prev_exp * 100.0) if prev_exp > 0 else 0.0

    # operational signals (best-effort)
    recent_files = 0
    errors = 0
    try:
        seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
        res = (
            _supabase_table("finance_file_processing")
            .select("status,created_at", count="exact")
            .gte("created_at", seven_days_ago)
            .execute()
        )
        rows = res.data or []
        recent_files = len(rows)
        errors = sum(1 for r in rows if (r.get("status") or "").lower() == "failed")
    except Exception:
        pass

    return DashboardMetricsResponse(
        today_cash_received=float(today_cash),
        today_expenses=float(today_exp),
        today_net_flow=float(today_cash - today_exp),
        month_cash_received=float(month_cash),
        month_expenses=float(month_exp),
        month_net_flow=float(month_cash - month_exp),
        prev_month_cash_received=float(prev_cash),
        prev_month_expenses=float(prev_exp),
        month_cash_growth_percent=float(cash_growth),
        month_expense_growth_percent=float(exp_growth),
        days_in_month=dim,
        days_passed=passed,
        days_remaining=remaining,
        month_progress_percent=float(passed / dim * 100.0),
        year_revenue=float(year_rev),
        year_expenditure=float(year_exp),
        year_profit_loss=float(year_rev - year_exp),
        total_outstanding_bills=_sum_outstanding_due(),
        recent_file_count=recent_files,
        processing_errors_count=errors,
        last_sync_time=datetime.utcnow(),
    )

# ============================================================================
# File processing stubs (wire your background worker later)
# ============================================================================
@router.post("/files/process", response_model=FileProcessingStatusResponse)
async def trigger_file_processing(
    request: FileProcessingTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_finance()
    # stub record; you can insert into finance_file_processing table
    try:
        row = {
            "source_file": request.file_name,
            "file_type": request.file_type or "unknown",
            "status": "pending" if not request.force_reprocess else "reprocess",
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        res = _supabase_table("finance_file_processing").insert(row).execute()
        return (res.data or [row])[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger processing: {e}")

@router.get("/files/processing", response_model=List[FileProcessingStatusResponse])
async def get_file_processing_status(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    _require_finance()
    try:
        q = _supabase_table("finance_file_processing").select("*").order("created_at", desc=True).limit(limit)
        if status:
            q = q.eq("status", status)
        res = q.execute()
        return res.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch status: {e}")

@router.post("/sync/manual")
async def trigger_manual_sync(
    request: ManualSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _require_finance()
    # Hook your real sync job here
    return {
        "message": f"Manual {request.sync_type} sync requested",
        "sync_type": request.sync_type,
        "triggered_at": datetime.utcnow().isoformat() + "Z",
        "triggered_by": current_user.get("email") or "system",
    }

# NOTE:
# - No @router.exception_handler usage here (that belongs on FastAPI app, not a router).
# - If you later add SQLAlchemy, you can branch on DATABASE_URL and use ORM instead.
