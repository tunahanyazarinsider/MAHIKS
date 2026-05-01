"""
Google Cloud Vertex AI KG extractor.

Uses the same google-genai SDK as GeminiKGExtractor, only the client init differs:
Vertex AI authenticates via Application Default Credentials (run
`gcloud auth application-default login`) and dispatches to a GCP project
+ region instead of the developer-API key path. Designed to consume the
$300 Google Cloud free credit.
"""
import os
from typing import Optional

from google import genai

from backend.agents.kg.KGExtractorTypeEnum import KGExtractorTypeEnum
from backend.agents.kg.GeminiKGExtractor import GeminiKGExtractor
from backend.agents.kg.KGExtractor import BaseKGExtractor
from backend.database.neo4j_handler import Neo4jHandler


class VertexKGExtractor(GeminiKGExtractor):
    method_name: KGExtractorTypeEnum = KGExtractorTypeEnum.VERTEX

    def __init__(self, neo4j_handler: Neo4jHandler,
                 project: Optional[str] = None,
                 location: Optional[str] = None,
                 model: Optional[str] = None):
        # Skip GeminiKGExtractor.__init__ (which expects an API key) and go
        # straight to the base; we set up the Vertex client ourselves.
        BaseKGExtractor.__init__(
            self,
            neo4j_handler,
            model=model or os.getenv("VERTEX_MODEL", "gemini-2.5-flash"),
        )

        project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project:
            raise ValueError("GOOGLE_CLOUD_PROJECT not set; required for Vertex AI")
        location = location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

        try:
            self.client: genai.Client = genai.Client(
                vertexai=True,
                project=project,
                location=location,
            )
        except Exception as e:
            raise ValueError(f"Failed to initialize Vertex AI client: {e}")

        print(f"✓ Vertex KG Extractor initialized (project={project}, location={location}, model={self.model})")
