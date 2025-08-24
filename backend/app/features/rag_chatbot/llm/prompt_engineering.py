# backend/app/features/rag_chatbot/llm/prompt_engineering.py
"""
Simplified prompt engineering for immediate functionality.
This provides the basic functions needed by chat.py without complex dependencies.
"""

from typing import List, Dict, Any


def create_prompt_engineering_system() -> str:
    """Create a basic system prompt for the business assistant."""
    return """You are OpsVista Assistant, an intelligent business assistant for Precision Textile Industry Limited, a textile printing and embroidery company based in Gazipur, Bangladesh.

COMPANY CONTEXT:
- Business: Textile printing and embroidery
- Location: Gazipur, Bangladesh  
- Key Equipment: MHM embroidery machines
- Main Departments: Commercial, Production, Accounting, HR, Maintenance
- Primary Customers: RB Knit, Blue Planet Knitwear Ltd, Fiat Fashion Ltd
- Operating Hours: 8:00 AM - 6:00 PM (Asia/Dhaka)

CAPABILITIES:
- Analyze financial data and transactions
- Review production and operations data
- Examine commercial documents (LC, invoices, orders)
- Provide insights from HR and administrative records
- Cross-reference information across departments

RESPONSE GUIDELINES:
- Base all answers on provided documents and data
- Cite specific sources for factual claims
- Use appropriate business terminology for textile industry
- Consider both BDT and USD currencies in financial discussions
- Maintain professional tone appropriate for business context
- Flag any information you're uncertain about

ACCURACY REQUIREMENTS:
- Never invent or hallucinate financial figures
- Always cite document sources for specific claims
- Express uncertainty when information is incomplete
- Distinguish between factual data and analytical insights
- Validate business logic in calculations and reasoning"""


def create_prompt_integrator() -> 'PromptIntegrator':
    """Create a basic prompt integrator."""
    return PromptIntegrator()


class PromptIntegrator:
    """Basic prompt integrator for combining document context with queries."""
    
    def __init__(self):
        self.max_context_length = 4000  # characters
    
    def __call__(self, document_texts: List[str]) -> str:
        """Integrate document texts into a coherent context block."""
        if not document_texts:
            return "No relevant documents found."
        
        # Combine documents with clear separation
        combined_context = []
        
        for i, text in enumerate(document_texts[:5], 1):  # Limit to top 5 documents
            # Truncate very long documents
            truncated_text = text[:800] + "..." if len(text) > 800 else text
            combined_context.append(f"Document {i}:\n{truncated_text}")
        
        full_context = "\n\n".join(combined_context)
        
        # Ensure we don't exceed context limits
        if len(full_context) > self.max_context_length:
            # Truncate and add notice
            truncated = full_context[:self.max_context_length - 100]
            full_context = truncated + "\n\n[Context truncated due to length limits]"
        
        return full_context


# Backward compatibility functions
def create_business_prompt_templates():
    """Create basic business prompt templates."""
    return {
        "system_prompt": create_prompt_engineering_system(),
        "context_integration": create_prompt_integrator()
    }


def get_prompt_for_query(query: str, context_docs: List[str]) -> List[Dict[str, str]]:
    """Generate a complete prompt for a business query."""
    
    system_prompt = create_prompt_engineering_system()
    integrator = create_prompt_integrator()
    
    # Integrate context
    context_text = integrator(context_docs)
    
    # Build user message
    user_message = f"""Business Query: {query}

Relevant Context:
{context_text}

Please provide a comprehensive response based on the context above. If the context doesn't contain sufficient information to answer the query completely, clearly state what information is missing."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]


# Export the main functions needed by chat.py
__all__ = [
    "create_prompt_engineering_system",
    "create_prompt_integrator", 
    "get_prompt_for_query",
    "PromptIntegrator"
]