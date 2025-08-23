# backend/app/features/rag_chatbot/api/discovery.py
"""
RAG System Discovery API Endpoints - FIXED IMPORTS

This module provides REST API endpoints for document discovery and analysis.
Updated to use your existing Supabase client structure.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

# Import your existing auth dependencies - UPDATE THESE TO MATCH YOUR STRUCTURE
from app.core.auth_deps import get_current_user, require_roles  # Update if different
from app.core.database import get_service_supabase_client  # Using the new database module

# Import RAG system components
from ..discovery.scanner import GoogleDriveScanner
from ..discovery.classifier import DocumentTypeClassifier, test_classification_system
from ..models.schemas import (
    DocumentDiscoveryRequest,
    DocumentDiscoveryResponse,
    FileAnalysisRequest,
    FileAnalysisResponse,
    DocumentInventoryResponse,
    DocumentStats,
    ProcessingError,
    AnalysisStatus,
    DocumentCategory,
    FileType
)

# Configuration
from app.core.config import settings

# Initialize router
router = APIRouter(prefix="/rag", tags=["RAG System"])

# Initialize logger
logger = logging.getLogger(__name__)

# Global classifier instance (initialized on startup)
_classifier_instance = None


async def get_classifier() -> DocumentTypeClassifier:
    """
    Dependency to get the document classifier instance.
    
    This ensures we reuse the same classifier instance across requests
    for efficiency (Google Drive authentication is cached).
    """
    global _classifier_instance
    
    if _classifier_instance is None:
        # Use service client for RAG operations (needs full database access)
        db_client = get_service_supabase_client()
        _classifier_instance = DocumentTypeClassifier(
            credentials_path=settings.GOOGLE_DRIVE_CREDENTIALS_PATH,
            database_client=db_client
        )
    
    return _classifier_instance


# =============================================================================
# DOCUMENT DISCOVERY ENDPOINTS
# =============================================================================

@router.post("/discover", 
             response_model=DocumentDiscoveryResponse,
             status_code=HTTP_201_CREATED,
             summary="Discover and analyze documents",
             description="Scan Google Drive folders for documents and perform comprehensive analysis")
async def discover_documents(
    request: DocumentDiscoveryRequest,
    background_tasks: BackgroundTasks,
    classifier: DocumentTypeClassifier = Depends(get_classifier),
    current_user = Depends(get_current_user),
    # UPDATE THIS LINE TO MATCH YOUR AUTH STRUCTURE:
    # user_roles = Depends(require_roles(["owner", "admin"]))  # Uncomment if you have this function
) -> DocumentDiscoveryResponse:
    """
    Trigger document discovery and analysis process.
    
    This endpoint initiates the complete document processing pipeline:
    1. Scans specified Google Drive folder
    2. Discovers new or updated documents
    3. Performs structural analysis (Excel/PDF)
    4. Classifies documents by business category
    5. Stores results in database
    
    **Permissions Required**: Owner or Admin role (if role checking is enabled)
    
    **Processing Time**: Can take several minutes for large folders
    
    **Background Processing**: Long-running operations are handled in background
    """
    try:
        logger.info(f"Document discovery initiated by user {current_user.get('email', 'unknown')} "
                   f"for folder: {request.folder_path}")
        
        # Validate folder path
        if not request.folder_path or request.folder_path.strip() == "":
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Folder path cannot be empty"
            )
        
        # For large operations, use background processing
        if request.max_files and request.max_files > 50:
            # Start background task for large operations
            background_tasks.add_task(
                _process_documents_background,
                classifier,
                request,
                current_user.get('id')
            )
            
            return DocumentDiscoveryResponse(
                total_files_found=0,
                new_files=0,
                updated_files=0,
                failed_files=0,
                documents=[],
                errors=[],
                processing_time_seconds=0.0,
                status="background_processing_started",
                message="Large discovery operation started in background. Check status endpoint for progress."
            )
        
        # For smaller operations, process synchronously
        start_time = datetime.now()
        
        results = await classifier.process_discovered_documents(
            folder_path=request.folder_path,
            force_reanalysis=request.force_reanalysis,
            file_patterns=request.file_patterns
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Convert results to response format
        response = DocumentDiscoveryResponse(
            total_files_found=results.get('discovery', {}).get('total_files', 0),
            new_files=results.get('discovery', {}).get('new_files', 0),
            updated_files=results.get('discovery', {}).get('updated_files', 0),
            failed_files=results.get('analysis', {}).get('failed', 0),
            documents=await _get_recent_documents(request.folder_path),
            errors=results.get('errors', []),
            processing_time_seconds=processing_time
        )
        
        logger.info(f"Discovery completed: {response.total_files_found} files found, "
                   f"{response.new_files} new, {response.failed_files} failed")
        
        return response
        
    except Exception as e:
        logger.error(f"Document discovery failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Document discovery failed: {str(e)}"
        )


@router.get("/documents",
            response_model=List[DocumentInventoryResponse],
            summary="List discovered documents",
            description="Retrieve list of documents with optional filtering")
async def list_documents(
    folder_path: Optional[str] = Query(None, description="Filter by folder path"),
    category: Optional[DocumentCategory] = Query(None, description="Filter by document category"),
    file_type: Optional[FileType] = Query(None, description="Filter by file type"),
    status: Optional[AnalysisStatus] = Query(None, description="Filter by analysis status"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of documents to return"),
    offset: int = Query(0, ge=0, description="Number of documents to skip"),
    current_user = Depends(get_current_user)
) -> List[DocumentInventoryResponse]:
    """
    Retrieve list of discovered documents with filtering and pagination.
    
    **Permissions**: All authenticated users can view documents
    
    **Filtering**: Multiple filters can be combined
    
    **Pagination**: Use limit and offset for large document sets
    """
    try:
        db_client = get_service_supabase_client()
        
        # Build query with filters
        query = db_client.table('rag_system.document_inventory').select('*')
        
        # Apply filters
        if folder_path:
            query = query.like('file_path', f'{folder_path}%')
        
        if category:
            query = query.eq('document_category', category.value)
        
        if file_type:
            query = query.eq('file_type', file_type.value)
        
        if status:
            query = query.eq('analysis_status', status.value)
        
        # Apply pagination and ordering
        query = query.order('created_at', desc=True).range(offset, offset + limit - 1)
        
        result = query.execute()
        
        # Convert to response models
        documents = []
        for doc_data in result.data or []:
            # Convert database record to response model
            doc_response = DocumentInventoryResponse(**doc_data)
            documents.append(doc_response)
        
        logger.info(f"Retrieved {len(documents)} documents for user {current_user.get('email', 'unknown')}")
        
        return documents
        
    except Exception as e:
        logger.error(f"Failed to list documents: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve documents: {str(e)}"
        )


@router.post("/documents/{document_id}/analyze",
             response_model=FileAnalysisResponse,
             summary="Analyze individual document",
             description="Trigger analysis for a specific document")
async def analyze_document(
    document_id: UUID,
    force_reanalysis: bool = Query(False, description="Force reanalysis even if already completed"),
    classifier: DocumentTypeClassifier = Depends(get_classifier),
    current_user = Depends(get_current_user),
    # UPDATE THIS LINE TO MATCH YOUR AUTH STRUCTURE:
    # user_roles = Depends(require_roles(["owner", "admin", "manager"]))  # Uncomment if available
) -> FileAnalysisResponse:
    """
    Analyze a specific document by its database ID.
    
    **Use Cases**:
    - Retry failed analysis
    - Update analysis with improved algorithms
    - On-demand analysis for newly discovered documents
    
    **Permissions Required**: Owner, Admin, or Manager role (if role checking enabled)
    """
    try:
        start_time = datetime.now()
        
        logger.info(f"Individual document analysis requested by {current_user.get('email', 'unknown')} "
                   f"for document: {document_id}")
        
        # Perform analysis
        result = await classifier.analyze_single_document(
            str(document_id),
            force_reanalysis=force_reanalysis
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Handle different result statuses
        if result['status'] == 'failed':
            if 'not found' in result.get('error', '').lower():
                raise HTTPException(
                    status_code=HTTP_404_NOT_FOUND,
                    detail=f"Document not found: {document_id}"
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=result.get('error', 'Analysis failed')
                )
        
        elif result['status'] == 'skipped':
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=result.get('message', 'Analysis not needed (already completed)')
            )
        
        # Success case
        response = FileAnalysisResponse(
            document_id=document_id,
            analysis_status=AnalysisStatus.ANALYZED,
            analysis_results=result.get('analysis_result'),
            processing_time_seconds=processing_time,
            error_message=None
        )
        
        logger.info(f"Document analysis completed for {document_id} in {processing_time:.2f}s")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document analysis failed for {document_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.get("/documents/{document_id}",
            response_model=DocumentInventoryResponse,
            summary="Get document details",
            description="Retrieve detailed information about a specific document")
async def get_document(
    document_id: UUID,
    current_user = Depends(get_current_user)
) -> DocumentInventoryResponse:
    """
    Retrieve detailed information about a specific document.
    
    **Permissions**: All authenticated users can view document details
    """
    try:
        db_client = get_service_supabase_client()
        
        result = db_client.table('rag_system.document_inventory').select('*').eq(
            'id', str(document_id)
        ).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        # Convert to response model
        document = DocumentInventoryResponse(**result.data[0])
        
        logger.info(f"Document details retrieved for {document_id} by {current_user.get('email', 'unknown')}")
        
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve document: {str(e)}"
        )


@router.get("/statistics",
            response_model=DocumentStats,
            summary="Get processing statistics",
            description="Retrieve comprehensive statistics about document processing")
async def get_processing_statistics(
    current_user = Depends(get_current_user)
) -> DocumentStats:
    """
    Get comprehensive statistics about document processing.
    
    **Use Cases**:
    - Dashboard metrics display
    - System health monitoring
    - Processing progress tracking
    
    **Permissions**: All authenticated users
    """
    try:
        classifier = await get_classifier()
        stats = await classifier.get_processing_statistics()
        
        if not stats:
            # Return empty stats if no data
            return DocumentStats(
                total_documents=0,
                by_file_type={},
                by_category={},
                by_status={},
                average_completeness=0.0,
                average_confidence=0.0,
                last_updated=datetime.now()
            )
        
        # Convert to response model
        document_stats = DocumentStats(
            total_documents=stats.get('total_documents', 0),
            by_file_type=stats.get('by_file_type', {}),
            by_category=stats.get('by_category', {}),
            by_status=stats.get('by_status', {}),
            average_completeness=stats.get('health', {}).get('success_rate', 0.0),
            average_confidence=stats.get('average_confidence', 0.0),
            last_updated=datetime.now()
        )
        
        logger.info(f"Statistics retrieved by {current_user.get('email', 'unknown')}")
        
        return document_stats
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.get("/health",
            summary="System health check",
            description="Check RAG system health and connectivity")
async def health_check(
    current_user = Depends(get_current_user)
) -> JSONResponse:
    """
    Perform comprehensive health check of RAG system components.
    
    **Checks Performed**:
    - Database connectivity
    - Google Drive authentication
    - Service availability
    - Recent processing activity
    
    **Permissions**: All authenticated users
    """
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "version": "1.0.0"
        }
        
        # Check database connectivity
        try:
            db_client = get_service_supabase_client()
            result = db_client.table('rag_system.document_inventory').select('count').limit(1).execute()
            health_status["components"]["database"] = {
                "status": "healthy",
                "message": "Database connection successful"
            }
        except Exception as e:
            health_status["components"]["database"] = {
                "status": "unhealthy",
                "message": f"Database connection failed: {str(e)}"
            }
            health_status["status"] = "degraded"
        
        # Check Google Drive connectivity
        try:
            classifier = await get_classifier()
            if hasattr(classifier.drive_scanner, 'drive_service') and classifier.drive_scanner.drive_service:
                health_status["components"]["google_drive"] = {
                    "status": "healthy",
                    "message": "Google Drive authentication active"
                }
            else:
                health_status["components"]["google_drive"] = {
                    "status": "warning",
                    "message": "Google Drive not authenticated (will authenticate on first use)"
                }
        except Exception as e:
            health_status["components"]["google_drive"] = {
                "status": "unhealthy",
                "message": f"Google Drive check failed: {str(e)}"
            }
            health_status["status"] = "degraded"
        
        # Check recent processing activity
        try:
            db_client = get_service_supabase_client()
            recent_docs = db_client.table('rag_system.document_inventory').select('created_at').gte(
                'created_at', (datetime.now().replace(hour=0, minute=0, second=0)).isoformat()
            ).execute()
            
            health_status["components"]["processing"] = {
                "status": "healthy",
                "message": f"Processed {len(recent_docs.data or [])} documents today"
            }
        except Exception as e:
            health_status["components"]["processing"] = {
                "status": "warning",
                "message": f"Could not check recent activity: {str(e)}"
            }
        
        # Determine overall status
        component_statuses = [comp["status"] for comp in health_status["components"].values()]
        if "unhealthy" in component_statuses:
            health_status["status"] = "unhealthy"
        elif "warning" in component_statuses:
            health_status["status"] = "warning"
        
        logger.info(f"Health check performed by {current_user.get('email', 'unknown')}: {health_status['status']}")
        
        return JSONResponse(content=health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            content={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            status_code=500
        )


@router.post("/test-setup",
             summary="Test system setup",
             description="Validate RAG system configuration and connectivity")
async def test_system_setup(
    test_folder: str = Query("Finance", description="Folder to test with"),
    current_user = Depends(get_current_user),
    # UPDATE THIS LINE TO MATCH YOUR AUTH STRUCTURE:
    # user_roles = Depends(require_roles(["owner", "admin"]))  # Uncomment if available
) -> JSONResponse:
    """
    Test RAG system setup and configuration.
    
    **Use Cases**:
    - Initial system validation
    - Troubleshooting connectivity issues
    - Pre-deployment verification
    
    **Permissions Required**: Owner or Admin role (if role checking enabled)
    """
    try:
        logger.info(f"System setup test initiated by {current_user.get('email', 'unknown')} "
                   f"for folder: {test_folder}")
        
        # Perform comprehensive system test
        db_client = get_service_supabase_client()
        test_results = await test_classification_system(
            credentials_path=settings.GOOGLE_DRIVE_CREDENTIALS_PATH,
            db_client=db_client,
            test_folder=test_folder
        )
        
        return JSONResponse(content=test_results)
        
    except Exception as e:
        logger.error(f"System setup test failed: {str(e)}")
        return JSONResponse(
            content={
                "test_status": "failed",
                "error": str(e),
                "recommendations": [
                    "Check Google Drive service account configuration",
                    "Verify database connection settings",
                    "Ensure test folder exists and has proper permissions"
                ]
            },
            status_code=500
        )


# =============================================================================
# BACKGROUND TASK FUNCTIONS
# =============================================================================

async def _process_documents_background(
    classifier: DocumentTypeClassifier,
    request: DocumentDiscoveryRequest,
    user_id: str
):
    """
    Background task for processing large document sets.
    """
    try:
        logger.info(f"Starting background document processing for user {user_id}")
        
        results = await classifier.process_discovered_documents(
            folder_path=request.folder_path,
            force_reanalysis=request.force_reanalysis,
            file_patterns=request.file_patterns
        )
        
        logger.info(f"Background processing completed for user {user_id}: "
                   f"{results.get('analysis', {}).get('successful', 0)} successful")
        
    except Exception as e:
        logger.error(f"Background processing failed for user {user_id}: {str(e)}")


async def _get_recent_documents(folder_path: str, limit: int = 20) -> List[DocumentInventoryResponse]:
    """
    Helper function to get recent documents for a folder.
    """
    try:
        db_client = get_service_supabase_client()
        
        result = db_client.table('rag_system.document_inventory').select('*').like(
            'file_path', f'{folder_path}%'
        ).order('created_at', desc=True).limit(limit).execute()
        
        documents = []
        for doc_data in result.data or []:
            doc_response = DocumentInventoryResponse(**doc_data)
            documents.append(doc_response)
        
        return documents
        
    except Exception as e:
        logger.error(f"Failed to get recent documents: {str(e)}")
        return []