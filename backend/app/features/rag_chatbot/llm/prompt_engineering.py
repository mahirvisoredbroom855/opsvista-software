# backend/app/features/rag_chatbot/llm/prompt_engineering.py
"""
Simplified prompt engineering for immediate functionality.
This provides the basic functions needed by chat.py without complex dependencies.
Enhanced to adapt response length/structure based on the query.
"""

from typing import List, Dict, Any
import re


# ---------------------------
# System prompt (technical)
# ---------------------------
def create_prompt_engineering_system() -> str:
    """Create a technical, business-focused system prompt for OpsVista."""
    return """You are **OpsVista Assistant**, a pragmatic, technical business assistant for
**Precision Textile Industry Limited** (textile printing & embroidery) in Gazipur, Bangladesh.

COMPANY CONTEXT
- Departments: Commercial, Production, Accounting, HR, Maintenance
- Equipment: MHM embroidery machines
- Typical data: LCs, invoices, orders, production logs, maintenance records
- Customers: RB Knit, Blue Planet Knitwear Ltd, Fiat Fashion Ltd
- Hours: 08:00–18:00 (Asia/Dhaka)

OPERATING PRINCIPLES
- Be precise, practical, and technically minded. Use correct textile/manufacturing terms.
- Prefer clear structure with short paragraphs and bullet points. Use Markdown headings where useful.
- Use **BDT (৳)** and **USD ($)**; format amounts with thousands separators.
- Use ISO-like dates (e.g., 2024-03-15). Note time zone where relevant (Asia/Dhaka).

SOURCES & RELIABILITY
- Base answers on provided context. **Do not invent** figures.
- If making calculations or inferences, state assumptions briefly.
- When citing, refer to documents by bracketed tags like **[D1]**, **[D2]** matching the context pack.

LENGTH POLICY (Adaptive)
- **Lookup / factual / status** → be concise (3–6 sentences or a short list).
- **Analytical / comparative / calculation** → provide a fuller, structured answer (typically 120–250 words).
- If the user explicitly asks for “short” or “long,” follow their preference.

OUTPUT FORMAT (when relevant)
- **Summary** (1–3 lines)
- **Details / Findings** (bullets or small table if helpful)
- **Calculations / Assumptions** (only key steps, no internal chain-of-thought)
- **Sources** as [D#]
- **Next steps** (optional)
"""


# ---------------------------
# Context integrator
# ---------------------------
def create_prompt_integrator() -> 'PromptIntegrator':
    """Create a basic prompt integrator."""
    return PromptIntegrator()


class PromptIntegrator:
    """Basic prompt integrator for combining document context with queries."""

    def __init__(self):
        # Keep the same default to avoid breaking callers
        self.max_context_length = 4000  # characters

    def __call__(self, document_texts: List[str]) -> str:
        """Integrate document texts into a coherent context block."""
        if not document_texts:
            return "No relevant documents found."

        # Build a compact, labeled pack: [D1], [D2], …
        combined: List[str] = []
        combined.append("Context Pack (cite as [D1], [D2], … in your answer):")

        for i, text in enumerate(document_texts[:5], 1):  # limit to top 5 docs
            # Light trimming: keep the beginning (usually most informative)
            snippet = text.strip()
            if len(snippet) > 800:
                snippet = snippet[:800].rstrip() + "…"
            combined.append(f"\n[D{i}] — Document {i}\n{snippet}")

        full_context = "\n".join(combined)

        # Hard cap to avoid overlong prompts
        if len(full_context) > self.max_context_length:
            full_context = full_context[: self.max_context_length - 120].rstrip() + \
                "\n\n[Context truncated due to length limits]"

        return full_context


# ---------------------------
# Tiny intent/verbosity heuristic
# ---------------------------
_ANALYTICAL_RE = re.compile(
    r"(analy(s|z)e|trend|compare|vs\.?|difference|delta|variance|margin|profit|"
    r"efficien|utili[sz]ation|ratio|breakdown|forecast|project|estimate|"
    r"calculate|calc|total|sum|average|agg(regate)?|by department|per (month|day|machine))",
    re.IGNORECASE,
)
_LOOKUP_RE = re.compile(
    r"^(find|show|get|list|where|when|status|lookup|retrieve)\b", re.IGNORECASE
)

def _classify_query(query: str) -> Dict[str, Any]:
    """Return a small directive based on the query text."""
    if _ANALYTICAL_RE.search(query or ""):
        return {
            "intent": "analytical",
            "length_hint": "Provide a structured analysis (~120–250 words).",
            "sections": ["Summary", "Details / Findings", "Calculations / Assumptions", "Sources"],
        }
    if _LOOKUP_RE.search(query or ""):
        return {
            "intent": "lookup",
            "length_hint": "Be concise (3–6 sentences or a short list).",
            "sections": ["Answer", "Sources"],
        }
    # default / mixed
    return {
        "intent": "general",
        "length_hint": "Balanced detail (5–8 sentences).",
        "sections": ["Summary", "Details", "Sources"],
    }


# ---------------------------
# Backward-compatibility shims
# ---------------------------
def create_business_prompt_templates():
    """Create basic business prompt templates."""
    return {
        "system_prompt": create_prompt_engineering_system(),
        "context_integration": create_prompt_integrator(),
    }


def get_prompt_for_query(query: str, context_docs: List[str]) -> List[Dict[str, str]]:
    """Generate a complete prompt for a business query with adaptive guidance."""

    system_prompt = create_prompt_engineering_system()
    integrator = create_prompt_integrator()
    context_text = integrator(context_docs)

    # Adaptive directive based on the query
    q = (query or "").strip()
    directive = _classify_query(q)
    sections = " • ".join(directive["sections"])

    user_message = f"""Business Query:
{q if q else "(empty query)"}

Relevant Context:
{context_text}

Answering Directives:
- {directive['length_hint']}
- Use Markdown where helpful. Prefer bullet points over long paragraphs.
- Include sections: {sections}.
- Cite documents explicitly using [D1], [D2], etc., matching the context pack.
- If data is missing or ambiguous, say so and suggest the next step.
- Do not invent figures; if you perform calculations, show only key steps and final numbers.

Now provide the best possible answer in English, unless the user asks otherwise.
"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]


# Keep exports identical so existing imports don’t break
__all__ = [
    "create_prompt_engineering_system",
    "create_prompt_integrator",
    "get_prompt_for_query",
    "PromptIntegrator",
]
