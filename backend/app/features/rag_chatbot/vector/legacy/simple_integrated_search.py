# backend/app/features/rag_chatbot/vector/simple_integrated_search.py
"""
Simple integrated search system that works without external search modules.
This provides basic functionality while you set up the full integration.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

# Import your existing vector infrastructure
# good
# if it imports any of these directly, make them relative:
from .enhanced_vector_client import EnhancedVectorDatabaseClient
from .integration_adapter import VectorDatabaseAdapter
from .search_integration import IntegratedSearchManager, get_production_search_manager
from ..search.vector_search_optimizer import BusinessSearchResult
# if you import from ../search, use: from ..search.query_engine import ...


logger = logging.getLogger(__name__)


# Simple query understanding without external dependencies
class QueryIntent(Enum):
    LOOKUP_SPECIFIC = "lookup_specific"
    LOOKUP_FILTERED = "lookup_filtered"
    ANALYSIS_FINANCIAL = "analysis_financial"
    ANALYSIS_COMPARISON = "analysis_comparison"
    ANALYSIS_TREND = "analysis_trend"
    SUMMARY_OVERVIEW = "summary_overview"
    UNKNOWN = "unknown"


class SimpleQueryAnalyzer:
    """Simple query analysis without external dependencies."""
    
    def __init__(self):
        self.intent_keywords = {
            QueryIntent.LOOKUP_SPECIFIC: ['find', 'show', 'get', 'where is', 'locate'],
            QueryIntent.ANALYSIS_FINANCIAL: ['calculate', 'cost', 'expense', 'revenue', 'profit', 'total', 'sum'],
            QueryIntent.ANALYSIS_COMPARISON: ['compare', 'vs', 'versus', 'difference', 'between'],
            QueryIntent.ANALYSIS_TREND: ['trend', 'over time', 'history', 'change', 'growth'],
            QueryIntent.SUMMARY_OVERVIEW: ['summary', 'overview', 'report', 'status']
        }
        
        self.business_entities = {
            'customers': ['RB Knit', 'Blue Planet Knitwear', 'Fiat Fashion'],
            'staff': ['Mizan', 'Alamin', 'Nizam', 'Jalil', 'Ria', 'Rafiq', 'Mozammel', 'Anoweer', 'Babu'],
            'departments': ['commercial', 'accounting', 'production', 'marketing', 'hr_admin', 'maintenance'],
            'machines': ['MHM', 'embroidery', 'printing', '16-head']
        }
    
    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze query and extract business context."""
        query_lower = query.lower()
        
        # Detect intent
        intent = QueryIntent.UNKNOWN
        for intent_type, keywords in self.intent_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                intent = intent_type
                break
        
        # Extract entities
        entities = {}
        for entity_type, entity_list in self.business_entities.items():
            found_entities = [entity for entity in entity_list if entity.lower() in query_lower]
            if found_entities:
                entities[entity_type] = found_entities
        
        # Suggest departments
        suggested_departments = []
        if 'financial' in query_lower or 'cost' in query_lower or 'expense' in query_lower:
            suggested_departments.append('accounting')
        if 'customer' in query_lower or 'order' in query_lower or 'export' in query_lower:
            suggested_departments.append('commercial')
        if 'machine' in query_lower or 'production' in query_lower or 'mhm' in query_lower:
            suggested_departments.append('production')
        
        return {
            'original_query': query,
            'intent': intent,
            'entities': entities,
            'suggested_departments': suggested_departments,
            'has_financial_terms': any(term in query_lower for term in ['cost', 'expense', 'revenue', 'profit', 'amount']),
            'has_temporal_terms': any(term in query_lower for term in ['last', 'this', 'quarter', 'month', 'year'])
        }


class SimpleIntegratedSearchSystem:
    """
    Simple integrated search system that works with your current setup.
    Provides enhanced search capabilities without requiring external modules.
    """
    
    def __init__(self):
        # Initialize vector infrastructure
        self.vector_client = EnhancedVectorDatabaseClient()
        self.vector_adapter = VectorDatabaseAdapter(self.vector_client)
        
        # Simple query analyzer
        self.query_analyzer = SimpleQueryAnalyzer()
        
        self.logger = logging.getLogger(__name__)
        self._initialized = False
    
    async def initialize(self):
        """Initialize the search system."""
        if not self._initialized:
            await self.vector_client.initialize()
            await self.vector_adapter.initialize()
            self._initialized = True
            self.logger.info("Simple integrated search system initialized")
    
    async def search(
        self,
        query: str,
        business_filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Perform enhanced search with query analysis and business filtering.
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            start_time = datetime.now()
            
            # Step 1: Analyze the query
            self.logger.info(f"Analyzing query: '{query}'")
            analysis = await self.query_analyzer.analyze_query(query)
            
            # Step 2: Prepare enhanced business filters
            enhanced_filters = self._prepare_business_filters(analysis, business_filters)
            
            # Step 3: Perform vector search
            self.logger.info(f"Searching with intent: {analysis['intent'].value}")
            search_results = await self.vector_client.search_similar_chunks(
                query_text=query,
                limit=limit,
                business_filters=enhanced_filters
            )
            
            # Step 4: Enhance results with business context
            enhanced_results = self._enhance_results_with_context(search_results, analysis)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return {
                'status': 'success',
                'query_analysis': {
                    'original_query': query,
                    'detected_intent': analysis['intent'].value,
                    'entities_found': analysis['entities'],
                    'suggested_departments': analysis['suggested_departments'],
                    'has_financial_context': analysis['has_financial_terms'],
                    'has_temporal_context': analysis['has_temporal_terms']
                },
                'search_metadata': {
                    'processing_time_seconds': processing_time,
                    'results_count': len(enhanced_results),
                    'filters_applied': enhanced_filters,
                    'search_strategy': self._determine_search_strategy(analysis)
                },
                'results': enhanced_results,
                'business_insights': self._generate_business_insights(enhanced_results, analysis)
            }
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'query': query
            }
    
    def _prepare_business_filters(
        self, 
        analysis: Dict[str, Any], 
        additional_filters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare business filters based on query analysis."""
        filters = additional_filters.copy() if additional_filters else {}
        
        # Add department filters from analysis
        if analysis['suggested_departments']:
            if 'department' not in filters:
                filters['department'] = analysis['suggested_departments'][0]  # Use primary suggestion
        
        # Add entity-based filters
        entities = analysis['entities']
        if 'customers' in entities:
            filters['customers'] = {'$overlap': entities['customers']}
        if 'staff' in entities:
            filters['staff_members'] = {'$overlap': entities['staff']}
        
        # Add context-based filters
        if analysis['has_financial_terms']:
            filters['has_financial_data'] = True
        
        return filters
    
    def _enhance_results_with_context(
        self, 
        search_results: List[BusinessSearchResult], 
        analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Enhance search results with business context."""
        enhanced_results = []
        
        for result in search_results:
            # Calculate business relevance score
            business_score = self._calculate_business_relevance(result, analysis)
            
            # Calculate entity matching score
            entity_score = self._calculate_entity_matching(result, analysis)
            
            # Create enhanced result
            enhanced_result = {
                'document_id': str(result.document_id),
                'chunk_index': result.chunk_index,
                'file_name': result.file_name,
                'document_type': result.document_type,
                'department': result.department,
                'snippet': result.snippet,
                'created_at': result.created_at.isoformat(),
                'scores': {
                    'similarity_score': result.score,
                    'business_relevance': business_score,
                    'entity_matching': entity_score,
                    'final_score': (result.score * 0.5 + business_score * 0.3 + entity_score * 0.2)
                },
                'business_context': {
                    'matches_intent': self._matches_intent(result, analysis),
                    'department_alignment': result.department in analysis['suggested_departments'],
                    'entity_mentions': self._find_entity_mentions(result, analysis),
                    'business_relevance_factors': self._identify_relevance_factors(result, analysis)
                }
            }
            
            enhanced_results.append(enhanced_result)
        
        # Sort by final score
        enhanced_results.sort(key=lambda x: x['scores']['final_score'], reverse=True)
        
        return enhanced_results
    
    def _calculate_business_relevance(self, result: BusinessSearchResult, analysis: Dict[str, Any]) -> float:
        """Calculate business relevance score."""
        score = 0.0
        
        # Department alignment
        if result.department in analysis['suggested_departments']:
            score += 0.4
        
        # Intent alignment
        if analysis['intent'] == QueryIntent.ANALYSIS_FINANCIAL:
            if any(term in result.snippet.lower() for term in ['cost', 'expense', 'amount', 'money']):
                score += 0.3
        elif analysis['intent'] == QueryIntent.LOOKUP_SPECIFIC:
            if any(entity in result.snippet.lower() for entities in analysis['entities'].values() for entity in entities):
                score += 0.3
        
        # Recency bonus
        days_old = (datetime.now() - result.created_at).days
        if days_old < 30:
            score += 0.2
        elif days_old < 90:
            score += 0.1
        
        return min(1.0, score)
    
    def _calculate_entity_matching(self, result: BusinessSearchResult, analysis: Dict[str, Any]) -> float:
        """Calculate entity matching score."""
        total_entities = sum(len(entities) for entities in analysis['entities'].values())
        if total_entities == 0:
            return 0.5  # Neutral score when no entities
        
        matched_entities = 0
        snippet_lower = result.snippet.lower()
        
        for entities in analysis['entities'].values():
            for entity in entities:
                if entity.lower() in snippet_lower:
                    matched_entities += 1
        
        return matched_entities / total_entities
    
    def _matches_intent(self, result: BusinessSearchResult, analysis: Dict[str, Any]) -> bool:
        """Check if result matches the detected intent."""
        intent = analysis['intent']
        snippet_lower = result.snippet.lower()
        
        if intent == QueryIntent.ANALYSIS_FINANCIAL:
            return any(term in snippet_lower for term in ['cost', 'expense', 'revenue', 'profit', 'amount'])
        elif intent == QueryIntent.LOOKUP_SPECIFIC:
            return any(entity.lower() in snippet_lower for entities in analysis['entities'].values() for entity in entities)
        elif intent == QueryIntent.ANALYSIS_COMPARISON:
            return len(analysis['entities'].get('customers', [])) > 1 or 'vs' in snippet_lower
        
        return True  # Default to true for other intents
    
    def _find_entity_mentions(self, result: BusinessSearchResult, analysis: Dict[str, Any]) -> Dict[str, List[str]]:
        """Find entity mentions in the result."""
        mentions = {}
        snippet_lower = result.snippet.lower()
        
        for entity_type, entities in analysis['entities'].items():
            found = [entity for entity in entities if entity.lower() in snippet_lower]
            if found:
                mentions[entity_type] = found
        
        return mentions
    
    def _identify_relevance_factors(self, result: BusinessSearchResult, analysis: Dict[str, Any]) -> List[str]:
        """Identify factors that make this result relevant."""
        factors = []
        
        if result.department in analysis['suggested_departments']:
            factors.append(f"Department match: {result.department}")
        
        if self._matches_intent(result, analysis):
            factors.append(f"Intent match: {analysis['intent'].value}")
        
        entity_mentions = self._find_entity_mentions(result, analysis)
        if entity_mentions:
            factors.append(f"Entity mentions: {list(entity_mentions.keys())}")
        
        days_old = (datetime.now() - result.created_at).days
        if days_old < 30:
            factors.append("Recent document")
        
        return factors
    
    def _determine_search_strategy(self, analysis: Dict[str, Any]) -> str:
        """Determine the search strategy used."""
        intent = analysis['intent']
        
        if intent == QueryIntent.LOOKUP_SPECIFIC:
            return "specific_entity_search"
        elif intent == QueryIntent.ANALYSIS_FINANCIAL:
            return "financial_analysis_search"
        elif intent == QueryIntent.ANALYSIS_COMPARISON:
            return "comparative_search"
        elif intent == QueryIntent.ANALYSIS_TREND:
            return "temporal_trend_search"
        else:
            return "general_semantic_search"
    
    def _generate_business_insights(self, results: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate business insights from search results."""
        if not results:
            return {}
        
        # Department distribution
        dept_distribution = {}
        for result in results:
            dept = result['department']
            dept_distribution[dept] = dept_distribution.get(dept, 0) + 1
        
        # Document type distribution
        doc_type_distribution = {}
        for result in results:
            doc_type = result['document_type']
            doc_type_distribution[doc_type] = doc_type_distribution.get(doc_type, 0) + 1
        
        # Average scores
        avg_similarity = sum(r['scores']['similarity_score'] for r in results) / len(results)
        avg_business_relevance = sum(r['scores']['business_relevance'] for r in results) / len(results)
        
        # High relevance results
        high_relevance_count = sum(1 for r in results if r['scores']['business_relevance'] > 0.7)
        
        return {
            'total_results': len(results),
            'department_distribution': dept_distribution,
            'document_type_distribution': doc_type_distribution,
            'average_similarity_score': round(avg_similarity, 3),
            'average_business_relevance': round(avg_business_relevance, 3),
            'high_relevance_results': high_relevance_count,
            'query_intent': analysis['intent'].value,
            'primary_departments': analysis['suggested_departments'],
            'entities_found': analysis['entities']
        }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status."""
        if not self._initialized:
            return {'status': 'not_initialized'}
        
        try:
            # Get vector client health
            vector_health = await self.vector_client.health_check()
            
            return {
                'status': 'operational',
                'components': {
                    'vector_client': vector_health.get('status', 'unknown'),
                    'query_analyzer': 'operational',
                    'business_intelligence': 'basic'
                },
                'capabilities': {
                    'query_understanding': True,
                    'entity_extraction': True,
                    'business_filtering': True,
                    'intent_detection': True,
                    'department_routing': True
                },
                'integration_status': {
                    'vector_database': vector_health.get('status') == 'healthy',
                    'business_context': True,
                    'ready_for_use': True
                }
            }
        
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def close(self):
        """Close the system."""
        try:
            await self.vector_client.close()
            await self.vector_adapter.close()
            self.logger.info("Simple integrated search system closed")
        except Exception as e:
            self.logger.error(f"Error closing system: {e}")


# Factory function for easy use
async def create_simple_search_system() -> SimpleIntegratedSearchSystem:
    """Create and initialize simple search system."""
    system = SimpleIntegratedSearchSystem()
    await system.initialize()
    return system