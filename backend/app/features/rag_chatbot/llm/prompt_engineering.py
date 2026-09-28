# backend/app/features/rag_chatbot/llm/prompt_engineering.py
"""
Simplified prompt engineering for immediate functionality.
This provides the basic functions needed by chat.py without complex dependencies.
Enhanced to adapt response length/structure based on the query.
"""
# ═══════════════════════════════════════════════════════════════════════
# MODULE: [OPS:LLM-004] — prompt assembly (system prompt + context
#          integration + adaptive length directives)
#
# get_prompt_for_query() [OPS:LLM-004d] is the one function chat.py
# actually calls; everything else in this file is a helper it composes.
# This is where "never write abstract [D1] citation markers" and "use
# BDT/USD with thousands separators" and "no LaTeX" live — instructions
# specific to how THIS app's frontend renders answers and what THIS
# company's data looks like, not generic prompt-engineering advice.
# ═══════════════════════════════════════════════════════════════════════

from typing import List, Dict, Any
import re


# ---------------------------
# System prompt (technical)
# ---------------------------
# [OPS:LLM-004a] create_prompt_engineering_system() — the static system
# prompt: company context (departments, equipment, customers), tone rules,
# the "never write [D1]-style markers — the UI already shows real source
# cards" instruction (this is WHY [OPS:CHAT-012] _render_sources() and the
# frontend's citation cards exist as separate UI, not inline in the
# answer text), and the adaptive length policy that
# [OPS:LLM-004c] _classify_query() below implements per-request.
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
- Refer to documents naturally by their real title or filename when it helps
  the reader (e.g. "According to the Profit and Loss Statement, ..."). Never
  use abstract bracket markers like [D1], [1], [2, 3] — the interface already
  shows the full source documents as separate citation cards below your
  answer, so do NOT write your own "Sources" section or reference list.

LENGTH & DEPTH POLICY (Adaptive) — answers must always be descriptive and
easy to understand, never a single terse fragment
- **Lookup / factual / status** → a complete, clear answer (4–8 sentences or
  a short structured list) — enough for the reader to fully understand the
  answer without needing to open the source document.
- **Analytical / comparative / calculation** → a thorough, structured answer
  (roughly 200–350 words) that explains the "why", not just the number.
- **General / mixed** → descriptive and complete (8–12 sentences), covering
  relevant context, not just the bare fact.
- If the user explicitly asks for "short" or "long," follow their preference
  instead of the defaults above.

OUTPUT FORMAT (when relevant)
- **Summary** (1–3 lines)
- **Details / Findings** (bullets or a small Markdown table if helpful)
- **Calculations / Assumptions** (only key steps, no internal chain-of-thought)
- **Next steps** (optional)

FORMATTING CONSTRAINTS
- Plain Markdown only (headings, **bold**, bullets, tables). The renderer
  does NOT support LaTeX/math notation — never use $$...$$, \\frac{}{}, or
  similar. Write calculations as plain arithmetic instead, e.g.
  "BDT 55,050,000 − BDT 53,100,000 = BDT 1,950,000 (+3.7%)".
"""


# ---------------------------
# Context integrator
# ---------------------------
def create_prompt_integrator() -> 'PromptIntegrator':
    """Create a basic prompt integrator."""
    return PromptIntegrator()


# ─────────────────────────────────────────────────────────────────────────
# [OPS:LLM-004b] PromptIntegrator — folds retrieved chunks into one
#                 context block, with its OWN independent size cap
#
# WHAT: takes at most the top 5 of the already-token-budgeted context
#       texts [OPS:CHAT-014] _enforce_token_budget() already trimmed,
#       truncates each individual chunk to 900 chars, then hard-caps the
#       WHOLE combined block at max_context_length=4000 chars as a final
#       safety net.
# NUANCE — TWO INDEPENDENT BUDGETS, NOT ONE: chat.py's
#       _enforce_token_budget() [OPS:CHAT-014] already trims the chunk
#       LIST by an estimated token count (default 6000 tokens ≈ 24000
#       chars) before this class ever sees it; this class then applies
#       its own SEPARATE, smaller, character-based cap (4000 chars) on
#       top. The two aren't coordinated by a shared constant — this is
#       a real overlap in the codebase worth being explicit about if
#       asked "how many context-size limits are there," since the
#       honest answer is "two, applied in sequence, for different units."
# CALLED BY: [OPS:LLM-004d] get_prompt_for_query(), once per request.
# ─────────────────────────────────────────────────────────────────────────
class PromptIntegrator:
    """Basic prompt integrator for combining document context with queries."""

    def __init__(self):
        # Keep the same default to avoid breaking callers
        self.max_context_length = 4000  # characters

    def __call__(self, document_texts: List[str]) -> str:
        """
        Integrate document texts into a coherent context block. Each entry in
        document_texts is expected to already carry its own identifying
        header (title/department/source) so the model can refer to it by
        name rather than needing an abstract [D#] label.
        """
        if not document_texts:
            return "No relevant documents found."

        combined: List[str] = ["Context (retrieved documents):"]

        for text in document_texts[:5]:  # limit to top 5 docs
            snippet = text.strip()
            if len(snippet) > 900:
                snippet = snippet[:900].rstrip() + "…"
            combined.append(f"\n---\n{snippet}")

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

# [OPS:LLM-004c] _classify_query() — regex-based intent heuristic (NOT an
# LLM call, NOT a classifier model — plain regex against the raw query
# text), picking one of three length/structure directives (analytical /
# lookup / general) baked into the user-message template by
# [OPS:LLM-004d] get_prompt_for_query(). Deliberately cheap: runs
# synchronously, in-process, on every single request with zero added
# latency or API cost.
def _classify_query(query: str) -> Dict[str, Any]:
    """Return a small directive based on the query text."""
    if _ANALYTICAL_RE.search(query or ""):
        return {
            "intent": "analytical",
            "length_hint": "Provide a thorough, structured analysis (~200–350 words) that explains the 'why', not just the number.",
            "sections": ["Summary", "Details / Findings", "Calculations / Assumptions"],
        }
    if _LOOKUP_RE.search(query or ""):
        return {
            "intent": "lookup",
            "length_hint": "Give a complete, easy-to-understand answer (4–8 sentences or a short structured list) — never a single bare fragment.",
            "sections": ["Answer"],
        }
    # default / mixed
    return {
        "intent": "general",
        "length_hint": "Descriptive and complete (8–12 sentences), covering relevant context, not just the bare fact.",
        "sections": ["Summary", "Details"],
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


# ─────────────────────────────────────────────────────────────────────────
# [OPS:LLM-004d] get_prompt_for_query() — THE function chat.py actually
#                 calls; assembles system + user messages
#
# CALLS: create_prompt_engineering_system() [OPS:LLM-004a],
#       PromptIntegrator [OPS:LLM-004b] (context folding),
#       _classify_query() [OPS:LLM-004c] (adaptive directive).
# RETURNS: [{"role": "system", ...}, {"role": "user", ...}] — the exact
#       messages-list shape [OPS:LLM-002]/[OPS:LLM-002b]'s backends
#       expect (OpenAI natively; Gemini via _messages_to_prompt()
#       flattening it to one string).
# CALLED BY: [OPS:CHAT-015] chat_complete(), [OPS:CHAT-020] chat_stream().
# ─────────────────────────────────────────────────────────────────────────
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
- Use Markdown where helpful (headings, bold, bullet points, small tables) —
  never return a single flat line of text.
- Cover: {sections}.
- Refer to source documents by their real name when useful; never use
  abstract markers like [D1] or [1] — do not write your own "Sources" list.
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
