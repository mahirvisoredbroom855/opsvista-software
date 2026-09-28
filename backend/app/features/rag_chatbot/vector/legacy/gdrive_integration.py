# backend/app/features/rag_chatbot/vector/gdrive_integration.py
"""
Google Drive to Vector Store Integration

This script connects your Google Drive service to the vector database,
processing Excel and document files for RAG search integration.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import pandas as pd
from io import BytesIO

# Import your existing services
from app.features.rag_chatbot.vector.persisted_inmemory_search import PersistedInMemorySearch
from .google_drive_service import GoogleDriveService


logger = logging.getLogger(__name__)


class GoogleDriveVectorIntegration:
    """
    Integrates Google Drive documents with your vector search system.
    
    This class:
    1. Scans Google Drive for target files
    2. Downloads and processes Excel files
    3. Converts content to searchable text chunks
    4. Adds them to your vector store
    5. Enables chat system to search Google Drive documents
    """
    
    def __init__(self, 
                 credentials_path: str = None,
                 vector_index_path: str = None):
        
        # Initialize Google Drive service
        creds_path = credentials_path or "credentials/google_credentials.json"
        self.gdrive = GoogleDriveService(creds_path)
        
        # Initialize vector store
        index_path = vector_index_path or os.getenv("RAG_INDEX_PATH", "backend/app/features/rag_chatbot/vector/.index.json")
        self.vector_store = PersistedInMemorySearch(index_path)
        
        # Processing stats
        self.stats = {
            "files_processed": 0,
            "documents_added": 0,
            "errors": 0,
            "start_time": None
        }
        
        logger.info("Google Drive Vector Integration initialized")
    
    async def index_all_target_files(self) -> Dict[str, Any]:
        """
        Main method to index all target finance files from Google Drive.
        """
        try:
            self.stats["start_time"] = datetime.now()
            logger.info("Starting Google Drive indexing process...")
            
            # Step 1: Find target files in Google Drive
            logger.info("Step 1: Finding target files in Google Drive...")
            target_files = self.gdrive.find_target_files_anywhere()
            
            if not target_files:
                logger.warning("No target files found in Google Drive")
                return {
                    "status": "warning",
                    "message": "No target files found",
                    "stats": self.stats
                }
            
            logger.info(f"Found {len(target_files)} target files")
            
            # Step 2: Process each file
            logger.info("Step 2: Processing files...")
            total_documents = 0
            
            for file_info in target_files:
                try:
                    logger.info(f"Processing: {file_info['name']}")
                    
                    # Download file
                    file_content = self.gdrive.download_file(file_info['id'])
                    
                    if not file_content:
                        logger.error(f"Failed to download: {file_info['name']}")
                        self.stats["errors"] += 1
                        continue
                    
                    # Process file content
                    documents = await self._process_excel_file(file_content, file_info)
                    
                    if documents:
                        # Add to vector store
                        self.vector_store.ingest_documents(documents)
                        total_documents += len(documents)
                        logger.info(f"Added {len(documents)} documents from {file_info['name']}")
                    
                    self.stats["files_processed"] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing {file_info['name']}: {e}")
                    self.stats["errors"] += 1
                    continue
            
            # Step 3: Update stats and return results
            self.stats["documents_added"] = total_documents
            processing_time = (datetime.now() - self.stats["start_time"]).total_seconds()
            
            result = {
                "status": "success",
                "message": f"Indexed {len(target_files)} files, added {total_documents} documents",
                "stats": {
                    **self.stats,
                    "processing_time_seconds": processing_time
                },
                "files_processed": [f["name"] for f in target_files]
            }
            
            logger.info(f"Indexing complete: {result['message']}")
            return result
            
        except Exception as e:
            logger.error(f"Google Drive indexing failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "stats": self.stats
            }
    
    async def _process_excel_file(self, file_content: bytes, file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process an Excel file into searchable document chunks.
        """
        try:
            # Read Excel file
            excel_data = BytesIO(file_content)
            
            # Try to read all sheets
            try:
                all_sheets = pd.read_excel(excel_data, sheet_name=None, dtype=str)
            except Exception as e:
                logger.warning(f"Could not read all sheets from {file_info['name']}: {e}")
                # Try reading just the first sheet
                all_sheets = {"Sheet1": pd.read_excel(excel_data, dtype=str)}
            
            documents = []
            
            # Process each sheet
            for sheet_name, df in all_sheets.items():
                if df.empty:
                    continue
                
                # Clean the dataframe
                df = df.dropna(how='all').dropna(axis=1, how='all')
                
                if df.empty:
                    continue
                
                # Convert to text representation
                sheet_documents = self._dataframe_to_documents(
                    df, file_info, sheet_name
                )
                documents.extend(sheet_documents)
            
            logger.info(f"Processed {file_info['name']}: {len(documents)} documents created")
            return documents
            
        except Exception as e:
            logger.error(f"Error processing Excel file {file_info['name']}: {e}")
            return []
    
    def _dataframe_to_documents(self, df: pd.DataFrame, file_info: Dict[str, Any], sheet_name: str) -> List[Dict[str, Any]]:
        """
        Convert a pandas DataFrame to searchable document chunks.
        """
        documents = []
        
        try:
            # Strategy 1: Row-based chunks (for transaction data)
            if len(df) > 1:  # Has multiple rows
                # Create chunks of rows
                chunk_size = 10  # Process 10 rows at a time
                
                for i in range(0, len(df), chunk_size):
                    chunk_df = df.iloc[i:i+chunk_size]
                    
                    # Convert chunk to readable text
                    text_content = self._format_dataframe_as_text(chunk_df, file_info['name'], sheet_name)
                    
                    if text_content.strip():
                        document = {
                            "id": f"{file_info['id']}_{sheet_name}_{i}",
                            "text": text_content,
                            "metadata": {
                                "source": "google_drive",
                                "file_name": file_info['name'],
                                "file_id": file_info['id'],
                                "sheet_name": sheet_name,
                                "chunk_index": i // chunk_size,
                                "modified_time": file_info['modified_time'],
                                "department": "finance",
                                "document_type": "excel_data",
                                "row_range": f"{i+1}-{min(i+chunk_size, len(df))}"
                            }
                        }
                        documents.append(document)
            
            # Strategy 2: Summary document
            summary_text = self._create_summary_document(df, file_info['name'], sheet_name)
            if summary_text:
                summary_doc = {
                    "id": f"{file_info['id']}_{sheet_name}_summary",
                    "text": summary_text,
                    "metadata": {
                        "source": "google_drive",
                        "file_name": file_info['name'],
                        "file_id": file_info['id'],
                        "sheet_name": sheet_name,
                        "chunk_index": -1,  # Summary
                        "modified_time": file_info['modified_time'],
                        "department": "finance",
                        "document_type": "excel_summary",
                        "total_rows": len(df)
                    }
                }
                documents.append(summary_doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error converting dataframe to documents: {e}")
            return []
    
    def _format_dataframe_as_text(self, df: pd.DataFrame, file_name: str, sheet_name: str) -> str:
        """
        Format a DataFrame chunk as readable text for vector search.
        """
        try:
            lines = []
            lines.append(f"Document: {file_name}")
            lines.append(f"Sheet: {sheet_name}")
            lines.append("")
            
            # Add column headers
            headers = [str(col) for col in df.columns if str(col) != 'nan']
            if headers:
                lines.append("Columns: " + " | ".join(headers))
                lines.append("")
            
            # Add row data
            for idx, row in df.iterrows():
                row_parts = []
                for col in df.columns:
                    value = row[col]
                    if pd.notna(value) and str(value).strip():
                        col_name = str(col) if str(col) != 'nan' else f"Col{df.columns.get_loc(col)}"
                        row_parts.append(f"{col_name}: {str(value).strip()}")
                
                if row_parts:
                    lines.append("Row " + str(idx + 1) + " - " + " | ".join(row_parts))
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error formatting dataframe: {e}")
            return ""
    
    def _create_summary_document(self, df: pd.DataFrame, file_name: str, sheet_name: str) -> str:
        """
        Create a summary document for the entire sheet.
        """
        try:
            lines = []
            lines.append(f"Financial Document Summary: {file_name}")
            lines.append(f"Sheet: {sheet_name}")
            lines.append("")
            
            # Basic stats
            lines.append(f"Total Records: {len(df)}")
            lines.append(f"Columns: {len(df.columns)}")
            lines.append("")
            
            # Column information
            lines.append("Available Data Fields:")
            for col in df.columns:
                if str(col) != 'nan':
                    non_null_count = df[col].count()
                    lines.append(f"- {col}: {non_null_count} entries")
            
            lines.append("")
            
            # Try to identify key financial information
            financial_keywords = ['amount', 'cost', 'price', 'total', 'balance', 'payment', 'expense', 'income', 'revenue']
            
            for col in df.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in financial_keywords):
                    try:
                        # Try to get numeric summary
                        numeric_data = pd.to_numeric(df[col], errors='coerce')
                        if not numeric_data.isna().all():
                            total = numeric_data.sum()
                            lines.append(f"Total {col}: {total:,.2f}")
                    except:
                        pass
            
            # Try to identify common business entities
            business_entities = []
            for col in df.columns:
                col_str = str(col).lower()
                if 'customer' in col_str or 'client' in col_str or 'party' in col_str:
                    unique_values = df[col].dropna().unique()[:5]  # Top 5
                    business_entities.extend([str(v) for v in unique_values if str(v) != 'nan'])
            
            if business_entities:
                lines.append("")
                lines.append("Key Business Entities: " + ", ".join(business_entities))
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error creating summary: {e}")
            return ""
    
    async def get_indexing_status(self) -> Dict[str, Any]:
        """
        Get the current status of Google Drive indexing.
        """
        try:
            # Get vector store stats
            vector_stats = self.vector_store.get_stats()
            
            # Check Google Drive connection
            gdrive_status = self.gdrive.test_connection()
            
            # Find available target files
            target_files = self.gdrive.find_target_files_anywhere()
            
            return {
                "status": "operational",
                "google_drive_connection": gdrive_status,
                "vector_store": vector_stats,
                "available_target_files": len(target_files),
                "target_file_names": [f["name"] for f in target_files],
                "last_processing_stats": self.stats
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def search_test(self, query: str) -> Dict[str, Any]:
        """
        Test search functionality across both local and Google Drive documents.
        """
        try:
            # Search in vector store
            results = self.vector_store.search(query, top_k=5)
            
            # Categorize results by source
            local_results = [r for r in results if r.get("metadata", {}).get("source") != "google_drive"]
            gdrive_results = [r for r in results if r.get("metadata", {}).get("source") == "google_drive"]
            
            return {
                "status": "success",
                "query": query,
                "total_results": len(results),
                "local_documents": len(local_results),
                "google_drive_documents": len(gdrive_results),
                "results": results
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "query": query
            }


# Standalone functions for easy testing
async def index_google_drive_files() -> Dict[str, Any]:
    """
    Standalone function to index Google Drive files.
    """
    integration = GoogleDriveVectorIntegration()
    return await integration.index_all_target_files()


async def test_gdrive_integration() -> Dict[str, Any]:
    """
    Test the complete Google Drive integration.
    """
    try:
        logger.info("Testing Google Drive Integration...")
        
        integration = GoogleDriveVectorIntegration()
        
        # Test 1: Check status
        logger.info("Test 1: Checking system status...")
        status = await integration.get_indexing_status()
        
        if status["status"] != "operational":
            return {
                "status": "failed",
                "test": "status_check",
                "error": status.get("error", "System not operational")
            }
        
        # Test 2: Index files (if any available)
        if status["available_target_files"] > 0:
            logger.info("Test 2: Indexing available files...")
            index_result = await integration.index_all_target_files()
            
            if index_result["status"] != "success":
                return {
                    "status": "failed", 
                    "test": "indexing",
                    "error": index_result.get("error", "Indexing failed")
                }
        else:
            logger.info("Test 2: No target files available to index")
            index_result = {"status": "skipped", "message": "No target files available"}
        
        # Test 3: Search test
        logger.info("Test 3: Testing search functionality...")
        search_result = await integration.search_test("financial data")
        
        if search_result["status"] != "success":
            return {
                "status": "failed",
                "test": "search",
                "error": search_result.get("error", "Search failed")
            }
        
        return {
            "status": "success",
            "message": "Google Drive integration test completed successfully",
            "system_status": status,
            "indexing_result": index_result,
            "search_result": search_result
        }
        
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# Command line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Google Drive Vector Integration")
    parser.add_argument("--index", action="store_true", help="Index all target files")
    parser.add_argument("--test", action="store_true", help="Run integration test")
    parser.add_argument("--status", action="store_true", help="Check system status")
    parser.add_argument("--search", type=str, help="Test search with query")
    
    args = parser.parse_args()
    
    async def main():
        integration = GoogleDriveVectorIntegration()
        
        if args.index:
            result = await integration.index_all_target_files()
            print(json.dumps(result, indent=2))
        
        elif args.test:
            result = await test_gdrive_integration()
            print(json.dumps(result, indent=2))
        
        elif args.status:
            result = await integration.get_indexing_status()
            print(json.dumps(result, indent=2))
        
        elif args.search:
            result = await integration.search_test(args.search)
            print(json.dumps(result, indent=2))
        
        else:
            print("Usage: python gdrive_integration.py [--index|--test|--status|--search 'query']")
    
    asyncio.run(main())