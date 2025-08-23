# backend/gdrive_to_enhanced_index.py
"""
Google Drive to Enhanced Index Embedder
Creates 1536-dimensional embeddings from Google Drive Excel files
Outputs in enhanced_index.json format
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from io import BytesIO
import uuid

# Import your existing components
from app.features.rag_chatbot.processing.document_processing_engine import DocumentProcessingOrchestrator
from app.features.rag_chatbot.vector.google_drive_service import GoogleDriveService

# Set up for 1536-dimensional embeddings
os.environ["USE_MOCK_EMBEDDINGS"] = "false"
os.environ["OPENAI_EMBEDDING_MODEL"] = "text-embedding-3-small"

logger = logging.getLogger(__name__)


class GoogleDriveEnhancedEmbedder:
    """
    Complete Google Drive to Enhanced Index embedder.
    Processes Excel files from Google Drive using Task 1C pipeline
    and creates 1536-dimensional embeddings in enhanced_index.json format.
    """
    
    def __init__(self, 
                 credentials_path: str = None,
                 output_index: str = None):
        
        # Initialize Google Drive service
        creds_path = credentials_path or self._find_credentials_path()
        if not creds_path or not Path(creds_path).exists():
            raise FileNotFoundError(f"Google credentials not found. Checked: {creds_path}")
        
        self.gdrive = GoogleDriveService(creds_path)
        
        # Initialize processing pipeline
        self.processor = DocumentProcessingOrchestrator()
        
        # Output path for enhanced index
        self.output_path = Path(output_index or "backend/app/features/rag_chatbot/vector/enhanced_index.json")
        
        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Processing stats
        self.stats = {
            "files_discovered": 0,
            "files_processed": 0,
            "documents_created": 0,
            "embeddings_stored": 0,
            "processing_time": 0.0
        }
        
        logger.info(f"Google Drive Enhanced Embedder initialized")
        logger.info(f"Credentials: {creds_path}")
        logger.info(f"Output: {self.output_path}")
    
    def _find_credentials_path(self) -> str:
        """Find Google credentials file."""
        possible_paths = [
            "credentials/google_credentials.json",          # From backend/
            "../credentials/google_credentials.json",       # From app/
            "backend/credentials/google_credentials.json",  # From repo root
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                return path
        
        return "credentials/google_credentials.json"  # Default
    
    async def create_enhanced_index_from_gdrive(self, 
                                               base_folder: str = "Md. Mizanur Rahman (PTIL)",
                                               force_reprocess: bool = False) -> Dict[str, Any]:
        """
        Main method: Create enhanced_index.json from Google Drive files.
        """
        start_time = datetime.now()
        
        try:
            logger.info("Starting Google Drive to Enhanced Index process...")
            
            # Step 1: Test Google Drive connection
            gdrive_status = self.gdrive.test_connection()
            if not gdrive_status.get('connected'):
                raise Exception(f"Google Drive connection failed: {gdrive_status.get('error')}")
            
            logger.info("Google Drive connection successful")
            
            # Step 2: Find target Excel files
            logger.info(f"Finding target files in Google Drive folder: {base_folder}")
            target_files = self.gdrive.find_target_files_anywhere(base_folder)
            
            if not target_files:
                return {
                    "status": "warning",
                    "message": f"No target files found in Google Drive folder '{base_folder}'",
                    "suggestion": "Check if the folder exists and contains Cash Book, Party Due Bill, or PTIL Expenditure files"
                }
            
            self.stats["files_discovered"] = len(target_files)
            logger.info(f"Found {len(target_files)} target files")
            
            # Step 3: Process each file through pipeline
            all_documents = []
            all_metadata = []
            
            for file_info in target_files:
                try:
                    logger.info(f"Processing: {file_info['name']}")
                    
                    # Download file
                    file_content = self.gdrive.download_file(file_info['id'])
                    if not file_content:
                        logger.error(f"Failed to download: {file_info['name']}")
                        continue
                    
                    # Process through Task 1C pipeline
                    processing_result = await self.processor.process_document(
                        file_path=file_info['name'],
                        file_data=BytesIO(file_content),
                        file_type='excel'
                    )
                    
                    if processing_result.status.value == 'completed':
                        # Convert to documents and metadata
                        documents, metadata = self._convert_to_enhanced_format(processing_result, file_info)
                        all_documents.extend(documents)
                        all_metadata.extend(metadata)
                        
                        self.stats["files_processed"] += 1
                        self.stats["documents_created"] += len(documents)
                        
                        logger.info(f"Created {len(documents)} documents from {file_info['name']}")
                    else:
                        logger.error(f"Processing failed for {file_info['name']}: {processing_result.errors}")
                        
                except Exception as e:
                    logger.error(f"Error processing {file_info['name']}: {e}")
                    continue
            
            # Step 4: Create embeddings
            if all_documents:
                logger.info(f"Creating 1536-dimensional embeddings for {len(all_documents)} documents...")
                embeddings = await self._create_openai_embeddings(all_documents)
                
                if len(embeddings) != len(all_documents):
                    raise Exception(f"Embedding count mismatch: {len(embeddings)} vs {len(all_documents)}")
                
                self.stats["embeddings_stored"] = len(embeddings)
                
                # Step 5: Save in enhanced_index.json format
                enhanced_index = self._create_enhanced_index_structure(
                    documents=all_documents,
                    embeddings=embeddings,
                    metadata=all_metadata
                )
                
                self._save_enhanced_index(enhanced_index)
                
                processing_time = (datetime.now() - start_time).total_seconds()
                self.stats["processing_time"] = processing_time
                
                return {
                    "status": "success",
                    "message": f"Created enhanced index with {len(all_documents)} documents from {self.stats['files_processed']} Google Drive files",
                    "stats": self.stats,
                    "files_processed": [f["name"] for f in target_files[:self.stats["files_processed"]]],
                    "output_file": str(self.output_path),
                    "embedding_info": {
                        "model": "text-embedding-3-small",
                        "dimensions": 1536,
                        "total_embeddings": len(embeddings)
                    },
                    "next_steps": [
                        f"Enhanced index saved to {self.output_path}",
                        "Start server with: uvicorn app.main:app --reload",
                        "Test search with: curl -X GET 'http://localhost:8000/api/rag/chat/_retrieve?q=financial+data'"
                    ]
                }
            else:
                return {
                    "status": "warning",
                    "message": "No documents were created from the processed files",
                    "stats": self.stats
                }
                
        except Exception as e:
            logger.error(f"Enhanced index creation failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "stats": self.stats
            }
    
    def _convert_to_enhanced_format(self, processing_result, file_info: Dict[str, Any]) -> tuple[List[str], List[Dict[str, Any]]]:
        """
        Convert processing result to enhanced index format.
        Returns: (documents_list, metadata_list)
        """
        documents = []
        metadata = []
        
        # Document 1: File Overview
        overview_text = self._create_overview_document(processing_result, file_info)
        documents.append(overview_text)
        metadata.append({
            "id": f"gdrive_{file_info['id']}_overview",
            "source": "google_drive",
            "file_name": file_info['name'],
            "file_id": file_info['id'],
            "chunk_type": "overview",
            "document_type": processing_result.document_type.value,
            "department": processing_result.department or "finance",
            "business_priority": processing_result.business_priority,
            "confidence_score": processing_result.confidence_score,
            "staff_involved": processing_result.staff_involved[:5],  # Limit for JSON size
            "customers_mentioned": processing_result.customers_mentioned[:5],
            "created_at": datetime.now().isoformat(),
            "modified_time": file_info.get('modified_time')
        })
        
        # Document 2: Business Entities Summary
        if processing_result.business_entities:
            entities_text = self._create_entities_document(processing_result, file_info)
            documents.append(entities_text)
            metadata.append({
                "id": f"gdrive_{file_info['id']}_entities",
                "source": "google_drive",
                "file_name": file_info['name'],
                "file_id": file_info['id'],
                "chunk_type": "business_entities",
                "department": processing_result.department or "finance",
                "business_entities": processing_result.business_entities,
                "created_at": datetime.now().isoformat()
            })
        
        # Document 3: Financial Data Summary
        financial_text = self._create_financial_document(processing_result, file_info)
        documents.append(financial_text)
        metadata.append({
            "id": f"gdrive_{file_info['id']}_financial",
            "source": "google_drive", 
            "file_name": file_info['name'],
            "file_id": file_info['id'],
            "chunk_type": "financial_summary",
            "department": "finance",
            "has_amounts": bool(processing_result.business_entities.get('amounts')),
            "has_dates": bool(processing_result.business_entities.get('dates')),
            "created_at": datetime.now().isoformat()
        })
        
        return documents, metadata
    
    def _create_overview_document(self, processing_result, file_info: Dict[str, Any]) -> str:
        """Create comprehensive overview document."""
        parts = [
            f"Google Drive Excel File: {file_info['name']}",
            f"Document Type: {processing_result.document_type.value}",
            f"Department: {processing_result.department or 'Finance'}",
            f"Business Priority: {processing_result.business_priority}",
            f"Processing Confidence: {processing_result.confidence_score:.2f}"
        ]
        
        if processing_result.staff_involved:
            parts.append(f"Staff Members: {', '.join(processing_result.staff_involved[:5])}")
        
        if processing_result.customers_mentioned:
            parts.append(f"Customers: {', '.join(processing_result.customers_mentioned[:5])}")
        
        extracted = processing_result.extracted_content
        if extracted:
            if extracted.get('total_sheets'):
                parts.append(f"Excel Sheets: {extracted['total_sheets']}")
            if extracted.get('total_rows'):
                parts.append(f"Data Rows: {extracted['total_rows']}")
        
        parts.append("This is a Precision Textile Industry Limited financial document from Google Drive containing business operations data.")
        
        return " ".join(parts)
    
    def _create_entities_document(self, processing_result, file_info: Dict[str, Any]) -> str:
        """Create business entities document."""
        parts = [f"Business Intelligence extracted from {file_info['name']}:"]
        
        entities = processing_result.business_entities
        for entity_type, entity_list in entities.items():
            if entity_list:
                entity_name = entity_type.replace('_', ' ').title()
                parts.append(f"{entity_name}: {', '.join(entity_list[:8])}")
        
        parts.append("This data represents key business relationships and financial transactions for textile manufacturing operations.")
        
        return " ".join(parts)
    
    def _create_financial_document(self, processing_result, file_info: Dict[str, Any]) -> str:
        """Create financial data document."""
        parts = [f"Financial analysis of {file_info['name']}:"]
        
        # Add normalized financial data
        if processing_result.normalized_data:
            normalized = processing_result.normalized_data
            if normalized.get('currencies'):
                currency_info = normalized['currencies'][:3]  # First 3 currencies
                currency_text = ", ".join([f"{c.get('formatted_amount', '')} {c.get('currency', '')}" for c in currency_info])
                parts.append(f"Currency amounts found: {currency_text}")
            
            if normalized.get('dates'):
                date_info = normalized['dates'][:3]  # First 3 dates
                date_text = ", ".join([d.get('formatted_date', '') for d in date_info])
                parts.append(f"Transaction dates: {date_text}")
        
        # Add business context
        if file_info['name'].lower().find('cash') != -1:
            parts.append("Cash book entries tracking daily financial transactions, payments, and receipts.")
        elif file_info['name'].lower().find('due') != -1:
            parts.append("Customer due bill tracking outstanding payments and account balances.")
        elif file_info['name'].lower().find('expenditure') != -1:
            parts.append("Expenditure records for LC operations and business expenses.")
        
        parts.append("Financial data for textile business operations including customer transactions, staff payments, and operational expenses.")
        
        return " ".join(parts)
    
    async def _create_openai_embeddings(self, documents: List[str]) -> List[List[float]]:
        """Create 1536-dimensional embeddings using OpenAI."""
        try:
            from openai import OpenAI
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise Exception("OPENAI_API_KEY environment variable not set")
            
            client = OpenAI(api_key=api_key)
            
            logger.info(f"Creating embeddings for {len(documents)} documents using text-embedding-3-small...")
            
            # Process in batches to handle rate limits
            embeddings = []
            batch_size = 100
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}/{(len(documents) + batch_size - 1)//batch_size}")
                
                response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=batch,
                    dimensions=1536
                )
                
                batch_embeddings = [d.embedding for d in response.data]
                embeddings.extend(batch_embeddings)
                
                # Brief pause between batches
                if i + batch_size < len(documents):
                    await asyncio.sleep(0.1)
            
            logger.info(f"Created {len(embeddings)} embeddings with {len(embeddings[0]) if embeddings else 0} dimensions")
            return embeddings
            
        except Exception as e:
            logger.error(f"OpenAI embedding creation failed: {e}")
            raise
    
    def _create_enhanced_index_structure(self, 
                                       documents: List[str], 
                                       embeddings: List[List[float]], 
                                       metadata: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create enhanced_index.json structure."""
        return {
            "version": "2.0",
            "embedding_model": "text-embedding-3-small", 
            "embedding_dim": 1536,
            "created_at": datetime.now().isoformat(),
            "total_documents": len(documents),
            "source": "google_drive_task1c_pipeline",
            "documents": documents,
            "embeddings": embeddings,
            "metadata": metadata
        }
    
    def _save_enhanced_index(self, enhanced_index: Dict[str, Any]):
        """Save enhanced index to file."""
        try:
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(enhanced_index, f, indent=1, ensure_ascii=False)
            
            file_size = self.output_path.stat().st_size / 1024 / 1024  # MB
            logger.info(f"Enhanced index saved: {self.output_path} ({file_size:.2f} MB)")
            
        except Exception as e:
            logger.error(f"Failed to save enhanced index: {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        try:
            gdrive_status = self.gdrive.test_connection()
            
            # Check if output file exists
            output_exists = self.output_path.exists()
            output_size = self.output_path.stat().st_size if output_exists else 0
            
            return {
                "google_drive": gdrive_status,
                "output_file": {
                    "path": str(self.output_path),
                    "exists": output_exists,
                    "size_mb": output_size / 1024 / 1024 if output_exists else 0
                },
                "processing_stats": self.stats,
                "openai_key_available": bool(os.getenv("OPENAI_API_KEY"))
            }
            
        except Exception as e:
            return {"error": str(e)}


# CLI interface
async def main():
    """Main CLI function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Google Drive to Enhanced Index Embedder")
    parser.add_argument("--folder", default="Md. Mizanur Rahman (PTIL)", 
                       help="Google Drive base folder name")
    parser.add_argument("--output", help="Output index file path")
    parser.add_argument("--credentials", help="Google credentials JSON file path")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--force", action="store_true", help="Force reprocessing")
    
    args = parser.parse_args()
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable not set")
        print("Please set it with: export OPENAI_API_KEY='your-api-key'")
        return
    
    try:
        embedder = GoogleDriveEnhancedEmbedder(
            credentials_path=args.credentials,
            output_index=args.output
        )
        
        if args.status:
            status = embedder.get_status()
            print(json.dumps(status, indent=2))
            return
        
        # Create enhanced index
        result = await embedder.create_enhanced_index_from_gdrive(
            base_folder=args.folder,
            force_reprocess=args.force
        )
        
        print(json.dumps(result, indent=2, default=str))
        
        if result["status"] == "success":
            print("\n" + "="*60)
            print("SUCCESS! Enhanced index created from Google Drive")
            print("="*60)
            print(f"Files processed: {result['stats']['files_processed']}")
            print(f"Documents created: {result['stats']['documents_created']}")
            print(f"Embeddings: {result['embedding_info']['total_embeddings']} x {result['embedding_info']['dimensions']}")
            print(f"Output: {result['output_file']}")
            print("\nNext steps:")
            for step in result['next_steps']:
                print(f"  - {step}")
                
    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(main())