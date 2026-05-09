"""OpenAI LLM client."""
import os
from typing import Dict, Iterator, List, Optional

from openai import OpenAI

from backend.agents.client.BaseLLMClient import BaseLLMClient


class OpenAIClient(BaseLLMClient):
    """Client for the OpenAI API."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_headers: Optional[Dict[str, str]] = None,
    ):
        model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        super().__init__(model)

        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API key is required for OpenAI client")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=default_headers,
        )
        print(f"✓ {type(self).__name__} initialized (model={self.model}, base_url={base_url or 'default'})")

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> Iterator[str]:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in resp:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """Use OpenAI's native JSON mode."""
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""