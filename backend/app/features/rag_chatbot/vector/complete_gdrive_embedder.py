# backend/app/features/rag_chatbot/vector/complete_gdrive_embedder.py
"""
Complete Google Drive to Enhanced Vector Store Integration System

This system integrates all your existing components:
1. GoogleDriveService - finds and downloads Excel files
2. DocumentProcessingEngine - processes Excel structure  
3. ProcessingEmbeddingBridge - connects processing to embeddings
4. PersistedInMemorySearch - stores in enhanced_index.json
5. Chat system integration - makes files searchable

Complete pipeline: Google Drive → Excel Processing → Business Intelligence → Vector Embeddings → Search
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from io import BytesIO
from uuid import uuid4

# Your existing services
from .google_drive_service import GoogleDriveService
from .persisted_inmemory_search import PersistedInMemorySearch
from ..processing.document_processing_engine import DocumentProcessingOrchestrator
from ..pipeline.processing_to_embedding_bridge import ProcessingEmbeddingBridge

logger = logging.getLogger(__name__)


class CompleteGDriveEmbedder:
    """
    Complete integration system that connects Google Drive Excel files 
    to your enhanced vector search system.
    
    Features:
    - Automatic Excel file discovery from Google Drive
    - Processing through your Task 1C pipeline
    - Business intelligence extraction (customers, staff, amounts, dates)
    - Storage in enhanced_index.json for chat system
    - Incremental updates for modified files
    - Full error handling and statistics
    """
    
    def __init__(self, 
                    credentials_path: str = None,
                    vector_index_path: str = None):
            
            # Initialize Google Drive service with graceful error handling
            creds_path = credentials_path
            
            if not creds_path:
                # Try different paths based on execution context
                possible_paths = [
                    'credentials/google_credentials.json',          # From backend/
                    '../credentials/google_credentials.json',       # From app/
                    'backend/credentials/google_credentials.json',  # From repo root
                ]
                for path in possible_paths:
                    if Path(path).exists():
                        creds_path = path
                        break
            
            # Initialize Google Drive service or set to None if credentials not found
            if creds_path and Path(creds_path).exists():
                try:
                    self.gdrive = GoogleDriveService(creds_path)
                    logger.info(f"Google Drive service initialized with credentials: {creds_path}")
                except Exception as e:
                    logger.warning(f"Google Drive service initialization failed: {e}")
                    self.gdrive = None
            else:
                logger.warning(f"Google Drive credentials not found. Checked paths: {possible_paths}")
                self.gdrive = None
    
    async def initialize(self):
        """Initialize all components."""
        await self.processing_bridge.initialize()
        logger.info("All components initialized successfully")
    
    async def embed_all_google_drive_files(self, 
                                         force_reprocess: bool = False,
                                         base_folder: str = "Md. Mizanur Rahman (PTIL)") -> Dict[str, Any]:
        
        """
        Main method: Discover all Excel files in Google Drive and embed them.
        
        Args:
            force_reprocess: Re-process files even if already embedded
            base_folder: Google Drive base folder to search
            
        Returns:
            Complete processing results
        """

        if not self.gdrive:
            return {
                "status": "error",
                "error": "Google Drive not available - credentials not found",
                "recommendation": "Add google_credentials.json to backend/credentials/ directory"
            }
    
        try:
            self.stats["start_time"] = datetime.now()
            logger.info(f"Starting complete Google Drive embedding process for folder: {base_folder}")
            
            # Step 1: Test Google Drive connection
            gdrive_status = self.gdrive.test_connection()
            if not gdrive_status.get('connected'):
                raise Exception(f"Google Drive connection failed: {gdrive_status.get('error')}")
            
            # Step 2: Discover all target Excel files
            logger.info("Discovering Excel files in Google Drive...")
            excel_files = self.gdrive.find_target_files_anywhere(base_folder)
            
            if not excel_files:
                return {
                    "status": "warning",
                    "message": "No target Excel files found in Google Drive",
                    "stats": self.stats,
                    "recommendations": [
                        f"Check if folder '{base_folder}' exists in Google Drive",
                        "Verify Google Drive service account has access to the folder",
                        "Ensure target files (Cash Book, Party Due Bill, PTIL Expenditure) exist"
                    ]
                }
            
            self.stats["files_discovered"] = len(excel_files)
            logger.info(f"Found {len(excel_files)} Excel files to process")
            
            # Step 3: Process each Excel file through complete pipeline
            successful_embeddings = 0
            total_chunks = 0
            processing_results = []
            
            for file_info in excel_files:
                try:
                    logger.info(f"Processing: {file_info['name']}")
                    
                    # Check if already processed (unless forcing reprocess)
                    if not force_reprocess and self._is_file_already_embedded(file_info):
                        logger.info(f"Skipping already processed file: {file_info['name']}")
                        self.stats["skipped_files"] += 1
                        continue
                    
                    # Process through complete pipeline
                    result = await self._process_excel_file_complete_pipeline(file_info)
                    processing_results.append(result)
                    
                    if result["status"] == "success":
                        successful_embeddings += 1
                        total_chunks += result.get("chunks_created", 0)
                        logger.info(f"Successfully embedded: {file_info['name']} "
                                  f"({result.get('chunks_created', 0)} chunks)")
                    else:
                        logger.error(f"Failed to embed: {file_info['name']} - {result.get('error')}")
                        self.stats["errors"] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing {file_info['name']}: {str(e)}")
                    self.stats["errors"] += 1
                    processing_results.append({
                        "status": "failed",
                        "file_name": file_info['name'],
                        "error": str(e)
                    })
                    continue
            
            # Step 4: Update final stats
            self.stats["files_processed"] = successful_embeddings
            self.stats["chunks_created"] = total_chunks
            self.stats["embeddings_stored"] = total_chunks
            self.stats["last_run"] = datetime.now()
            
            processing_time = (self.stats["last_run"] - self.stats["start_time"]).total_seconds()
            
            # Create comprehensive results
            result = {
                "status": "success",
                "message": f"Embedded {successful_embeddings}/{len(excel_files)} Excel files from Google Drive",
                "stats": {
                    **self.stats,
                    "processing_time_seconds": processing_time,
                    "average_time_per_file": processing_time / len(excel_files) if excel_files else 0
                },
                "files_discovered": [f["name"] for f in excel_files],
                "processing_results": processing_results,
                "vector_store_info": {
                    "index_path": str(self.vector_store.index_path),
                    "total_documents_in_index": len(self.vector_store.items),
                    "embedding_dimension": self.vector_store.dim
                },
                "next_steps": [
                    "Test search functionality with: await embedder.test_search('financial data')",
                    "Check chat system integration with the embedded documents",
                    "Set up automatic periodic updates for modified files"
                ]
            }
            
            logger.info(f"Complete embedding process finished: {result['message']}")
            return result
            
        except Exception as e:
            logger.error(f"Complete Google Drive embedding failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "stats": self.stats,
                "troubleshooting": [
                    "Check Google Drive credentials path",
                    "Verify internet connection", 
                    "Ensure vector index directory is writable",
                    "Check that all required Python packages are installed"
                ]
            }
    
    async def _process_excel_file_complete_pipeline(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single Excel file through the complete pipeline:
        Google Drive → Download → Process → Extract Business Intelligence → Embed → Store
        """
        file_name = file_info['name']
        file_id = file_info['id']
        
        try:
            # Step 1: Download file from Google Drive
            logger.info(f"Downloading {file_name} from Google Drive...")
            file_content = self.gdrive.download_file(file_id)
            
            if not file_content:
                return {
                    "status": "failed",
                    "error": "Failed to download file from Google Drive",
                    "file_name": file_name
                }
            
            # Step 2: Process Excel file using your DocumentProcessingEngine
            logger.info(f"Processing Excel structure for {file_name}...")
            processing_result = await self.doc_processor.process_document(
                file_path=file_name,
                file_data=BytesIO(file_content),  # Convert bytes to file-like object
                file_type='excel'
            )
            
            if processing_result.status.value != 'completed':
                return {
                    "status": "failed",
                    "error": f"Document processing failed: {processing_result.errors}",
                    "file_name": file_name
                }
            
            # Step 3: Convert to documents for vector store
            logger.info(f"Converting to searchable documents for {file_name}...")
            documents = self._convert_processing_result_to_documents(processing_result, file_info)
            
            # Step 4: Store in vector database
            logger.info(f"Storing embeddings for {file_name}...")
            self.vector_store.ingest_documents(documents)
            
            return {
                "status": "success",
                "file_name": file_name,
                "file_id": file_id,
                "chunks_created": len(documents),
                "processing_metadata": {
                    "document_type": processing_result.document_type.value,
                    "department": processing_result.department,
                    "business_priority": processing_result.business_priority,
                    "confidence_score": processing_result.confidence_score,
                    "staff_involved": processing_result.staff_involved,
                    "customers_mentioned": processing_result.customers_mentioned,
                    "business_entities": processing_result.business_entities
                }
            }
            
        except Exception as e:
            logger.error(f"Complete pipeline processing failed for {file_name}: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "file_name": file_name
            }
    
    def _convert_processing_result_to_documents(self, processing_result, file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert Task 1C processing result to documents for vector storage.
        This creates multiple searchable chunks from the Excel file.
        """
        documents = []
        
        # Document 1: File Overview
        overview_content = self._create_file_overview(processing_result, file_info)
        documents.append({
            "id": f"gdrive_{file_info['id']}_overview",
            "text": overview_content,
            "metadata": {
                "source": "google_drive",
                "file_name": file_info['name'],
                "file_id": file_info['id'],
                "chunk_type": "overview",
                "modified_time": file_info['modified_time'],
                "document_type": processing_result.document_type.value,
                "department": processing_result.department or "unknown",
                "business_priority": processing_result.business_priority,
                "confidence_score": processing_result.confidence_score,
                **self._extract_metadata_from_entities(processing_result.business_entities)
            }
        })
        
        # Document 2: Business Entities Summary
        if processing_result.business_entities:
            entities_content = self._create_entities_summary(processing_result, file_info)
            documents.append({
                "id": f"gdrive_{file_info['id']}_entities",
                "text": entities_content,
                "metadata": {
                    "source": "google_drive",
                    "file_name": file_info['name'],
                    "file_id": file_info['id'],
                    "chunk_type": "business_entities",
                    "modified_time": file_info['modified_time'],
                    "department": processing_result.department or "unknown",
                    **self._extract_metadata_from_entities(processing_result.business_entities)
                }
            })
        
        # Document 3: Detailed Content (if available)
        if processing_result.extracted_content:
            detailed_content = self._create_detailed_content(processing_result, file_info)
            documents.append({
                "id": f"gdrive_{file_info['id']}_details",
                "text": detailed_content,
                "metadata": {
                    "source": "google_drive",
                    "file_name": file_info['name'], 
                    "file_id": file_info['id'],
                    "chunk_type": "detailed_content",
                    "modified_time": file_info['modified_time'],
                    "department": processing_result.department or "unknown",
                    **self._extract_metadata_from_entities(processing_result.business_entities)
                }
            })
        
        return documents
    
    def _create_file_overview(self, processing_result, file_info: Dict[str, Any]) -> str:
        """Create overview content for the file."""
        parts = []
        parts.append(f"Google Drive Excel File: {file_info['name']}")
        parts.append(f"Document Type: {processing_result.document_type.value}")
        parts.append(f"Department: {processing_result.department or 'General'}")
        parts.append(f"Business Priority: {processing_result.business_priority}")
        parts.append(f"Processing Confidence: {processing_result.confidence_score:.2f}")
        
        if processing_result.staff_involved:
            parts.append(f"Staff Mentioned: {', '.join(processing_result.staff_involved[:5])}")
        
        if processing_result.customers_mentioned:
            parts.append(f"Customers: {', '.join(processing_result.customers_mentioned[:5])}")
        
        extracted = processing_result.extracted_content
        if extracted:
            if extracted.get('total_sheets'):
                parts.append(f"Contains {extracted['total_sheets']} Excel sheets")
            if extracted.get('total_rows'):
                parts.append(f"Total data rows: {extracted['total_rows']}")
        
        parts.append("Precision Textile Industry Limited business document from Google Drive")
        
        return ". ".join(parts)
    
    def _create_entities_summary(self, processing_result, file_info: Dict[str, Any]) -> str:
        """Create business entities summary."""
        parts = []
        parts.append(f"Business Entities from {file_info['name']}")
        
        entities = processing_result.business_entities
        for entity_type, entity_list in entities.items():
            if entity_list:
                entity_name = entity_type.replace('_', ' ').title()
                parts.append(f"{entity_name}: {', '.join(entity_list[:10])}")
        
        parts.append("Extracted business intelligence from Excel file analysis")
        return ". ".join(parts)
    
    def _create_detailed_content(self, processing_result, file_info: Dict[str, Any]) -> str:
        """Create detailed content summary."""
        parts = []
        parts.append(f"Detailed Analysis of {file_info['name']}")
        
        extracted = processing_result.extracted_content
        if extracted.get('sheets'):
            sheets = list(extracted['sheets'].keys())
            parts.append(f"Excel sheets analyzed: {', '.join(sheets)}")
        
        if processing_result.normalized_data:
            if processing_result.normalized_data.get('currencies'):
                parts.append("Contains financial data with currency amounts")
            if processing_result.normalized_data.get('dates'):
                parts.append("Contains time-series data with date information")
        
        parts.append("Comprehensive business document analysis from Google Drive")
        return ". ".join(parts)
    
    def _extract_metadata_from_entities(self, business_entities: Dict[str, List[str]]) -> Dict[str, Any]:
        """Extract metadata from business entities for search filtering."""
        metadata = {}
        
        # Add entity lists for filtering
        for entity_type, entity_list in business_entities.items():
            if entity_list:
                metadata[entity_type] = entity_list[:10]  # Limit to 10 items
        
        # Add flags for quick filtering
        metadata.update({
            "has_customers": bool(business_entities.get('customers')),
            "has_staff": bool(business_entities.get('staff_members')),
            "has_amounts": bool(business_entities.get('amounts')),
            "has_dates": bool(business_entities.get('dates')),
            "entity_count": sum(len(entities) for entities in business_entities.values())
        })
        
        return metadata
    
    def _is_file_already_embedded(self, file_info: Dict[str, Any]) -> bool:
        """Check if file is already embedded in vector store."""
        try:
            # Search for existing documents from this file
            search_results = self.vector_store.search(
                query=f"file_id:{file_info['id']}",
                top_k=1
            )
            return len(search_results) > 0
        except Exception:
            return False
    
    async def update_modified_files(self, since_hours: int = 24) -> Dict[str, Any]:
        """Update embeddings only for files modified in the last N hours."""
        try:
            from datetime import timedelta
            
            since_time = datetime.now() - timedelta(hours=since_hours)
            
            # Find modified files
            modified_files = self.gdrive.find_modified_target_files_since(since_time)
            
            if not modified_files:
                return {
                    "status": "success",
                    "message": f"No files modified in last {since_hours} hours",
                    "files_updated": 0
                }
            
            logger.info(f"Found {len(modified_files)} modified files to update")
            
            # Process modified files
            updated_count = 0
            update_results = []
            
            for file_info in modified_files:
                try:
                    result = await self._process_excel_file_complete_pipeline(file_info)
                    update_results.append(result)
                    
                    if result["status"] == "success":
                        updated_count += 1
                        logger.info(f"Updated embeddings for: {file_info['name']}")
                except Exception as e:
                    logger.error(f"Failed to update {file_info['name']}: {str(e)}")
                    update_results.append({
                        "status": "failed",
                        "file_name": file_info['name'],
                        "error": str(e)
                    })
            
            return {
                "status": "success",
                "message": f"Updated {updated_count}/{len(modified_files)} modified files",
                "files_updated": updated_count,
                "update_results": update_results
            }
            
        except Exception as e:
            logger.error(f"Update process failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def test_search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Test search functionality on embedded Google Drive files."""
        try:
            logger.info(f"Testing search with query: '{query}'")
            
            # Search in vector store
            results = self.vector_store.search(query, top_k=top_k)
            
            # Categorize results
            gdrive_results = [r for r in results if r.get("metadata", {}).get("source") == "google_drive"]
            other_results = [r for r in results if r.get("metadata", {}).get("source") != "google_drive"]
            
            return {
                "status": "success",
                "query": query,
                "total_results": len(results),
                "google_drive_results": len(gdrive_results),
                "other_results": len(other_results),
                "results": results,
                "search_working": len(results) > 0,
                "gdrive_integration_working": len(gdrive_results) > 0
            }
            
        except Exception as e:
            logger.error(f"Search test failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "query": query
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        try:
            # Google Drive status
            gdrive_status = self.gdrive.test_connection()
            
            # Vector store status
            vector_stats = self.vector_store.get_stats()
            
            # Available files
            try:
                available_files = self.gdrive.find_target_files_anywhere()
                gdrive_file_count = len(available_files)
                gdrive_file_names = [f["name"] for f in available_files]
            except Exception as e:
                gdrive_file_count = 0
                gdrive_file_names = []
                logger.warning(f"Could not get file list: {e}")
            
            # Embedded files count
            gdrive_embedded_count = 0
            total_documents = len(self.vector_store.items)
            
            for item in self.vector_store.items:
                if item.get("metadata", {}).get("source") == "google_drive":
                    gdrive_embedded_count += 1
            
            return {
                "status": "operational",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "google_drive": {
                        "connected": gdrive_status.get('connected', False),
                        "available_files": gdrive_file_count,
                        "file_names": gdrive_file_names,
                        "error": gdrive_status.get('error') if not gdrive_status.get('connected') else None
                    },
                    "vector_store": {
                        "total_documents": total_documents,
                        "google_drive_documents": gdrive_embedded_count,
                        "other_documents": total_documents - gdrive_embedded_count,
                        "index_path": str(self.vector_store.index_path),
                        "embedding_dimension": vector_stats.get("embedding_dimension"),
                        "using_mock_embeddings": vector_stats.get("using_mock_embeddings")
                    },
                    "processing_pipeline": {
                        "document_processor": "ready",
                        "processing_bridge": "ready"
                    }
                },
                "integration_health": {
                    "files_available": gdrive_file_count,
                    "files_embedded": gdrive_embedded_count,
                    "embedding_coverage": (gdrive_embedded_count / max(gdrive_file_count, 1)) * 100,
                    "ready_for_chat": gdrive_embedded_count > 0
                },
                "last_processing_stats": self.stats
            }
            
        except Exception as e:
            logger.error(f"Status check failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Utility functions for easy usage
async def embed_all_google_drive_files(force_reprocess: bool = False) -> Dict[str, Any]:
    """Convenience function to embed all Google Drive files."""
    embedder = CompleteGDriveEmbedder()
    await embedder.initialize()
    return await embedder.embed_all_google_drive_files(force_reprocess=force_reprocess)


async def update_modified_google_drive_files(hours: int = 24) -> Dict[str, Any]:
    """Convenience function to update recently modified files."""
    embedder = CompleteGDriveEmbedder()
    await embedder.initialize()
    return await embedder.update_modified_files(since_hours=hours)


async def test_complete_integration() -> Dict[str, Any]:
    """Complete integration test."""
    try:
        logger.info("Starting complete Google Drive integration test...")
        
        embedder = CompleteGDriveEmbedder()
        await embedder.initialize()
        
        # Test 1: System status
        logger.info("Test 1: Checking system status...")
        status = await embedder.get_system_status()
        
        if status["status"] != "operational":
            return {
                "status": "failed",
                "test": "system_status",
                "error": status.get("error", "System not operational"),
                "details": status
            }
        
        # Test 2: Embed files (if any available)
        if status["components"]["google_drive"]["available_files"] > 0:
            logger.info("Test 2: Embedding available files...")
            embed_result = await embedder.embed_all_google_drive_files(force_reprocess=False)
            
            if embed_result["status"] != "success":
                return {
                    "status": "failed", 
                    "test": "embedding",
                    "error": embed_result.get("error", "Embedding failed"),
                    "details": embed_result
                }
        else:
            logger.info("Test 2: No files available to embed")
            embed_result = {"status": "skipped", "message": "No files available"}
        
        # Test 3: Search test
        logger.info("Test 3: Testing search functionality...")
        search_result = await embedder.test_search("financial data cash payment")
        
        if search_result["status"] != "success":
            return {
                "status": "failed",
                "test": "search",
                "error": search_result.get("error", "Search failed"),
                "details": search_result
            }
        
        return {
            "status": "success",
            "message": "Complete Google Drive integration test successful",
            "system_status": status,
            "embedding_result": embed_result,
            "search_result": search_result,
            "integration_ready": True,
            "chat_system_ready": search_result.get("gdrive_integration_working", False)
        }
        
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Complete Google Drive Vector Integration")
    parser.add_argument("--embed-all", action="store_true", help="Embed all Google Drive files")
    parser.add_argument("--update", type=int, default=24, help="Update files modified in last N hours")
    parser.add_argument("--test", action="store_true", help="Run complete integration test")
    parser.add_argument("--status", action="store_true", help="Check system status")
    parser.add_argument("--search", type=str, help="Test search with query")
    parser.add_argument("--force", action="store_true", help="Force reprocessing of files")
    
    args = parser.parse_args()
    
    async def main():
        embedder = CompleteGDriveEmbedder()
        await embedder.initialize()
        
        if args.embed_all:
            result = await embedder.embed_all_google_drive_files(force_reprocess=args.force)
            print(json.dumps(result, indent=2, default=str))
        
        elif args.update:
            result = await embedder.update_modified_files(since_hours=args.update)
            print(json.dumps(result, indent=2, default=str))
        
        elif args.test:
            result = await test_complete_integration()
            print(json.dumps(result, indent=2, default=str))
        
        elif args.status:
            result = await embedder.get_system_status()
            print(json.dumps(result, indent=2, default=str))
        
        elif args.search:
            result = await embedder.test_search(args.search)
            print(json.dumps(result, indent=2, default=str))
        
        else:
            print("Usage: python complete_gdrive_embedder.py [--embed-all|--update N|--test|--status|--search 'query'] [--force]")
            print("\nQuick start:")
            print("1. python complete_gdrive_embedder.py --status")
            print("2. python complete_gdrive_embedder.py --embed-all")
            print("3. python complete_gdrive_embedder.py --search 'cash payment RB Knit'")
    
    asyncio.run(main())