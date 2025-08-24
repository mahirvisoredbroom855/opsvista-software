# Auto-generated __init__.py
"""
RAG vector package.

Exports:
- PersistedInMemorySearch: tiny file-backed/memory-backed vector store
"""
from .persisted_inmemory_search import PersistedInMemorySearch

__all__ = ["PersistedInMemorySearch"]
__version__ = "0.1.0"
# Add to backend/app/features/rag_chatbot/vector/__init__.py:



# backend/app/features/rag_chatbot/vector/__init__.py
"""
Vector module initialization with safe imports.
"""

# Safe imports with fallbacks
try:
    from .enhanced_vector_client import EnhancedVectorDatabaseClient, create_vector_client
except ImportError:
    EnhancedVectorDatabaseClient = None
    create_vector_client = None


try:
    from .sophisticated_embedding_system import SophisticatedEmbeddingSystem
except ImportError:
    SophisticatedEmbeddingSystem = None

# Export available components
__all__ = [
    'EnhancedVectorDatabaseClient',
    'create_vector_client', 
    'PersistedInMemorySearch',
    'SophisticatedEmbeddingSystem'
]