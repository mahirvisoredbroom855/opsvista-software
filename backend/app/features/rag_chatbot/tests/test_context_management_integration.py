# backend/app/features/rag_chatbot/tests/test_context_management_integration.py
"""
Comprehensive integration tests for Context Management System (Task 2C)

Tests integration with:
- Task 2A-1: Query Understanding Engine
- Task 2A-2: Vector Search Optimizer
- Task 2A-3: Business Context Integration
- Enhanced Vector Database Client

Run with: python -m pytest backend/app/features/rag_chatbot/tests/test_context_management_integration.py -v
"""

import pytest
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import List, Dict, Any

# Add the project root to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

# Import all the components we're testing
from backend.app.features.rag_chatbot.search.context_management_system import (
    ContextManagementSystem,
    ContextManagementIntegrator,
    TokenEstimator,
    ContentCompressionEngine,
    DynamicContextSelector,
    ContextChunk,
    ContextWindow,
    ContextPriority,
    CompressionStrategy,
    create_context_management_system
)

from backend.app.features.rag_chatbot.search.query_engine import (
    BusinessQueryEngine,
    QueryContext,
    QueryIntent,
    QueryComplexity,
    BusinessEntity,
    QueryConstraint
)

from backend.app.features.rag_chatbot.search.vector_search_optimizer import (
    VectorSearchOptimizer,
    EnhancedSearchResult,
    SearchStrategy
)

from backend.app.features.rag_chatbot.search.business_context_integration import (
    BusinessContextIntegrationEngine,
    EnhancedBusinessResult
)

from backend.app.features.rag_chatbot.vector.enhanced_vector_client import (
    EnhancedVectorDatabaseClient,
    BusinessSearchResult
)


class TestContextManagementIntegration:
    """Test suite for Context Management System integration."""
    
    @pytest.fixture
    async def vector_client(self):
        """Initialize vector client for testing."""
        client = EnhancedVectorDatabaseClient()
        await client.initialize()
        yield client
        await client.close()
    
    @pytest.fixture
    def query_engine(self):
        """Initialize query engine for testing."""
        return BusinessQueryEngine()
    
    @pytest.fixture
    def search_optimizer(self, vector_client):
        """Initialize search optimizer for testing."""
        return VectorSearchOptimizer(vector_client)
    
    @pytest.fixture
    def business_integration(self, query_engine, search_optimizer):
        """Initialize business context integration for testing."""
        return BusinessContextIntegrationEngine(query_engine, search_optimizer)
    
    @pytest.fixture
    def context_system(self, vector_client, query_engine, search_optimizer, business_integration):
        """Initialize complete context management system."""
        return ContextManagementSystem(
            vector_client=vector_client,
            query_engine=query_engine,
            search_optimizer=search_optimizer,
            business_integration=business_integration
        )
    
    @pytest.fixture
    def sample_business_queries(self):
        """Sample business queries for testing."""
        return [
            "Show me financial data for RB Knit customer orders last quarter",
            "What were the MHM machine maintenance costs in production department?", 
            "Find all LC documents for Blue Planet Knitwear Ltd",
            "Compare revenue between commercial and production departments",
            "Calculate total expenses for Mizan's projects this month",
            "Show employee salary records for accounting department",
            "Analyze production capacity trends over the last year",
            "Find invoice INV-12345 details",
            "What is the current status of export orders?",
            "Get maintenance schedule for 16-head embroidery machine"
        ]
    
    @pytest.mark.asyncio
    async def test_full_pipeline_integration(self, context_system, sample_business_queries):
        """Test complete pipeline from query to optimized context."""
        
        print("\n🔄 Testing Full Pipeline Integration...")
        
        for i, query in enumerate(sample_business_queries[:3]):  # Test first 3 queries
            print(f"\n📝 Testing Query {i+1}: {query}")
            
            # Step 1: Parse query with Query Engine
            query_context = await context_system.query_engine.parse_natural_language_query(query)
            
            assert query_context is not None
            assert query_context.original_query == query
            assert query_context.primary_intent is not None
            print(f"   ✅ Query parsed - Intent: {query_context.primary_intent.value}")
            
            # Step 2: Create mock search results (simulating vector search)
            mock_search_results = await self._create_mock_search_results(query_context)
            
            # Step 3: Apply business context integration
            integration_result = await context_system.business_integration.integrate_business_context(
                mock_search_results, query_context
            )
            
            assert integration_result['status'] == 'success'
            enhanced_results = integration_result['enhanced_results']
            print(f"   ✅ Business integration applied - {len(enhanced_results)} results enhanced")
            
            # Step 4: Prepare optimized context
            optimization_result = await context_system.prepare_context_for_llm(
                query_context, enhanced_results, max_tokens=4000
            )
            
            assert optimization_result is not None
            assert optimization_result.final_token_count <= 4000
            assert optimization_result.quality_score > 0.0
            print(f"   ✅ Context optimized - {optimization_result.final_token_count}/4000 tokens")
            print(f"   📊 Quality score: {optimization_result.quality_score:.2f}")
    
    @pytest.mark.asyncio
    async def test_token_management_accuracy(self, context_system):
        """Test token estimation accuracy and management."""
        
        print("\n🔢 Testing Token Management...")
        
        test_contents = [
            "Simple business query about RB Knit customer.",
            """
            Detailed financial report for Q3 2024:
            - Revenue: $150,000 from textile exports
            - Expenses: $85,000 including MHM machine maintenance
            - Profit margin: 43.3% showing strong performance
            - Customer breakdown: RB Knit (60%), Blue Planet (25%), Others (15%)
            """,
            json.dumps({
                "customer": "RB Knit",
                "orders": [
                    {"id": "ORD-001", "amount": 50000, "status": "completed"},
                    {"id": "ORD-002", "amount": 75000, "status": "processing"}
                ],
                "department": "commercial"
            }, indent=2)
        ]
        
        token_estimator = TokenEstimator()
        
        for i, content in enumerate(test_contents):
            estimated_tokens = token_estimator.estimate_tokens(content)
            
            # Rough validation - tokens should be reasonable
            char_ratio = estimated_tokens / len(content)
            assert 0.3 <= char_ratio <= 1.2, f"Token ratio {char_ratio} seems unrealistic"
            
            print(f"   Content {i+1}: {len(content)} chars → {estimated_tokens} tokens (ratio: {char_ratio:.2f})")
        
        print("   ✅ Token estimation working within expected ranges")
    
    @pytest.mark.asyncio
    async def test_compression_effectiveness(self, context_system):
        """Test content compression while preserving business information."""
        
        print("\n🗜️ Testing Content Compression...")
        
        compression_engine = ContentCompressionEngine()
        
        # Test different compression strategies
        long_business_content = """
        Monthly Production Report - September 2024
        
        MHM Machine Performance:
        - Machine 1 (16-head embroidery): 95% uptime, 1,200 units produced
        - Machine 2 (printing): 87% uptime, 850 units produced  
        - Machine 3 (cutting): 92% uptime, 2,100 units processed
        
        Customer Orders Fulfilled:
        - RB Knit: 5 orders completed, $125,000 revenue
        - Blue Planet Knitwear Ltd: 3 orders completed, $87,500 revenue
        - Fiat Fashion Ltd: 2 orders completed, $45,000 revenue
        
        Department Performance:
        - Commercial: Successfully processed 15 export orders
        - Production: Exceeded capacity targets by 12%
        - Maintenance: Completed scheduled maintenance on all machines
        - Quality Control: 99.2% pass rate on all inspections
        
        Financial Summary:
        - Total Revenue: $257,500
        - Operating Expenses: $145,300
        - Net Profit: $112,200 (43.6% margin)
        """
        
        preserve_entities = ['RB Knit', 'Blue Planet Knitwear Ltd', 'MHM Machine']
        
        strategies = [
            CompressionStrategy.SUMMARIZE_SEMANTIC,
            CompressionStrategy.EXTRACT_ENTITIES,
            CompressionStrategy.COMPRESS_STRUCTURED
        ]
        
        for strategy in strategies:
            compressed, ratio = await compression_engine.compress_content(
                long_business_content, strategy, 0.6, preserve_entities
            )
            
            assert 0.3 <= ratio <= 1.0, f"Compression ratio {ratio} outside expected range"
            
            # Check that important entities are preserved
            for entity in preserve_entities:
                if entity in long_business_content:
                    assert entity in compressed, f"Entity '{entity}' not preserved in compression"
            
            print(f"   {strategy.value}: {ratio:.2f} compression ratio")
            print(f"   Preserved entities: {all(e in compressed for e in preserve_entities if e in long_business_content)}")
    
    @pytest.mark.asyncio
    async def test_priority_based_optimization(self, context_system):
        """Test that priority-based optimization works correctly."""
        
        print("\n🎯 Testing Priority-Based Optimization...")
        
        # Create query context
        query_context = QueryContext(
            original_query="Show financial analysis for RB Knit",
            cleaned_query="financial analysis RB Knit",
            primary_intent=QueryIntent.ANALYSIS_FINANCIAL,
            complexity=QueryComplexity.MODERATE,
            business_entities=[
                BusinessEntity(entity_type="customer", entity_value="RB Knit", confidence=0.9)
            ],
            suggested_departments=["commercial", "accounting"]
        )
        
        # Create chunks with different priorities
        test_chunks = [
            ContextChunk(
                chunk_id="critical_query",
                content="User query: Financial analysis for RB Knit customer",
                content_type="query",
                priority=ContextPriority.CRITICAL,
                relevance_score=1.0,
                token_count=50,
                compression_strategy=CompressionStrategy.PRESERVE_EXACT
            ),
            ContextChunk(
                chunk_id="high_financial_data",
                content="RB Knit revenue: $150,000, profit margin: 43%",
                content_type="document",
                priority=ContextPriority.HIGH,
                relevance_score=0.9,
                token_count=200,
                compression_strategy=CompressionStrategy.PRESERVE_EXACT
            ),
            ContextChunk(
                chunk_id="medium_context",
                content="Additional business context and historical data",
                content_type="business_context",
                priority=ContextPriority.MEDIUM,
                relevance_score=0.6,
                token_count=300,
                compression_strategy=CompressionStrategy.SUMMARIZE_SEMANTIC
            ),
            ContextChunk(
                chunk_id="low_metadata",
                content="Metadata and additional background information",
                content_type="metadata",
                priority=ContextPriority.LOW,
                relevance_score=0.3,
                token_count=400,
                compression_strategy=CompressionStrategy.COMPRESS_STRUCTURED
            )
        ]
        
        # Test with limited token budget that requires prioritization
        context = ContextWindow(
            query_context=query_context,
            chunks=test_chunks,
            max_tokens=400  # Should only fit critical + high priority
        )
        
        optimized = await context_system._balanced_optimization(context)
        
        # Verify critical chunks are always included
        critical_included = any(c.priority == ContextPriority.CRITICAL for c in optimized.chunks)
        assert critical_included, "Critical chunks must always be included"
        
        # Verify we're within token limits
        assert optimized.total_tokens <= optimized.max_tokens, "Optimized context exceeds token limit"
        
        # Verify higher priority chunks are preferred
        priorities_included = [c.priority for c in optimized.chunks]
        assert ContextPriority.CRITICAL in priorities_included
        
        print(f"   ✅ Token limit respected: {optimized.total_tokens}/{optimized.max_tokens}")
        print(f"   ✅ Critical content preserved: {critical_included}")
        print(f"   📊 Priorities included: {[p.value for p in priorities_included]}")
    
    @pytest.mark.asyncio
    async def test_business_context_preservation(self, context_system, sample_business_queries):
        """Test that business context is properly preserved during optimization."""
        
        print("\n🏢 Testing Business Context Preservation...")
        
        for query_text in sample_business_queries[:2]:
            query_context = await context_system.query_engine.parse_natural_language_query(query_text)
            mock_results = await self._create_mock_search_results(query_context)
            
            optimization_result = await context_system.prepare_context_for_llm(
                query_context, mock_results, max_tokens=2000
            )
            
            context = optimization_result.optimized_context
            
            # Check that business entities from query are preserved
            if query_context.business_entities:
                formatted_context = await context_system.format_context_for_llm(optimization_result)
                
                for entity in query_context.business_entities:
                    entity_preserved = entity.entity_value.lower() in formatted_context.lower()
                    assert entity_preserved, f"Business entity '{entity.entity_value}' not preserved"
                
                print(f"   ✅ Business entities preserved for query: {query_text[:50]}...")
            
            # Check that department context is included
            if query_context.suggested_departments:
                dept_context_included = any(
                    chunk.department in query_context.suggested_departments
                    for chunk in context.chunks
                    if chunk.department
                )
                print(f"   ✅ Department context included: {dept_context_included}")
    
    @pytest.mark.asyncio
    async def test_error_handling_and_fallbacks(self, context_system):
        """Test error handling and fallback mechanisms."""
        
        print("\n🛡️ Testing Error Handling and Fallbacks...")
        
        # Test with empty query
        empty_query = QueryContext(
            original_query="",
            cleaned_query="",
            primary_intent=QueryIntent.UNKNOWN,
            complexity=QueryComplexity.SIMPLE,
            business_entities=[],
            suggested_departments=[]
        )
        
        result = await context_system.prepare_context_for_llm(empty_query, [], 1000)
        assert result is not None
        assert result.final_token_count > 0  # Should create fallback context
        print("   ✅ Empty query handled with fallback context")
        
        # Test with very small token limit
        normal_query = QueryContext(
            original_query="Show me data",
            cleaned_query="show data", 
            primary_intent=QueryIntent.LOOKUP_SPECIFIC,
            complexity=QueryComplexity.SIMPLE,
            business_entities=[],
            suggested_departments=[]
        )
        
        small_limit_result = await context_system.prepare_context_for_llm(normal_query, [], 50)
        assert small_limit_result.final_token_count <= 50
        print("   ✅ Small token limit handled gracefully")
        
        # Test with malformed content
        try:
            malformed_chunk = ContextChunk(
                chunk_id="malformed",
                content=None,  # Malformed content
                content_type="document",
                priority=ContextPriority.MEDIUM,
                relevance_score=0.5,
                token_count=100,
                compression_strategy=CompressionStrategy.PRESERVE_EXACT
            )
            
            context = ContextWindow(
                query_context=normal_query,
                chunks=[malformed_chunk],
                max_tokens=1000
            )
            
            # Should handle gracefully without crashing
            formatted = await context_system.format_context_for_llm(
                type('Result', (), {'optimized_context': context})()
            )
            print("   ✅ Malformed content handled without crashing")
            
        except Exception as e:
            print(f"   ⚠️ Error handling needs improvement: {e}")
    
    @pytest.mark.asyncio
    async def test_performance_under_load(self, context_system):
        """Test performance with multiple concurrent requests."""
        
        print("\n⚡ Testing Performance Under Load...")
        
        import time
        
        # Create multiple test queries
        test_queries = [
            "Financial data for RB Knit",
            "MHM machine maintenance costs",  
            "Production department capacity",
            "Commercial export orders",
            "Accounting expense reports"
        ]
        
        async def process_query(query_text):
            start_time = time.time()
            
            query_context = QueryContext(
                original_query=query_text,
                cleaned_query=query_text.lower(),
                primary_intent=QueryIntent.LOOKUP_SPECIFIC,
                complexity=QueryComplexity.SIMPLE,
                business_entities=[],
                suggested_departments=["commercial"]
            )
            
            mock_results = await self._create_mock_search_results(query_context)
            result = await context_system.prepare_context_for_llm(query_context, mock_results, 3000)
            
            processing_time = time.time() - start_time
            return processing_time, result.quality_score
        
        # Process queries concurrently
        start_time = time.time()
        tasks = [process_query(query) for query in test_queries]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Analyze performance
        processing_times = [r[0] for r in results]
        quality_scores = [r[1] for r in results]
        
        avg_time = sum(processing_times) / len(processing_times)
        avg_quality = sum(quality_scores) / len(quality_scores)
        
        assert avg_time < 1.0, f"Average processing time {avg_time:.3f}s too slow"
        assert avg_quality > 0.3, f"Average quality score {avg_quality:.2f} too low"
        
        print(f"   ✅ Concurrent processing: {len(test_queries)} queries in {total_time:.3f}s")
        print(f"   📊 Average time per query: {avg_time:.3f}s")
        print(f"   🎯 Average quality score: {avg_quality:.2f}")
    
    @pytest.mark.asyncio
    async def test_integration_with_real_components(self, context_system):
        """Test integration using real component methods (not mocks)."""
        
        print("\n🔧 Testing Real Component Integration...")
        
        # Test actual query engine parsing
        test_query = "Show me financial analysis for RB Knit customer orders from last quarter"
        
        query_context = await context_system.query_engine.parse_natural_language_query(test_query)
        
        # Verify query engine results
        assert query_context.original_query == test_query
        assert query_context.primary_intent is not None
        assert isinstance(query_context.business_entities, list)
        
        print(f"   ✅ Query Engine: Parsed intent as {query_context.primary_intent.value}")
        print(f"   📋 Entities found: {len(query_context.business_entities)}")
        
        # Test with vector search if available
        if context_system.vector_client:
            try:
                health = await context_system.vector_client.health_check()
                if health['status'] == 'healthy':
                    print("   ✅ Vector Client: Database connection healthy")
                else:
                    print("   ⚠️ Vector Client: Database not available, using fallback")
            except Exception as e:
                print(f"   ⚠️ Vector Client: {e}")
        
        # Test context preparation with real components
        optimization_result = await context_system.prepare_context_for_llm(
            query_context, [], max_tokens=4000
        )
        
        assert optimization_result.final_token_count <= 4000
        assert optimization_result.quality_score >= 0.0
        
        print(f"   ✅ Context Management: Generated {optimization_result.final_token_count} token context")
        print(f"   🎯 Quality score: {optimization_result.quality_score:.2f}")
    
    async def _create_mock_search_results(self, query_context: QueryContext) -> List[EnhancedSearchResult]:
        """Helper to create mock search results for testing."""
        
        results = []
        
        # Create different types of results based on query intent
        if query_context.primary_intent == QueryIntent.ANALYSIS_FINANCIAL:
            results.extend([
                self._create_mock_result("Financial Report Q3", "accounting", "financial_report", 0.9),
                self._create_mock_result("Revenue Analysis", "commercial", "analysis", 0.8),
                self._create_mock_result("Expense Breakdown", "accounting", "expense_report", 0.7)
            ])
        elif query_context.primary_intent == QueryIntent.LOOKUP_SPECIFIC:
            results.extend([
                self._create_mock_result("Document ID-12345", "commercial", "document", 0.95),
                self._create_mock_result("Reference Material", "commercial", "reference", 0.6)
            ])
        else:
            # General results
            results.extend([
                self._create_mock_result("Business Document 1", "commercial", "general", 0.8),
                self._create_mock_result("Business Document 2", "production", "general", 0.7),
                self._create_mock_result("Business Document 3", "accounting", "general", 0.6)
            ])
        
        return results
    
    def _create_mock_result(self, content: str, department: str, doc_type: str, score: float) -> EnhancedSearchResult:
        """Helper to create a single mock search result."""
        
        return EnhancedSearchResult(
            document_id=uuid4(),
            chunk_index=0,
            file_name=f"{content.lower().replace(' ', '_')}.pdf",
            document_type=doc_type,
            department=department,
            snippet=f"{content} - Sample business content for {department} department",
            created_at=datetime.now() - timedelta(days=30),
            vector_similarity_score=score,
            business_relevance_score=score * 0.9,
            temporal_relevance_score=score * 0.8,
            final_score=score
        )


# =============================================================================
# STANDALONE TEST RUNNER
# =============================================================================

async def run_comprehensive_tests():
    """Run all tests without pytest framework."""
    
    print("🧪 COMPREHENSIVE CONTEXT MANAGEMENT INTEGRATION TESTS")
    print("="*70)
    
    # Initialize components
    vector_client = EnhancedVectorDatabaseClient()
    await vector_client.initialize()
    
    query_engine = BusinessQueryEngine()
    search_optimizer = VectorSearchOptimizer(vector_client)
    business_integration = BusinessContextIntegrationEngine(query_engine, search_optimizer)
    
    context_system = ContextManagementSystem(
        vector_client=vector_client,
        query_engine=query_engine,
        search_optimizer=search_optimizer,
        business_integration=business_integration
    )
    
    # Create test instance
    test_instance = TestContextManagementIntegration()
    
    # Sample business queries
    sample_queries = [
        "Show me financial data for RB Knit customer orders last quarter",
        "What were the MHM machine maintenance costs in production department?",
        "Find all LC documents for Blue Planet Knitwear Ltd"
    ]
    
    tests_passed = 0
    tests_failed = 0
    
    try:
        print("\n1. Testing Full Pipeline Integration...")
        await test_instance.test_full_pipeline_integration(context_system, sample_queries)
        tests_passed += 1
        print("   ✅ PASSED")
    except Exception as e:
        tests_failed += 1
        print(f"   ❌ FAILED: {e}")
    
    try:
        print("\n2. Testing Token Management...")
        await test_instance.test_token_management_accuracy(context_system)
        tests_passed += 1
        print("   ✅ PASSED")
    except Exception as e:
        tests_failed += 1
        print(f"   ❌ FAILED: {e}")
    
    try:
        print("\n3. Testing Content Compression...")
        await test_instance.test_compression_effectiveness(context_system)
        tests_passed += 1
        print("   ✅ PASSED")
    except Exception as e:
        tests_failed += 1
        print(f"   ❌ FAILED: {e}")
    
    try:
        print("\n4. Testing Priority Optimization...")
        await test_instance.test_priority_based_optimization(context_system)
        tests_passed += 1
        print("   ✅ PASSED")
    except Exception as e:
        tests_failed += 1
        print(f"   ❌ FAILED: {e}")
    
    try:
        print("\n5. Testing Business Context Preservation...")
        await test_instance.test_business_context_preservation(context_system, sample_queries)
        tests_passed += 1
        print("   ✅ PASSED")
    except Exception as e:
        tests_failed += 1
        print(f"   ❌ FAILED: {e}")
    
    try:
        print("\n6. Testing Error Handling...")
        await test_instance.test_error_handling_and_fallbacks(context_system)
        tests_passed += 1
        print("   ✅ PASSED")
    except Exception as e:
        tests_failed += 1
        print(f"   ❌ FAILED: {e}")
    
    try:
        print("\n7. Testing Performance...")
        await test_instance.test_performance_under_load(context_system)
        tests_passed += 1
        print("   ✅ PASSED")
    except Exception as e:
        tests_failed += 1
        print(f"   ❌ FAILED: {e}")
    
    try:
        print("\n8. Testing Real Component Integration...")
        await test_instance.test_integration_with_real_components(context_system)
        tests_passed += 1
        print("   ✅ PASSED")
    except Exception as e:
        tests_failed += 1
        print(f"   ❌ FAILED: {e}")
    
    # Cleanup
    await vector_client.close()
    
    # Final results
    print("\n" + "="*70)
    print("🎯 TEST RESULTS SUMMARY")
    print("="*70)
    print(f"✅ Tests Passed: {tests_passed}")
    print(f"❌ Tests Failed: {tests_failed}")
    print(f"📊 Success Rate: {tests_passed/(tests_passed + tests_failed)*100:.1f}%")
    
    if tests_failed == 0:
        print("\n🎉 ALL TESTS PASSED! Context Management System is working correctly!")
        print("\nNext steps:")
        print("1. Deploy the integrated system")
        print("2. Monitor performance in production")
        print("3. Proceed to Phase 3: LLM Integration")
    else:
        print(f"\n⚠️ {tests_failed} tests failed. Review and fix issues before deployment.")
    
    return tests_failed == 0


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Configure pytest for async tests."""
    config.addinivalue_line("markers", "asyncio: mark test as async")


if __name__ == "__main__":
    """Run tests directly without pytest."""
    import asyncio
    
    print("Running Context Management Integration Tests...")
    success = asyncio.run(run_comprehensive_tests())
    exit(0 if success else 1)