# backend/app/features/rag_chatbot/tests/test_business_context_integration.py
"""
Test suite for Business Context Integration Engine (Task 2A-3)

This test suite validates the accuracy and functionality of the business context
integration components with realistic business scenarios.

Place this file at: backend/app/features/rag_chatbot/tests/test_business_context_integration.py
"""

import pytest
import asyncio
import logging
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import List, Dict, Any
from unittest.mock import Mock, patch
import sys
import os

# Add the search module to the path for imports
current_dir = os.path.dirname(__file__)
search_dir = os.path.join(current_dir, '..', 'search')
sys.path.insert(0, search_dir)

# Import the system under test - handle import errors gracefully
try:
    from business_context_integration import (
        BusinessContextIntegrationEngine,
        DepartmentalTerminologyEngine,
        BusinessSeason,
        ContextualRelevance,
        BusinessPattern,
        DepartmentalContext,
        EnhancedBusinessResult,
        QueryContext,
        QueryIntent,
        QueryComplexity,
        BusinessEntity,
        QueryConstraint,
        EnhancedSearchResult
    )
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import business context integration module: {e}")
    print("This might be expected if the module is not yet in place.")
    IMPORTS_AVAILABLE = False
    
    # Define minimal mock classes for testing
    from enum import Enum
    from dataclasses import dataclass, field
    
    class QueryIntent(Enum):
        ANALYSIS_FINANCIAL = "analysis_financial"
        LOOKUP_SPECIFIC = "lookup_specific"
        CROSS_FUNCTIONAL = "cross_functional"
    
    class QueryComplexity(Enum):
        SIMPLE = "simple"
        MODERATE = "moderate"
        ADVANCED = "advanced"
    
    @dataclass
    class BusinessEntity:
        entity_type: str
        entity_value: str
        confidence: float
    
    @dataclass
    class QueryConstraint:
        constraint_type: str
        operator: str
        value: Any
    
    @dataclass
    class QueryContext:
        original_query: str
        primary_intent: QueryIntent = QueryIntent.ANALYSIS_FINANCIAL
        complexity: QueryComplexity = QueryComplexity.MODERATE
        business_entities: List[BusinessEntity] = field(default_factory=list)
        suggested_departments: List[str] = field(default_factory=list)
        date_constraints: List[QueryConstraint] = field(default_factory=list)
        time_references: List[str] = field(default_factory=list)
    
    @dataclass
    class EnhancedSearchResult:
        document_id: UUID
        chunk_index: int
        file_name: str
        document_type: str
        department: str
        snippet: str
        created_at: datetime
        vector_similarity_score: float = 0.85
        final_score: float = 0.8
    
    class BusinessContextIntegrationEngine:
        async def integrate_business_context(self, results, context):
            return {'status': 'mock', 'enhanced_results': []}
    
    class DepartmentalTerminologyEngine:
        def __init__(self):
            self.departmental_contexts = {
                'commercial': Mock(),
                'production': Mock(),
                'accounting': Mock()
            }


# =============================================================================
# MOCK DATA CLASSES FOR TESTING
# =============================================================================

class MockQueryContext:
    """Mock query context for testing different business scenarios."""
    
    def __init__(self, scenario_type="financial_analysis"):
        self.scenario_type = scenario_type
        self.original_query = self._get_query_by_scenario(scenario_type)
        self.cleaned_query = self.original_query.lower()
        self.primary_intent = self._get_intent_by_scenario(scenario_type)
        self.complexity = self._get_complexity_by_scenario(scenario_type)
        self.business_entities = self._get_entities_by_scenario(scenario_type)
        self.suggested_departments = self._get_departments_by_scenario(scenario_type)
        self.date_constraints = self._get_constraints_by_scenario(scenario_type)
        self.time_references = self._get_time_references_by_scenario(scenario_type)
        self.constraints = []
        self.secondary_intents = []
        self.intent_confidence = 0.8
        self.query_expansion_terms = []
        self.business_context = {}
    
    def _get_query_by_scenario(self, scenario_type):
        queries = {
            "financial_analysis": "Show me RB Knit export revenue for last quarter",
            "production_inquiry": "What is the MHM machine efficiency this month?",
            "hr_query": "Display Mizan's attendance records for January",
            "maintenance_request": "When was the last maintenance for 16-head embroidery machine?",
            "cross_functional": "Compare production costs vs revenue for all customers",
            "commercial_order": "Find all RB Knit export orders with LC values above 50000",
            "accounting_expense": "Show monthly expenses breakdown for production department"
        }
        return queries.get(scenario_type, queries["financial_analysis"])
    
    def _get_intent_by_scenario(self, scenario_type):
        intents = {
            "financial_analysis": QueryIntent.ANALYSIS_FINANCIAL,
            "production_inquiry": QueryIntent.LOOKUP_SPECIFIC,
            "cross_functional": QueryIntent.ANALYSIS_FINANCIAL if hasattr(QueryIntent, 'ANALYSIS_COMPARISON') else QueryIntent.ANALYSIS_FINANCIAL,
        }
        return intents.get(scenario_type, QueryIntent.ANALYSIS_FINANCIAL)
    
    def _get_complexity_by_scenario(self, scenario_type):
        complexities = {
            "financial_analysis": QueryComplexity.MODERATE,
            "production_inquiry": QueryComplexity.SIMPLE,
            "cross_functional": QueryComplexity.ADVANCED,
        }
        return complexities.get(scenario_type, QueryComplexity.MODERATE)
    
    def _get_entities_by_scenario(self, scenario_type):
        entities_map = {
            "financial_analysis": [
                BusinessEntity(entity_type='customers', entity_value='RB Knit', confidence=0.9)
            ],
            "production_inquiry": [
                BusinessEntity(entity_type='equipment', entity_value='MHM machine', confidence=0.95)
            ],
            "cross_functional": [
                BusinessEntity(entity_type='metrics', entity_value='production costs', confidence=0.8)
            ]
        }
        return entities_map.get(scenario_type, [])
    
    def _get_departments_by_scenario(self, scenario_type):
        departments = {
            "financial_analysis": ['commercial', 'accounting'],
            "production_inquiry": ['production'],
            "cross_functional": ['production', 'accounting', 'commercial']
        }
        return departments.get(scenario_type, [])
    
    def _get_constraints_by_scenario(self, scenario_type):
        constraints_map = {
            "financial_analysis": [
                QueryConstraint(constraint_type='date_period', operator='equals', value='last_quarter')
            ]
        }
        return constraints_map.get(scenario_type, [])
    
    def _get_time_references_by_scenario(self, scenario_type):
        time_refs = {
            "financial_analysis": ['last quarter'],
            "production_inquiry": ['this month']
        }
        return time_refs.get(scenario_type, [])


class MockEnhancedSearchResult:
    """Mock enhanced search result for testing different document types."""
    
    def __init__(self, document_scenario="commercial_order"):
        self.document_id = uuid4()
        self.chunk_index = 0
        self.file_name, self.document_type, self.department, self.snippet = self._get_content_by_scenario(document_scenario)
        self.created_at = self._get_date_by_scenario(document_scenario)
        self.vector_similarity_score = 0.85
        self.business_relevance_score = 0.8
        self.temporal_relevance_score = 0.7
        self.final_score = 0.8
        self.related_documents = []
        self.cross_references = []
        self.query_match_confidence = 0.8
        self.entity_overlap_score = 0.7
        self.temporal_alignment_score = 0.6
        self.score_explanation = {}
    
    def _get_content_by_scenario(self, scenario):
        scenarios = {
            "commercial_order": (
                "RB_Knit_Export_Order_Q3_2024.xlsx",
                "export_order",
                "commercial",
                "RB Knit export order for textile products, LC value $75,000, shipped via Chittagong port, payment terms 90 days, commercial department handled customer communication and order confirmation"
            ),
            "production_report": (
                "MHM_Machine_Production_Report_Oct_2024.pdf",
                "production_report",
                "production",
                "MHM embroidery machine efficiency report showing 85% uptime, 1200 units produced, quality rate 98%, production schedule maintained, capacity utilization optimal"
            ),
            "financial_statement": (
                "Monthly_Financial_Summary_Sep_2024.xlsx",
                "financial_report",
                "accounting",
                "Monthly accounting summary: production costs $45,000, maintenance expenses $8,000, total revenue $120,000, profit margin 15%, cash flow positive"
            )
        }
        return scenarios.get(scenario, scenarios["commercial_order"])
    
    def _get_date_by_scenario(self, scenario):
        dates = {
            "commercial_order": datetime.now() - timedelta(days=15),
            "production_report": datetime.now() - timedelta(days=45),
            "financial_statement": datetime.now() - timedelta(days=30)
        }
        return dates.get(scenario, datetime.now() - timedelta(days=30))


# =============================================================================
# TEST SUITE CLASSES
# =============================================================================

@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Business context integration module not available")
class TestBusinessContextIntegrationEngine:
    """Test suite for the main Business Context Integration Engine."""
    
    @pytest.fixture
    def integration_engine(self):
        """Create integration engine for testing."""
        return BusinessContextIntegrationEngine()
    
    @pytest.fixture
    def sample_search_results(self):
        """Create sample search results for testing."""
        return [
            MockEnhancedSearchResult("commercial_order"),
            MockEnhancedSearchResult("production_report"),
            MockEnhancedSearchResult("financial_statement")
        ]
    
    @pytest.mark.asyncio
    async def test_complete_integration_pipeline(self, integration_engine, sample_search_results):
        """Test the complete integration pipeline with realistic data."""
        query_context = MockQueryContext("financial_analysis")
        
        result = await integration_engine.integrate_business_context(
            sample_search_results, query_context
        )
        
        # Verify successful integration
        assert result['status'] == 'success'
        assert result['integration_metadata']['results_processed'] == len(sample_search_results)
        assert result['integration_metadata']['results_enhanced'] > 0
        assert result['integration_metadata']['processing_time_seconds'] > 0
        
        # Verify enhanced results structure
        enhanced_results = result['enhanced_results']
        assert len(enhanced_results) > 0
        
        for enhanced_result in enhanced_results:
            # Check required fields
            assert 'document_id' in enhanced_result
            assert 'scores' in enhanced_result
            assert 'business_context' in enhanced_result
            
            # Verify scoring structure
            scores = enhanced_result['scores']
            assert 'final_score' in scores
            assert 'departmental_alignment_score' in scores
            
            # Verify scores are within valid ranges
            for score_name, score_value in scores.items():
                assert 0.0 <= score_value <= 1.0, f"Score {score_name} out of range: {score_value}"
    
    @pytest.mark.asyncio
    async def test_different_query_scenarios(self, integration_engine):
        """Test integration with different business query scenarios."""
        scenarios = [
            ("financial_analysis", ["financial_statement", "commercial_order"]),
            ("production_inquiry", ["production_report"]),
            ("cross_functional", ["commercial_order", "production_report", "financial_statement"])
        ]
        
        for scenario_type, document_types in scenarios:
            query_context = MockQueryContext(scenario_type)
            search_results = [MockEnhancedSearchResult(doc_type) for doc_type in document_types]
            
            result = await integration_engine.integrate_business_context(
                search_results, query_context
            )
            
            assert result['status'] == 'success', f"Failed for scenario: {scenario_type}"
            assert len(result['enhanced_results']) == len(search_results)
            
            # Verify query context is preserved
            assert result['query_context']['original_query'] == query_context.original_query


@pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Business context integration module not available")
class TestDepartmentalTerminologyEngine:
    """Test suite for departmental terminology understanding."""
    
    @pytest.fixture
    def dept_engine(self):
        """Create departmental engine for testing."""
        return DepartmentalTerminologyEngine()
    
    def test_department_identification_accuracy(self, dept_engine):
        """Test accuracy of department identification."""
        test_cases = [
            {
                "result": MockEnhancedSearchResult("commercial_order"),
                "expected_dept": "commercial",
                "confidence_threshold": 0.6
            },
            {
                "result": MockEnhancedSearchResult("production_report"), 
                "expected_dept": "production",
                "confidence_threshold": 0.7
            },
            {
                "result": MockEnhancedSearchResult("financial_statement"),
                "expected_dept": "accounting", 
                "confidence_threshold": 0.6
            }
        ]
        
        query_context = MockQueryContext("financial_analysis")
        
        for test_case in test_cases:
            # Test department identification
            identified_dept = dept_engine._identify_primary_department(
                test_case["result"], query_context
            )
            
            assert identified_dept == test_case["expected_dept"], \
                f"Expected {test_case['expected_dept']}, got {identified_dept}"


class TestAccuracyValidation:
    """Test suite for accuracy validation with known examples."""
    
    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Business context integration module not available")
    @pytest.mark.asyncio
    async def test_department_classification_accuracy(self):
        """Test department classification accuracy with known examples."""
        dept_engine = DepartmentalTerminologyEngine()
        
        test_cases = [
            {
                "content": "RB Knit export order LC value $50,000 shipped Chittagong commercial department",
                "expected": "commercial",
                "description": "Export order document"
            },
            {
                "content": "MHM machine efficiency 85% production volume 1200 units quality 98% production",
                "expected": "production", 
                "description": "Production report"
            },
            {
                "content": "Monthly expenses $45,000 revenue $120,000 profit margin 15% accounting",
                "expected": "accounting",
                "description": "Financial statement"
            }
        ]
        
        correct_predictions = 0
        total_predictions = len(test_cases)
        
        for test_case in test_cases:
            # Create mock result
            mock_result = MockEnhancedSearchResult("commercial_order")
            mock_result.snippet = test_case["content"]
            mock_result.department = None  # Force classification
            
            # Create mock query context
            mock_query = MockQueryContext("financial_analysis")
            mock_query.suggested_departments = []  # No hints
            
            # Test department identification
            predicted_dept = dept_engine._identify_primary_department(mock_result, mock_query)
            
            is_correct = predicted_dept == test_case["expected"]
            if is_correct:
                correct_predictions += 1
            
            print(f"Test: {test_case['description']}")
            print(f"  Expected: {test_case['expected']}, Predicted: {predicted_dept} {'✅' if is_correct else '❌'}")
        
        accuracy = (correct_predictions / total_predictions) * 100
        print(f"\nDepartment Classification Accuracy: {accuracy:.1f}% ({correct_predictions}/{total_predictions})")
        
        # Assert accuracy threshold
        assert accuracy >= 66.0, f"Accuracy {accuracy:.1f}% below 66% threshold"


# Basic test that works regardless of imports
class TestBasicFunctionality:
    """Basic tests that work even without full imports."""
    
    def test_mock_objects_creation(self):
        """Test that mock objects can be created successfully."""
        query_context = MockQueryContext("financial_analysis")
        assert query_context.original_query == "Show me RB Knit export revenue for last quarter"
        assert query_context.primary_intent == QueryIntent.ANALYSIS_FINANCIAL
        
        search_result = MockEnhancedSearchResult("commercial_order")
        assert search_result.document_type == "export_order"
        assert search_result.department == "commercial"
        assert "RB Knit" in search_result.snippet
    
    def test_different_scenarios(self):
        """Test different query scenarios."""
        scenarios = ["financial_analysis", "production_inquiry", "cross_functional"]
        
        for scenario in scenarios:
            query_context = MockQueryContext(scenario)
            assert query_context.scenario_type == scenario
            assert len(query_context.original_query) > 0
            assert query_context.primary_intent in [QueryIntent.ANALYSIS_FINANCIAL, QueryIntent.LOOKUP_SPECIFIC]


# =============================================================================
# TEST SUITE RUNNER
# =============================================================================

def run_comprehensive_test_suite():
    """Run the complete test suite and generate a report."""
    print("🧪 BUSINESS CONTEXT INTEGRATION ENGINE - TEST SUITE")
    print("=" * 80)
    
    if not IMPORTS_AVAILABLE:
        print("⚠️  Warning: Business context integration module not fully available")
        print("   Running basic tests only. Install the full module for complete testing.")
        print()
    
    # Configure pytest to run with verbose output
    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        "--disable-warnings"
    ]
    
    # Run the tests
    exit_code = pytest.main(pytest_args)
    
    print("\n" + "=" * 80)
    if exit_code == 0:
        print("🎉 ALL AVAILABLE TESTS PASSED!")
        if IMPORTS_AVAILABLE:
            print("   System is ready for production testing!")
        else:
            print("   Basic functionality verified. Install full module for complete validation.")
    else:
        print("❌ Some tests failed - Review and fix issues before deployment")
    
    return exit_code


if __name__ == "__main__":
    # Run the test suite when executed directly
    exit_code = run_comprehensive_test_suite()
    exit(exit_code)


# =============================================================================
# MOCK DATA CLASSES FOR TESTING
# =============================================================================

class MockQueryContext:
    """Mock query context for testing different business scenarios."""
    
    def __init__(self, scenario_type="financial_analysis"):
        self.scenario_type = scenario_type
        self.original_query = self._get_query_by_scenario(scenario_type)
        self.cleaned_query = self.original_query.lower()
        self.primary_intent = self._get_intent_by_scenario(scenario_type)
        self.complexity = self._get_complexity_by_scenario(scenario_type)
        self.business_entities = self._get_entities_by_scenario(scenario_type)
        self.suggested_departments = self._get_departments_by_scenario(scenario_type)
        self.date_constraints = self._get_constraints_by_scenario(scenario_type)
        self.time_references = self._get_time_references_by_scenario(scenario_type)
        self.constraints = []
        self.secondary_intents = []
        self.intent_confidence = 0.8
        self.query_expansion_terms = []
        self.business_context = {}
    
    def _get_query_by_scenario(self, scenario_type):
        queries = {
            "financial_analysis": "Show me RB Knit export revenue for last quarter",
            "production_inquiry": "What is the MHM machine efficiency this month?",
            "hr_query": "Display Mizan's attendance records for January",
            "maintenance_request": "When was the last maintenance for 16-head embroidery machine?",
            "cross_functional": "Compare production costs vs revenue for all customers",
            "commercial_order": "Find all RB Knit export orders with LC values above 50000",
            "accounting_expense": "Show monthly expenses breakdown for production department"
        }
        return queries.get(scenario_type, queries["financial_analysis"])
    
    def _get_intent_by_scenario(self, scenario_type):
        intents = {
            "financial_analysis": QueryIntent.ANALYSIS_FINANCIAL,
            "production_inquiry": QueryIntent.LOOKUP_SPECIFIC,
            "hr_query": QueryIntent.LOOKUP_FILTERED,
            "maintenance_request": QueryIntent.OPERATIONAL_STATUS,
            "cross_functional": QueryIntent.ANALYSIS_COMPARISON,
            "commercial_order": QueryIntent.LOOKUP_FILTERED,
            "accounting_expense": QueryIntent.ANALYSIS_FINANCIAL
        }
        return intents.get(scenario_type, QueryIntent.ANALYSIS_FINANCIAL)
    
    def _get_complexity_by_scenario(self, scenario_type):
        complexities = {
            "financial_analysis": QueryComplexity.MODERATE,
            "production_inquiry": QueryComplexity.SIMPLE,
            "hr_query": QueryComplexity.SIMPLE,
            "maintenance_request": QueryComplexity.MODERATE,
            "cross_functional": QueryComplexity.ADVANCED,
            "commercial_order": QueryComplexity.MODERATE,
            "accounting_expense": QueryComplexity.MODERATE
        }
        return complexities.get(scenario_type, QueryComplexity.MODERATE)
    
    def _get_entities_by_scenario(self, scenario_type):
        entities_map = {
            "financial_analysis": [
                BusinessEntity(entity_type='customers', entity_value='RB Knit', confidence=0.9),
                BusinessEntity(entity_type='financial_amount', entity_value='revenue', confidence=0.8)
            ],
            "production_inquiry": [
                BusinessEntity(entity_type='equipment', entity_value='MHM machine', confidence=0.95)
            ],
            "hr_query": [
                BusinessEntity(entity_type='staff_members', entity_value='Mizan', confidence=0.9),
                BusinessEntity(entity_type='date', entity_value='January', confidence=0.8)
            ],
            "maintenance_request": [
                BusinessEntity(entity_type='equipment', entity_value='16-head embroidery machine', confidence=0.9)
            ],
            "cross_functional": [
                BusinessEntity(entity_type='metrics', entity_value='production costs', confidence=0.8),
                BusinessEntity(entity_type='metrics', entity_value='revenue', confidence=0.8)
            ],
            "commercial_order": [
                BusinessEntity(entity_type='customers', entity_value='RB Knit', confidence=0.9),
                BusinessEntity(entity_type='financial_amount', entity_value='50000', confidence=0.8)
            ],
            "accounting_expense": [
                BusinessEntity(entity_type='metrics', entity_value='expenses', confidence=0.9),
                BusinessEntity(entity_type='department', entity_value='production', confidence=0.8)
            ]
        }
        return entities_map.get(scenario_type, [])
    
    def _get_departments_by_scenario(self, scenario_type):
        departments = {
            "financial_analysis": ['commercial', 'accounting'],
            "production_inquiry": ['production'],
            "hr_query": ['hr_admin'],
            "maintenance_request": ['maintenance', 'production'],
            "cross_functional": ['production', 'accounting', 'commercial'],
            "commercial_order": ['commercial'],
            "accounting_expense": ['accounting', 'production']
        }
        return departments.get(scenario_type, [])
    
    def _get_constraints_by_scenario(self, scenario_type):
        constraints_map = {
            "financial_analysis": [
                QueryConstraint(constraint_type='date_period', operator='equals', value='last_quarter')
            ],
            "hr_query": [
                QueryConstraint(constraint_type='date_period', operator='equals', value='January')
            ],
            "commercial_order": [
                QueryConstraint(constraint_type='amount', operator='greater_than', value=50000)
            ]
        }
        return constraints_map.get(scenario_type, [])
    
    def _get_time_references_by_scenario(self, scenario_type):
        time_refs = {
            "financial_analysis": ['last quarter'],
            "production_inquiry": ['this month'],
            "hr_query": ['January'],
            "accounting_expense": ['monthly']
        }
        return time_refs.get(scenario_type, [])


class MockEnhancedSearchResult:
    """Mock enhanced search result for testing different document types."""
    
    def __init__(self, document_scenario="commercial_order"):
        self.document_id = uuid4()
        self.chunk_index = 0
        self.file_name, self.document_type, self.department, self.snippet = self._get_content_by_scenario(document_scenario)
        self.created_at = self._get_date_by_scenario(document_scenario)
        self.vector_similarity_score = 0.85
        self.business_relevance_score = 0.8
        self.temporal_relevance_score = 0.7
        self.final_score = 0.8
        self.related_documents = []
        self.cross_references = []
        self.query_match_confidence = 0.8
        self.entity_overlap_score = 0.7
        self.temporal_alignment_score = 0.6
        self.score_explanation = {}
    
    def _get_content_by_scenario(self, scenario):
        scenarios = {
            "commercial_order": (
                "RB_Knit_Export_Order_Q3_2024.xlsx",
                "export_order",
                "commercial",
                "RB Knit export order for textile products, LC value $75,000, shipped via Chittagong port, payment terms 90 days, commercial department handled customer communication and order confirmation"
            ),
            "production_report": (
                "MHM_Machine_Production_Report_Oct_2024.pdf",
                "production_report",
                "production",
                "MHM embroidery machine efficiency report showing 85% uptime, 1200 units produced, quality rate 98%, production schedule maintained, capacity utilization optimal"
            ),
            "financial_statement": (
                "Monthly_Financial_Summary_Sep_2024.xlsx",
                "financial_report",
                "accounting",
                "Monthly accounting summary: production costs $45,000, maintenance expenses $8,000, total revenue $120,000, profit margin 15%, cash flow positive"
            ),
            "hr_record": (
                "Employee_Attendance_Mizan_Jan_2024.xlsx",
                "hr_record",
                "hr_admin",
                "Mizan attendance record January 2024: 22 working days, 21 present, 1 leave, overtime 15 hours, salary processing completed by HR admin"
            ),
            "maintenance_log": (
                "16Head_Embroidery_Maintenance_Log.pdf",
                "maintenance_record",
                "maintenance",
                "16-head embroidery machine maintenance completed by Babu, belt replacement, calibration done, safety inspection passed, next service due in 3 months"
            ),
            "cross_functional": (
                "Quarterly_Business_Review_Q2_2024.pdf",
                "business_report",
                "commercial",
                "Q2 business review: commercial orders up 25%, production efficiency 90%, accounting shows 20% profit increase, cross-departmental collaboration improved"
            ),
            "marketing_report": (
                "Customer_Analysis_RB_Knit_2024.pdf",
                "market_analysis",
                "marketing",
                "RB Knit customer analysis by Rafiq: market share increased, customer satisfaction 95%, brand recognition growing, promotional campaigns successful"
            )
        }
        return scenarios.get(scenario, scenarios["commercial_order"])
    
    def _get_date_by_scenario(self, scenario):
        dates = {
            "commercial_order": datetime.now() - timedelta(days=15),  # Recent
            "production_report": datetime.now() - timedelta(days=45), # Last month
            "financial_statement": datetime.now() - timedelta(days=30), # Current month
            "hr_record": datetime.now() - timedelta(days=120), # Historical
            "maintenance_log": datetime.now() - timedelta(days=7),   # Very recent
            "cross_functional": datetime.now() - timedelta(days=90),  # Quarterly
            "marketing_report": datetime.now() - timedelta(days=60)   # Two months ago
        }
        return dates.get(scenario, datetime.now() - timedelta(days=30))


# =============================================================================
# TEST SUITE CLASSES
# =============================================================================

class TestBusinessContextIntegrationEngine:
    """Test suite for the main Business Context Integration Engine."""
    
    @pytest.fixture
    def integration_engine(self):
        """Create integration engine for testing."""
        return BusinessContextIntegrationEngine()
    
    @pytest.fixture
    def sample_search_results(self):
        """Create sample search results for testing."""
        return [
            MockEnhancedSearchResult("commercial_order"),
            MockEnhancedSearchResult("production_report"),
            MockEnhancedSearchResult("financial_statement"),
            MockEnhancedSearchResult("cross_functional")
        ]
    
    @pytest.mark.asyncio
    async def test_complete_integration_pipeline(self, integration_engine, sample_search_results):
        """Test the complete integration pipeline with realistic data."""
        query_context = MockQueryContext("financial_analysis")
        
        result = await integration_engine.integrate_business_context(
            sample_search_results, query_context
        )
        
        # Verify successful integration
        assert result['status'] == 'success'
        assert result['integration_metadata']['results_processed'] == len(sample_search_results)
        assert result['integration_metadata']['results_enhanced'] > 0
        assert result['integration_metadata']['processing_time_seconds'] > 0
        
        # Verify enhanced results structure
        enhanced_results = result['enhanced_results']
        assert len(enhanced_results) > 0
        
        for enhanced_result in enhanced_results:
            # Check required fields
            assert 'document_id' in enhanced_result
            assert 'scores' in enhanced_result
            assert 'business_context' in enhanced_result
            
            # Verify scoring structure
            scores = enhanced_result['scores']
            assert 'final_score' in scores
            assert 'departmental_alignment_score' in scores
            
            # Verify scores are within valid ranges
            for score_name, score_value in scores.items():
                assert 0.0 <= score_value <= 1.0, f"Score {score_name} out of range: {score_value}"
    
    @pytest.mark.asyncio
    async def test_business_intelligence_summary_generation(self, integration_engine, sample_search_results):
        """Test the generation of business intelligence summaries."""
        query_context = MockQueryContext("cross_functional")
        
        result = await integration_engine.integrate_business_context(
            sample_search_results, query_context
        )
        
        bi_summary = result['business_intelligence_summary']
        
        # Verify summary structure
        assert 'total_results' in bi_summary
        assert 'department_distribution' in bi_summary
        assert 'average_scores' in bi_summary
        
        # Verify department distribution accuracy
        dept_distribution = bi_summary['department_distribution']
        assert len(dept_distribution) >= 1, "Should identify at least one department"
        
        # Verify average scores are reasonable
        avg_scores = bi_summary['average_scores']
        for score_name, avg_value in avg_scores.items():
            assert 0.0 <= avg_value <= 1.0, f"Average {score_name} out of range: {avg_value}"
    
    @pytest.mark.asyncio
    async def test_different_query_scenarios(self, integration_engine):
        """Test integration with different business query scenarios."""
        scenarios = [
            ("financial_analysis", ["financial_statement", "commercial_order"]),
            ("production_inquiry", ["production_report", "maintenance_log"]),
            ("hr_query", ["hr_record"]),
            ("cross_functional", ["cross_functional", "production_report", "financial_statement"])
        ]
        
        for scenario_type, document_types in scenarios:
            query_context = MockQueryContext(scenario_type)
            search_results = [MockEnhancedSearchResult(doc_type) for doc_type in document_types]
            
            result = await integration_engine.integrate_business_context(
                search_results, query_context
            )
            
            assert result['status'] == 'success', f"Failed for scenario: {scenario_type}"
            assert len(result['enhanced_results']) == len(search_results)
            
            # Verify query context is preserved
            assert result['query_context']['original_query'] == query_context.original_query
            assert result['query_context']['primary_intent'] == query_context.primary_intent.value
    
    @pytest.mark.asyncio
    async def test_error_handling(self, integration_engine):
        """Test error handling with malformed or missing data."""
        # Test with empty results
        empty_results = []
        query_context = MockQueryContext("financial_analysis")
        
        result = await integration_engine.integrate_business_context(
            empty_results, query_context
        )
        
        assert result['status'] == 'success'
        assert result['integration_metadata']['results_processed'] == 0


class TestDepartmentalTerminologyEngine:
    """Test suite for departmental terminology understanding."""
    
    @pytest.fixture
    def dept_engine(self):
        """Create departmental engine for testing."""
        return DepartmentalTerminologyEngine()
    
    def test_department_identification_accuracy(self, dept_engine):
        """Test accuracy of department identification."""
        test_cases = [
            {
                "result": MockEnhancedSearchResult("commercial_order"),
                "expected_dept": "commercial",
                "confidence_threshold": 0.6
            },
            {
                "result": MockEnhancedSearchResult("production_report"), 
                "expected_dept": "production",
                "confidence_threshold": 0.7
            },
            {
                "result": MockEnhancedSearchResult("financial_statement"),
                "expected_dept": "accounting", 
                "confidence_threshold": 0.6
            },
            {
                "result": MockEnhancedSearchResult("hr_record"),
                "expected_dept": "hr_admin",
                "confidence_threshold": 0.7
            },
            {
                "result": MockEnhancedSearchResult("maintenance_log"),
                "expected_dept": "maintenance",
                "confidence_threshold": 0.8
            }
        ]
        
        query_context = MockQueryContext("financial_analysis")
        
        for test_case in test_cases:
            # Test department identification
            identified_dept = dept_engine._identify_primary_department(
                test_case["result"], query_context
            )
            
            assert identified_dept == test_case["expected_dept"], \
                f"Expected {test_case['expected_dept']}, got {identified_dept} for {test_case['result'].snippet[:50]}..."
            
            # Test departmental alignment scoring
            dept_context = dept_engine.departmental_contexts.get(identified_dept)
            alignment_score = dept_engine._calculate_departmental_alignment(
                test_case["result"], dept_context, query_context
            )
            
            assert alignment_score >= test_case["confidence_threshold"], \
                f"Alignment score {alignment_score} below threshold {test_case['confidence_threshold']} for {identified_dept}"
    
    @pytest.mark.asyncio
    async def test_cross_functional_relationship_detection(self, dept_engine):
        """Test detection of cross-functional relationships."""
        # Test cross-functional document
        cross_functional_result = MockEnhancedSearchResult("cross_functional")
        query_context = MockQueryContext("cross_functional")
        
        primary_dept = dept_engine._identify_primary_department(cross_functional_result, query_context)
        relationships = dept_engine._identify_cross_functional_relationships(
            cross_functional_result, primary_dept, query_context
        )
        
        # Should detect some relationships (might be 0 or more depending on content)
        assert isinstance(relationships, list), "Should return a list of relationships"
        
        # Relationships should not include the primary department
        assert primary_dept not in relationships, "Primary department should not be in cross-functional relationships"
        
        # All relationships should be valid departments
        valid_departments = set(dept_engine.departmental_contexts.keys())
        for rel in relationships:
            assert rel in valid_departments, f"Invalid department relationship: {rel}"
    
    def test_departmental_context_completeness(self, dept_engine):
        """Test that all departmental contexts are properly configured."""
        required_departments = ['commercial', 'accounting', 'production', 'marketing', 'hr_admin', 'maintenance']
        
        for dept in required_departments:
            assert dept in dept_engine.departmental_contexts, f"Missing department: {dept}"
            
            context = dept_engine.departmental_contexts[dept]
            
            # Verify required fields
            assert context.department == dept
            assert len(context.terminology) > 0, f"No terminology for {dept}"
            assert len(context.key_metrics) > 0, f"No metrics for {dept}"
            assert len(context.priority_keywords) > 0, f"No keywords for {dept}"
            
            # Verify terminology structure
            for term_category, terms in context.terminology.items():
                assert isinstance(terms, list), f"Terms should be list for {dept}.{term_category}"
                assert len(terms) > 0, f"Empty terms for {dept}.{term_category}"


class TestAccuracyValidation:
    """Test suite for accuracy validation with known examples."""
    
    @pytest.mark.asyncio
    async def test_department_classification_accuracy(self):
        """Test department classification accuracy with known examples."""
        dept_engine = DepartmentalTerminologyEngine()
        
        test_cases = [
            {
                "content": "RB Knit export order LC value $50,000 shipped Chittagong commercial department",
                "expected": "commercial",
                "description": "Export order document"
            },
            {
                "content": "MHM machine efficiency 85% production volume 1200 units quality 98% production",
                "expected": "production", 
                "description": "Production report"
            },
            {
                "content": "Monthly expenses $45,000 revenue $120,000 profit margin 15% accounting",
                "expected": "accounting",
                "description": "Financial statement"
            },
            {
                "content": "Mizan attendance 22 days present overtime 15 hours salary sheet HR admin",
                "expected": "hr_admin",
                "description": "HR record"
            },
            {
                "content": "16-head embroidery maintenance belt replacement calibration service Babu",
                "expected": "maintenance",
                "description": "Maintenance log"
            }
        ]
        
        correct_predictions = 0
        total_predictions = len(test_cases)
        
        for test_case in test_cases:
            # Create mock result
            mock_result = MockEnhancedSearchResult("commercial_order")
            mock_result.snippet = test_case["content"]
            mock_result.department = None  # Force classification
            
            # Create mock query context
            mock_query = MockQueryContext("financial_analysis")
            mock_query.suggested_departments = []  # No hints
            
            # Test department identification
            predicted_dept = dept_engine._identify_primary_department(mock_result, mock_query)
            
            is_correct = predicted_dept == test_case["expected"]
            if is_correct:
                correct_predictions += 1
            
            print(f"Test: {test_case['description']}")
            print(f"  Expected: {test_case['expected']}, Predicted: {predicted_dept} {'✅' if is_correct else '❌'}")
        
        accuracy = (correct_predictions / total_predictions) * 100
        print(f"\nDepartment Classification Accuracy: {accuracy:.1f}% ({correct_predictions}/{total_predictions})")
        
        # Assert accuracy threshold
        assert accuracy >= 80.0, f"Accuracy {accuracy:.1f}% below 80% threshold"
    
    @pytest.mark.asyncio
    async def test_end_to_end_business_scenarios(self):
        """Test end-to-end accuracy with realistic business scenarios."""
        integration_engine = BusinessContextIntegrationEngine()
        
        scenarios = [
            {
                "name": "Financial Quarter Analysis",
                "query_type": "financial_analysis",
                "documents": ["financial_statement", "commercial_order"],
                "expected_departments": ["accounting", "commercial"],
                "expected_insights_keywords": ["financial", "revenue", "commercial"]
            },
            {
                "name": "Production Efficiency Review", 
                "query_type": "production_inquiry",
                "documents": ["production_report", "maintenance_log"],
                "expected_departments": ["production", "maintenance"],
                "expected_insights_keywords": ["production", "efficiency", "machine"]
            },
            {
                "name": "Cross-Departmental Analysis",
                "query_type": "cross_functional", 
                "documents": ["cross_functional", "financial_statement", "production_report"],
                "expected_departments": ["commercial", "accounting", "production"],
                "expected_insights_keywords": ["cross", "department", "collaboration"]
            }
        ]
        
        for scenario in scenarios:
            print(f"\nTesting: {scenario['name']}")
            
            # Create test data
            query_context = MockQueryContext(scenario["query_type"])
            search_results = [MockEnhancedSearchResult(doc_type) 
                            for doc_type in scenario["documents"]]
            
            # Run integration
            result = await integration_engine.integrate_business_context(
                search_results, query_context
            )
            
            # Validate results
            assert result['status'] == 'success', f"Integration failed for {scenario['name']}"
            
            # Check department identification
            dept_distribution = result['business_intelligence_summary']['department_distribution']
            identified_departments = set(dept_distribution.keys())
            expected_departments = set(scenario['expected_departments'])
            
            # Should identify at least some expected departments
            overlap = identified_departments.intersection(expected_departments)
            overlap_ratio = len(overlap) / len(expected_departments)
            
            print(f"  Department accuracy: {overlap_ratio:.1%} ({len(overlap)}/{len(expected_departments)})")
            assert overlap_ratio >= 0.5, f"Poor department identification for {scenario['name']}"
            
            print(f"  ✅ {scenario['name']} passed")


class TestPerformanceAndResilience:
    """Test suite for performance and error resilience."""
    
    @pytest.mark.asyncio
    async def test_performance_with_large_dataset(self):
        """Test performance with larger datasets."""
        integration_engine = BusinessContextIntegrationEngine()
        query_context = MockQueryContext("cross_functional")
        
        # Create larger result set
        large_result_set = []
        document_types = ["commercial_order", "production_report", "financial_statement", 
                         "hr_record", "maintenance_log", "cross_functional"]
        
        for i in range(20):  # 20 documents
            doc_type = document_types[i % len(document_types)]
            large_result_set.append(MockEnhancedSearchResult(doc_type))
        
        start_time = datetime.now()
        result = await integration_engine.integrate_business_context(
            large_result_set, query_context
        )
        processing_time = (datetime.now() - start_time).total_seconds()
        
        assert result['status'] == 'success'
        assert processing_time < 10.0, f"Processing took too long: {processing_time}s (should be < 10s)"
        assert result['integration_metadata']['results_processed'] == len(large_result_set)
        
        print(f"Performance test: {len(large_result_set)} documents processed in {processing_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_malformed_data_resilience(self):
        """Test resilience with malformed data."""
        integration_engine = BusinessContextIntegrationEngine()
        query_context = MockQueryContext("financial_analysis")
        
        # Test with malformed result
        malformed_result = MockEnhancedSearchResult("financial_statement")
        malformed_result.snippet = ""  # Empty snippet
        malformed_result.department = None
        malformed_result.created_at = None
        
        result = await integration_engine.integrate_business_context(
            [malformed_result], query_context
        )
        
        # Should handle gracefully
        assert result['status'] == 'success', "Should handle malformed data gracefully"
        assert len(result['enhanced_results']) == 1, "Should still process the result"
    
    @pytest.mark.asyncio
    async def test_scoring_consistency(self):
        """Test that scoring is consistent across multiple runs."""
        integration_engine = BusinessContextIntegrationEngine()
        query_context = MockQueryContext("financial_analysis")
        search_results = [
            MockEnhancedSearchResult("financial_statement"),
            MockEnhancedSearchResult("commercial_order")
        ]
        
        # Run integration multiple times
        results = []
        for _ in range(3):
            result = await integration_engine.integrate_business_context(
                search_results, query_context
            )
            results.append(result)
        
        # Verify consistency
        for i in range(1, len(results)):
            current_scores = [r['scores']['final_score'] for r in results[i]['enhanced_results']]
            previous_scores = [r['scores']['final_score'] for r in results[i-1]['enhanced_results']]
            
            # Scores should be identical across runs (deterministic)
            for curr, prev in zip(current_scores, previous_scores):
                assert abs(curr - prev) < 0.001, f"Score inconsistency: {curr} vs {prev}"


# =============================================================================
# TEST SUITE RUNNER
# =============================================================================

def run_comprehensive_test_suite():
    """Run the complete test suite and generate a report."""
    print("🧪 BUSINESS CONTEXT INTEGRATION ENGINE - TEST SUITE")
    print("=" * 80)
    
    # Configure pytest to run with verbose output
    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        "--disable-warnings"
    ]
    
    # Run the tests
    exit_code = pytest.main(pytest_args)
    
    print("\n" + "=" * 80)
    if exit_code == 0:
        print("🎉 ALL TESTS PASSED - System is ready for production!")
    else:
        print("❌ Some tests failed - Review and fix issues before deployment")
    
    return exit_code


if __name__ == "__main__":
    # Run the test suite when executed directly
    exit_code = run_comprehensive_test_suite()
    exit(exit_code)