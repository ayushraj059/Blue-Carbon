import os
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

INDEX_NAME = "carbon-coefficients"
MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_index = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _get_index():
    global _index
    if _index is None:
        from pinecone import Pinecone

        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY not set")
        pc = Pinecone(api_key=api_key)
        _index = pc.Index(INDEX_NAME)
    return _index


def get_ecosystem_multiplier(location: str, vegetation_density: float) -> dict:
    try:
        model = _get_model()
        index = _get_index()

        query = (
            f"Coastal ecosystem in {location} with vegetation density {vegetation_density:.2f}. "
            f"What is the ecosystem type and carbon multiplier?"
        )
        embedding = model.encode(query).tolist()

        results = index.query(vector=embedding, top_k=3, include_metadata=True)

        if not results.matches:
            return {
                "ecosystem_type": "coastal_wetland",
                "ecosystem_multiplier": 1.1,
                "confidence": 0.0,
                "source": "default",
            }

        best_match = results.matches[0]
        metadata = best_match.metadata

        return {
            "ecosystem_type": metadata.get("ecosystem_type", "coastal_wetland"),
            "ecosystem_multiplier": float(metadata.get("ecosystem_multiplier", 1.1)),
            "confidence": float(best_match.score),
            "source": "pinecone_rag",
            "carbon_range": {
                "min": metadata.get("carbon_min", 40),
                "max": metadata.get("carbon_max", 90),
            },
            "matched_text": metadata.get("text", "")[:200],
        }

    except Exception as e:
        logger.error(f"RAG retrieval failed for {location}: {e}")
        return {
            "ecosystem_type": "coastal_wetland",
            "ecosystem_multiplier": 1.1,
            "confidence": 0.0,
            "source": "fallback_on_error",
            "error": str(e),
        }
