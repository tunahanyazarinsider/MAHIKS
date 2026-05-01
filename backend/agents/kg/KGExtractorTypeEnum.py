from enum import Enum

class KGExtractorTypeEnum(Enum):
    OLLAMA = "ollama"
    LOCAL = "local"
    GEMINI = "gemini"
    VERTEX = "vertex"
    OPENROUTER = "openrouter"
    BASE = "base"