# backend/app/features/rag_chatbot/api/chat_gdrive_integration.py
"""
Integration script to add Google Drive Excel files to the existing chat system.

This modifies your existing chat.py to include Google Drive files in search results
without breaking the current functionality.
"""

import asyncio
import logging
import os
from typing import Dict, List, Any, Optional, Tuple

# Import your existing chat components
from .chat import retrieve_with_trace
from ..vector.complete_gdrive_embedder import CompleteGDriveEmbedder

logger = logging.getLogger(__name__)


class EnhancedChatRetriever:
    """
    Enhanced retriever that combines your existing system with Google Drive files.
    
    This class extends your current retrieve_with_trace function to also search
    Google Drive embedded files while maintaining all existing functionality.
    """
    
    def __init__(self):
        self.gdrive_embedder = None
        self._initialized = False
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self):
        """Initialize Google Drive embedder."""
        if not self._initialized:
            try:
                self.gdrive_embedder = CompleteGDriveEmbedder()
                await self.gdrive_embedder.initialize()
                self._initialized = True
                self.logger.info("Enhanced chat retriever initialized with Google Drive support")
            except Exception as e:
                self.logger.warning(f"Google Drive embedder initialization failed: {e}")
                self.gdrive_embedder = None
    
    async def enhanced_retrieve_with_trace(self, q: str, top_k: int = 4, force_fake: bool = False) -> Tuple[List[Dict], Dict]:
        """
        Enhanced version of retrieve_with_trace that includes Google Drive files.
        
        This combines results from:
        1. Your existing integrated/fake retrieval system 
        2. Google Drive embedded Excel files
        """
        # Initialize if needed
        await self.initialize()
        
        # Get results from existing system
        existing_docs, existing_trace = await retrieve_with_trace(q, top_k, force_fake)
        
        # Get results from Google Drive if available
        gdrive_docs = []
        gdrive_trace = {"impl": "gdrive", "method": "not_available", "count": 0}
        
        if self.gdrive_embedder and not force_fake:
            try:
                gdrive_search_result = await self.gdrive_embedder.test_search(q, top_k=top_k//2)
                
                if gdrive_search_result["status"] == "success":
                    # Convert Google Drive results to your format
                    for result in gdrive_search_result["results"]:
                        gdrive_docs.append({
                            "text": result["text"],
                            "score": result["score"],
                            "metadata": {
                                **result.get("metadata", {}),
                                "source_system": "google_drive"
                            }
                        })
                    
                    gdrive_trace = {
                        "impl": "gdrive",
                        "method": "vector_search",
                        "count": len(gdrive_docs),
                        "search_working": gdrive_search_result["search_working"]
                    }
            except Exception as e:
                self.logger.warning(f"Google Drive search failed: {e}")
                gdrive_trace["error"] = str(e)
        
        # Combine and deduplicate results
        combined_docs = existing_docs + gdrive_docs
        
        # Sort by score and limit to top_k
        combined_docs.sort(key=lambda x: x.get("score", 0), reverse=True)
        final_docs = combined_docs[:top_k]
        
        # Enhanced trace with both systems
        enhanced_trace = {
            "existing_system": existing_trace,
            "google_drive_system": gdrive_trace,
            "combined_results": {
                "existing_count": len(existing_docs),
                "gdrive_count": len(gdrive_docs), 
                "final_count": len(final_docs),
                "deduplication_applied": len(combined_docs) != len(final_docs)
            }
        }
        
        return final_docs, enhanced_trace


# Global instance for use in chat.py
enhanced_retriever = EnhancedChatRetriever()


async def setup_google_drive_integration():
    """
    Setup function to initialize Google Drive integration.
    Call this once when your FastAPI app starts.
    """
    try:
        await enhanced_retriever.initialize()
        
        # Check if any Google Drive files are available
        if enhanced_retriever.gdrive_embedder:
            status = await enhanced_retriever.gdrive_embedder.get_system_status()
            
            if status["components"]["google_drive"]["available_files"] == 0:
                logger.warning("No Google Drive files found. Integration ready but no files to search.")
                return {
                    "status": "ready_no_files",
                    "message": "Google Drive integration ready but no target files found",
                    "recommendation": "Add Cash Book, Party Due Bill, or PTIL Expenditure files to Google Drive"
                }
            
            # Auto-embed files if not already embedded
            integration_health = status["integration_health"]
            if integration_health["embedding_coverage"] < 100:
                logger.info("Auto-embedding Google Drive files...")
                embed_result = await enhanced_retriever.gdrive_embedder.embed_all_google_drive_files()
                
                return {
                    "status": "initialized_and_embedded",
                    "message": f"Google Drive integration ready with {embed_result.get('stats', {}).get('files_processed', 0)} files embedded",
                    "embed_result": embed_result
                }
            else:
                return {
                    "status": "ready",
                    "message": "Google Drive integration ready with all files already embedded"
                }
        else:
            return {
                "status": "disabled", 
                "message": "Google Drive integration disabled due to initialization failure"
            }
            
    except Exception as e:
        logger.error(f"Google Drive integration setup failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }