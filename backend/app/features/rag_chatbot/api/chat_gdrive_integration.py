# backend/app/features/rag_chatbot/api/chat_gdrive_integration.py
"""
Google Drive + Chat integration.

This module augments your existing chat retrieval by merging results from:
1) the existing retrieve_with_trace() pipeline, and
2) embedded Google Drive Excel documents (via CompleteGDriveEmbedder).

It also exposes a small API to check status, initialize, embed, and search.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

# Fixed: Import from settings instance instead of individual fields
from app.core.config import settings
from .chat import retrieve_with_trace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat/gdrive", tags=["chat_gdrive"])

# Helper function to check if credentials exist
def google_credentials_exist() -> bool:
    """Check if Google Drive credentials file exists."""
    try:
        return settings.GOOGLE_DRIVE_CREDENTIALS_PATH.exists()
    except Exception:
        return False

# -----------------------
# Core integration class
# -----------------------
class EnhancedChatRetriever:
    """
    Combines your current retrieval with Google Drive embedded files.
    """

    def __init__(self) -> None:
        self.gdrive_embedder: Optional[Any] = None  # CompleteGDriveEmbedder
        self._initialized: bool = False
        self.logger = logging.getLogger(__name__)

    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize the Google Drive embedder (idempotent).
        """
        if self._initialized:
            return {"status": "already_initialized"}

        if not settings.GOOGLE_DRIVE_ENABLED:
            self.logger.info("Google Drive integration disabled via env.")
            return {"status": "disabled_env"}

        if not google_credentials_exist():
            msg = f"Credentials not found at {settings.GOOGLE_DRIVE_CREDENTIALS_PATH}"
            self.logger.warning(msg)
            return {"status": "missing_credentials", "path": str(settings.GOOGLE_DRIVE_CREDENTIALS_PATH)}

        try:
            # Import here to avoid import errors if the module doesn't exist
            try:
                from ..vector.complete_gdrive_embedder import CompleteGDriveEmbedder
                self.gdrive_embedder = CompleteGDriveEmbedder()  # reads creds path from config/env
                await self.gdrive_embedder.initialize()
                self._initialized = True
                self.logger.info("EnhancedChatRetriever: Google Drive initialized")
                return {"status": "initialized"}
            except ImportError as ie:
                self.logger.warning(f"CompleteGDriveEmbedder not available: {ie}")
                return {"status": "embedder_not_available", "error": str(ie)}
        except Exception as e:
            self.logger.warning(f"Google Drive initialization failed: {e}")
            self.gdrive_embedder = None
            return {"status": "init_failed", "error": str(e)}

    async def enhanced_retrieve_with_trace(
        self,
        q: str,
        top_k: int = 4,
        force_fake: bool = False,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Merge (existing) + (gdrive) results. Sort by score and trim to top_k.
        """
        # Ensure initialized if possible
        if not self._initialized:
            await self.initialize()

        # 1) Existing system
        try:
            existing_docs, existing_trace = await retrieve_with_trace(q, top_k, force_fake)
        except Exception as e:
            self.logger.warning(f"Existing retrieval failed: {e}")
            existing_docs, existing_trace = [], {"error": str(e), "count": 0}

        # 2) Google Drive results
        gdrive_docs: List[Dict[str, Any]] = []
        gdrive_trace: Dict[str, Any] = {"impl": "gdrive", "method": "not_available", "count": 0}

        if self.gdrive_embedder and not force_fake:
            try:
                # take half of top_k from Drive to keep balance
                gk = max(1, top_k // 2)
                gdrive_search_result = await self.gdrive_embedder.test_search(q, top_k=gk)

                if gdrive_search_result.get("status") == "success":
                    for r in gdrive_search_result.get("results", []):
                        gdrive_docs.append(
                            {
                                "text": r.get("text", ""),
                                "score": r.get("score", 0.0),
                                "metadata": {
                                    **(r.get("metadata") or {}),
                                    "source_system": "google_drive",
                                },
                            }
                        )
                    gdrive_trace = {
                        "impl": "gdrive",
                        "method": "vector_search",
                        "count": len(gdrive_docs),
                        "search_working": gdrive_search_result.get("search_working"),
                    }
            except Exception as e:
                self.logger.warning(f"Google Drive search failed: {e}")
                gdrive_trace["error"] = str(e)

        # Combine, sort by score, trim
        combined_docs = (existing_docs or []) + gdrive_docs
        combined_docs.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        final_docs = combined_docs[:top_k]

        enhanced_trace = {
            "existing_system": existing_trace,
            "google_drive_system": gdrive_trace,
            "combined_results": {
                "existing_count": len(existing_docs),
                "gdrive_count": len(gdrive_docs),
                "final_count": len(final_docs),
                "deduplication_applied": len(combined_docs) != len(final_docs),
            },
        }
        return final_docs, enhanced_trace


# Single global instance (imported by router handlers)
enhanced_retriever = EnhancedChatRetriever()


# -----------------------
# API endpoints
# -----------------------
@router.get("/status")
async def gdrive_status():
    return {
        "enabled": settings.GOOGLE_DRIVE_ENABLED,
        "credentials_path": str(settings.GOOGLE_DRIVE_CREDENTIALS_PATH),
        "credentials_exist": google_credentials_exist(),
        "initialized": enhanced_retriever._initialized,
    }


@router.post("/initialize")
async def gdrive_initialize():
    return await enhanced_retriever.initialize()


@router.post("/embed")
async def gdrive_embed_all():
    if not enhanced_retriever._initialized or not enhanced_retriever.gdrive_embedder:
        raise HTTPException(status_code=400, detail="GDrive not initialized")
    try:
        result = await enhanced_retriever.gdrive_embedder.embed_all_google_drive_files()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {e}")


@router.get("/search")
async def gdrive_search(
    q: str = Query(..., description="Query text"),
    top_k: int = Query(4, ge=1, le=20),
    force_fake: bool = Query(False),
):
    docs, trace = await enhanced_retriever.enhanced_retrieve_with_trace(q, top_k, force_fake)
    return {"docs": docs, "trace": trace}