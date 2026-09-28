# backend/app/features/rag_chatbot/llm/prompt_engineering.py
"""
This file writes the actual instructions sent to the AI — company
context, tone rules, and how long/detailed the answer should be based
on what kind of question was asked (a quick lookup gets a short
answer, an analytical question gets a longer, structured one). It also
folds in the retrieved document snippets so the AI has real material
to answer from, instead of just guessing.
"""
# ─────────────────────────────────────────────────────────────────────────
# MODULE: [OPS:LLM-004]
#
# What it does: builds the actual text instructions sent to the AI
# model. get_prompt_for_query() is the one function chat.py calls
# directly — everything else here is a helper it uses to build that
# final prompt (the fixed company-context system prompt, folding in
# retrieved document snippets, and picking a length/structure directive
# based on what kind of question was asked).
# ─────────────────────────────────────────────────────────────────────────

from typing import List, Dict, Any
import re


# ---------------------------
# System prompt (technical)
# ---------------------------
# [OPS:LLM-004a] create_prompt_engineering_system()
#
# What it does: returns one fixed block of instruction text, sent as the
# "system" message on every single request. It tells the model what
# company it's answering for, what tone to use, to write currency with
# proper formatting, and — importantly — to never write bracket-style
# citation markers like "[D1]", because the frontend already shows the
# real source documents as separate cards below the answer.
#
# Called by: get_prompt_for_query(), once per request.
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
# [OPS:LLM-004b] PromptIntegrator
#
# What it does: takes the retrieved document snippets and joins them
# into one text block to paste into the prompt. It keeps at most the top
# 5 snippets, cuts each one down to 900 characters, and then, as a final
# safety net, cuts the WHOLE combined block down to 4000 characters if
# it's still too long.
#
# Note: chat.py already trims the snippet list down by an estimated
# token count before this ever runs — so there are actually two separate
# size limits applied back to back, one by token estimate and one here
# by raw character count, and they aren't tied to the same number.
#
# Called by: get_prompt_for_query(), once per request.
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

# [OPS:LLM-004c] _classify_query()
#
# What it does: guesses what kind of question this is using plain
# keyword-matching regex — no AI model involved, no extra API call. It
# checks the question text against two word lists (analytical words like
# "compare"/"trend"/"total", or lookup words like "find"/"show"/"where")
# and returns one of three instructions telling the model how long and
# how structured its answer should be.
#
# Called by: get_prompt_for_query(), once per request.
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
# [OPS:LLM-004d] get_prompt_for_query()
#
# What it does: the one function chat.py actually calls. It combines the
# fixed system prompt, the folded-together document context, and the
# per-question length directive into the final two-message list — one
# "system" message, one "user" message — in the exact shape the LLM
# backends expect.
#
# Called by: chat_complete() and chat_stream() in chat.py.
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
