# backend/app/features/rag_chatbot/models/schemas.py
"""
RAG System Data Models

This file defines all Pydantic models for the RAG chatbot system.
Pydantic provides automatic validation, serialization, and documentation.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# =============================================================================
# ENUMERATIONS - Define allowed values for categorical fields
# =============================================================================

class FileType(str, Enum):
    """
    Supported file types for document processing.
    """
    EXCEL = "excel"
    PDF = "pdf"
    CSV = "csv"
    DOC = "doc"
    DOCX = "docx"
    UNKNOWN = "unknown"


class DocumentCategory(str, Enum):
    """
    Business document categories for your textile company.
    """
    FINANCE = "finance"
    HR = "hr"
    LC = "lc"  # Letter of Credit
    INVOICE = "invoice"
    INVENTORY = "inventory"
    REPORTS = "reports"
    UNKNOWN = "unknown"


class AnalysisStatus(str, Enum):
    """
    Document analysis pipeline status tracking.
    """
    PENDING = "pending"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    FAILED = "failed"
    NEEDS_REPROCESSING = "needs_reprocessing"


# =============================================================================
# ANALYSIS RESULT MODELS - Structure complex JSONB data
# =============================================================================

class ColumnInfo(BaseModel):
    """
    Individual Excel column analysis.
    """
    name: str = Field(..., description="Column header name")
    data_type: str = Field(..., description="Detected data type (string, number, date, boolean)")
    business_type: Optional[str] = Field(None, description="Inferred business meaning (currency, employee_id, vendor_name)")
    sample_values: List[str] = Field(default_factory=list, description="Sample values for pattern analysis")
    null_count: int = Field(0, description="Number of null/empty values")
    unique_count: int = Field(0, description="Number of unique values")

    @field_validator('sample_values', mode='after')
    @classmethod
    def limit_sample_size(cls, v: List[str]) -> List[str]:
        """Limit sample values to prevent excessive data storage."""
        return v[:5] if v else v


class ExcelAnalysisResult(BaseModel):
    """
    Complete Excel file analysis results.
    """
    sheet_names: List[str] = Field(..., description="Names of all sheets in workbook")
    analyzed_sheet: str = Field(..., description="Primary sheet that was analyzed")
    total_rows: int = Field(..., description="Number of data rows (excluding headers)")
    total_columns: int = Field(..., description="Number of columns")

    columns: List[ColumnInfo] = Field(..., description="Detailed analysis of each column")

    # Business context detection
    has_dates: bool = Field(False, description="Contains date columns")
    has_amounts: bool = Field(False, description="Contains monetary amounts")
    has_ids: bool = Field(False, description="Contains ID/reference columns")

    # Data quality metrics
    completeness_score: float = Field(..., description="Percentage of non-null values (0-1)")
    consistency_score: float = Field(..., description="Data format consistency (0-1)")

    # Business pattern detection
    detected_patterns: List[str] = Field(default_factory=list, description="Business patterns found (transaction_log, employee_roster, etc.)")

    @field_validator('completeness_score', 'consistency_score', mode='after')
    @classmethod
    def score_range(cls, v: float) -> float:
        """Clamp scores to [0, 1]."""
        if v is None:
            return v
        try:
            v = float(v)
        except Exception as e:
            raise ValueError("score must be a float") from e
        return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


class PDFAnalysisResult(BaseModel):
    """
    PDF document classification and analysis results.
    """
    page_count: int = Field(..., description="Total number of pages")
    text_extractable: bool = Field(..., description="Whether text could be extracted directly")
    ocr_required: bool = Field(False, description="Whether OCR was needed")

    # Classification results
    classification_confidence: float = Field(..., description="Confidence in document category (0-1)")
    detected_keywords: List[str] = Field(default_factory=list, description="Key terms that influenced classification")

    # Content analysis
    has_tables: bool = Field(False, description="Contains tabular data")
    has_forms: bool = Field(False, description="Contains form fields")
    language_detected: str = Field("english", description="Primary language detected")

    # Text quality metrics
    text_quality_score: float = Field(..., description="Quality of extracted text (0-1)")
    character_count: int = Field(0, description="Total characters extracted")

    # LC-specific fields
    is_letter_of_credit: bool = Field(False, description="Specifically identified as LC document")
    lc_confidence: float = Field(0.0, description="Confidence this is an LC document")

    @field_validator('classification_confidence', 'text_quality_score', 'lc_confidence', mode='after')
    @classmethod
    def confidence_range(cls, v: float) -> float:
        """Clamp confidences to [0, 1]."""
        if v is None:
            return v
        try:
            v = float(v)
        except Exception as e:
            raise ValueError("confidence must be a float") from e
        return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


# =============================================================================
# MAIN DATA MODELS - Core business entities
# =============================================================================

class DocumentInventoryBase(BaseModel):
    """
    Base model for document inventory.
    """
    file_path: str = Field(..., description="Full path in Google Drive")
    file_name: str = Field(..., description="Original filename")
    file_type: FileType = Field(..., description="Detected file type")
    document_category: DocumentCategory = Field(DocumentCategory.UNKNOWN, description="Business category")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    google_drive_id: Optional[str] = Field(None, description="Google Drive unique identifier")
    analysis_status: AnalysisStatus = Field(AnalysisStatus.PENDING, description="Current processing status")


class DocumentInventoryCreate(DocumentInventoryBase):
    """Model for creating new document inventory records."""
    pass


class DocumentInventoryUpdate(BaseModel):
    """
    Model for updating document inventory records.
    """
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[FileType] = None
    document_category: Optional[DocumentCategory] = None
    analysis_status: Optional[AnalysisStatus] = None
    analysis_results: Optional[Dict[str, Any]] = None


class DocumentInventoryResponse(DocumentInventoryBase):
    """
    Complete document inventory record for API responses.
    """
    id: UUID = Field(..., description="Unique document identifier")
    last_modified: Optional[datetime] = Field(None, description="Last modification time from Google Drive")
    analysis_results: Optional[Dict[str, Any]] = Field(None, description="Analysis results (Excel or PDF)")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Pydantic v2 config
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "file_path": "Finance/March 2024.xlsx",
                "file_name": "March 2024.xlsx",
                "file_type": "excel",
                "document_category": "finance",
                "file_size": 51200,
                "analysis_status": "analyzed",
                "analysis_results": {
                    "sheet_names": ["Transactions"],
                    "total_rows": 150,
                    "has_amounts": True
                }
            }
        }
    )


# =============================================================================
# REQUEST/RESPONSE MODELS - API endpoint contracts
# =============================================================================

class DocumentDiscoveryRequest(BaseModel):
    """
    Request model for triggering document discovery.
    """
    folder_path: Optional[str] = Field(
        "Finance",
        description="Google Drive folder path to scan"
    )
    force_reanalysis: bool = Field(
        False,
        description="Whether to reanalyze already processed files"
    )
    file_patterns: Optional[List[str]] = Field(
        None,
        description="Filename patterns to include (e.g., ['*.xlsx', 'LC*.pdf'])"
    )
    max_files: Optional[int] = Field(
        100,
        description="Maximum number of files to process in one batch"
    )


class DocumentDiscoveryResponse(BaseModel):
    """
    Response model for document discovery results.
    """
    total_files_found: int = Field(..., description="Total files discovered")
    new_files: int = Field(..., description="Newly added files")
    updated_files: int = Field(..., description="Files with updated metadata")
    failed_files: int = Field(..., description="Files that couldn't be processed")

    documents: List[DocumentInventoryResponse] = Field(
        ...,
        description="List of discovered/updated documents"
    )

    errors: List[str] = Field(
        default_factory=list,
        description="Any errors encountered during discovery"
    )

    processing_time_seconds: float = Field(..., description="Time taken for discovery")


class FileAnalysisRequest(BaseModel):
    """
    Request model for analyzing individual files.
    """
    document_id: UUID = Field(..., description="Document ID to analyze")
    force_reanalysis: bool = Field(False, description="Force reanalysis even if already done")


class FileAnalysisResponse(BaseModel):
    """
    Response model for individual file analysis.
    """
    document_id: UUID = Field(..., description="Analyzed document ID")
    analysis_status: AnalysisStatus = Field(..., description="Analysis result status")
    analysis_results: Union[ExcelAnalysisResult, PDFAnalysisResult] = Field(
        ...,
        description="Structured analysis results"
    )
    processing_time_seconds: float = Field(..., description="Analysis processing time")
    error_message: Optional[str] = Field(None, description="Error details if analysis failed")


# =============================================================================
# UTILITY MODELS - Supporting data structures
# =============================================================================

class DocumentStats(BaseModel):
    """
    Statistics about the document collection.
    """
    total_documents: int = Field(..., description="Total documents in system")

    # Distribution by type
    by_file_type: Dict[FileType, int] = Field(
        default_factory=dict,
        description="Count of documents by file type"
    )

    # Distribution by category
    by_category: Dict[DocumentCategory, int] = Field(
        default_factory=dict,
        description="Count of documents by business category"
    )

    # Processing status
    by_status: Dict[AnalysisStatus, int] = Field(
        default_factory=dict,
        description="Count of documents by analysis status"
    )

    # Quality metrics
    average_completeness: float = Field(0.0, description="Average data completeness score")
    average_confidence: float = Field(0.0, description="Average classification confidence")

    last_updated: datetime = Field(..., description="When these stats were calculated")


class ProcessingError(BaseModel):
    """
    Structured error information for failed processing.
    """
    error_type: str = Field(..., description="Category of error (network, parsing, validation)")
    error_message: str = Field(..., description="Human-readable error description")
    file_path: str = Field(..., description="File that caused the error")
    error_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for debugging"
    )
    timestamp: datetime = Field(..., description="When the error occurred")
    recoverable: bool = Field(True, description="Whether this error can be retried")


# =============================================================================
# ADVANCED MODELS - For future phases
# =============================================================================

class EmbeddingMetadata(BaseModel):
    """
    Metadata for document embeddings (Phase 2).
    """
    document_id: UUID = Field(..., description="Source document ID")
    chunk_index: int = Field(..., description="Position within document")
    chunk_type: str = Field(..., description="Type of chunk (row, paragraph, section)")
    business_context: str = Field(..., description="Business context for this chunk")

    # Filtering metadata
    date_range: Optional[str] = None
    department: Optional[str] = None
    amount_range: Optional[str] = None

    # Pydantic v2 config placeholder for future expansion
    model_config = ConfigDict()


# =============================================================================
# EXPORT ALL MODELS
# =============================================================================

__all__ = [
    # Enums
    "FileType",
    "DocumentCategory",
    "AnalysisStatus",

    # Analysis Results
    "ColumnInfo",
    "ExcelAnalysisResult",
    "PDFAnalysisResult",

    # Core Models
    "DocumentInventoryBase",
    "DocumentInventoryCreate",
    "DocumentInventoryUpdate",
    "DocumentInventoryResponse",

    # Request/Response
    "DocumentDiscoveryRequest",
    "DocumentDiscoveryResponse",
    "FileAnalysisRequest",
    "FileAnalysisResponse",

    # Utilities
    "DocumentStats",
    "ProcessingError",

    # Future
    "EmbeddingMetadata",
]
