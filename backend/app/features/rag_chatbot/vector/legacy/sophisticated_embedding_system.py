#!/usr/bin/env python3
"""
Sophisticated Embedding System with Complete RAG Integration
Leverages all existing processors: document analysis, intelligent chunking, and business patterns
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
from uuid import uuid4

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Import your sophisticated processing pipeline
import pandas as pd
from google_drive_service import GoogleDriveService

# Import existing processors based on the tree structure
import sys
sys.path.append('../processing')
sys.path.append('../chunking')
sys.path.append('../discovery')
sys.path.append('../models')

try:
    from document_processing_engine import DocumentProcessingOrchestrator, create_document_processor
    from chunking_framework import IntelligentChunkingOrchestrator, create_chunking_orchestrator
    from analyzer import ExcelStructureAnalyzer, PDFClassifier
    from classifier import DocumentTypeClassifier
    from schemas import (
        FileType, DocumentCategory, AnalysisStatus, 
        ExcelAnalysisResult, PDFAnalysisResult, 
        DocumentInventoryResponse
    )
    PROCESSORS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import processors: {e}")
    PROCESSORS_AVAILABLE = False

logger = logging.getLogger(__name__)

class SophisticatedEmbeddingSystem:
    """
    Advanced embedding system that leverages the complete RAG processing pipeline.
    
    Integration Flow:
    1. GoogleDriveService -> Document Discovery
    2. DocumentProcessingOrchestrator -> Excel/PDF Analysis
    3. IntelligentChunkingOrchestrator -> Business-Aware Chunking
    4. Enhanced Embeddings -> 1536-dim OpenAI with Rich Metadata
    5. Vector Storage -> Unified Database with Business Intelligence
    """
    
    def __init__(self, 
                 credentials_path: str = None,
                 index_path: str = None,
                 openai_api_key: str = None):
        
        # Initialize OpenAI client
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for sophisticated embedding system")
        
        if not OPENAI_AVAILABLE:
            raise ValueError("OpenAI library not available. Run: pip install openai")
        
        self.openai_client = OpenAI(api_key=self.api_key)
        self.embedding_model = "text-embedding-3-small"  # 1536 dimensions
        self.embedding_dim = 1536
        
        # Initialize Google Drive service with auto-detection
        if not credentials_path:
            possible_paths = [
                "credentials/google_credentials.json",
                "../credentials/google_credentials.json", 
                "../../credentials/google_credentials.json",
                "../../../credentials/google_credentials.json",
                "../../../../credentials/google_credentials.json",
                "../../../../../credentials/google_credentials.json"
            ]
            creds_path = None
            for path in possible_paths:
                if Path(path).exists():
                    creds_path = path
                    break
            if not creds_path:
                raise FileNotFoundError("Google credentials not found. Please provide --credentials path")
        else:
            creds_path = credentials_path
            
        self.gdrive = GoogleDriveService(creds_path)
        
        # Initialize sophisticated processing pipeline
        if PROCESSORS_AVAILABLE:
            self.document_processor = create_document_processor()
            self.chunking_orchestrator = create_chunking_orchestrator()
            self.excel_analyzer = ExcelStructureAnalyzer()
            self.pdf_classifier = PDFClassifier()
            self.document_classifier = DocumentTypeClassifier(creds_path, None)
        else:
            logger.warning("Advanced processors not available - using fallback processing")
            self.document_processor = None
            self.chunking_orchestrator = None
        
        # Initialize enhanced vector store
        self.index_path = Path(index_path or "backend/app/features/rag_chatbot/vector/.sophisticated_index.json")
        self.documents = []
        self.embeddings = []
        self.metadata = []
        self.business_intelligence = []
        
        # Processing configuration
        self.batch_size = 30  # Optimal for OpenAI rate limits
        self.rate_limit_delay = 0.05  # Faster processing
        
        # Enable comprehensive logging
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Load existing sophisticated index
        self._load_sophisticated_index()
        
        logger.info(f"Sophisticated Embedding System initialized with {len(self.documents)} existing documents")
    
    def _load_sophisticated_index(self):
        """Load existing sophisticated index with full metadata."""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Validate sophisticated index format
                if (data.get('embedding_dim') == self.embedding_dim and 
                    data.get('embedding_model') == self.embedding_model and
                    data.get('version') == '3.0'):
                    
                    self.documents = data.get('documents', [])
                    self.embeddings = data.get('embeddings', [])
                    self.metadata = data.get('metadata', [])
                    self.business_intelligence = data.get('business_intelligence', [])
                    
                    logger.info(f"Loaded sophisticated index with {len(self.documents)} documents")
                else:
                    logger.warning("Existing index incompatible with sophisticated system, starting fresh")
                    self._clear_index()
            except Exception as e:
                logger.error(f"Error loading sophisticated index: {e}, starting fresh")
                self._clear_index()
    
    def _clear_index(self):
        """Clear the current index."""
        self.documents = []
        self.embeddings = []
        self.metadata = []
        self.business_intelligence = []
    
    def _save_sophisticated_index(self):
        """Save the sophisticated index with complete metadata."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        index_data = {
            'version': '3.0',
            'system_type': 'sophisticated_rag_embedding',
            'embedding_model': self.embedding_model,
            'embedding_dim': self.embedding_dim,
            'created_at': datetime.now().isoformat(),
            'total_documents': len(self.documents),
            'pipeline_features': [
                'document_processing_engine',
                'intelligent_chunking',
                'business_pattern_recognition',
                'content_normalization',
                'relationship_mapping'
            ],
            'documents': self.documents,
            'embeddings': self.embeddings,
            'metadata': self.metadata,
            'business_intelligence': self.business_intelligence
        }
        
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2)
        
        logger.info(f"Saved sophisticated index with {len(self.documents)} documents and rich metadata")
    
    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate OpenAI embeddings with intelligent batching and error handling."""
        all_embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            try:
                logger.info(f"Generating embeddings for batch {i//self.batch_size + 1}/{(len(texts)-1)//self.batch_size + 1} ({len(batch)} texts)")
                
                response = self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=batch
                )
                
                batch_embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # Intelligent rate limiting
                if i + self.batch_size < len(texts):
                    await asyncio.sleep(self.rate_limit_delay)
                
            except Exception as e:
                logger.error(f"Error generating embeddings for batch {i//self.batch_size + 1}: {e}")
                # Add zero vectors for failed batches to maintain alignment
                zero_vector = [0.0] * self.embedding_dim
                all_embeddings.extend([zero_vector] * len(batch))
        
        return all_embeddings
    
    def _document_exists(self, doc_id: str) -> bool:
        """Check if a document already exists in the sophisticated index."""
        return any(meta.get('id') == doc_id for meta in self.metadata)
    
    async def add_sophisticated_demo_documents(self) -> Dict[str, Any]:
        """Add sophisticated demo documents with full processing pipeline."""
        sophisticated_demos = [
            {
                "id": "textile_operations_overview",
                "raw_content": {
                    "text": (
                        "Precision Textile Industry Limited Operations Overview\n\n"
                        "Company Profile: Leading textile printing and embroidery manufacturer based in Gazipur, Bangladesh. "
                        "Established operations serving major customers including RB Knit, Blue Planet Knitwear Ltd, and Fiat Fashion Ltd. "
                        "Production Capacity: 16-head MHM embroidery machines with daily output of 2,000 dozen pieces. "
                        "Staff Structure: Commercial Manager Md. Mizanur Rahman (PTIL), Accounting Assistant Zahedul Islam Nizam, "
                        "Assistant Commercial Manager Md. Alamin, Maintenance Manager Khorshed Alam Babu. "
                        "Financial Operations: Multi-currency transactions in BDT and USD. Monthly revenue target: $50,000. "
                        "Quality Standards: 98% efficiency rating with Grade A export quality requirements. "
                        "Operating Hours: 8:00 AM - 6:00 PM (Asia/Dhaka timezone). "
                        "Key Services: Embroidery printing, quality control, export documentation, LC processing."
                    ),
                    "type": "overview_document"
                },
                "metadata": {
                    "file_type": "overview",
                    "department": "management",
                    "priority": "high"
                }
            },
            {
                "id": "customer_relationship_management",
                "raw_content": {
                    "text": (
                        "Customer Relationship Management System\n\n"
                        "Primary Customers:\n"
                        "1. RB Knit - Major client with monthly orders of $15,000-20,000. Contact: Procurement Manager. "
                        "Specializes in knitted garments for export. Payment terms: 30 days LC at sight.\n"
                        "2. Blue Planet Knitwear Ltd - Premium customer with quarterly contracts worth $35,000. "
                        "Focus on sustainable textile practices. Requires certified organic materials.\n"
                        "3. Fiat Fashion Ltd - Fashion apparel manufacturer. Weekly orders of 500-800 dozen pieces. "
                        "Strict quality requirements with 99% acceptance rate needed.\n"
                        "Customer Service Standards: 24-hour response time for inquiries. Weekly quality reports. "
                        "Dedicated account managers for each major client. Customer satisfaction score: 96%.\n"
                        "Export Documentation: Commercial invoices, packing lists, certificates of origin managed by Commercial Department."
                    ),
                    "type": "customer_management"
                },
                "metadata": {
                    "file_type": "customer_data",
                    "department": "commercial",
                    "priority": "critical"
                }
            },
            {
                "id": "financial_operations_system",
                "raw_content": {
                    "text": (
                        "Financial Operations and Cash Management\n\n"
                        "Currency Operations: Dual currency system handling BDT (Bangladeshi Taka) and USD (US Dollar). "
                        "Exchange rate monitoring daily. Current rate: 1 USD = 110 BDT approximately.\n"
                        "Payment Processing: LC (Letter of Credit) documents processed through Accounting Department. "
                        "Nizam manages cash book entries. Daily cash reconciliation required.\n"
                        "Monthly Financial Targets:\n"
                        "- Export Revenue: $45,000-55,000\n"
                        "- Domestic Sales: 2,500,000 BDT\n"
                        "- Operating Expenses: 1,800,000 BDT\n"
                        "- Net Profit Margin: 15-18%\n"
                        "Banking Partners: Standard Chartered, HSBC for LC processing. Local banks for BDT operations.\n"
                        "Audit Schedule: Monthly internal audits. Annual external audit by certified CA firm.\n"
                        "Tax Compliance: VAT registration current. Export incentive claims processed quarterly."
                    ),
                    "type": "financial_system"
                },
                "metadata": {
                    "file_type": "financial_data",
                    "department": "accounting",
                    "priority": "critical"
                }
            }
        ]
        
        added_count = 0
        skipped_count = 0
        
        for demo_doc in sophisticated_demos:
            if self._document_exists(demo_doc["id"]):
                logger.info(f"Sophisticated demo document {demo_doc['id']} already exists, skipping")
                skipped_count += 1
                continue
            
            # Process through sophisticated pipeline
            processed_result = await self._process_through_sophisticated_pipeline(
                demo_doc["raw_content"], 
                demo_doc["id"], 
                demo_doc["metadata"]
            )
            
            if processed_result:
                added_count += 1
                logger.info(f"Added sophisticated demo document: {demo_doc['id']}")
        
        if added_count > 0:
            self._save_sophisticated_index()
        
        return {
            "status": "success",
            "added": added_count,
            "skipped": skipped_count,
            "total_demo_docs": len(sophisticated_demos),
            "processing_pipeline": "sophisticated_rag_integration"
        }
    
    async def add_google_drive_documents(self) -> Dict[str, Any]:
        """Add Google Drive documents through sophisticated processing pipeline."""
        try:
            logger.info("Starting sophisticated Google Drive document processing...")
            
            # Find target files using existing Google Drive service
            target_files = self.gdrive.find_target_files_anywhere()
            
            if not target_files:
                return {
                    "status": "warning",
                    "message": "No target files found in Google Drive",
                    "added": 0,
                    "skipped": 0,
                    "errors": 0
                }
            
            added_count = 0
            skipped_count = 0
            error_count = 0
            
            for file_info in target_files:
                try:
                    file_id = file_info['id']
                    file_name = file_info['name']
                    
                    # Check if already processed
                    if self._document_exists(f"gdrive_{file_id}"):
                        logger.info(f"Google Drive file {file_name} already exists, skipping")
                        skipped_count += 1
                        continue
                    
                    logger.info(f"Processing Google Drive file through sophisticated pipeline: {file_name}")
                    
                    # Download file content
                    file_content = self.gdrive.download_file(file_id)
                    if not file_content:
                        logger.error(f"Failed to download {file_name}")
                        error_count += 1
                        continue
                    
                    # Process through sophisticated pipeline
                    processed_results = await self._process_google_drive_file(
                        file_content, file_info
                    )
                    
                    added_count += len(processed_results)
                    logger.info(f"Added {len(processed_results)} sophisticated chunks from {file_name}")
                    
                except Exception as e:
                    logger.error(f"Error processing {file_info['name']}: {e}")
                    error_count += 1
                    continue
            
            # Save updated sophisticated index
            if added_count > 0:
                self._save_sophisticated_index()
            
            return {
                "status": "success",
                "added": added_count,
                "skipped": skipped_count,
                "errors": error_count,
                "total_files": len(target_files),
                "processing_type": "sophisticated_rag_pipeline"
            }
            
        except Exception as e:
            logger.error(f"Sophisticated Google Drive processing failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "added": 0,
                "skipped": 0,
                "errors": 1
            }
    
    async def _process_google_drive_file(self, file_content: bytes, file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process Google Drive file through sophisticated pipeline."""
        if not PROCESSORS_AVAILABLE:
            logger.warning("Sophisticated processors not available, using fallback")
            return await self._fallback_process_file(file_content, file_info)
        
        try:
            file_name = file_info['name']
            file_type = self._determine_file_type(file_name)
            
            # Step 1: Document Processing Engine Analysis
            logger.info(f"Step 1: Running Document Processing Engine on {file_name}")
            processing_result = await self.document_processor.process_document(
                file_path=file_name,
                file_data=file_content,
                file_type=file_type
            )
            
            if processing_result.status.value != "completed":
                logger.warning(f"Document processing failed for {file_name}: {processing_result.errors}")
                return []
            
            # Step 2: Intelligent Chunking
            logger.info(f"Step 2: Running Intelligent Chunking on {file_name}")
            
            # Prepare data for chunking
            chunking_input = {
                'file_path': file_name,
                'file_data': processing_result.extracted_content,
                'file_type': file_type
            }
            
            chunk_result = await self.chunking_orchestrator.process_document(
                file_name, 
                processing_result.extracted_content, 
                file_type
            )
            
            if chunk_result['status'] != 'success':
                logger.warning(f"Chunking failed for {file_name}")
                return []
            
            # Step 3: Convert sophisticated chunks to embeddings
            logger.info(f"Step 3: Converting {len(chunk_result['chunks'])} chunks to embeddings")
            
            processed_documents = []
            
            for chunk in chunk_result['chunks']:
                # Extract sophisticated content from chunk
                sophisticated_content = self._extract_sophisticated_content(chunk, processing_result)
                
                # Generate embedding
                embeddings = await self._generate_embeddings([sophisticated_content['text']])
                
                if embeddings:
                    # Add to sophisticated index
                    self.documents.append(sophisticated_content['text'])
                    self.embeddings.append(embeddings[0])
                    self.metadata.append(sophisticated_content['metadata'])
                    self.business_intelligence.append(sophisticated_content['business_intelligence'])
                    
                    processed_documents.append(sophisticated_content)
            
            return processed_documents
            
        except Exception as e:
            logger.error(f"Sophisticated processing failed for {file_info['name']}: {e}")
            return []
    
    def _determine_file_type(self, file_name: str) -> str:
        """Determine file type for processing engine."""
        name_lower = file_name.lower()
        if name_lower.endswith(('.xlsx', '.xls')):
            return 'excel'
        elif name_lower.endswith('.pdf'):
            return 'pdf'
        elif name_lower.endswith('.csv'):
            return 'csv'
        else:
            return 'unknown'
    
    def _extract_sophisticated_content(self, chunk_context, processing_result) -> Dict[str, Any]:
        """Extract sophisticated content from chunk context with full business intelligence."""
        
        # Build sophisticated text content
        content_parts = []
        
        # Document context
        content_parts.append(f"Business Document: {processing_result.file_name}")
        content_parts.append(f"Department: {processing_result.department or 'Unknown'}")
        content_parts.append(f"Business Priority: {processing_result.business_priority}")
        content_parts.append(f"Document Type: {processing_result.document_type.value}")
        
        # Chunk-specific content
        if hasattr(chunk_context, 'content'):
            content_parts.append(f"Content: {chunk_context.content}")
        
        # Business entities context
        if processing_result.business_entities:
            for entity_type, entities in processing_result.business_entities.items():
                if entities:
                    content_parts.append(f"{entity_type.title()}: {', '.join(entities[:5])}")
        
        # Quality and confidence indicators
        content_parts.append(f"Processing Confidence: {processing_result.confidence_score:.2f}")
        
        # Textile business context
        content_parts.append("Gazipur-based textile printing and embroidery operations")
        
        sophisticated_text = ". ".join(content_parts)
        
        # Create sophisticated metadata
        sophisticated_metadata = {
            "id": f"sophisticated_{processing_result.document_id}_{getattr(chunk_context, 'chunk_id', 'unknown')}",
            "source": "sophisticated_rag_pipeline",
            "file_name": processing_result.file_name,
            "file_id": getattr(processing_result, 'google_drive_id', None),
            "chunk_type": getattr(chunk_context, 'chunk_type', 'unknown'),
            "chunk_index": getattr(chunk_context, 'chunk_index', 0),
            "department": processing_result.department,
            "business_priority": processing_result.business_priority,
            "document_type": processing_result.document_type.value,
            "confidence_score": processing_result.confidence_score,
            "processing_time": processing_result.processing_time,
            "created_at": datetime.now().isoformat(),
            "pipeline_version": "3.0",
            "analysis_engine": "document_processing_engine",
            "chunking_engine": "intelligent_chunking_orchestrator"
        }
        
        # Create business intelligence metadata
        business_intelligence = {
            "customers": processing_result.business_entities.get('customers', []),
            "staff_members": processing_result.business_entities.get('staff_members', []),
            "amounts": processing_result.business_entities.get('amounts', []),
            "dates": processing_result.business_entities.get('dates', []),
            "departments": processing_result.business_entities.get('departments', []),
            "machines": processing_result.business_entities.get('machines', []),
            "business_patterns": getattr(chunk_context, 'detected_patterns', []),
            "quality_metrics": processing_result.quality_metrics,
            "relationships": getattr(chunk_context, 'relationships', []),
            "temporal_data": getattr(chunk_context, 'temporal_data', {}),
            "financial_data": getattr(chunk_context, 'financial_data', {})
        }
        
        return {
            "text": sophisticated_text,
            "metadata": sophisticated_metadata,
            "business_intelligence": business_intelligence
        }
    
    async def _process_through_sophisticated_pipeline(self, raw_content: Dict[str, Any], 
                                                    doc_id: str, metadata: Dict[str, Any]) -> bool:
        """Process content through sophisticated pipeline even for demo documents."""
        try:
            # For demo documents, create mock processing result
            processing_result = type('MockResult', (), {
                'file_name': doc_id,
                'document_id': doc_id,
                'department': metadata.get('department', 'management'),
                'business_priority': metadata.get('priority', 'medium'),
                'document_type': type('MockType', (), {'value': metadata.get('file_type', 'demo')})(),
                'business_entities': {
                    'customers': ['RB Knit', 'Blue Planet Knitwear Ltd', 'Fiat Fashion Ltd'],
                    'staff_members': ['Mizan', 'Nizam', 'Alamin', 'Jalil', 'Babu'],
                    'amounts': ['$50,000', '2,500,000 BDT', '$15,000'],
                    'dates': [datetime.now().strftime('%Y-%m-%d')],
                    'departments': ['Commercial', 'Accounting', 'Production']
                },
                'confidence_score': 0.95,
                'processing_time': 0.1,
                'quality_metrics': {'overall_quality': 0.95}
            })()
            
            # Create mock chunk context
            chunk_context = type('MockChunk', (), {
                'content': raw_content.get('text', ''),
                'chunk_id': f"chunk_{doc_id}",
                'chunk_type': 'sophisticated_demo',
                'chunk_index': 0,
                'detected_patterns': ['textile_operations', 'business_intelligence'],
                'relationships': [],
                'temporal_data': {'has_temporal_data': True},
                'financial_data': {'has_financial_data': True}
            })()
            
            # Extract sophisticated content
            sophisticated_content = self._extract_sophisticated_content(chunk_context, processing_result)
            
            # Generate embedding
            embeddings = await self._generate_embeddings([sophisticated_content['text']])
            
            if embeddings:
                # Add to sophisticated index
                self.documents.append(sophisticated_content['text'])
                self.embeddings.append(embeddings[0])
                self.metadata.append(sophisticated_content['metadata'])
                self.business_intelligence.append(sophisticated_content['business_intelligence'])
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Sophisticated pipeline processing failed for {doc_id}: {e}")
            return False
    
    async def _fallback_process_file(self, file_content: bytes, file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fallback processing when sophisticated processors are not available."""
        logger.warning("Using fallback processing - sophisticated features not available")
        
        try:
            # Basic Excel processing
            if file_info['name'].lower().endswith(('.xlsx', '.xls')):
                documents = await self._basic_excel_processing(file_content, file_info)
            else:
                # Create basic document
                documents = [{
                    "text": f"Basic processing for {file_info['name']}",
                    "metadata": {
                        "id": f"fallback_{file_info['id']}",
                        "source": "fallback_processing",
                        "file_name": file_info['name']
                    },
                    "business_intelligence": {}
                }]
            
            # Generate embeddings for fallback documents
            for doc in documents:
                embeddings = await self._generate_embeddings([doc['text']])
                if embeddings:
                    self.documents.append(doc['text'])
                    self.embeddings.append(embeddings[0])
                    self.metadata.append(doc['metadata'])
                    self.business_intelligence.append(doc.get('business_intelligence', {}))
            
            return documents
            
        except Exception as e:
            logger.error(f"Fallback processing failed: {e}")
            return []
    
    async def _basic_excel_processing(self, file_content: bytes, file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Basic Excel processing fallback."""
        import pandas as pd
        from io import BytesIO
        
        try:
            excel_data = BytesIO(file_content)
            all_sheets = pd.read_excel(excel_data, sheet_name=None, dtype=str)
            
            documents = []
            for sheet_name, df in all_sheets.items():
                if df.empty:
                    continue
                
                # Create basic summary
                summary_text = f"Excel Sheet: {sheet_name} from {file_info['name']}. "
                summary_text += f"Contains {len(df)} rows and {len(df.columns)} columns. "
                
                # Add column information
                if not df.empty:
                    sample_data = df.head(3).to_string()
                    summary_text += f"Sample data: {sample_data}"
                
                documents.append({
                    "text": summary_text,
                    "metadata": {
                        "id": f"fallback_{file_info['id']}_{sheet_name}",
                        "source": "fallback_excel",
                        "file_name": file_info['name'],
                        "sheet_name": sheet_name
                    },
                    "business_intelligence": {}
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"Basic Excel processing failed: {e}")
            return []
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search sophisticated index with enhanced business intelligence."""
        if not self.documents:
            return []
        
        try:
            # Generate query embedding
            query_response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=[query]
            )
            query_embedding = query_response.data[0].embedding
            
            # Calculate similarities with business intelligence weighting
            similarities = []
            for i, doc_embedding in enumerate(self.embeddings):
                similarity = self._cosine_similarity(query_embedding, doc_embedding)
                
                # Apply business intelligence boosting
                business_boost = self._calculate_business_relevance_boost(
                    query, 
                    self.metadata[i], 
                    self.business_intelligence[i]
                )
                
                final_score = similarity * (1 + business_boost)
                
                similarities.append({
                    "index": i,
                    "score": final_score,
                    "base_similarity": similarity,
                    "business_boost": business_boost,
                    "text": self.documents[i],
                    "metadata": self.metadata[i],
                    "business_intelligence": self.business_intelligence[i]
                })
            
            # Sort by enhanced score and return top k
            similarities.sort(key=lambda x: x["score"], reverse=True)
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"Sophisticated search failed: {e}")
            return []
    
    def _calculate_business_relevance_boost(self, query: str, metadata: Dict[str, Any], 
                                         business_intel: Dict[str, Any]) -> float:
        """Calculate business relevance boost based on query and business intelligence."""
        boost = 0.0
        query_lower = query.lower()
        
        # Customer-related queries
        customers = business_intel.get('customers', [])
        for customer in customers:
            if customer.lower() in query_lower:
                boost += 0.3
        
        # Staff-related queries
        staff = business_intel.get('staff_members', [])
        for staff_member in staff:
            if staff_member.lower() in query_lower:
                boost += 0.2
        
        # Department-specific queries
        department = metadata.get('department', '')
        if department and department.lower() in query_lower:
            boost += 0.25
        
        # Priority-based boosting
        priority = metadata.get('business_priority', 'medium')
        if priority == 'critical' and any(term in query_lower for term in ['urgent', 'critical', 'important']):
            boost += 0.4
        elif priority == 'high' and any(term in query_lower for term in ['high', 'priority']):
            boost += 0.2
        
        # Financial data relevance
        if business_intel.get('financial_data', {}).get('has_financial_data') and any(
            term in query_lower for term in ['payment', 'amount', 'money', 'cost', 'price', 'financial']
        ):
            boost += 0.3
        
        # Temporal data relevance
        if business_intel.get('temporal_data', {}).get('has_temporal_data') and any(
            term in query_lower for term in ['date', 'time', 'when', 'schedule']
        ):
            boost += 0.2
        
        return min(boost, 1.0)  # Cap boost at 100%
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math
        
        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = math.sqrt(sum(x * x for x in a))
        magnitude_b = math.sqrt(sum(y * y for y in b))
        
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        
        return dot_product / (magnitude_a * magnitude_b)
    
    async def rebuild_sophisticated_index(self, include_demo: bool = True, include_gdrive: bool = True) -> Dict[str, Any]:
        """Rebuild the complete sophisticated index from scratch."""
        logger.info("Starting complete sophisticated index rebuild...")
        
        # Clear existing index
        self._clear_index()
        
        results = {
            "demo_result": None,
            "gdrive_result": None,
            "total_documents": 0,
            "processing_pipeline": "sophisticated_rag_integration",
            "features_enabled": []
        }
        
        # Add processing pipeline features
        if PROCESSORS_AVAILABLE:
            results["features_enabled"] = [
                "document_processing_engine",
                "intelligent_chunking_orchestrator", 
                "business_pattern_recognition",
                "content_normalization",
                "excel_structure_analyzer",
                "pdf_classifier"
            ]
        else:
            results["features_enabled"] = ["fallback_processing"]
        
        # Add sophisticated demo documents
        if include_demo:
            logger.info("Adding sophisticated demo documents...")
            results["demo_result"] = await self.add_sophisticated_demo_documents()
        
        # Add Google Drive documents
        if include_gdrive:
            logger.info("Adding Google Drive documents through sophisticated pipeline...")
            results["gdrive_result"] = await self.add_google_drive_documents()
        
        results["total_documents"] = len(self.documents)
        
        logger.info(f"Sophisticated index rebuild complete: {results['total_documents']} total documents")
        return results
    
    def get_sophisticated_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the sophisticated index."""
        if not self.metadata:
            return {"total_documents": 0}
        
        # Count by source and analyze business intelligence
        source_counts = {}
        department_counts = {}
        priority_counts = {}
        business_entity_stats = {
            "total_customers": set(),
            "total_staff": set(),
            "total_departments": set()
        }
        
        for i, meta in enumerate(self.metadata):
            source = meta.get("source", "unknown")
            department = meta.get("department", "unknown")
            priority = meta.get("business_priority", "medium")
            
            source_counts[source] = source_counts.get(source, 0) + 1
            department_counts[department] = department_counts.get(department, 0) + 1
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            # Aggregate business entities
            if i < len(self.business_intelligence):
                bi = self.business_intelligence[i]
                business_entity_stats["total_customers"].update(bi.get("customers", []))
                business_entity_stats["total_staff"].update(bi.get("staff_members", []))
                business_entity_stats["total_departments"].update(bi.get("departments", []))
        
        # Convert sets to counts
        for key in business_entity_stats:
            business_entity_stats[key] = len(business_entity_stats[key])
        
        # Calculate average confidence
        confidence_scores = [meta.get("confidence_score", 0.0) for meta in self.metadata]
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        return {
            "total_documents": len(self.documents),
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dim,
            "pipeline_version": "3.0",
            "index_file": str(self.index_path),
            "index_size_mb": round(self.index_path.stat().st_size / (1024*1024), 2) if self.index_path.exists() else 0,
            "by_source": source_counts,
            "by_department": department_counts,
            "by_priority": priority_counts,
            "business_intelligence": business_entity_stats,
            "average_confidence": round(avg_confidence, 3),
            "processors_available": PROCESSORS_AVAILABLE,
            "last_updated": datetime.now().isoformat(),
            "features": {
                "document_processing_engine": PROCESSORS_AVAILABLE,
                "intelligent_chunking": PROCESSORS_AVAILABLE,
                "business_pattern_recognition": True,
                "content_normalization": PROCESSORS_AVAILABLE,
                "sophisticated_search": True,
                "business_intelligence_boosting": True
            }
        }
    
    async def search_with_business_context(self, query: str, 
                                         department_filter: str = None,
                                         priority_filter: str = None,
                                         top_k: int = 5) -> Dict[str, Any]:
        """Enhanced search with business context filtering."""
        if not self.documents:
            return {
                "results": [],
                "total_results": 0,
                "query": query,
                "filters_applied": {}
            }
        
        try:
            # Get initial results
            initial_results = self.search(query, top_k * 2)  # Get more for filtering
            
            # Apply business context filters
            filtered_results = []
            for result in initial_results:
                metadata = result["metadata"]
                
                # Department filter
                if department_filter and metadata.get("department") != department_filter:
                    continue
                
                # Priority filter
                if priority_filter and metadata.get("business_priority") != priority_filter:
                    continue
                
                filtered_results.append(result)
                
                if len(filtered_results) >= top_k:
                    break
            
            return {
                "results": filtered_results,
                "total_results": len(filtered_results),
                "query": query,
                "filters_applied": {
                    "department": department_filter,
                    "priority": priority_filter
                },
                "business_intelligence_enhanced": True,
                "search_type": "sophisticated_rag_search"
            }
            
        except Exception as e:
            logger.error(f"Business context search failed: {e}")
            return {
                "results": [],
                "total_results": 0,
                "query": query,
                "error": str(e)
            }
    
    async def analyze_business_patterns(self) -> Dict[str, Any]:
        """Analyze business patterns across all documents in the sophisticated index."""
        if not self.business_intelligence:
            return {"status": "no_data"}
        
        analysis = {
            "customer_analysis": {},
            "staff_analysis": {},
            "department_distribution": {},
            "priority_distribution": {},
            "temporal_patterns": {},
            "financial_patterns": {}
        }
        
        try:
            # Aggregate all business intelligence
            all_customers = []
            all_staff = []
            all_departments = []
            all_amounts = []
            
            for bi in self.business_intelligence:
                all_customers.extend(bi.get("customers", []))
                all_staff.extend(bi.get("staff_members", []))
                all_departments.extend(bi.get("departments", []))
                all_amounts.extend(bi.get("amounts", []))
            
            # Customer analysis
            from collections import Counter
            customer_freq = Counter(all_customers)
            analysis["customer_analysis"] = {
                "top_customers": dict(customer_freq.most_common(10)),
                "total_unique_customers": len(customer_freq),
                "most_mentioned": customer_freq.most_common(1)[0] if customer_freq else None
            }
            
            # Staff analysis
            staff_freq = Counter(all_staff)
            analysis["staff_analysis"] = {
                "top_staff": dict(staff_freq.most_common(10)),
                "total_unique_staff": len(staff_freq),
                "most_mentioned": staff_freq.most_common(1)[0] if staff_freq else None
            }
            
            # Department distribution
            dept_freq = Counter(all_departments)
            analysis["department_distribution"] = dict(dept_freq)
            
            # Priority analysis from metadata
            priorities = [meta.get("business_priority", "medium") for meta in self.metadata]
            priority_freq = Counter(priorities)
            analysis["priority_distribution"] = dict(priority_freq)
            
            # Financial patterns (simplified)
            analysis["financial_patterns"] = {
                "total_amounts_mentioned": len(all_amounts),
                "currency_diversity": len(set(
                    amount.split()[1] if len(amount.split()) > 1 else "BDT" 
                    for amount in all_amounts[:50]  # Sample first 50
                ))
            }
            
            return {
                "status": "success",
                "analysis": analysis,
                "total_documents_analyzed": len(self.business_intelligence),
                "analysis_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Business pattern analysis failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# Standalone functions for easy integration
async def rebuild_sophisticated_index(credentials_path: str = None, 
                                    openai_api_key: str = None) -> Dict[str, Any]:
    """Rebuild the complete sophisticated index from scratch."""
    system = SophisticatedEmbeddingSystem(
        credentials_path=credentials_path,
        openai_api_key=openai_api_key
    )
    
    result = await system.rebuild_sophisticated_index(include_demo=True, include_gdrive=True)
    return result


async def search_sophisticated_index(query: str, 
                                   top_k: int = 5,
                                   department: str = None,
                                   priority: str = None,
                                   credentials_path: str = None,
                                   openai_api_key: str = None) -> List[Dict[str, Any]]:
    """Search the sophisticated index with business context."""
    system = SophisticatedEmbeddingSystem(
        credentials_path=credentials_path,
        openai_api_key=openai_api_key
    )
    
    result = await system.search_with_business_context(
        query=query,
        department_filter=department,
        priority_filter=priority,
        top_k=top_k
    )
    
    return result["results"]


# Command line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Sophisticated Embedding System with Complete RAG Integration")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild complete sophisticated index")
    parser.add_argument("--search", type=str, help="Search query")
    parser.add_argument("--analyze", action="store_true", help="Analyze business patterns")
    parser.add_argument("--stats", action="store_true", help="Show sophisticated index statistics")
    parser.add_argument("--department", type=str, help="Filter by department")
    parser.add_argument("--priority", type=str, help="Filter by priority")
    parser.add_argument("--credentials", type=str, help="Path to Google credentials")
    parser.add_argument("--api-key", type=str, help="OpenAI API key")
    
    args = parser.parse_args()
    
    async def main():
        if args.rebuild:
            print("Rebuilding complete sophisticated index with RAG integration...")
            result = await rebuild_sophisticated_index(args.credentials, args.api_key)
            print(json.dumps(result, indent=2))
        
        elif args.search:
            print(f"Searching sophisticated index: {args.search}")
            if args.department or args.priority:
                print(f"Filters - Department: {args.department}, Priority: {args.priority}")
            
            results = await search_sophisticated_index(
                args.search, 5, args.department, args.priority, args.credentials, args.api_key
            )
            
            for i, result in enumerate(results, 1):
                print(f"\n{i}. Score: {result['score']:.3f} (Base: {result['base_similarity']:.3f}, Boost: {result['business_boost']:.3f})")
                print(f"Department: {result['metadata'].get('department', 'Unknown')}")
                print(f"Priority: {result['metadata'].get('business_priority', 'medium')}")
                print(f"Source: {result['metadata'].get('source', 'unknown')}")
                
                # Show business intelligence
                bi = result.get('business_intelligence', {})
                if bi.get('customers'):
                    print(f"Customers: {', '.join(bi['customers'][:3])}")
                if bi.get('staff_members'):
                    print(f"Staff: {', '.join(bi['staff_members'][:3])}")
                
                print(f"Text: {result['text'][:200]}...")
        
        elif args.analyze:
            system = SophisticatedEmbeddingSystem(args.credentials, openai_api_key=args.api_key)
            analysis = await system.analyze_business_patterns()
            print(json.dumps(analysis, indent=2))
        
        elif args.stats:
            system = SophisticatedEmbeddingSystem(args.credentials, openai_api_key=args.api_key)
            stats = system.get_sophisticated_stats()
            print(json.dumps(stats, indent=2))
        
        else:
            print("Usage: python sophisticated_embedding_system.py [--rebuild|--search 'query'|--analyze|--stats]")
            print("Advanced options: --department, --priority for filtering")
    
    asyncio.run(main())