
# Finance Feature API Router
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from typing import List, Optional
from datetime import date, datetime, timedelta
import uuid

# Import our schemas and models
from .schemas import (
    FinanceTransactionCreateRequest, FinanceTransactionResponse,
    FileProcessingTriggerRequest, FileProcessingStatusResponse,
    FinanceQueryRequest, PaginatedFinanceResponse,
    DashboardMetricsResponse, HealthCheckResponse,
    ErrorResponse, ManualSyncRequest
)
from .models import FactFinance, RawDriveFinance, FinanceSummary, FinanceFileProcessing

# Import core dependencies (you'll need to adjust these imports based on your core structure)
from app.core.supabase_client import get_supabase_session  # Adjust import path
from app.core.auth_deps import get_current_user  # Adjust import path

# Create router
router = APIRouter(prefix="/api/v1/finance", tags=["Finance"])

# Dependency to get database session
def get_db():
    """Get database session - adjust this based on your setup"""
    # This is a placeholder - adjust based on your actual database setup
    session = get_supabase_session()
    try:
        yield session
    finally:
        session.close()

# =====================================
# Health Check & Status Endpoints
# =====================================

@router.get("/health", response_model=HealthCheckResponse)
async def health_check(db: Session = Depends(get_db)):
    """Check system health and status"""
    try:
        # Test database connection
        db.execute("SELECT 1")
        db_connected = True
    except Exception:
        db_connected = False
    
    # Check recent processing activity
    try:
        pending_count = db.query(FinanceFileProcessing).filter(
            FinanceFileProcessing.status == 'pending'
        ).count()
        
        error_count = db.query(FinanceFileProcessing).filter(
            FinanceFileProcessing.status == 'failed'
        ).count()
        
        last_sync = db.query(FinanceFileProcessing.processing_completed).filter(
            FinanceFileProcessing.status == 'completed'
        ).order_by(desc(FinanceFileProcessing.processing_completed)).first()
        
    except Exception:
        pending_count = 0
        error_count = 0
        last_sync = None
    
    return HealthCheckResponse(
        status="healthy" if db_connected else "unhealthy",
        database_connection=db_connected,
        google_drive_connection=True,  # TODO: Actually test Google Drive
        services={
            "database": db_connected,
            "google_drive": True,
            "background_tasks": True
        },
        last_sync_time=last_sync[0] if last_sync else None,
        pending_files=pending_count,
        processing_errors=error_count
    )

# =====================================
# Transaction CRUD Endpoints
# =====================================

@router.post("/transactions", response_model=FinanceTransactionResponse)
async def create_transaction(
    request: FinanceTransactionCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)  # Require authentication
):
    """Create new finance transaction"""
    try:
        # Create new transaction record
        db_transaction = FactFinance(
            transaction_date=request.transaction_date,
            transaction_type=request.transaction_type,
            amount_bdt=request.amount_bdt,
            amount_usd=request.amount_usd,
            amount_original=request.amount_bdt or request.amount_usd,
            currency_original='BDT' if request.amount_bdt else 'USD',
            party_name=request.party_name,
            vendor_supplier=request.vendor_supplier,
            description=request.description,
            transaction_category=request.transaction_category,
            bill_reference=request.bill_reference,
            created_by=current_user.get('email', 'system') if current_user else 'system'
        )
        
        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        
        return db_transaction
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")

@router.get("/transactions", response_model=PaginatedFinanceResponse)
async def get_transactions(
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date"),
    transaction_type: Optional[str] = Query(None, description="Filter by type"),
    party_name: Optional[str] = Query(None, description="Filter by party"),
    limit: int = Query(100, ge=1, le=1000, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results to skip"),
    db: Session = Depends(get_db)
):
    """Get finance transactions with filtering and pagination"""
    try:
        # Build query with filters
        query = db.query(FactFinance).filter(FactFinance.is_active == True)
        
        if start_date:
            query = query.filter(FactFinance.transaction_date >= start_date)
        
        if end_date:
            query = query.filter(FactFinance.transaction_date <= end_date)
        
        if transaction_type:
            query = query.filter(FactFinance.transaction_type == transaction_type)
        
        if party_name:
            query = query.filter(FactFinance.party_name.ilike(f"%{party_name}%"))
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        transactions = query.order_by(desc(FactFinance.transaction_date)).offset(offset).limit(limit).all()
        
        return PaginatedFinanceResponse(
            data=transactions,
            total_count=total_count,
            page_size=limit,
            current_offset=offset,
            has_next=offset + limit < total_count,
            has_previous=offset > 0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch transactions: {str(e)}")

@router.get("/transactions/{transaction_id}", response_model=FinanceTransactionResponse)
async def get_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get specific transaction by ID"""
    transaction = db.query(FactFinance).filter(
        FactFinance.finance_id == transaction_id,
        FactFinance.is_active == True
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return transaction

@router.put("/transactions/{transaction_id}", response_model=FinanceTransactionResponse)
async def update_transaction(
    transaction_id: uuid.UUID,
    request: FinanceTransactionCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update existing transaction"""
    try:
        transaction = db.query(FactFinance).filter(
            FactFinance.finance_id == transaction_id,
            FactFinance.is_active == True
        ).first()
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        # Update fields
        transaction.transaction_date = request.transaction_date
        transaction.transaction_type = request.transaction_type
        transaction.amount_bdt = request.amount_bdt
        transaction.amount_usd = request.amount_usd
        transaction.party_name = request.party_name
        transaction.description = request.description
        transaction.transaction_category = request.transaction_category
        # updated_at will be set automatically by trigger
        
        db.commit()
        db.refresh(transaction)
        
        return transaction
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update transaction: {str(e)}")

@router.delete("/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Soft delete transaction (set is_active = False)"""
    try:
        transaction = db.query(FactFinance).filter(
            FactFinance.finance_id == transaction_id,
            FactFinance.is_active == True
        ).first()
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        # Soft delete
        transaction.is_active = False
        db.commit()
        
        return {"message": "Transaction deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete transaction: {str(e)}")

# =====================================
# Dashboard & Analytics Endpoints
# =====================================

@router.get("/dashboard/metrics", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Get key dashboard metrics"""
    try:
        today = date.today()
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)
        
        # Today's metrics
        today_cash = db.query(func.coalesce(func.sum(FactFinance.amount_bdt), 0)).filter(
            FactFinance.transaction_date == today,
            FactFinance.transaction_type == 'cash_receipt'
        ).scalar() or 0
        
        today_expenses = db.query(func.coalesce(func.sum(FactFinance.amount_bdt), 0)).filter(
            FactFinance.transaction_date == today,
            FactFinance.transaction_type == 'expense'
        ).scalar() or 0
        
        # Month metrics
        month_cash = db.query(func.coalesce(func.sum(FactFinance.amount_bdt), 0)).filter(
            FactFinance.transaction_date >= month_start,
            FactFinance.transaction_type == 'cash_receipt'
        ).scalar() or 0
        
        month_expenses = db.query(func.coalesce(func.sum(FactFinance.amount_bdt), 0)).filter(
            FactFinance.transaction_date >= month_start,
            FactFinance.transaction_type == 'expense'
        ).scalar() or 0
        
        # Year metrics
        year_revenue = db.query(func.coalesce(func.sum(FactFinance.amount_bdt), 0)).filter(
            FactFinance.transaction_date >= year_start,
            FactFinance.transaction_type.in_(['cash_receipt'])
        ).scalar() or 0
        
        year_expenditure = db.query(func.coalesce(func.sum(FactFinance.amount_bdt), 0)).filter(
            FactFinance.transaction_date >= year_start,
            FactFinance.transaction_type.in_(['expense'])
        ).scalar() or 0
        
        # Outstanding bills
        outstanding_bills = db.query(func.coalesce(func.sum(FactFinance.amount_due), 0)).filter(
            FactFinance.transaction_type == 'due_bill',
            FactFinance.amount_due > 0
        ).scalar() or 0
        
        # File processing stats
        recent_files = db.query(FinanceFileProcessing).filter(
            FactFinance.created_at >= datetime.now() - timedelta(days=7)
        ).count()
        
        processing_errors = db.query(FinanceFileProcessing).filter(
            FinanceFileProcessing.status == 'failed'
        ).count()
        
        return DashboardMetricsResponse(
            today_cash_received=float(today_cash),
            today_expenses=float(today_expenses),
            today_net_flow=float(today_cash - today_expenses),
            month_cash_received=float(month_cash),
            month_expenses=float(month_expenses),
            month_net_flow=float(month_cash - month_expenses),
            year_revenue=float(year_revenue),
            year_expenditure=float(year_expenditure),
            year_profit_loss=float(year_revenue - year_expenditure),
            total_outstanding_bills=float(outstanding_bills),
            recent_file_count=recent_files,
            processing_errors_count=processing_errors,
            last_sync_time=datetime.now()  # TODO: Get actual last sync time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard metrics: {str(e)}")

# =====================================
# File Processing Endpoints
# =====================================

@router.post("/files/process", response_model=FileProcessingStatusResponse)
async def trigger_file_processing(
    request: FileProcessingTriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Trigger processing of specific Excel file"""
    try:
        # Check if file already processed (unless force_reprocess)
        if not request.force_reprocess:
            existing = db.query(FinanceFileProcessing).filter(
                FinanceFileProcessing.source_file == request.file_name,
                FinanceFileProcessing.status == 'completed'
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=409, 
                    detail=f"File {request.file_name} already processed. Use force_reprocess=true to reprocess."
                )
        
        # Create processing record
        processing_record = FinanceFileProcessing(
            source_file=request.file_name,
            file_type=request.file_type or 'unknown',
            status='pending'
        )
        
        db.add(processing_record)
        db.commit()
        db.refresh(processing_record)
        
        # Add to background processing queue
        # background_tasks.add_task(process_excel_file, request.file_name, processing_record.id)
        
        return processing_record
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to trigger file processing: {str(e)}")

@router.get("/files/processing", response_model=List[FileProcessingStatusResponse])
async def get_file_processing_status(
    status: Optional[str] = Query(None, description="Filter by processing status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get file processing status"""
    try:
        query = db.query(FinanceFileProcessing)
        
        if status:
            query = query.filter(FinanceFileProcessing.status == status)
        
        processing_records = query.order_by(desc(FinanceFileProcessing.created_at)).limit(limit).all()
        
        return processing_records
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch processing status: {str(e)}")

@router.post("/sync/manual")
async def trigger_manual_sync(
    request: ManualSyncRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Trigger manual Google Drive sync"""
    try:
        # TODO: Implement actual Google Drive sync logic
        # background_tasks.add_task(sync_google_drive, request.sync_type)
        
        return {
            "message": f"Manual {request.sync_type} sync triggered successfully",
            "sync_type": request.sync_type,
            "triggered_at": datetime.now().isoformat(),
            "triggered_by": current_user.get('email', 'system') if current_user else 'system'
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger sync: {str(e)}")

# =====================================
# Error Handler
# =====================================

@router.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler for finance routes"""
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_server_error",
            message="An unexpected error occurred",
            details={"exception": str(exc)}
        ).dict()
    )
