# backend/app/features/rag_chatbot/vector/__init__.py
"""
Exports a stable ComprehensiveSearchSystem symbol so both the editor (Pylance)
and runtime can resolve it, regardless of which implementation is available.
"""

# Try the "full" implementation first
try:
    from .integrated_search_system import ComprehensiveSearchSystem  # type: ignore[attr-defined]
    __all__ = ["ComprehensiveSearchSystem"]
except Exception:
    # Fall back to the simpler implementation if the full one isn't present/ready
    try:
        from .simple_integrated_search import SimpleIntegratedSearch as ComprehensiveSearchSystem
        __all__ = ["ComprehensiveSearchSystem"]
    except Exception:
        # Final safety shim so Pylance stops complaining; will raise at use-time if called.
        class ComprehensiveSearchSystem:  # type: ignore[no-redef]
            def __init__(self, *a, **kw):
                raise ImportError(
                    "No search implementation available. "
                    "Ensure integrated_search_system.py or simple_integrated_search.py is present "
                    "and imports succeed."
                )
        __all__ = ["ComprehensiveSearchSystem"]
