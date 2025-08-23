# backend/app/features/rag_chatbot/tests/test_vector_search_optimization.py
"""
Comprehensive Testing Suite for Task 2A-2: Vector Search Optimization Engine

This test suite validates:
- Multi-stage retrieval with reranking
- Similarity threshold optimization
- Cross-document relationship discovery
- Temporal query handling
- Query routing and strategy selection
- Performance and quality metrics

Run with: pytest test_vector_search_optimization.py -v --asyncio-mode=auto
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
from uuid import UUID, uuid4
from unittest.mock import Mock, AsyncMock, patch
import numpy as np

# Import the components to test
try:
    from ..search.vector_search_optimizer import (
        VectorSearchOptimizer,
        MultiStageRetrievalEngine,
        CrossDocumentRelationshipDiscovery,
        TemporalQueryHandler,
        SearchStrategyFactory,
        SimilarityThresholdOptimizer,
        AdvancedQueryRouter,
        VectorSearchOptimizationIntegrator,
        EnhancedSearchResult,
        SearchStrategy
    )
    from ..search.query_engine import QueryIntent, QueryComplexity
except ImportError:
    # Mock imports for standalone testing
    from enum import Enum
    
    class QueryIntent(Enum):
        LOOKUP_SPECIFIC = "lookup_specific"
        ANALYSIS_FINANCIAL = "analysis_financial"
        ANALYSIS_COMPARISON = "analysis_comparison"
        ANALYSIS_TREND = "analysis_trend"
    
    class QueryComplexity(Enum):
        SIMPLE = "simple"
        MODERATE = "moderate"
        COMPLEX = "complex"
        ADVANCED = "advanced"


# =============================================================================
# TEST FIXTURES AND MOCK DATA
# =============================================================================

@pytest.fixture
def mock_vector_client():
    """Mock enhanced vector database client."""
    client = Mock()
    client.search_similar_chunks = AsyncMock()
    client.get_document_relationships = AsyncMock()
    return client

@pytest.fixture
def sample_business_search_results():
    """Sample business search results for testing."""
    return [
        Mock(
            document_id=UUID('12345678-1234-5678-1234-567812345678'),
            chunk_index=0,
            score=0.85,
            file_name="Monthly_Cash_Summary_March_2024.xlsx",
            document_type="financial_report",
            department="accounting",
            snippet="Cash flow analysis for March 2024 showing RB Knit payment of ৳75,000",
            created_at=datetime.now() - timedelta(days=15)
        ),
        Mock(
            document_id=UUID('87654321-4321-8765-4321-876543218765'),
            chunk_index=1,
            score=0.72,
            file_name="RB_Knit_Order_History.xlsx",
            document_type="customer_record",
            department="commercial",
            snippet="RB Knit order history showing consistent monthly orders of 500 dozen",
            created_at=datetime.now() - timedelta(days=30)
        ),
        Mock(
            document_id=UUID('11111111-2222-3333-4444-555555555555'),
            chunk_index=0,
            score=0.68,
            file_name="Production_Schedule_Q1_2024.xlsx",
            document_type="production_plan",
            department="production",
            snippet="Q1 production schedule including MHM machine capacity for textile orders",
            created_at=datetime.now() - timedelta(days=45)
        )
    ]

@pytest.fixture
def sample_query_contexts():
    """Sample query contexts for different business scenarios."""
    
    class MockEntity:
        def __init__(self, entity_type, entity_value):
            self.entity_type = entity_type
            self.entity_value = entity_value
    
    class MockConstraint:
        def __init__(self, constraint_type, value):
            self.constraint_type = constraint_type
            self.value = value
    
    class MockQueryContext:
        def __init__(self, query, intent, complexity, entities=None, constraints=None):
            self.original_query = query
            self.cleaned_query = query.lower()
            self.primary_intent = intent
            self.complexity = complexity
            self.business_entities = entities or []
            self.constraints = constraints or []
            self.date_constraints = [c for c in self.constraints if 'date' in c.constraint_type]
            self.time_references = ['last quarter'] if 'last quarter' in query else []
            self.suggested_departments = ['accounting'] if 'financial' in query else ['commercial']
    
    return {
        'specific_lookup': MockQueryContext(
            "Find invoice number INV-2024-001",
            QueryIntent.LOOKUP_SPECIFIC,
            QueryComplexity.SIMPLE,
            [MockEntity('reference_id', 'INV-2024-001')]
        ),
        'financial_analysis': MockQueryContext(
            "Show me financial analysis for RB Knit last quarter",
            QueryIntent.ANALYSIS_FINANCIAL,
            QueryComplexity.MODERATE,
            [MockEntity('customer', 'RB Knit')],
            [MockConstraint('date_period', 'last_quarter')]
        ),
        'comparison_query': MockQueryContext(
            "Compare RB Knit vs Blue Planet revenue this year",
            QueryIntent.ANALYSIS_COMPARISON,
            QueryComplexity.COMPLEX,
            [MockEntity('customer', 'RB Knit'), MockEntity('customer', 'Blue Planet')]
        ),
        'trend_analysis': MockQueryContext(
            "What are the production trends over the last 6 months",
            QueryIntent.ANALYSIS_TREND,
            QueryComplexity.ADVANCED,
            [],
            [MockConstraint('date_period', 'last_6_months')]
        )
    }


# =============================================================================
# SEARCH STRATEGY FACTORY TESTS
# =============================================================================

class TestSearchStrategyFactory:
    """Test search strategy creation for different query types."""
    
    def test_specific_lookup_strategy(self, sample_query_contexts):
        """Test strategy for specific lookup queries."""
        query_context = sample_query_contexts['specific_lookup']
        strategy = SearchStrategyFactory.create_strategy(query_context)
        
        assert strategy.strategy_name == "specific_lookup"
        assert strategy.similarity_threshold >= 0.7  # High threshold for specific queries
        assert strategy.initial_retrieval_count <= 30  # Limited retrieval
        assert strategy.reranking_enabled == False  # No need for reranking
        assert strategy.vector_weight >= 0.7  # High vector weight for exact matching
    
    def test_financial_analysis_strategy(self, sample_query_contexts):
        """Test strategy for financial analysis queries."""
        query_context = sample_query_contexts['financial_analysis']
        strategy = SearchStrategyFactory.create_strategy(query_context)
        
        assert strategy.strategy_name == "financial_analysis"
        assert strategy.similarity_threshold <= 0.4  # Lower threshold for analysis
        assert strategy.initial_retrieval_count >= 80  # More comprehensive retrieval
        assert strategy.reranking_enabled == True  # Reranking for relevance
        assert strategy.temporal_boost_enabled == True  # Temporal considerations
        assert strategy.business_weight >= 0.3  # Business context important
    
    def test_comparison_analysis_strategy(self, sample_query_contexts):
        """Test strategy for comparison queries."""
        query_context = sample_query_contexts['comparison_query']
        strategy = SearchStrategyFactory.create_strategy(query_context)
        
        assert strategy.strategy_name == "comparison_analysis"
        assert strategy.cross_document_discovery == True  # Need cross-document analysis
        assert strategy.entity_weight > 0  # Entity matching important
        assert strategy.final_result_count >= 10  # Need diverse results
    
    def test_trend_analysis_strategy(self, sample_query_contexts):
        """Test strategy for trend analysis queries."""
        query_context = sample_query_contexts['trend_analysis']
        strategy = SearchStrategyFactory.create_strategy(query_context)
        
        assert strategy.strategy_name == "trend_analysis"
        assert strategy.similarity_threshold <= 0.3  # Very inclusive for trends
        assert strategy.temporal_boost_enabled == True  # Temporal analysis crucial
        assert strategy.temporal_weight >= 0.3  # High temporal weight
        assert strategy.final_result_count >= 15  # Need many results for trends


# =============================================================================
# MULTI-STAGE RETRIEVAL ENGINE TESTS
# =============================================================================

class TestMultiStageRetrievalEngine:
    """Test multi-stage retrieval with reranking."""
    
    @pytest.mark.asyncio
    async def test_retrieve_and_rerank_success(self, mock_vector_client, sample_business_search_results, sample_query_contexts):
        """Test successful multi-stage retrieval."""
        # Setup mock
        mock_vector_client.search_similar_chunks.return_value = sample_business_search_results
        
        # Create engine and test
        engine = MultiStageRetrievalEngine(mock_vector_client)
        query_context = sample_query_contexts['financial_analysis']
        strategy = SearchStrategyFactory.create_strategy(query_context)
        
        results = await engine.retrieve_and_rerank(query_context, strategy)
        
        # Verify results
        assert len(results) > 0
        assert all(hasattr(result, 'final_score') for result in results)
        assert all(hasattr(result, 'business_relevance_score') for result in results)
        
        # Verify sorting by final score
        scores = [result.final_score for result in results]
        assert scores == sorted(scores, reverse=True)
    
    @pytest.mark.asyncio
    async def test_business_relevance_scoring(self, mock_vector_client, sample_business_search_results, sample_query_contexts):
        """Test business relevance scoring logic."""
        mock_vector_client.search_similar_chunks.return_value = sample_business_search_results
        
        engine = MultiStageRetrievalEngine(mock_vector_client)
        query_context = sample_query_contexts['financial_analysis']
        strategy = SearchStrategyFactory.create_strategy(query_context)
        
        results = await engine.retrieve_and_rerank(query_context, strategy)
        
        # Financial query should prefer accounting department results
        financial_results = [r for r in results if r.department == 'accounting']
        other_results = [r for r in results if r.department != 'accounting']
        
        if financial_results and other_results:
            assert max(r.business_relevance_score for r in financial_results) >= \
                   max(r.business_relevance_score for r in other_results)
    
    @pytest.mark.asyncio
    async def test_empty_results_handling(self, mock_vector_client, sample_query_contexts):
        """Test handling of empty search results."""
        mock_vector_client.search_similar_chunks.return_value = []
        
        engine = MultiStageRetrievalEngine(mock_vector_client)
        query_context = sample_query_contexts['specific_lookup']
        strategy = SearchStrategyFactory.create_strategy(query_context)
        
        results = await engine.retrieve_and_rerank(query_context, strategy)
        
        assert results == []
    
    @pytest.mark.asyncio
    async def test_diversity_in_final_selection(self, mock_vector_client, sample_query_contexts):
        """Test diversity enforcement in final result selection."""
        # Create results from same document to test diversity
        same_doc_results = []
        for i in range(10):
            result = Mock(
                document_id=UUID('12345678-1234-5678-1234-567812345678'),
                chunk_index=i,
                score=0.8 - i * 0.01,
                file_name="same_document.xlsx",
                document_type="financial_report",
                department="accounting",
                snippet=f"Content chunk {i}",
                created_at=datetime.now()
            )
            same_doc_results.append(result)
        
        mock_vector_client.search_similar_chunks.return_value = same_doc_results
        
        engine = MultiStageRetrievalEngine(mock_vector_client)
        query_context = sample_query_contexts['financial_analysis']
        strategy = SearchStrategyFactory.create_strategy(query_context)
        strategy.final_result_count = 5
        
        results = await engine.retrieve_and_rerank(query_context, strategy)
        
        # Should limit results from same document
        assert len(results) <= strategy.final_result_count


# =============================================================================
# SIMILARITY THRESHOLD OPTIMIZER TESTS
# =============================================================================

class TestSimilarityThresholdOptimizer:
    """Test similarity threshold optimization."""
    
    def test_threshold_optimization_by_intent(self, sample_query_contexts):
        """Test threshold optimization based on query intent."""
        optimizer = SimilarityThresholdOptimizer()
        
        # Test different intents
        specific_context = sample_query_contexts['specific_lookup']
        financial_context = sample_query_contexts['financial_analysis']
        
        base_strategy = SearchStrategy("test", similarity_threshold=0.5)
        
        specific_threshold = optimizer.optimize_threshold(specific_context, base_strategy)
        financial_threshold = optimizer.optimize_threshold(financial_context, base_strategy)
        
        # Specific queries should have higher thresholds
        assert specific_threshold > financial_threshold
        assert 0.1 <= specific_threshold <= 0.9
        assert 0.1 <= financial_threshold <= 0.9
    
    def test_threshold_optimization_by_complexity(self, sample_query_contexts):
        """Test threshold optimization based on query complexity."""
        optimizer = SimilarityThresholdOptimizer()
        base_strategy = SearchStrategy("test", similarity_threshold=0.5)
        
        simple_context = sample_query_contexts['specific_lookup']  # Simple
        complex_context = sample_query_contexts['trend_analysis']  # Advanced
        
        simple_threshold = optimizer.optimize_threshold(simple_context, base_strategy)
        complex_threshold = optimizer.optimize_threshold(complex_context, base_strategy)
        
        # Simple queries should have higher thresholds
        assert simple_threshold >= complex_threshold
    
    @pytest.mark.asyncio
    async def test_performance_data_update(self, sample_query_contexts):
        """Test performance data update mechanism."""
        optimizer = SimilarityThresholdOptimizer()
        query_context = sample_query_contexts['financial_analysis']
        
        # Record initial performance data
        initial_data = optimizer.threshold_performance[QueryIntent.ANALYSIS_FINANCIAL].copy()
        
        # Update with good results
        await optimizer.update_performance_data(query_context, 0.4, 0.9)
        
        # Performance data should be updated
        updated_data = optimizer.threshold_performance[QueryIntent.ANALYSIS_FINANCIAL]
        assert updated_data['confidence'] >= initial_data['confidence']


# =============================================================================
# TEMPORAL QUERY HANDLER TESTS
# =============================================================================

class TestTemporalQueryHandler:
    """Test temporal query handling capabilities."""
    
    @pytest.mark.asyncio
    async def test_temporal_query_detection(self, mock_vector_client, sample_query_contexts):
        """Test detection of temporal queries."""
        handler = TemporalQueryHandler(mock_vector_client)
        
        temporal_context = sample_query_contexts['trend_analysis']
        non_temporal_context = sample_query_contexts['specific_lookup']
        
        assert handler._is_temporal_query(temporal_context) == True
        assert handler._is_temporal_query(non_temporal_context) == False
    
    @pytest.mark.asyncio
    async def test_temporal_ranking_boost(self, mock_vector_client, sample_query_contexts, sample_business_search_results):
        """Test temporal ranking boost for recent documents."""
        handler = TemporalQueryHandler(mock_vector_client)
        
        # Create results with different ages
        results = []
        for i, base_result in enumerate(sample_business_search_results):
            enhanced_result = Mock()
            enhanced_result.created_at = datetime.now() - timedelta(days=i * 30)
            enhanced_result.final_score = 0.5  # Base score
            results.append(enhanced_result)
        
        query_context = sample_query_contexts['financial_analysis']
        # Add 'current' to trigger recent document boost
        query_context.original_query = "current financial analysis for RB Knit"
        
        processed_results = await handler._apply_temporal_ranking(results, query_context)
        
        # Recent documents should have higher scores
        recent_scores = [r.final_score for r in processed_results if (datetime.now() - r.created_at).days < 30]
        older_scores = [r.final_score for r in processed_results if (datetime.now() - r.created_at).days >= 30]
        
        if recent_scores and older_scores:
            assert max(recent_scores) >= max(older_scores)
    
    def test_document_period_matching(self, mock_vector_client):
        """Test document matching against time periods."""
        handler = TemporalQueryHandler(mock_vector_client)
        current_date = datetime.now()
        
        # Test current quarter matching
        current_quarter_doc = Mock()
        current_quarter_doc.created_at = current_date - timedelta(days=30)  # Within current quarter
        
        old_doc = Mock()
        old_doc.created_at = current_date - timedelta(days=200)  # Outside current quarter
        
        assert handler._document_matches_period(current_quarter_doc, 'current_quarter', current_date) == True
        assert handler._document_matches_period(old_doc, 'current_quarter', current_date) == False


# =============================================================================
# CROSS-DOCUMENT RELATIONSHIP DISCOVERY TESTS
# =============================================================================

class TestCrossDocumentRelationshipDiscovery:
    """Test cross-document relationship discovery."""
    
    @pytest.mark.asyncio
    async def test_relationship_discovery(self, mock_vector_client, sample_query_contexts):
        """Test discovery of document relationships."""
        # Mock relationships
        mock_relationships = [
            Mock(
                relationship_type='cross_reference',
                target_document_id=UUID('99999999-9999-9999-9999-999999999999')
            )
        ]
        mock_vector_client.get_document_relationships.return_value = mock_relationships
        
        discovery = CrossDocumentRelationshipDiscovery(mock_vector_client)
        
        # Create test result
        test_result = Mock()
        test_result.document_id = UUID('12345678-1234-5678-1234-567812345678')
        test_result.snippet = "Reference to invoice INV-2024-001 and order ORD-2024-002"
        
        query_context = sample_query_contexts['financial_analysis']
        enhanced_results = await discovery.discover_relationships([test_result], query_context)
        
        # Verify relationships were discovered
        assert len(enhanced_results) == 1
        assert hasattr(enhanced_results[0], 'related_documents')
        assert hasattr(enhanced_results[0], 'cross_references')
        assert len(enhanced_results[0].cross_references) > 0  # Should find INV and ORD references
    
    @pytest.mark.asyncio
    async def test_cross_reference_extraction(self, mock_vector_client, sample_query_contexts):
        """Test extraction of cross-references from content."""
        discovery = CrossDocumentRelationshipDiscovery(mock_vector_client)
        
        test_result = Mock()
        test_result.document_id = UUID('12345678-1234-5678-1234-567812345678')
        test_result.snippet = "Payment for Invoice: INV-2024-001, Order: ORD-2024-002, LC: LC-2024-001"
        
        cross_refs = await discovery._find_cross_references(test_result, sample_query_contexts['financial_analysis'])
        
        # Should extract various reference patterns
        assert len(cross_refs) >= 2  # At least INV and ORD patterns


# =============================================================================
# ADVANCED QUERY ROUTER TESTS
# =============================================================================

class TestAdvancedQueryRouter:
    """Test advanced query routing logic."""
    
    def test_financial_query_routing(self, sample_query_contexts):
        """Test routing for financial analysis queries."""
        router = AdvancedQueryRouter()
        query_context = sample_query_contexts['financial_analysis']
        
        routing_decision = router.route_query(query_context)
        
        assert routing_decision['primary_route'] == 'financial_analysis'
        assert 'currency_normalization' in routing_decision['preprocessing_steps']
        assert 'financial_validation' in routing_decision['postprocessing_steps']
        assert routing_decision['optimization_flags']['enable_temporal_boost'] == True
    
    def test_comparison_query_routing(self, sample_query_contexts):
        """Test routing for comparison queries."""
        router = AdvancedQueryRouter()
        query_context = sample_query_contexts['comparison_query']
        
        routing_decision = router.route_query(query_context)
        
        assert routing_decision['primary_route'] == 'comparative_analysis'
        assert 'entity_pair_extraction' in routing_decision['preprocessing_steps']
        assert 'result_pairing' in routing_decision['postprocessing_steps']
        assert routing_decision['optimization_flags']['ensure_diversity'] == True
    
    def test_complex_query_handling(self, sample_query_contexts):
        """Test handling of complex queries."""
        router = AdvancedQueryRouter()
        query_context = sample_query_contexts['trend_analysis']  # Advanced complexity
        
        routing_decision = router.route_query(query_context)
        
        assert 'complex_query_decomposition' in routing_decision['preprocessing_steps']
        assert 'multi_perspective_synthesis' in routing_decision['postprocessing_steps']
        assert routing_decision['optimization_flags']['enable_advanced_reranking'] == True


# =============================================================================
# VECTOR SEARCH OPTIMIZER INTEGRATION TESTS
# =============================================================================

class TestVectorSearchOptimizer:
    """Test the main vector search optimizer."""
    
    @pytest.mark.asyncio
    async def test_optimized_search_success(self, mock_vector_client, sample_business_search_results, sample_query_contexts):
        """Test successful optimized search."""
        mock_vector_client.search_similar_chunks.return_value = sample_business_search_results
        mock_vector_client.get_document_relationships.return_value = []
        
        optimizer = VectorSearchOptimizer(mock_vector_client)
        query_context = sample_query_contexts['financial_analysis']
        
        result = await optimizer.optimized_search(query_context)
        
        # Verify response structure
        assert result['status'] == 'success'
        assert 'query_context' in result
        assert 'search_metadata' in result
        assert 'results' in result
        assert 'optimization_insights' in result
        
        # Verify metadata
        assert result['search_metadata']['strategy_used'] == 'financial_analysis'
        assert result['search_metadata']['processing_time'] > 0
        assert len(result['results']) > 0
    
    @pytest.mark.asyncio
    async def test_empty_search_results(self, mock_vector_client, sample_query_contexts):
        """Test handling of empty search results."""
        mock_vector_client.search_similar_chunks.return_value = []
        
        optimizer = VectorSearchOptimizer(mock_vector_client)
        query_context = sample_query_contexts['specific_lookup']
        
        result = await optimizer.optimized_search(query_context)
        
        assert result['status'] == 'success'
        assert len(result['results']) == 0
        assert 'no_results_reason' in result['search_metadata']
        assert 'suggestions' in result['optimization_insights']
    
    @pytest.mark.asyncio
    async def test_search_analytics(self, mock_vector_client):
        """Test search analytics functionality."""
        optimizer = VectorSearchOptimizer(mock_vector_client)
        
        analytics = await optimizer.get_search_analytics()
        
        assert analytics['optimizer_status'] == 'active'
        assert len(analytics['supported_strategies']) >= 4
        assert analytics['capabilities']['multi_stage_retrieval'] == True
        assert 'performance_targets' in analytics


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestVectorSearchOptimizationIntegrator:
    """Test the integration layer."""
    
    @pytest.mark.asyncio
    async def test_integrated_search(self, mock_vector_client, sample_business_search_results, sample_query_contexts):
        """Test integrated search with all components."""
        mock_vector_client.search_similar_chunks.return_value = sample_business_search_results
        mock_vector_client.get_document_relationships.return_value = []
        
        integrator = VectorSearchOptimizationIntegrator(mock_vector_client)
        query_context = sample_query_contexts['financial_analysis']
        
        result = await integrator.integrated_search(query_context)
        
        # Verify integration features
        assert result['status'] == 'success'
        assert 'routing_info' in result
        assert result['routing_info']['primary_route'] == 'financial_analysis'
        
        # Verify optimization insights
        insights = result['optimization_insights']
        assert 'avg_final_score' in insights
        assert 'document_diversity' in insights
    
    @pytest.mark.asyncio
    async def test_search_quality_calculation(self, mock_vector_client, sample_business_search_results, sample_query_contexts):
        """Test search quality calculation."""
        mock_vector_client.search_similar_chunks.return_value = sample_business_search_results
        mock_vector_client.get_document_relationships.return_value = []
        
        integrator = VectorSearchOptimizationIntegrator(mock_vector_client)
        
        # Create a successful search result
        search_result = {
            'status': 'success',
            'results': [{'final_score': 0.8}, {'final_score': 0.7}],
            'optimization_insights': {
                'avg_final_score': 0.75,
                'document_diversity': {'diversity_score': 0.6}
            }
        }
        
        quality_score = integrator._calculate_search_quality(search_result)
        
        assert 0.0 <= quality_score <= 1.0
        assert quality_score > 0.5  # Should be decent quality


# =============================================================================
# PERFORMANCE AND STRESS TESTS
# =============================================================================

class TestPerformanceMetrics:
    """Test performance and quality metrics."""
    
    @pytest.mark.asyncio
    async def test_search_performance_timing(self, mock_vector_client, sample_business_search_results, sample_query_contexts):
        """Test search performance timing."""
        mock_vector_client.search_similar_chunks.return_value = sample_business_search_results
        mock_vector_client.get_document_relationships.return_value = []
        
        optimizer = VectorSearchOptimizer(mock_vector_client)
        query_context = sample_query_contexts['financial_analysis']
        
        result = await optimizer.optimized_search(query_context)
        
        # Verify performance timing
        processing_time = result['search_metadata']['processing_time']
        assert processing_time > 0
        assert processing_time < 5.0  # Should complete within 5 seconds
    
    def test_score_distribution_analysis(self):
        """Test score distribution analysis."""
        # Import the class to test its methods directly
        from ..search.vector_search_optimizer import VectorSearchOptimizer
        
        # Create mock results with known scores
        mock_results = []
        scores = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]
        for score in scores:
            result = Mock()
            result.final_score = score
            mock_results.append(result)
        
        optimizer = VectorSearchOptimizer(Mock())
        distribution = optimizer._analyze_score_distribution(mock_results)
        
        assert distribution['min_score'] == 0.4
        assert distribution['max_score'] == 0.9
        assert distribution['high_confidence_results'] == 1  # Only 0.9 > 0.8
        assert distribution['score_range'] == 0.5
    
    def test_document_diversity_calculation(self):
        """Test document diversity calculation."""
        # Import the class to test its methods directly
        from ..search.vector_search_optimizer import VectorSearchOptimizer
        
        # Create mock results with diverse characteristics
        mock_results = []
        doc_types = ['financial_report', 'customer_record', 'financial_report']
        departments = ['accounting', 'commercial', 'accounting']
        
        for i, (doc_type, dept) in enumerate(zip(doc_types, departments)):
            result = Mock()
            result.document_type = doc_type
            result.department = dept
            result.created_at = datetime.now() - timedelta(days=i*10)
            mock_results.append(result)
        
        optimizer = VectorSearchOptimizer(Mock())
        diversity = optimizer._calculate_document_diversity(mock_results)
        
        assert diversity['unique_document_types'] == 2
        assert diversity['unique_departments'] == 2
        assert 0.0 <= diversity['diversity_score'] <= 1.0


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_vector_client_failure(self, mock_vector_client, sample_query_contexts):
        """Test handling of vector client failures."""
        mock_vector_client.search_similar_chunks.side_effect = Exception("Database connection failed")
        
        optimizer = VectorSearchOptimizer(mock_vector_client)
        query_context = sample_query_contexts['financial_analysis']
        
        result = await optimizer.optimized_search(query_context)
        
        assert result['status'] == 'error'
        assert 'error' in result
        assert 'query_context' in result
    
    @pytest.mark.asyncio
    async def test_malformed_query_context(self, mock_vector_client):
        """Test handling of malformed query context."""
        # Create malformed query context
        malformed_context = Mock()
        malformed_context.original_query = None
        malformed_context.primary_intent = "invalid_intent"
        
        optimizer = VectorSearchOptimizer(mock_vector_client)
        
        # Should handle gracefully without crashing
        try:
            result = await optimizer.optimized_search(malformed_context)
            assert result['status'] == 'error'
        except Exception:
            pytest.fail("Should handle malformed context gracefully")


# =============================================================================
# INTEGRATION WITH BUSINESS LOGIC TESTS
# =============================================================================

class TestBusinessLogicIntegration:
    """Test integration with textile business logic."""
    
    @pytest.mark.asyncio
    async def test_textile_business_context_scoring(self, mock_vector_client, sample_query_contexts):
        """Test business context scoring for textile business scenarios."""
        # Create textile-specific search results
        textile_results = [
            Mock(
                document_id=UUID('12345678-1234-5678-1234-567812345678'),
                chunk_index=0,
                score=0.75,
                file_name="MHM_Machine_Production_Report.xlsx",
                document_type="production_report",
                department="production",
                snippet="MHM embroidery machine production: 150 dozen pieces for RB Knit customer",
                created_at=datetime.now() - timedelta(days=5)
            ),
            Mock(
                document_id=UUID('87654321-4321-8765-4321-876543218765'),
                chunk_index=1,
                score=0.70,
                file_name="Textile_Customer_Orders.xlsx",
                document_type="customer_order",
                department="commercial",
                snippet="Blue Planet Knitwear order for 500 dozen at $7.50 per dozen",
                created_at=datetime.now() - timedelta(days=10)
            ),
            Mock(
                document_id=UUID('11111111-2222-3333-4444-555555555555'),
                chunk_index=0,
                score=0.65,
                file_name="Gazipur_Factory_Operations.xlsx",
                document_type="operations_report",
                department="production",
                snippet="Gazipur textile printing factory operations with MHM equipment",
                created_at=datetime.now() - timedelta(days=15)
            )
        ]
        
        mock_vector_client.search_similar_chunks.return_value = textile_results
        mock_vector_client.get_document_relationships.return_value = []
        
        engine = MultiStageRetrievalEngine(mock_vector_client)
        
        # Test with textile-specific query
        textile_query = Mock()
        textile_query.original_query = "Show MHM machine production for RB Knit"
        textile_query.cleaned_query = "mhm machine production rb knit"
        textile_query.primary_intent = QueryIntent.ANALYSIS_FINANCIAL
        textile_query.complexity = QueryComplexity.MODERATE
        textile_query.business_entities = [
            Mock(entity_type='customer', entity_value='RB Knit'),
            Mock(entity_type='machine', entity_value='MHM')
        ]
        textile_query.constraints = []
        textile_query.date_constraints = []
        textile_query.time_references = []
        textile_query.suggested_departments = ['production']
        
        strategy = SearchStrategyFactory.create_strategy(textile_query)
        results = await engine.retrieve_and_rerank(textile_query, strategy)
        
        # Verify textile business context is properly scored
        assert len(results) > 0
        
        # Results mentioning both RB Knit and MHM should score higher
        rb_knit_mhm_results = [r for r in results if 'rb knit' in r.snippet.lower() and 'mhm' in r.snippet.lower()]
        other_results = [r for r in results if not ('rb knit' in r.snippet.lower() and 'mhm' in r.snippet.lower())]
        
        if rb_knit_mhm_results and other_results:
            assert max(r.business_relevance_score for r in rb_knit_mhm_results) >= \
                   max(r.business_relevance_score for r in other_results)
    
    def test_textile_pricing_context_recognition(self, sample_query_contexts):
        """Test recognition of textile pricing context in queries."""
        router = AdvancedQueryRouter()
        
        # Create pricing-focused query
        pricing_query = Mock()
        pricing_query.original_query = "Compare pricing strategies for dozen embroidery between customers"
        pricing_query.primary_intent = QueryIntent.ANALYSIS_COMPARISON
        pricing_query.complexity = QueryComplexity.COMPLEX
        pricing_query.business_entities = [Mock(entity_type='pricing', entity_value='per dozen')]
        pricing_query.constraints = []
        
        routing_decision = router.route_query(pricing_query)
        
        # Should route to comparative analysis with pricing considerations
        assert routing_decision['primary_route'] == 'comparative_analysis'
        assert routing_decision['optimization_flags']['balance_entities'] == True
    
    @pytest.mark.asyncio
    async def test_department_specific_optimization(self, mock_vector_client, sample_business_search_results):
        """Test department-specific search optimization."""
        optimizer = VectorSearchOptimizer(mock_vector_client)
        mock_vector_client.search_similar_chunks.return_value = sample_business_search_results
        mock_vector_client.get_document_relationships.return_value = []
        
        # Test commercial department query
        commercial_query = Mock()
        commercial_query.original_query = "Show customer order status for commercial department"
        commercial_query.cleaned_query = "customer order status commercial department"
        commercial_query.primary_intent = QueryIntent.ANALYSIS_FINANCIAL  # Changed from non-existent LOOKUP_FILTERED
        commercial_query.complexity = QueryComplexity.MODERATE
        commercial_query.business_entities = []
        commercial_query.constraints = []
        commercial_query.date_constraints = []
        commercial_query.time_references = []
        commercial_query.suggested_departments = ['commercial']
        
        result = await optimizer.optimized_search(commercial_query)
        
        assert result['status'] == 'success'
        # Should have department-specific routing information
        assert 'commercial' in result['query_context']['suggested_departments'] or \
               'commercial' in str(result['search_metadata'])


# =============================================================================
# COMPREHENSIVE WORKFLOW TESTS
# =============================================================================

class TestComprehensiveWorkflows:
    """Test complete workflows from query to results."""
    
    @pytest.mark.asyncio
    async def test_financial_analysis_workflow(self, mock_vector_client):
        """Test complete financial analysis workflow."""
        # Setup comprehensive mock data
        financial_results = [
            Mock(
                document_id=UUID('12345678-1234-5678-1234-567812345678'),
                chunk_index=0,
                score=0.85,
                file_name="Monthly_Financial_Report_March_2024.xlsx",
                document_type="financial_report",
                department="accounting",
                snippet="March 2024 financial summary: Total revenue ৳500,000, expenses ৳350,000, profit ৳150,000. Major customer payments from RB Knit ৳75,000.",
                created_at=datetime.now() - timedelta(days=15)
            ),
            Mock(
                document_id=UUID('87654321-4321-8765-4321-876543218765'),
                chunk_index=1,
                score=0.78,
                file_name="Cash_Flow_Analysis_Q1_2024.xlsx",
                document_type="cash_flow",
                department="accounting",
                snippet="Q1 cash flow analysis showing strong performance with consistent monthly revenue. RB Knit contributing 15% of total revenue.",
                created_at=datetime.now() - timedelta(days=30)
            ),
            Mock(
                document_id=UUID('11111111-2222-3333-4444-555555555555'),
                chunk_index=0,
                score=0.72,
                file_name="Customer_Payment_History.xlsx",
                document_type="payment_record",
                department="accounting",
                snippet="Customer payment tracking: RB Knit - consistent payments, average ৳70,000 monthly",
                created_at=datetime.now() - timedelta(days=45)
            )
        ]
        
        mock_vector_client.search_similar_chunks.return_value = financial_results
        mock_vector_client.get_document_relationships.return_value = []
        
        # Create integrator
        integrator = VectorSearchOptimizationIntegrator(mock_vector_client)
        
        # Create financial analysis query
        financial_query = Mock()
        financial_query.original_query = "Analyze financial performance for RB Knit customer last quarter"
        financial_query.cleaned_query = "analyze financial performance rb knit customer last quarter"
        financial_query.primary_intent = QueryIntent.ANALYSIS_FINANCIAL
        financial_query.complexity = QueryComplexity.COMPLEX
        financial_query.business_entities = [Mock(entity_type='customer', entity_value='RB Knit')]
        financial_query.constraints = [Mock(constraint_type='date_period', value='last_quarter')]
        financial_query.date_constraints = [Mock(constraint_type='date_period', value='last_quarter')]
        financial_query.time_references = ['last quarter']
        financial_query.suggested_departments = ['accounting']
        
        # Execute workflow
        result = await integrator.integrated_search(financial_query)
        
        # Verify complete workflow results
        assert result['status'] == 'success'
        assert result['search_metadata']['strategy_used'] == 'financial_analysis'
        assert len(result['results']) > 0
        
        # Verify business intelligence
        insights = result['optimization_insights']
        assert insights['avg_final_score'] > 0.5
        assert 'document_diversity' in insights
        
        # Verify routing worked correctly
        routing_info = result['routing_info']
        assert routing_info['primary_route'] == 'financial_analysis'
        assert 'financial_validation' in routing_info['postprocessing_steps']
    
    @pytest.mark.asyncio
    async def test_production_trend_analysis_workflow(self, mock_vector_client):
        """Test production trend analysis workflow."""
        production_results = [
            Mock(
                document_id=UUID('12345678-1234-5678-1234-567812345678'),
                chunk_index=i,
                score=0.8 - i * 0.05,
                file_name=f"Production_Report_{month}_2024.xlsx",
                document_type="production_report",
                department="production",
                snippet=f"Production report for {month} 2024: MHM machines produced {1500 + i*100} dozen pieces",
                created_at=datetime.now() - timedelta(days=30*i)
            )
            for i, month in enumerate(['March', 'February', 'January'])
        ]
        
        mock_vector_client.search_similar_chunks.return_value = production_results
        mock_vector_client.get_document_relationships.return_value = []
        
        integrator = VectorSearchOptimizationIntegrator(mock_vector_client)
        
        # Create trend analysis query
        trend_query = Mock()
        trend_query.original_query = "Show production trends for MHM machines over the last 6 months"
        trend_query.cleaned_query = "production trends mhm machines last 6 months"
        trend_query.primary_intent = QueryIntent.ANALYSIS_TREND
        trend_query.complexity = QueryComplexity.ADVANCED
        trend_query.business_entities = [Mock(entity_type='machine', entity_value='MHM')]
        trend_query.constraints = [Mock(constraint_type='date_period', value='last_6_months')]
        trend_query.date_constraints = [Mock(constraint_type='date_period', value='last_6_months')]
        trend_query.time_references = ['last 6 months']
        trend_query.suggested_departments = ['production']
        
        result = await integrator.integrated_search(trend_query)
        
        # Verify trend analysis workflow
        assert result['status'] == 'success'
        assert result['search_metadata']['strategy_used'] == 'trend_analysis'
        assert result['search_metadata']['temporal_processing'] == True
        
        # Should have comprehensive results for trend analysis
        assert len(result['results']) >= 3  # Multiple time periods
        
        # Verify temporal handling
        routing_info = result['routing_info']
        assert routing_info['optimization_flags']['temporal_prioritization'] == True
    
    @pytest.mark.asyncio
    async def test_customer_comparison_workflow(self, mock_vector_client):
        """Test customer comparison workflow."""
        comparison_results = [
            Mock(
                document_id=UUID('12345678-1234-5678-1234-567812345678'),
                chunk_index=0,
                score=0.85,
                file_name="RB_Knit_Customer_Analysis.xlsx",
                document_type="customer_analysis",
                department="commercial",
                snippet="RB Knit performance: Monthly orders 500 dozen, average price $7.50 per dozen, payment terms 30 days",
                created_at=datetime.now() - timedelta(days=10)
            ),
            Mock(
                document_id=UUID('87654321-4321-8765-4321-876543218765'),
                chunk_index=1,
                score=0.82,
                file_name="Blue_Planet_Customer_Analysis.xlsx",
                document_type="customer_analysis",
                department="commercial",
                snippet="Blue Planet Knitwear performance: Monthly orders 400 dozen, average price $8.00 per dozen, payment terms 45 days",
                created_at=datetime.now() - timedelta(days=12)
            ),
            Mock(
                document_id=UUID('11111111-2222-3333-4444-555555555555'),
                chunk_index=0,
                score=0.78,
                file_name="Customer_Revenue_Comparison.xlsx",
                document_type="revenue_analysis",
                department="commercial",
                snippet="Revenue comparison: RB Knit ৳300,000/month vs Blue Planet ৳320,000/month",
                created_at=datetime.now() - timedelta(days=5)
            )
        ]
        
        mock_vector_client.search_similar_chunks.return_value = comparison_results
        mock_vector_client.get_document_relationships.return_value = []
        
        integrator = VectorSearchOptimizationIntegrator(mock_vector_client)
        
        # Create comparison query
        comparison_query = Mock()
        comparison_query.original_query = "Compare performance between RB Knit and Blue Planet customers"
        comparison_query.cleaned_query = "compare performance rb knit blue planet customers"
        comparison_query.primary_intent = QueryIntent.ANALYSIS_COMPARISON
        comparison_query.complexity = QueryComplexity.COMPLEX
        comparison_query.business_entities = [
            Mock(entity_type='customer', entity_value='RB Knit'),
            Mock(entity_type='customer', entity_value='Blue Planet')
        ]
        comparison_query.constraints = []
        comparison_query.date_constraints = []
        comparison_query.time_references = []
        comparison_query.suggested_departments = ['commercial']
        
        result = await integrator.integrated_search(comparison_query)
        
        # Verify comparison workflow
        assert result['status'] == 'success'
        assert result['search_metadata']['strategy_used'] == 'comparison_analysis'
        
        # Should have results covering both entities
        rb_knit_results = [r for r in result['results'] if 'rb knit' in r['snippet'].lower()]
        blue_planet_results = [r for r in result['results'] if 'blue planet' in r['snippet'].lower()]
        
        assert len(rb_knit_results) > 0
        assert len(blue_planet_results) > 0
        
        # Verify diversity and balance
        insights = result['optimization_insights']
        assert insights['document_diversity']['diversity_score'] > 0.3


# =============================================================================
# CONFIGURATION AND PYTEST SETUP
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# TEST EXECUTION AND REPORTING
# =============================================================================

class TestResultSummary:
    """Generate test execution summary and performance metrics."""
    
    @pytest.mark.asyncio
    async def test_performance_benchmark(self, mock_vector_client):
        """Benchmark overall system performance."""
        # Setup comprehensive test data
        large_result_set = []
        for i in range(100):
            result = Mock(
                document_id=uuid4(),
                chunk_index=i % 10,
                score=0.9 - (i * 0.005),
                file_name=f"test_document_{i}.xlsx",
                document_type="financial_report",
                department="accounting",
                snippet=f"Test content {i} with business data",
                created_at=datetime.now() - timedelta(days=i)
            )
            large_result_set.append(result)
        
        mock_vector_client.search_similar_chunks.return_value = large_result_set
        mock_vector_client.get_document_relationships.return_value = []
        
        optimizer = VectorSearchOptimizer(mock_vector_client)
        
        # Create test query
        test_query = Mock()
        test_query.original_query = "Performance test query for large dataset"
        test_query.cleaned_query = "performance test query large dataset"
        test_query.primary_intent = QueryIntent.ANALYSIS_FINANCIAL
        test_query.complexity = QueryComplexity.ADVANCED
        test_query.business_entities = []
        test_query.constraints = []
        test_query.date_constraints = []
        test_query.time_references = []
        test_query.suggested_departments = ['accounting']
        
        # Measure performance
        start_time = datetime.now()
        result = await optimizer.optimized_search(test_query)
        end_time = datetime.now()
        
        processing_time = (end_time - start_time).total_seconds()
        
        # Verify performance targets
        assert result['status'] == 'success'
        assert processing_time < 3.0  # Should complete within 3 seconds
        assert len(result['results']) > 0
        assert result['search_metadata']['processing_time'] > 0
        
        print(f"\n📊 Performance Benchmark Results:")
        print(f"   Total Processing Time: {processing_time:.3f} seconds")
        print(f"   Results Returned: {len(result['results'])}")
        print(f"   Strategy Used: {result['search_metadata']['strategy_used']}")
        print(f"   Average Score: {result['optimization_insights']['avg_final_score']:.3f}")


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers."""
    for item in items:
        # Mark slow tests
        if "performance" in item.nodeid or "workflow" in item.nodeid:
            item.add_marker(pytest.mark.slow)
        
        # Mark integration tests
        if "integration" in item.nodeid or "workflow" in item.nodeid:
            item.add_marker(pytest.mark.integration)


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

if __name__ == "__main__":
    """Run tests directly with python -m pytest."""
    import sys
    
    print("🧪 Task 2A-2: Vector Search Optimization Testing Suite")
    print("=" * 70)
    print("\nRunning comprehensive tests for:")
    print("✅ Multi-stage retrieval with reranking")
    print("✅ Similarity threshold optimization")
    print("✅ Cross-document relationship discovery")
    print("✅ Temporal query handling")
    print("✅ Query routing and strategy selection")
    print("✅ Performance and quality metrics")
    print("✅ Business logic integration")
    print("✅ Complete workflow testing")
    print("")
    
    # Run pytest programmatically
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--durations=10",
        "-x"  # Stop on first failure
    ])
    
    if exit_code == 0:
        print("\n🎉 All tests passed successfully!")
        print("Task 2A-2 Vector Search Optimization is ready for production!")
    else:
        print(f"\n❌ Tests failed with exit code: {exit_code}")
        print("Please review the test output and fix any issues.")
    
    sys.exit(exit_code)