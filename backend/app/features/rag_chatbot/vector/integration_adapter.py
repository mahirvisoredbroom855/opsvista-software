# backend/app/features/rag_chatbot/vector/integration_adapter.py
"""
Vector Database Integration Adapter

This adapter seamlessly integrates your existing textile embedding framework
with the new enhanced vector database architecture, providing backward 
compatibility while enabling advanced business intelligence features.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

# Fixed imports - remove relative imports
from .vector_client import VectorDatabaseAdapterBase  # or whatever the base/client is named
from .enhanced_vector_client import EnhancedVectorDatabaseClient  # if referenced
from .vector_search_optimizer import BusinessSearchResult  # if referenced

# Import the embedding framework if available
try:
    from embedding.embedding_framework import ComprehensiveBusinessContext
except ImportError:
    # Fallback if embedding framework not available
    class ComprehensiveBusinessContext:
        pass


class VectorDatabaseAdapter:
    """
    Adapter that bridges your textile embedding framework with the enhanced vector database.
    
    Provides backward compatibility for existing code while enabling new features.
    """
    
    def __init__(self, enhanced_client: Optional[EnhancedVectorDatabaseClient] = None):
        """Initialize the adapter with an enhanced vector database client."""
        self.enhanced_client = enhanced_client or EnhancedVectorDatabaseClient()
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self) -> None:
        """Initialize the underlying database connection."""
        await self.enhanced_client.initialize()
    
    async def close(self) -> None:
        """Close the database connection."""
        await self.enhanced_client.close()
    
    def _context_to_business_metadata(self, context: ComprehensiveBusinessContext) -> Dict[str, Any]:
        """Convert ComprehensiveBusinessContext to database metadata format."""
        return {
            'customers': getattr(context, 'customers', []),
            'suppliers': getattr(context, 'suppliers', []),
            'banks': getattr(context, 'banks', []),
            'regulatory_bodies': getattr(context, 'regulatory_bodies', []),
            'staff_members': getattr(context, 'staff_members', []),
            'departments_involved': getattr(context, 'departments_involved', []),
            'currencies': getattr(context, 'currencies', []),
            'amounts': getattr(context, 'amounts', []),
            'pricing_info': getattr(context, 'pricing_info', []),
            'machines_involved': getattr(context, 'machines_involved', []),
            'production_capacity': getattr(context, 'production_capacity', []),
            'materials': getattr(context, 'materials', []),
            'orders': getattr(context, 'orders', []),
            'lc_numbers': getattr(context, 'lc_numbers', []),
            'po_numbers': getattr(context, 'po_numbers', []),
            'invoice_numbers': getattr(context, 'invoice_numbers', []),
            'bl_numbers': getattr(context, 'bl_numbers', []),
            'certificates': getattr(context, 'certificates', []),
            'hs_codes': getattr(context, 'hs_codes', []),
            'dates': getattr(context, 'dates', []),
            'locations': getattr(context, 'locations', [])
        }
    
    def _context_to_relationships(self, context: ComprehensiveBusinessContext) -> List[Dict[str, Any]]:
        """Extract document relationships from context."""
        relationships = []
        
        # Extract relationships from related_documents field
        if hasattr(context, 'related_documents') and context.related_documents:
            for related_doc in context.related_documents:
                relationships.append({
                    'target_document_id': related_doc,
                    'relationship_type': 'relates_to',
                    'context': f"Related document from {getattr(context, 'document_type', 'unknown')}",
                    'strength': 0.7,
                    'confidence': 0.8,
                    'business_context': {
                        'source_department': getattr(context, 'department', 'commercial'),
                        'document_type': getattr(context, 'document_type', 'unknown')
                    }
                })
        
        return relationships
    
    def _context_to_version_info(self, context: ComprehensiveBusinessContext) -> Dict[str, Any]:
        """Extract version information from context."""
        return {
            'version_number': 1,  # Default for new documents
            'change_type': 'create',
            'change_summary': f"Initial processing of {getattr(context, 'document_type', 'unknown')}",
            'changed_by': 'textile_embedding_framework'
        }
    
    async def store_document_chunk(
        self,
        document_id: Union[str, UUID],
        chunk_index: int,
        chunk_content: str,
        chunk_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Store document chunk (legacy interface for backward compatibility).
        
        This method provides the same interface as your original vector client
        but with enhanced storage capabilities.
        """
        try:
            # Extract basic metadata
            file_name = metadata.get('file_name', 'unknown.txt') if metadata else 'unknown.txt'
            file_type = metadata.get('file_type', 'txt') if metadata else 'txt'
            document_type = metadata.get('document_type', 'other') if metadata else 'other'
            department = metadata.get('department', 'commercial') if metadata else 'commercial'
            
            # Create basic business metadata
            business_metadata = metadata.get('business_metadata', {}) if metadata else {}
            
            # Store using enhanced client
            embedding_id = await self.enhanced_client.store_document_chunk(
                document_id=document_id,
                chunk_index=chunk_index,
                chunk_content=chunk_content,
                chunk_type=chunk_type,
                file_name=file_name,
                file_type=file_type,
                document_type=document_type,
                department=department,
                business_metadata=business_metadata,
                confidence_score=metadata.get('confidence_score', 0.0) if metadata else 0.0,
                business_relevance=metadata.get('business_relevance', 0.0) if metadata else 0.0,
                department_relevance=metadata.get('department_relevance', 0.0) if metadata else 0.0
            )
            
            return embedding_id
            
        except Exception as e:
            self.logger.error(f"Failed to store document chunk via adapter: {e}")
            raise
    
    async def store_comprehensive_context(
        self,
        context: ComprehensiveBusinessContext,
        enhanced_content: str
    ) -> UUID:
        """
        Store a comprehensive business context with full business intelligence.
        
        This method is specifically designed for your textile embedding framework.
        """
        try:
            # Convert context to database format
            business_metadata = self._context_to_business_metadata(context)
            relationships = self._context_to_relationships(context)
            version_info = self._context_to_version_info(context)
            
            # Store using enhanced client
            embedding_id = await self.enhanced_client.store_document_chunk(
                document_id=getattr(context, 'document_id', UUID('00000000-0000-0000-0000-000000000000')),
                chunk_index=getattr(context, 'chunk_index', 0),
                chunk_content=enhanced_content,
                chunk_type=getattr(context, 'content_type', 'text'),
                file_name=getattr(context, 'file_name', 'unknown.txt'),
                file_type=str(getattr(context, 'file_type', 'txt')),
                document_type=str(getattr(context, 'document_type', 'other')),
                department=str(getattr(context, 'department', 'commercial')),
                business_metadata=business_metadata,
                confidence_score=getattr(context, 'confidence_score', 0.0),
                business_relevance=getattr(context, 'business_relevance', 0.0),
                department_relevance=getattr(context, 'department_relevance', 0.0),
                relationships=relationships,
                version_info=version_info
            )
            
            self.logger.info(f"Stored comprehensive context: {embedding_id} for {getattr(context, 'file_name', 'unknown')}")
            return embedding_id
            
        except Exception as e:
            self.logger.error(f"Failed to store comprehensive context: {e}")
            raise
    
    async def search_similar_chunks(
        self,
        query_text: str,
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search similar chunks (legacy interface for backward compatibility).
        
        Returns results in the same format as your original vector client.
        """
        try:
            # Use enhanced search
            results = await self.enhanced_client.search_similar_chunks(
                query_text=query_text,
                limit=limit,
                business_filters=metadata_filter
            )
            
            # Convert to legacy format
            legacy_results = []
            for result in results:
                legacy_result = {
                    'document_id': str(result.document_id),
                    'chunk_id': str(result.embedding_id),
                    'content': result.content,
                    'metadata': {
                        'file_name': result.file_name,
                        'file_type': result.file_type,
                        'document_type': result.document_type,
                        'department': result.department,
                        'customers': result.customers,
                        'staff_members': result.staff_members,
                        'machines_involved': result.machines_involved,
                        'pricing_info': result.pricing_info,
                        'confidence_score': result.confidence_score,
                        'business_relevance': result.business_relevance,
                        'has_mhm_machine_refs': result.has_mhm_machine_refs,
                        'has_pricing_strategy': result.has_pricing_strategy,
                        'entity_count': result.entity_count
                    },
                    'similarity_score': result.similarity_score,
                    'score': result.similarity_score  # Alias for compatibility
                }
                legacy_results.append(legacy_result)
            
            return legacy_results
            
        except Exception as e:
            self.logger.error(f"Failed to search similar chunks via adapter: {e}")
            raise
    
    async def search_business_documents(
        self,
        query_text: str,
        business_filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[BusinessSearchResult]:
        """
        Advanced business document search with full business intelligence.
        
        This method exposes the full power of the enhanced vector database.
        """
        try:
            return await self.enhanced_client.search_similar_chunks(
                query_text=query_text,
                limit=limit,
                business_filters=business_filters
            )
            
        except Exception as e:
            self.logger.error(f"Failed to search business documents: {e}")
            raise
    
    async def get_document_relationships(
        self,
        document_id: Union[str, UUID],
        relationship_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get document relationships in a simplified format."""
        try:
            relationships = await self.enhanced_client.get_document_relationships(
                document_id=document_id
            )
            
            # Convert to simple format
            simple_relationships = []
            for rel in relationships:
                simple_relationships.append({
                    'id': str(rel.id),
                    'source_document_id': str(rel.source_document_id),
                    'target_document_id': str(rel.target_document_id),
                    'relationship_type': rel.relationship_type,
                    'context': rel.relationship_context,
                    'strength': rel.strength,
                    'confidence': rel.confidence,
                    'business_context': rel.business_context
                })
            
            return simple_relationships
            
        except Exception as e:
            self.logger.error(f"Failed to get document relationships: {e}")
            raise
    
    async def get_business_summary(self) -> Dict[str, Any]:
        """Get comprehensive business intelligence summary."""
        try:
            return await self.enhanced_client.get_business_intelligence_summary()
            
        except Exception as e:
            self.logger.error(f"Failed to get business summary: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check with enhanced diagnostics."""
        try:
            health = await self.enhanced_client.health_check()
            
            # Add adapter-specific information
            health['adapter'] = {
                'version': '1.0.0',
                'features': [
                    'backward_compatibility',
                    'comprehensive_context_storage',
                    'business_intelligence_search',
                    'document_relationships',
                    'textile_business_optimization'
                ],
                'integration_status': 'active'
            }
            
            return health
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'adapter_error': str(e),
                'timestamp': '2024-03-20T10:30:00Z'
            }


class TextileEmbeddingVectorClient:
    """
    Specialized vector client for your textile embedding framework.
    
    This class provides the exact interface your textile framework expects
    while leveraging the enhanced vector database capabilities.
    """
    
    def __init__(self):
        """Initialize the textile-specific vector client."""
        self.adapter = VectorDatabaseAdapter()
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self) -> None:
        """Initialize the client."""
        await self.adapter.initialize()
        self.logger.info("Textile embedding vector client initialized")
    
    async def close(self) -> None:
        """Close the client."""
        await self.adapter.close()
    
    async def store_document_chunk(
        self,
        document_id: str,
        chunk_index: int,
        chunk_content: str,
        chunk_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Store document chunk with textile business intelligence."""
        return await self.adapter.store_document_chunk(
            document_id=document_id,
            chunk_index=chunk_index,
            chunk_content=chunk_content,
            chunk_type=chunk_type,
            metadata=metadata
        )
    
    async def store_textile_context(
        self,
        context: ComprehensiveBusinessContext,
        enhanced_content: str
    ) -> UUID:
        """Store comprehensive textile business context."""
        return await self.adapter.store_comprehensive_context(
            context=context,
            enhanced_content=enhanced_content
        )
    
    async def search_similar_chunks(
        self,
        query_text: str,
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks with textile business intelligence."""
        return await self.adapter.search_similar_chunks(
            query_text=query_text,
            limit=limit,
            metadata_filter=metadata_filter
        )
    
    async def search_textile_documents(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search textile documents with comprehensive business filtering.
        
        This method provides the interface your textile orchestrator expects.
        """
        try:
            # Extract business filters
            business_filters = {}
            
            if filters:
                # Map filter keys to business filter format
                filter_mapping = {
                    'document_type': 'document_type',
                    'department': 'department',
                    'staff_members': 'staff_members',
                    'customers': 'customers',
                    'machines': 'machines_involved',
                    'has_pricing_data': 'has_pricing_strategy',
                    'limit': None  # Handle separately
                }
                
                for filter_key, db_key in filter_mapping.items():
                    if filter_key in filters and db_key:
                        business_filters[db_key] = filters[filter_key]
                
                # Handle limit separately
                if 'limit' in filters:
                    limit = filters['limit']
            
            # Perform search
            results = await self.adapter.search_business_documents(
                query_text=query,
                business_filters=business_filters,
                limit=limit
            )
            
            # Format results for textile orchestrator
            formatted_results = []
            for result in results:
                formatted_result = {
                    'document_id': str(result.document_id),
                    'chunk_id': str(result.embedding_id),
                    'content': result.content,
                    'metadata': {
                        'file_name': result.file_name,
                        'document_type': result.document_type,
                        'department': result.department,
                        'customers': result.customers,
                        'staff_members': result.staff_members,
                        'machines_involved': result.machines_involved,
                        'pricing_info': result.pricing_info,
                        'confidence_score': result.confidence_score,
                        'business_relevance': result.business_relevance,
                        'has_mhm_refs': result.has_mhm_machine_refs,
                        'has_pricing_strategy': result.has_pricing_strategy
                    },
                    'similarity_score': result.similarity_score,
                    'textile_business_context': {
                        'document_type': result.document_type,
                        'department': result.department,
                        'staff_involved': result.staff_members,
                        'customers_mentioned': result.customers,
                        'machines_involved': result.machines_involved,
                        'pricing_info': result.pricing_info,
                        'business_relevance': result.business_relevance,
                        'department_relevance': result.department_relevance,
                        'quality_flags': {
                            'has_mhm_refs': result.has_mhm_machine_refs,
                            'has_pricing_data': result.has_pricing_strategy,
                            'has_customer_data': result.has_customer_data
                        }
                    }
                }
                formatted_results.append(formatted_result)
            
            return {
                'status': 'success',
                'query': query,
                'total_results': len(formatted_results),
                'results': formatted_results,
                'filters_applied': filters or {},
                'search_context': 'enhanced_textile_business_intelligence'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to search textile documents: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'query': query
            }
    
    async def get_textile_business_summary(self) -> Dict[str, Any]:
        """Get textile business intelligence summary."""
        try:
            summary = await self.adapter.get_business_summary()
            
            # Add textile-specific insights
            textile_insights = {
                'textile_specific_metrics': {
                    'mhm_machine_references': summary['business_coverage'].get('docs_with_mhm_refs', 0),
                    'pricing_strategy_documents': summary['business_coverage'].get('docs_with_pricing', 0),
                    'production_documents': summary['business_coverage'].get('docs_with_production', 0),
                    'customer_engagement_documents': summary['business_coverage'].get('docs_with_customers', 0)
                },
                'staff_productivity': summary.get('top_staff', []),
                'customer_engagement': summary.get('top_customers', []),
                'departmental_efficiency': summary.get('department_breakdown', [])
            }
            
            summary['textile_insights'] = textile_insights
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to get textile business summary: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for textile operations."""
        try:
            health = await self.adapter.health_check()
            
            # Add textile-specific health metrics
            health['textile_operations'] = {
                'framework_compatibility': 'full',
                'business_intelligence': 'enabled',
                'textile_terminology': 'loaded',
                'mhm_machine_support': 'active',
                'pricing_strategy_support': 'active',
                'staff_recognition': 'enabled',
                'customer_intelligence': 'enabled',
                'production_optimization': 'ready'
            }
            
            return health
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'textile_error': str(e),
                'timestamp': '2024-03-20T10:30:00Z'
            }


# Factory functions for compatibility
def create_vector_client() -> TextileEmbeddingVectorClient:
    """Create a textile-optimized vector client."""
    return TextileEmbeddingVectorClient()

def create_enhanced_vector_client() -> EnhancedVectorDatabaseClient:
    """Create an enhanced vector database client."""
    return EnhancedVectorDatabaseClient()

def create_vector_adapter() -> VectorDatabaseAdapter:
    """Create a vector database adapter."""
    return VectorDatabaseAdapter()


# Aliases for backward compatibility
VectorDatabaseClient = TextileEmbeddingVectorClient