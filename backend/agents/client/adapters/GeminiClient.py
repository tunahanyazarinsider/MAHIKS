"""
Google Gemini LLM client — Developer API (API key) and Vertex AI (ADC).
"""
import os
from typing import Dict, Iterator, List, Optional

from google import genai

from backend.agents.client.BaseLLMClient import BaseLLMClient


class GeminiClient(BaseLLMClient):
    """Client for Google Gemini (Developer API key path)."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        super().__init__(model)

        api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY is required")

        self.client = genai.Client(api_key=api_key)
        print(f"✓ GeminiClient initialized (model={self.model})")

    def _convert_messages(self, messages: List[Dict[str, str]]):
        """Convert OpenAI-style messages to Gemini format."""
        system_instruction = None
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
            elif msg["role"] == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
        return system_instruction, contents

    def chat(self, messages: List[Dict[str, str]],temperature: float = 0.3,max_tokens: int = 2000,) -> str:
        system_instruction, contents = self._convert_messages(messages)
        config = {"temperature": temperature, "max_output_tokens": max_tokens}
        if system_instruction:
            config["system_instruction"] = system_instruction

        resp = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )
        return resp.text or ""

    def chat_stream(self, messages: List[Dict[str, str]],temperature: float = 0.3, max_tokens: int = 2000) -> Iterator[str]:
        system_instruction, contents = self._convert_messages(messages)
        config = {"temperature": temperature, "max_output_tokens": max_tokens}
        if system_instruction:
            config["system_instruction"] = system_instruction

        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                yield chunk.text

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """Use Gemini's native JSON response mode."""
        from backend.agents.kg.KGExtractor import KG_JSON_SCHEMA

        system_instruction, contents = self._convert_messages(messages)
        config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "response_mime_type": "application/json",
            "response_schema": KG_JSON_SCHEMA,
        }
        if system_instruction:
            config["system_instruction"] = system_instruction

        resp = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )
        return resp.text or ""