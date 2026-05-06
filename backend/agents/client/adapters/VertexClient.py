from backend.agents.client.BaseLLMClient import BaseLLMClient
from backend.agents.client.adapters.GeminiClient import GeminiClient

import os
from typing import Optional
from google import genai


class VertexClient(GeminiClient):
    """Client for Google Vertex AI (uses ADC instead of API key)."""

    def __init__(
        self,
        model: Optional[str] = None,
        project: Optional[str] = None,
        location: Optional[str] = None,
    ):
        # Skip GeminiClient.__init__ — we set up the Vertex client ourselves
        model = model or os.getenv("VERTEX_MODEL", "gemini-2.5-flash")
        BaseLLMClient.__init__(self, model)

        project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project:
            raise ValueError("GOOGLE_CLOUD_PROJECT is required for Vertex AI")
        location = location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

        self.client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )
        print(f"✓ VertexClient initialized (project={project}, model={self.model})")