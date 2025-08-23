from __future__ import annotations
import os
from typing import Dict, Any, Optional, List, Protocol, runtime_checkable
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
@runtime_checkable
class VectorDatabaseAdapterBase(Protocol):
    async def health_check(self) -> Dict[str, Any]: ...
    async def store_document(
        self,
        *,
        doc_id: Optional[str] = None,
        filename: Optional[str] = None,
        content: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[Any] = None,
    ) -> str: ...
    async def search(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Any]: ...


