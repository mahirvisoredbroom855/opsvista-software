# backend/app/features/rag_chatbot/llm/llm_client.py
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


class LLMClient:
    """
    Wrapper class that chat.py expects to import.
    Provides a simpler interface that matches the expected API.
    """
    
    def __init__(self, model: Optional[str] = None):
        self.openai_llm = OpenAILLM()
        # Override model if provided
        if model:
            self.openai_llm.model = model
        self.last_usage = None
    
    async def complete(self, prompt: str) -> str:
        """
        Simple completion method that takes a string prompt
        and returns just the content string.
        """
        messages = [{"role": "user", "content": prompt}]
        result = self.openai_llm.complete(messages)
        self.last_usage = result.get("usage")
        return result["content"]
    
    def complete_sync(self, prompt: str) -> str:
        """
        Synchronous version for backward compatibility
        """
        messages = [{"role": "user", "content": prompt}]
        result = self.openai_llm.complete(messages)
        self.last_usage = result.get("usage")
        return result["content"]
    
    async def complete_with_messages(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Full completion method that returns complete response
        """
        result = self.openai_llm.complete(messages)
        self.last_usage = result.get("usage")
        return result
    
    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        Streaming completion
        """
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self.openai_llm.stream(messages):
            yield chunk


# For backward compatibility, export both classes
__all__ = ["OpenAILLM", "LLMClient"]