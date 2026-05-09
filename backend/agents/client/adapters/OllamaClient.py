"""
Ollama LLM client — local inference via /api/chat.
"""
import json
import os
from typing import Dict, Iterator, List, Optional

import requests

from backend.agents.client.BaseLLMClient import BaseLLMClient


class OllamaClient(BaseLLMClient):
    """Local Ollama LLM client."""

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        super().__init__(model)
        self.base_url = (
            base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")

        # Connection test
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                available = [m["name"] for m in resp.json().get("models", [])]
                if self.model not in available:
                    print(f"⚠ Model '{self.model}' not found. Available: {available}")
                print(f"✓ OllamaClient initialized (model={self.model})")
            else:
                print(f"⚠ Could not connect to Ollama at {self.base_url}")
        except Exception as e:
            print(f"⚠ Ollama connection test failed: {e}")

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> Iterator[str]:
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
            stream=True,
            timeout=180,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode("utf-8"))
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                except json.JSONDecodeError:
                    continue

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """Ollama supports native JSON mode via format='json'."""
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")