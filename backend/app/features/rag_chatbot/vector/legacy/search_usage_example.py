#!/usr/bin/env python3
"""
Example usage of the integrated search system.
"""

import asyncio
from integrated_search_system import ComprehensiveSearchSystem

async def main():
    """Example of using the comprehensive search system."""
    
    # Initialize the search system
    search_system = ComprehensiveSearchSystem()
    await search_system.initialize()
    
    # Get system status
    status = await search_system.get_system_status()
    print(f"System ready: {status['integration_status']['ready_for_production']}")
    
    # Perform a comprehensive search
    results = await search_system.comprehensive_search(
        query="Find RB Knit orders above $5000 from last quarter",
        business_filters={
            "department": "commercial",
            "has_financial_data": True
        }
    )
    
    if results['status'] == 'success':
        print(f"Query analyzed: {results['query_analysis']['parsed_intent']}")
        print(f"Found {len(results['results'])} results")
        print(f"Processing time: {results['performance_metrics']['total_processing_time']:.3f}s")
        
        # Show business intelligence
        bi = results['business_intelligence']
        print(f"Business insights: {len(bi.get('top_insights', []))} insights generated")
    
    # Close the system
    await search_system.close()

if __name__ == "__main__":
    asyncio.run(main())
