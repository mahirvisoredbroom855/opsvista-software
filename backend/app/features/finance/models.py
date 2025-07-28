# Create SQLAlchemy models for our finance tables

# Finance Feature Database Models
from sqlalchemy import Column, Integer, BigInteger, String, Date, DateTime, Numeric, Text, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class RawDriveFinance(Base):
    """Raw Excel data landing table - stores ALL file formats"""
    __tablename__ = "raw_drive_finance"
    
    # Primary key and system fields
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source_file = Column(Text, nullable=False)
    sheet_name = Column(Text, nullable=False)
    row_number = Column(Integer, nullable=False)
    
    # Common date fields
    transaction_date = Column(Date)
    date_string = Column(Text)  # Original date as text for parsing issues
    
    # Cash Book specific fields
    cash_received = Column(Numeric(15, 2))
    factory_amount = Column(Numeric(15, 2))
    factory_cr = Column(Numeric(15, 2))
    head_off = Column(Numeric(15, 2))
    particulars = Column(Text)
    
    # Party Due Bill specific fields
    sl_number = Column(Integer)
    description = Column(Text)
    party_name = Column(Text)
    bill_number = Column(Text)
    quantity = Column(Numeric(10, 2))
    unit_price = Column(Numeric(15, 2))
    total_amount = Column(Numeric(15, 2))
    advance_tk = Column(Numeric(15, 2))
    due_bill = Column(Numeric(15, 2))
    
    # Multi-year summary fields
    year_period = Column(Text)
    expenditure = Column(Numeric(20, 2))
    expenditure_fixed_cost = Column(Numeric(20, 2))
    ptil_total_tk = Column(Numeric(20, 2))
    lc_usd = Column(Numeric(15, 2))
    bill_usd = Column(Numeric(15, 2))
    due_usd = Column(Numeric(15, 2))
    total_usd = Column(Numeric(15, 2))
    bd_tk = Column(Numeric(20, 2))
    loss_amount = Column(Numeric(20, 2))
    profit_amount = Column(Numeric(20, 2))
    
    # Generic fields
    amount = Column(Numeric(15, 2))
    currency = Column(Text, default='BDT')
    category = Column(Text)
    vendor_supplier = Column(Text)
    description_notes = Column(Text)
    reference_number = Column(Text)
    
    # System fields
    raw_data = Column(JSONB)  # Store complete original row
    file_hash = Column(Text)
    processing_status = Column(Text, default='pending')
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class FactFinance(Base):
    """Processed, normalized finance data for dashboards"""
    __tablename__ = "fact_finance"
    
    # Primary key
    finance_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Core transaction data
    transaction_date = Column(Date, nullable=False)
    transaction_type = Column(Text, nullable=False)  # 'cash_receipt', 'expense', 'due_bill', 'yearly_summary'
    
    # Financial amounts (normalized to BDT)
    amount_bdt = Column(Numeric(20, 2))
    amount_usd = Column(Numeric(15, 2))
    amount_original = Column(Numeric(20, 2))
    currency_original = Column(Text, default='BDT')
    
    # Business entities
    party_name = Column(Text)
    vendor_supplier = Column(Text)
    bill_reference = Column(Text)
    
    # Categorization
    transaction_category = Column(Text)  # 'factory_expense', 'cash_received', 'supplier_payment'
    sub_category = Column(Text)
    department = Column(Text)
    
    # Additional details
    description = Column(Text)
    quantity = Column(Numeric(10, 2))
    unit_price = Column(Numeric(15, 2))
    
    # Outstanding amounts (for due bills)
    total_amount = Column(Numeric(15, 2))
    advance_paid = Column(Numeric(15, 2))
    amount_due = Column(Numeric(15, 2))
    
    # System fields
    source_reference = Column(Text)  # Link back to raw data
    data_quality_score = Column(Numeric(3, 2), default=1.0)
    is_active = Column(Boolean, default=True)
    created_by = Column(Text, default='system')
    loaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class FinanceSummary(Base):
    """Pre-calculated business summaries for fast dashboard loading"""
    __tablename__ = "finance_summary"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    summary_type = Column(Text, nullable=False)  # 'daily', 'monthly', 'yearly'
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    
    # Cash flow summaries
    total_cash_received = Column(Numeric(20, 2), default=0)
    total_expenses = Column(Numeric(20, 2), default=0)
    net_cash_flow = Column(Numeric(20, 2), default=0)
    
    # Outstanding amounts
    total_bills_due = Column(Numeric(20, 2), default=0)
    total_advances_paid = Column(Numeric(20, 2), default=0)
    
    # Currency breakdowns
    amounts_bdt = Column(Numeric(20, 2), default=0)
    amounts_usd = Column(Numeric(15, 2), default=0)
    
    # Profit/Loss tracking
    total_revenue = Column(Numeric(20, 2), default=0)
    total_expenditure = Column(Numeric(20, 2), default=0)
    profit_loss = Column(Numeric(20, 2), default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class FinanceFileProcessing(Base):
    """Track processing status of Excel files"""
    __tablename__ = "finance_file_processing"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_file = Column(Text, nullable=False)
    file_type = Column(Text, nullable=False)  # 'cash_book', 'party_due_bill', 'expenditure_summary'
    sheet_name = Column(Text)
    
    processing_started = Column(DateTime(timezone=True))
    processing_completed = Column(DateTime(timezone=True))
    status = Column(Text, default='pending')  # 'pending', 'processing', 'completed', 'failed'
    
    rows_processed = Column(Integer, default=0)
    rows_successful = Column(Integer, default=0)
    rows_failed = Column(Integer, default=0)
    
    error_details = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
