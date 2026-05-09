"""OpenRouter LLM client using the raw HTTP API."""
import json
import os
from typing import Dict, Iterator, List, Optional

import requests

from backend.agents.client.BaseLLMClient import BaseLLMClient
from backend.config import Config


class OpenRouterClient(BaseLLMClient):
    """Client for OpenRouter that calls the REST API directly via `requests`."""

    BASE_URL = "https://openrouter.ai/api/v1"
    CHAT_COMPLETIONS_PATH = "/chat/completions"
    DEFAULT_TIMEOUT = 60

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        model = model or Config.KG_OPENROUTER_MODEL or "qwen/qwen-2.5-72b-instruct"
        super().__init__(model)

        api_key = api_key or Config.OPENROUTER_API_KEY
        print(api_key)
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required")

        self.api_key = api_key
        self.timeout = timeout
        print("Using model:", self.model)
        self.url = f"{self.BASE_URL}{self.CHAT_COMPLETIONS_PATH}"

        self.headers: Dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        referer = Config.OPENROUTER_REFERER
        title = Config.OPENROUTER_TITLE or "MAHIKS-TR"
        if referer:
            self.headers["HTTP-Referer"] = referer
        if title:
            self.headers["X-Title"] = title
        if extra_headers:
            self.headers.update(extra_headers)

        print(f"✓ OpenRouterClient initialized (model={self.model})")

    def _post(self, payload: Dict, stream: bool = False) -> requests.Response:
        resp = requests.post(
            url=self.url,
            headers=self.headers,
            data=json.dumps(payload),
            stream=stream,
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"OpenRouter HTTP {resp.status_code}: {resp.text}"
            )
        return resp

    def _build_payload(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
        stream: bool = False,
    ) -> Dict:
        payload: Dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if stream:
            payload["stream"] = True
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        payload = self._build_payload(messages, temperature, max_tokens)
        resp = self._post(payload)
        data = resp.json()
        return data["choices"][0]["message"].get("content") or ""

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        payload = self._build_payload(
            messages, temperature, max_tokens, json_mode=True
        )
        resp = self._post(payload)
        data = resp.json()
        return data["choices"][0]["message"].get("content") or ""

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> Iterator[str]:
        payload = self._build_payload(
            messages, temperature, max_tokens, stream=True
        )
        resp = self._post(payload, stream=True)
        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data:"):
                continue
            chunk = raw_line[len("data:"):].strip()
            if chunk == "[DONE]":
                break
            try:
                event = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            choices = event.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            if content:
                yield content
