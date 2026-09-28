# backend/app/features/rag_chatbot/llm/llm_client.py
# ═══════════════════════════════════════════════════════════════════════
# MODULE: [OPS:LLM] — the generation layer (as opposed to [OPS:IDX]/
#          [OPS:PVEC], which are retrieval/embedding)
#
# Two concrete backends (OpenAILLM, GeminiLLM) behind one interface
# (LLMClient), each implementing complete() (blocking) and stream()
# (async generator) — so chat.py's [OPS:CHAT-015]/[OPS:CHAT-020] never
# need to know which provider is actually active.
# ═══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import os
from typing import List, Dict, Any, AsyncGenerator, Optional

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Try to import settings, fallback if not available
try:
    from app.core.config import settings
except ImportError:
    # Mock settings for testing
    class MockSettings:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
        OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
        OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "4000"))
    
    settings = MockSettings()


# ─────────────────────────────────────────────────────────────────────────
# [OPS:LLM-002] OpenAILLM — the OpenAI backend (higher provider priority
#                 than Gemini, see [OPS:LLM-001]'s known bug note)
#
# API/CALL: OpenAI chat.completions.create() — both complete() (stream=
#       False, one response object) and stream() (stream=True, an
#       iterator of delta chunks) use the exact same _chat_args() request
#       shape, differing only in that one flag — keeps the two code
#       paths from silently drifting in model/temperature/max_tokens.
# NUANCE (stream()): guards chunk.choices/.delta/.delta.content all being
#       truthy before yielding — OpenAI's streaming protocol sends
#       chunks with an empty delta (e.g. the first chunk, which only
#       carries role) that would otherwise yield an empty/None string.
# BREAKS IF: OPENAI_API_KEY unset — raises at construction (__init__),
#       which is why [OPS:LLM-003] LLMClient only constructs this class
#       when it has already confirmed the key is set.
# ─────────────────────────────────────────────────────────────────────────
class OpenAILLM:
    def __init__(self):
        if not OPENAI_AVAILABLE:
            raise RuntimeError("OpenAI library not installed. Run: pip install openai")
        
        api_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        
        self.client = OpenAI(api_key=api_key)
        self.model = getattr(settings, "OPENAI_MODEL", "gpt-4")
        self.temperature = getattr(settings, "OPENAI_TEMPERATURE", 0.7)
        self.max_tokens = getattr(settings, "OPENAI_MAX_TOKENS", 4000)

    def _chat_args(self, messages: List[Dict[str, str]], stream: bool = False) -> Dict[str, Any]:
        return {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }

    def complete(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        try:
            resp = self.client.chat.completions.create(**self._chat_args(messages, stream=False))
            choice = resp.choices[0]
            content = choice.message.content or ""
            
            usage_dict = None
            if hasattr(resp, "usage") and resp.usage:
                usage_dict = {
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens,
                    "total_tokens": resp.usage.total_tokens
                }
            
            return {
                "content": content,
                "model": resp.model,
                "usage": usage_dict,
            }
        except Exception as e:
            raise RuntimeError(f"OpenAI error: {e}") from e

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """
        Fixed streaming implementation that yields clean text chunks.
        """
        try:
            # Create streaming response
            stream = self.client.chat.completions.create(**self._chat_args(messages, stream=True))
            
            # Process chunks properly
            for chunk in stream:
                # Check if chunk has choices and delta content
                if (chunk.choices and 
                    len(chunk.choices) > 0 and 
                    chunk.choices[0].delta and 
                    chunk.choices[0].delta.content):
                    
                    content = chunk.choices[0].delta.content
                    
                    # Only yield non-empty content
                    if content and content.strip():
                        yield content
                        
        except Exception as e:
            # Surface an error token so frontend can display gracefully
            yield f"\n[LLM Error: {e}]\n"


# ─────────────────────────────────────────────────────────────────────────
# [OPS:LLM-002b] GeminiLLM — the Gemini backend (the one actually active
#                 in this deployment — see the provider-priority bug at
#                 [OPS:LLM-001])
#
# API/CALL: Gemini generate_content() (complete()) / generate_content_
#       stream() (stream()) — genai.Client.models.
# NUANCE (_messages_to_prompt): Gemini's simple generate_content API
#       takes ONE prompt string, not a chat-message list like OpenAI's
#       API — so this method folds the {system, user} messages list
#       [OPS:LLM-004] get_prompt_for_query() builds into a single joined
#       string, tagging non-user roles with a "[role]" prefix so the
#       distinction survives the flattening. This is a deliberate
#       simplification (not Gemini's full multi-turn chat API) since
#       this app is single-turn Q&A per request, not a persisted
#       conversation.
# BREAKS IF: GEMINI_API_KEY unset — raises at construction.
# ─────────────────────────────────────────────────────────────────────────
class GeminiLLM:
    """Google Gemini backend (free tier via Google AI Studio)."""

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
        self.max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "4000"))

    @staticmethod
    def _messages_to_prompt(messages: List[Dict[str, str]]) -> str:
        # Gemini's simple text API takes one prompt string; fold chat messages in.
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            parts.append(content if role == "user" else f"[{role}] {content}")
        return "\n\n".join(parts)

    def complete(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        from google.genai import types

        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=self._messages_to_prompt(messages),
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                ),
            )
            content = resp.text or ""

            usage_dict = None
            usage = getattr(resp, "usage_metadata", None)
            if usage:
                usage_dict = {
                    "prompt_tokens": getattr(usage, "prompt_token_count", 0) or 0,
                    "completion_tokens": getattr(usage, "candidates_token_count", 0) or 0,
                    "total_tokens": getattr(usage, "total_token_count", 0) or 0,
                }

            return {"content": content, "model": self.model, "usage": usage_dict}
        except Exception as e:
            raise RuntimeError(f"Gemini error: {e}") from e

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        from google.genai import types

        try:
            stream = self.client.models.generate_content_stream(
                model=self.model,
                contents=self._messages_to_prompt(messages),
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                ),
            )
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            yield f"\n[LLM Error: {e}]\n"


# ─────────────────────────────────────────────────────────────────────────
# [OPS:LLM-001] / [OPS:LLM-003] LLMClient — the single entrypoint chat.py
#                 imports; provider selection lives here
#
# WHAT: constructs whichever backend ([OPS:LLM-002] OpenAILLM or
#       [OPS:LLM-002b] GeminiLLM) matches the first API key found, then
#       exposes a uniform surface: complete_with_messages() (blocking,
#       used by [OPS:CHAT-015] chat_complete()), stream_with_messages()
#       (async generator, used by [OPS:CHAT-020] chat_stream()).
#       last_usage is stashed as instance state after every call so the
#       caller can read token counts without a second return value —
#       this is what chat.py reads into its `usage` dict.
# KNOWN BUG (documented, not fixed — same class of bug as [OPS:IDX-002]
#       embed_texts()'s provider-priority order): if BOTH OPENAI_API_KEY
#       and GEMINI_API_KEY are set in the environment, OpenAI silently
#       wins here — there's no warning, no way to force Gemini short of
#       unsetting OPENAI_API_KEY. This matters because this project's
#       real deployment intentionally runs on Gemini (its free tier);
#       an accidentally-set OPENAI_API_KEY would silently switch the
#       active model without any visible error.
# CALLS: OpenAILLM.__init__ / GeminiLLM.__init__ — both can raise if
#       their own required env var isn't actually set despite the outer
#       os.getenv() check passing (e.g. an empty string) — that
#       exception propagates up to chat.py's own try/except around LLM
#       construction, which is what triggers the retrieval-only fallback
#       response documented at [OPS:CHAT-015].
# ─────────────────────────────────────────────────────────────────────────
class LLMClient:
    """
    Wrapper class that chat.py expects to import.
    Provides a simpler interface that matches the expected API.

    Provider selection: OpenAI if OPENAI_API_KEY is set, else Gemini if
    GEMINI_API_KEY is set, else raises (caller falls back to retrieval-only
    response, same as today).
    """

    def __init__(self, model: Optional[str] = None):
        if os.getenv("OPENAI_API_KEY"):
            self.backend = OpenAILLM()
        elif os.getenv("GEMINI_API_KEY"):
            self.backend = GeminiLLM()
        else:
            raise RuntimeError("No LLM provider configured: set OPENAI_API_KEY or GEMINI_API_KEY")

        # Override model if provided (only meaningful for the active backend)
        if model and os.getenv("OPENAI_API_KEY"):
            self.backend.model = model

        self.last_usage = None

    async def complete(self, prompt: str) -> str:
        """
        Simple completion method that takes a string prompt
        and returns just the content string.
        """
        messages = [{"role": "user", "content": prompt}]
        result = self.backend.complete(messages)
        self.last_usage = result.get("usage")
        return result["content"]

    def complete_sync(self, prompt: str) -> str:
        """
        Synchronous version for backward compatibility
        """
        messages = [{"role": "user", "content": prompt}]
        result = self.backend.complete(messages)
        self.last_usage = result.get("usage")
        return result["content"]

    async def complete_with_messages(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Full completion method that returns complete response
        """
        result = self.backend.complete(messages)
        self.last_usage = result.get("usage")
        return result

    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        Streaming completion
        """
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self.backend.stream(messages):
            yield chunk

    async def stream_with_messages(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """
        Streaming completion from a full chat-message list (system + user),
        matching complete_with_messages's input shape.
        """
        async for chunk in self.backend.stream(messages):
            yield chunk


# For backward compatibility, export both classes
__all__ = ["OpenAILLM", "GeminiLLM", "LLMClient"]