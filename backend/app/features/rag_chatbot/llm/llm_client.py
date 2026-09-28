# backend/app/features/rag_chatbot/llm/llm_client.py
"""
This file is the only place in the backend that actually talks to an
AI model to write an answer. It supports two different providers —
Google Gemini and OpenAI — behind one shared interface, so the rest of
the app never has to know or care which one is actually configured.
Whichever API key is set in the environment decides which provider
runs.
"""
# ─────────────────────────────────────────────────────────────────────────
# MODULE: [OPS:LLM]
#
# What it does: two provider classes (OpenAILLM, GeminiLLM) that both
# offer the same two methods — complete() (wait for the whole answer)
# and stream() (yield the answer piece by piece). LLMClient picks one of
# the two based on which API key is set, so chat.py never needs to know
# which provider is actually running.
# ─────────────────────────────────────────────────────────────────────────
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
# [OPS:LLM-002] OpenAILLM
#
# What it does: talks to OpenAI's chat API. complete() waits and returns
# the full answer at once; stream() sends back one small piece of text
# at a time as OpenAI generates it, skipping the empty pieces OpenAI's
# streaming protocol sometimes sends (like the very first chunk, which
# carries no actual text). Raises an error immediately at construction
# if OPENAI_API_KEY isn't set.
#
# Called by: LLMClient, when OPENAI_API_KEY is set.
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
# [OPS:LLM-002b] GeminiLLM
#
# What it does: same job as OpenAILLM, but talks to Google Gemini
# instead — this is the provider actually meant to run in production.
# Gemini's API only accepts one plain text string, not a list of
# {system, user} messages like OpenAI, so _messages_to_prompt() joins
# them into one string first, labeling non-user messages with a
# "[role]" prefix so the distinction isn't lost. Raises an error
# immediately at construction if GEMINI_API_KEY isn't set.
#
# Called by: LLMClient, when GEMINI_API_KEY is set (and OPENAI_API_KEY
# is not).
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
# [OPS:LLM-001] / [OPS:LLM-003] LLMClient
#
# What it does: the one class chat.py actually imports. On construction,
# it checks which API key is set and builds the matching backend
# (OpenAILLM or GeminiLLM), then offers one shared set of methods
# (complete_with_messages(), stream_with_messages()) regardless of which
# one it picked. It also remembers the token usage from the last call in
# self.last_usage, so the caller can read it afterward instead of
# needing a second return value.
#
# Known bug, not fixed: if BOTH OPENAI_API_KEY and GEMINI_API_KEY are
# set, OpenAI silently wins, with no warning — even though this app's
# real deployment is meant to run on Gemini's free tier. An accidentally
# set OPENAI_API_KEY would silently switch which model answers every
# question.
#
# Called by: chat_complete() and chat_stream() in chat.py.
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