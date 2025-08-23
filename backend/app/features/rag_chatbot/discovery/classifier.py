# backend/app/features/rag_chatbot/discovery/classifier.py
"""
Document Type Classification Orchestrator

This module coordinates the classification process for discovered documents.
It routes different file types to appropriate analyzers and manages the
overall analysis workflow.

Key responsibilities:
1. Orchestrate analysis workflow for different file types
2. Manage processing status and error handling
3. Store analysis results in the database
4. Provide processing statistics and monitoring
5. Handle retry logic for failed analyses
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from io import BytesIO

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .analyzer import ExcelStructureAnalyzer, PDFClassifier
from .scanner import GoogleDriveScanner
from ..models.schemas import (
    FileType,
    DocumentCategory,
    AnalysisStatus,
    DocumentInventoryResponse,
    ExcelAnalysisResult,
    PDFAnalysisResult,
    ProcessingError
)


class DocumentTypeClassifier:
    """
    Main orchestrator for document classification and analysis.
    
    This class manages the entire document processing pipeline from
    discovery through analysis and storage. It's designed to handle
    your textile company's mixed document environment efficiently.
    
    Processing workflow:
    1. Discover documents via GoogleDriveScanner
    2. Route to appropriate analyzer (Excel/PDF)
    3. Store analysis results in database
    4. Update processing status and handle errors
    5. Provide monitoring and statistics
    """
    
    def __init__(self, credentials_path: str, database_client=None):
        """
        Initialize the document classification system.
        
        Args:
            credentials_path: Path to Google service account JSON
            database_client: Supabase client for database operations
        """
        self.credentials_path = credentials_path
        self.db_client = database_client
        self.logger = logging.getLogger(__name__)
        
        # Initialize analyzers
        self.excel_analyzer = ExcelStructureAnalyzer()
        self.pdf_classifier = PDFClassifier()
        self.drive_scanner = GoogleDriveScanner(credentials_path, database_client)
        
        # Processing configuration
        self.max_retries = 3
        self.batch_size = 10  # Process documents in batches
        self.timeout_seconds = 300  # 5 minutes per document
        
        # File size limits (in bytes)
        self.size_limits = {
            FileType.EXCEL: 50 * 1024 * 1024,  # 50MB
            FileType.PDF: 100 * 1024 * 1024,   # 100MB
            FileType.CSV: 20 * 1024 * 1024,    # 20MB
        }
        
        # Performance tracking
        self.processing_stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': None
        }
    
    async def process_discovered_documents(self, folder_path: str = "Finance",
                                         force_reanalysis: bool = False,
                                         file_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Complete document discovery and analysis workflow.
        
        This is the main entry point for processing documents. It discovers
        documents in Google Drive and then analyzes them comprehensively.
        
        Args:
            folder_path: Google Drive folder to scan
            force_reanalysis: Whether to reanalyze already processed documents
            file_patterns: Optional filename patterns to filter by
        
        Returns:
            Processing results summary
        """
        self.processing_stats['start_time'] = datetime.now()
        
        try:
            # Step 1: Discover documents
            self.logger.info(f"Starting document discovery in folder: {folder_path}")
            discovery_results = await self.drive_scanner.scan_folder(
                folder_path=folder_path,
                force_rescan=force_reanalysis,
                file_patterns=file_patterns
            )
            
            if discovery_results['total_files'] == 0:
                return {
                    'status': 'completed',
                    'discovery': discovery_results,
                    'analysis': {'processed': 0, 'successful': 0, 'failed': 0},
                    'errors': discovery_results.get('errors', [])
                }
            
            # Step 2: Get documents that need analysis
            documents_to_analyze = await self._get_documents_for_analysis(
                folder_path, force_reanalysis
            )
            
            if not documents_to_analyze:
                return {
                    'status': 'completed',
                    'discovery': discovery_results,
                    'analysis': {'processed': 0, 'successful': 0, 'failed': 0},
                    'message': 'No documents require analysis'
                }
            
            # Step 3: Analyze documents in batches
            self.logger.info(f"Analyzing {len(documents_to_analyze)} documents")
            analysis_results = await self._analyze_documents_batch(documents_to_analyze)
            
            # Step 4: Generate summary
            summary = {
                'status': 'completed',
                'discovery': discovery_results,
                'analysis': analysis_results,
                'processing_time': (datetime.now() - self.processing_stats['start_time']).total_seconds(),
                'errors': discovery_results.get('errors', []) + analysis_results.get('errors', [])
            }
            
            self.logger.info(f"Document processing completed: {analysis_results['successful']} successful, "
                           f"{analysis_results['failed']} failed")
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Document processing failed: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'processing_time': (datetime.now() - self.processing_stats['start_time']).total_seconds() if self.processing_stats['start_time'] else 0
            }
    
    async def analyze_single_document(self, document_id: str, force_reanalysis: bool = False) -> Dict[str, Any]:
        """
        Analyze a single document by its database ID.
        
        Useful for on-demand analysis or retry operations.
        
        Args:
            document_id: UUID of document in database
            force_reanalysis: Force reanalysis even if already done
        
        Returns:
            Analysis result for the single document
        """
        try:
            # Get document information
            document = await self._get_document_by_id(document_id)
            if not document:
                return {
                    'status': 'failed',
                    'error': f'Document not found: {document_id}'
                }
            
            # Check if analysis is needed
            if (document['analysis_status'] == AnalysisStatus.ANALYZED and 
                not force_reanalysis):
                return {
                    'status': 'skipped',
                    'message': 'Document already analyzed (use force_reanalysis=True to override)'
                }
            
            # Perform analysis
            result = await self._analyze_single_document_impl(document)
            
            return {
                'status': 'completed',
                'document_id': document_id,
                'analysis_result': result
            }
            
        except Exception as e:
            self.logger.error(f"Single document analysis failed for {document_id}: {str(e)}")
            return {
                'status': 'failed',
                'document_id': document_id,
                'error': str(e)
            }
    
    async def _get_documents_for_analysis(self, folder_path: str, 
                                        force_reanalysis: bool) -> List[Dict]:
        """
        Get list of documents that need analysis.
        
        Filters documents based on analysis status and force_reanalysis flag.
        
        Args:
            folder_path: Folder path to filter by
            force_reanalysis: Whether to include already analyzed documents
        
        Returns:
            List of document records that need analysis
        """
        if not self.db_client:
            return []
        
        try:
            # Build query conditions
            query = self.db_client.table('rag_system.document_inventory').select('*')
            
            # Filter by folder path
            query = query.like('file_path', f'{folder_path}%')
            
            # Filter by analysis status
            if not force_reanalysis:
                query = query.in_('analysis_status', [
                    AnalysisStatus.PENDING.value,
                    AnalysisStatus.FAILED.value,
                    AnalysisStatus.NEEDS_REPROCESSING.value
                ])
            
            # Order by priority and creation time
            query = query.order('priority_level').order('created_at')
            
            result = query.execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            self.logger.error(f"Error getting documents for analysis: {str(e)}")
            return []
    
    async def _analyze_documents_batch(self, documents: List[Dict]) -> Dict[str, Any]:
        """
        Analyze multiple documents in batches with concurrency control.
        
        Processes documents in controlled batches to manage resource usage
        and provide progress tracking.
        
        Args:
            documents: List of document records to analyze
        
        Returns:
            Batch analysis results
        """
        results = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        # Process in batches
        for i in range(0, len(documents), self.batch_size):
            batch = documents[i:i + self.batch_size]
            
            self.logger.info(f"Processing batch {i//self.batch_size + 1}: "
                           f"{len(batch)} documents")
            
            # Process batch with limited concurrency
            batch_tasks = [
                self._analyze_single_document_with_timeout(doc)
                for doc in batch
            ]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process batch results
            for doc, result in zip(batch, batch_results):
                results['processed'] += 1
                
                if isinstance(result, Exception):
                    results['failed'] += 1
                    error_msg = f"Document {doc['file_name']}: {str(result)}"
                    results['errors'].append(error_msg)
                    self.logger.error(error_msg)
                    
                    # Update document status to failed
                    await self._update_document_status(
                        doc['id'], 
                        AnalysisStatus.FAILED,
                        error_message=str(result)
                    )
                    
                elif result['status'] == 'success':
                    results['successful'] += 1
                    self.logger.info(f"Successfully analyzed: {doc['file_name']}")
                    
                elif result['status'] == 'skipped':
                    results['skipped'] += 1
                    
                else:
                    results['failed'] += 1
                    error_msg = f"Document {doc['file_name']}: {result.get('error', 'Unknown error')}"
                    results['errors'].append(error_msg)
            
            # Brief pause between batches to prevent resource exhaustion
            if i + self.batch_size < len(documents):
                await asyncio.sleep(2)
        
        return results
    
    async def _analyze_single_document_with_timeout(self, document: Dict) -> Dict[str, Any]:
        """
        Analyze a single document with timeout protection.
        
        Wraps document analysis with timeout to prevent hanging on problematic files.
        
        Args:
            document: Document record from database
        
        Returns:
            Analysis result or timeout error
        """
        try:
            result = await asyncio.wait_for(
                self._analyze_single_document_impl(document),
                timeout=self.timeout_seconds
            )
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"Analysis timeout ({self.timeout_seconds}s) for {document['file_name']}"
            self.logger.error(error_msg)
            return {
                'status': 'failed',
                'error': error_msg
            }
        except Exception as e:
            return {
                'status': 'failed', 
                'error': str(e)
            }
    
    async def _analyze_single_document_impl(self, document: Dict) -> Dict[str, Any]:
        """
        Core implementation for analyzing a single document.
        
        Routes to appropriate analyzer based on file type and handles
        the complete analysis workflow.
        
        Args:
            document: Document record from database
        
        Returns:
            Analysis result dictionary
        """
        document_id = document['id']
        file_name = document['file_name']
        file_type = FileType(document['file_type'])
        google_drive_id = document['google_drive_id']
        
        try:
            # Update status to processing
            await self._update_document_status(document_id, AnalysisStatus.PROCESSING)
            
            # Check file size limits
            file_size = document.get('file_size', 0)
            size_limit = self.size_limits.get(file_type)
            if size_limit and file_size > size_limit:
                raise ValueError(f"File too large: {file_size} bytes (limit: {size_limit})")
            
            # Download file content from Google Drive
            file_content = await self._download_file_content(google_drive_id)
            if not file_content:
                raise ValueError("Failed to download file content")
            
            # Route to appropriate analyzer
            if file_type == FileType.EXCEL:
                analysis_result = await self.excel_analyzer.analyze_excel_file(
                    file_content, file_name
                )
                category = self._infer_category_from_excel_analysis(analysis_result, file_name)
                
            elif file_type == FileType.PDF:
                analysis_result = await self.pdf_classifier.analyze_pdf_document(
                    file_content, file_name
                )
                category = self._infer_category_from_pdf_analysis(analysis_result, file_name)
                
            else:
                # For unsupported file types, create basic analysis
                analysis_result = self._create_basic_analysis_result(document)
                category = DocumentCategory.UNKNOWN
            
            # Store analysis results
            await self._store_analysis_results(
                document_id, 
                analysis_result, 
                category,
                AnalysisStatus.ANALYZED
            )
            
            return {
                'status': 'success',
                'analysis_result': analysis_result,
                'inferred_category': category
            }
            
        except Exception as e:
            # Log the error and update document status
            error_msg = f"Analysis failed for {file_name}: {str(e)}"
            self.logger.error(error_msg)
            
            await self._update_document_status(
                document_id, 
                AnalysisStatus.FAILED,
                error_message=str(e)
            )
            
            raise e
    
    async def _download_file_content(self, google_drive_id: str) -> Optional[bytes]:
        """
        Download file content from Google Drive.
        
        Uses the same Google Drive service as the scanner for consistency.
        
        Args:
            google_drive_id: Google Drive file ID
        
        Returns:
            File content as bytes or None if failed
        """
        try:
            # Ensure we have an authenticated Drive service
            if not self.drive_scanner.drive_service:
                await self.drive_scanner.authenticate()
            
            if not self.drive_scanner.drive_service:
                raise ValueError("Google Drive authentication failed")
            
            # Download file content
            request = self.drive_scanner.drive_service.files().get_media(fileId=google_drive_id)
            file_content = request.execute()
            
            if isinstance(file_content, bytes):
                return file_content
            else:
                # Convert to bytes if needed
                return file_content.encode() if isinstance(file_content, str) else bytes(file_content)
                
        except HttpError as e:
            self.logger.error(f"Google Drive API error downloading {google_drive_id}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error downloading file {google_drive_id}: {str(e)}")
            return None
    
    def _infer_category_from_excel_analysis(self, analysis: ExcelAnalysisResult, 
                                          file_name: str) -> DocumentCategory:
        """
        Infer document category from Excel analysis results.
        
        Uses the structural analysis to determine business category.
        
        Args:
            analysis: Excel analysis results
            file_name: Original filename
        
        Returns:
            Inferred document category
        """
        # Check detected patterns first
        if 'transaction_log' in analysis.detected_patterns:
            return DocumentCategory.FINANCE
        elif 'employee_roster' in analysis.detected_patterns:
            return DocumentCategory.HR
        elif 'inventory_list' in analysis.detected_patterns:
            return DocumentCategory.INVENTORY
        elif 'financial_summary' in analysis.detected_patterns:
            return DocumentCategory.FINANCE
        
        # Check column business types
        business_types = [col.business_type for col in analysis.columns if col.business_type]
        
        # Financial indicators
        if ('currency' in business_types and 'date' in business_types and
            any('transaction' in col.name.lower() or 'payment' in col.name.lower() 
                for col in analysis.columns)):
            return DocumentCategory.FINANCE
        
        # HR indicators
        if (any('employee' in col.name.lower() or 'staff' in col.name.lower() 
               for col in analysis.columns) and
            ('name' in business_types or 'id' in business_types)):
            return DocumentCategory.HR
        
        # Inventory indicators
        if ('quantity' in business_types and
            any('stock' in col.name.lower() or 'inventory' in col.name.lower() or 'product' in col.name.lower()
                for col in analysis.columns)):
            return DocumentCategory.INVENTORY
        
        # Fallback to filename-based inference
        return self._infer_category_from_filename(file_name)
    
    def _infer_category_from_pdf_analysis(self, analysis: PDFAnalysisResult,
                                        file_name: str) -> DocumentCategory:
        """
        Infer document category from PDF analysis results.
        
        Uses classification confidence and detected keywords.
        
        Args:
            analysis: PDF analysis results
            file_name: Original filename
        
        Returns:
            Inferred document category
        """
        # Check if it's specifically identified as LC
        if analysis.is_letter_of_credit and analysis.lc_confidence > 0.7:
            return DocumentCategory.LC
        
        # Use the highest confidence classification from keywords
        if analysis.classification_confidence > 0.3:
            # This would require extending the PDF classifier to return the best category
            # For now, use keyword-based inference
            keywords_text = ' '.join(analysis.detected_keywords).lower()
            
            if any(word in keywords_text for word in ['letter of credit', 'lc', 'credit']):
                return DocumentCategory.LC
            elif any(word in keywords_text for word in ['invoice', 'bill', 'payment']):
                return DocumentCategory.INVOICE
            elif any(word in keywords_text for word in ['financial', 'statement', 'balance']):
                return DocumentCategory.FINANCE
            elif any(word in keywords_text for word in ['employee', 'staff', 'hr']):
                return DocumentCategory.HR
        
        # Fallback to filename-based inference
        return self._infer_category_from_filename(file_name)
    
    def _infer_category_from_filename(self, file_name: str) -> DocumentCategory:
        """
        Fallback category inference based on filename patterns.
        
        Args:
            file_name: Original filename
        
        Returns:
            Inferred document category
        """
        name_lower = file_name.lower()
        
        # Pattern matching for your textile business
        if any(word in name_lower for word in ['lc', 'letter', 'credit']):
            return DocumentCategory.LC
        elif any(word in name_lower for word in ['finance', 'transaction', 'payment', 'cash']):
            return DocumentCategory.FINANCE
        elif any(word in name_lower for word in ['hr', 'employee', 'staff', 'payroll']):
            return DocumentCategory.HR
        elif any(word in name_lower for word in ['invoice', 'bill', 'receipt']):
            return DocumentCategory.INVOICE
        elif any(word in name_lower for word in ['inventory', 'stock', 'product']):
            return DocumentCategory.INVENTORY
        elif any(word in name_lower for word in ['report', 'analysis', 'summary']):
            return DocumentCategory.REPORTS
        
        return DocumentCategory.UNKNOWN
    
    def _create_basic_analysis_result(self, document: Dict) -> Dict[str, Any]:
        """
        Create basic analysis result for unsupported file types.
        
        Args:
            document: Document record
        
        Returns:
            Basic analysis result dictionary
        """
        return {
            'file_type': document['file_type'],
            'file_size': document.get('file_size', 0),
            'analysis_type': 'basic',
            'supported': False,
            'message': f"Analysis not supported for file type: {document['file_type']}"
        }
    
    async def _store_analysis_results(self, document_id: str, 
                                    analysis_result: Any,
                                    category: DocumentCategory,
                                    status: AnalysisStatus) -> bool:
        """
        Store analysis results in the database.
        
        Updates the document record with analysis results and inferred category.
        
        Args:
            document_id: Document UUID
            analysis_result: Analysis result object
            category: Inferred document category
            status: Analysis status
        
        Returns:
            True if successful, False otherwise
        """
        if not self.db_client:
            return False
        
        try:
            # Convert analysis result to dict for JSON storage
            if hasattr(analysis_result, 'dict'):
                analysis_dict = analysis_result.dict()
            elif hasattr(analysis_result, 'model_dump'):
                analysis_dict = analysis_result.model_dump()
            else:
                analysis_dict = analysis_result
            
            # Update document record
            update_data = {
                'analysis_status': status.value,
                'analysis_results': analysis_dict,
                'document_category': category.value,
                'updated_at': datetime.now().isoformat()
            }
            
            result = self.db_client.table('rag_system.document_inventory').update(
                update_data
            ).eq('id', document_id).execute()
            
            if result.data:
                self.logger.debug(f"Stored analysis results for document {document_id}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error storing analysis results for {document_id}: {str(e)}")
            return False
    
    async def _update_document_status(self, document_id: str, 
                                    status: AnalysisStatus,
                                    error_message: Optional[str] = None) -> bool:
        """
        Update document processing status.
        
        Args:
            document_id: Document UUID
            status: New analysis status
            error_message: Optional error message if status is FAILED
        
        Returns:
            True if successful, False otherwise
        """
        if not self.db_client:
            return False
        
        try:
            update_data = {
                'analysis_status': status.value,
                'updated_at': datetime.now().isoformat()
            }
            
            if error_message:
                update_data['error_message'] = error_message
            
            result = self.db_client.table('rag_system.document_inventory').update(
                update_data
            ).eq('id', document_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            self.logger.error(f"Error updating document status for {document_id}: {str(e)}")
            return False
    
    async def _get_document_by_id(self, document_id: str) -> Optional[Dict]:
        """
        Get document record by ID.
        
        Args:
            document_id: Document UUID
        
        Returns:
            Document record or None if not found
        """
        if not self.db_client:
            return None
        
        try:
            result = self.db_client.table('rag_system.document_inventory').select('*').eq(
                'id', document_id
            ).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting document {document_id}: {str(e)}")
            return None
    
    async def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive processing statistics.
        
        Useful for monitoring and dashboard display.
        
        Returns:
            Processing statistics dictionary
        """
        if not self.db_client:
            return {}
        
        try:
            # Get document counts by status
            result = self.db_client.table('rag_system.document_inventory').select(
                'analysis_status, document_category, file_type'
            ).execute()
            
            if not result.data:
                return {'total_documents': 0}
            
            # Process statistics
            stats = {
                'total_documents': len(result.data),
                'by_status': {},
                'by_category': {},
                'by_file_type': {},
                'last_updated': datetime.now().isoformat()
            }
            
            for doc in result.data:
                # Count by status
                status = doc['analysis_status']
                stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
                
                # Count by category
                category = doc['document_category']
                stats['by_category'][category] = stats['by_category'].get(category, 0) + 1
                
                # Count by file type
                file_type = doc['file_type']
                stats['by_file_type'][file_type] = stats['by_file_type'].get(file_type, 0) + 1
            
            # Add processing health indicators
            total = stats['total_documents']
            analyzed = stats['by_status'].get(AnalysisStatus.ANALYZED.value, 0)
            failed = stats['by_status'].get(AnalysisStatus.FAILED.value, 0)
            
            stats['health'] = {
                'success_rate': (analyzed / total) if total > 0 else 0,
                'failure_rate': (failed / total) if total > 0 else 0,
                'pending_count': stats['by_status'].get(AnalysisStatus.PENDING.value, 0)
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting processing statistics: {str(e)}")
            return {}


# =============================================================================
# UTILITY FUNCTIONS FOR TESTING AND INTEGRATION
# =============================================================================

async def test_classification_system(credentials_path: str, 
                                   db_client=None,
                                   test_folder: str = "Finance") -> Dict[str, Any]:
    """
    Test the complete classification system with a small sample.
    
    This function helps validate your setup before running full processing.
    
    Args:
        credentials_path: Path to Google service account credentials
        db_client: Database client for testing
        test_folder: Folder to test with
    
    Returns:
        Test results dictionary
    """
    classifier = DocumentTypeClassifier(credentials_path, db_client)
    
    try:
        # Test with a small sample
        results = await classifier.process_discovered_documents(
            folder_path=test_folder,
            force_reanalysis=False
        )
        
        return {
            'test_status': 'success',
            'results': results,
            'recommendations': _generate_test_recommendations(results)
        }
        
    except Exception as e:
        return {
            'test_status': 'failed',
            'error': str(e),
            'recommendations': [
                'Check Google Drive authentication',
                'Verify database connection',
                'Ensure test folder exists and has documents'
            ]
        }


def _generate_test_recommendations(results: Dict[str, Any]) -> List[str]:
    """
    Generate recommendations based on test results.
    
    Args:
        results: Test processing results
    
    Returns:
        List of recommendation strings
    """
    recommendations = []
    
    analysis = results.get('analysis', {})
    
    if analysis.get('failed', 0) > 0:
        recommendations.append("Some documents failed analysis - check error messages and file formats")
    
    if analysis.get('successful', 0) == 0:
        recommendations.append("No documents were successfully analyzed - verify file types and content")
    
    if len(results.get('errors', [])) > 0:
        recommendations.append("Errors occurred during processing - review error messages for issues")
    
    if not recommendations:
        recommendations.append("System test passed - ready for full processing")
    
    return recommendations


def create_classifier_from_config(config: Dict[str, Any]) -> DocumentTypeClassifier:
    """
    Factory function to create classifier from configuration.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Configured DocumentTypeClassifier instance
    """
    return DocumentTypeClassifier(
        credentials_path=config['credentials_path'],
        database_client=config.get('database_client')
    )