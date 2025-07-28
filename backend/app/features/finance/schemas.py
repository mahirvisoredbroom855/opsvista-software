
# Finance Feature Pydantic Schemas - API Layer
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import date, datetime
from decimal import Decimal
import uuid

# =====================================
# Request Schemas (API Input)
# =====================================

class FinanceTransactionCreateRequest(BaseModel):
    """Create new finance transaction"""
    transaction_date: date = Field(description="Transaction date")
    transaction_type: str = Field(description="Type: cash_receipt, expense, due_bill, yearly_summary")
    amount_bdt: Optional[float] = Field(None, gt=0, description="Amount in BDT")
    amount_usd: Optional[float] = Field(None, gt=0, description="Amount in USD")
    party_name: Optional[str] = Field(None, min_length=1, max_length=200)
    vendor_supplier: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    transaction_category: Optional[str] = Field(None, description="Business category")
    bill_reference: Optional[str] = Field(None, max_length=100)
    
    @validator('transaction_type')
    def validate_transaction_type(cls, v):
        allowed_types = ['cash_receipt', 'expense', 'due_bill', 'yearly_summary']
        if v not in allowed_types:
            raise ValueError(f'transaction_type must be one of: {allowed_types}')
        return v

class FileProcessingTriggerRequest(BaseModel):
    """Trigger processing of specific Excel file"""
    file_name: str = Field(description="Name of Excel file in Google Drive")
    force_reprocess: bool = Field(False, description="Reprocess even if already done")
    file_type: Optional[str] = Field(None, description="cash_book, party_due_bill, expenditure_summary")

class FinanceQueryRequest(BaseModel):
    """Query finance transactions with filters"""
    start_date: Optional[date] = Field(None, description="Filter from this date")
    end_date: Optional[date] = Field(None, description="Filter to this date")
    transaction_type: Optional[str] = Field(None, description="Filter by transaction type")
    transaction_category: Optional[str] = Field(None, description="Filter by category")
    party_name: Optional[str] = Field(None, description="Filter by party name")
    min_amount: Optional[float] = Field(None, ge=0, description="Minimum amount filter")
    max_amount: Optional[float] = Field(None, ge=0, description="Maximum amount filter")
    currency: Optional[str] = Field('BDT', description="Filter by currency")
    limit: int = Field(100, ge=1, le=1000, description="Number of records")
    offset: int = Field(0, ge=0, description="Records to skip for pagination")

class ManualSyncRequest(BaseModel):
    """Trigger manual Google Drive sync"""  
    sync_type: str = Field('incremental', description="incremental or full")
    
    @validator('sync_type')
    def validate_sync_type(cls, v):
        if v not in ['incremental', 'full']:
            raise ValueError('sync_type must be incremental or full')
        return v

# =====================================
# Response Schemas (API Output)
# =====================================

class FinanceTransactionResponse(BaseModel):
    """Individual finance transaction data"""
    finance_id: uuid.UUID
    transaction_date: date
    transaction_type: str
    amount_bdt: Optional[float]
    amount_usd: Optional[float]
    amount_original: Optional[float]
    currency_original: str
    party_name: Optional[str]
    vendor_supplier: Optional[str]
    description: Optional[str]
    transaction_category: Optional[str]
    bill_reference: Optional[str]
    data_quality_score: Optional[float]
    loaded_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v),
            Decimal: lambda v: float(v) if v else None
        }

class RawFinanceDataResponse(BaseModel):
    """Raw Excel data response"""
    id: int
    ingestion_time: datetime
    source_file: str
    sheet_name: str
    row_number: int
    transaction_date: Optional[date]
    processing_status: str
    error_message: Optional[str]
    retry_count: int
    
    # Dynamic fields based on file type
    cash_received: Optional[float]
    particulars: Optional[str]
    party_name: Optional[str]
    amount: Optional[float]
    
    class Config:
        from_attributes = True
        json_encoders = {
            date: lambda v: v.isoformat() if v else None,
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v) if v else None
        }

class FileProcessingStatusResponse(BaseModel):
    """File processing status"""
    id: int
    source_file: str
    file_type: str
    sheet_name: Optional[str]
    status: str
    rows_processed: int
    rows_successful: int
    rows_failed: int
    processing_started: Optional[datetime]
    processing_completed: Optional[datetime]
    error_details: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class FinanceSummaryResponse(BaseModel):
    """Finance summary/dashboard data"""
    id: int
    summary_type: str
    period_start: date
    period_end: date
    total_cash_received: float
    total_expenses: float
    net_cash_flow: float
    total_bills_due: float
    total_advances_paid: float
    amounts_bdt: float
    amounts_usd: float
    total_revenue: float
    total_expenditure: float
    profit_loss: float
    
    class Config:
        from_attributes = True
        json_encoders = {
            date: lambda v: v.isoformat(),
            Decimal: lambda v: float(v) if v else 0.0
        }

class PaginatedFinanceResponse(BaseModel):
    """Paginated finance transaction results"""
    data: List[FinanceTransactionResponse]
    total_count: int
    page_size: int
    current_offset: int
    has_next: bool
    has_previous: bool

class PaginatedRawDataResponse(BaseModel):
    """Paginated raw data results"""
    data: List[RawFinanceDataResponse]
    total_count: int
    page_size: int
    current_offset: int
    has_next: bool
    has_previous: bool

# =====================================
# Dashboard/Analytics Schemas
# =====================================

class DashboardMetricsResponse(BaseModel):
    """Key dashboard metrics"""
    today_cash_received: float
    today_expenses: float
    today_net_flow: float
    month_cash_received: float
    month_expenses: float
    month_net_flow: float
    year_revenue: float
    year_expenditure: float
    year_profit_loss: float
    total_outstanding_bills: float
    recent_file_count: int
    processing_errors_count: int
    last_sync_time: Optional[datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class MonthlyTrendResponse(BaseModel):
    """Monthly financial trends"""
    month: date
    cash_received: float
    expenses: float
    net_flow: float
    transaction_count: int

class CategoryBreakdownResponse(BaseModel):
    """Spending by category"""
    category: str
    total_amount: float
    transaction_count: int
    percentage: float

# =====================================
# Error Response Schemas
# =====================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(description="Error type")
    message: str = Field(description="Human-readable message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ValidationErrorResponse(BaseModel):
    """Request validation error response"""
    error: str = "validation_error"
    message: str = "Request validation failed"
    validation_errors: List[Dict[str, Any]]

# =====================================
# System Health Schemas
# =====================================

class HealthCheckResponse(BaseModel):
    """System health status"""
    status: str = Field(description="overall, database, google_drive")
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str = "1.0.0"
    services: Dict[str, bool] = Field(description="Service status")
    database_connection: bool
    google_drive_connection: bool
    last_sync_time: Optional[datetime]
    pending_files: int = 0
    processing_errors: int = 0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class GoogleDriveStatusResponse(BaseModel):
    """Google Drive API status"""
    connected: bool
    last_check: datetime
    files_found: int
    quota_usage: Optional[Dict[str, Any]]
    error_message: Optional[str]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
