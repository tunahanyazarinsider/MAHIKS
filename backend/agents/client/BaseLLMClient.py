"""
Abstract base for all LLM clients.
"""
from abc import ABC, abstractmethod
from typing import Dict, Iterator, List, Optional


class BaseLLMClient(ABC):
    """
    Minimal LLM client interface.

    Every provider implements `chat()`.
    Streaming is optional — the default raises NotImplementedError.
    """

    def __init__(self, model: str):
        self.model : str = model

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """
        Send chat messages and return the full response text.

        Args:
            messages: List of {"role": "system"|"user"|"assistant", "content": "..."}
            temperature: Sampling temperature
            max_tokens: Max tokens to generate

        Returns:
            Generated text string
        """

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> Iterator[str]:
        """
        Stream tokens. Override in providers that support it.
        Default: falls back to non-streaming chat().
        """
        yield self.chat(messages, temperature, max_tokens)

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """
        Chat with JSON-mode hint where supported.
        Default: same as chat(). Providers override to use native JSON mode.
        """
        return self.chat(messages, temperature, max_tokens)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model!r})"