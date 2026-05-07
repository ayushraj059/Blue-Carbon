import os
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

INDEX_NAME = "carbon-coefficients"
EMBEDDING_DIM = 384
MODEL_NAME = "all-MiniLM-L6-v2"

CARBON_DOCUMENTS = [
    {
        "id": "mangrove-001",
        "text": "Mangrove forests are highly productive coastal ecosystems found in tropical and subtropical regions. "
                "They store large amounts of blue carbon in their biomass and sediments. "
                "Ecosystem type: mangrove. Ecosystem multiplier: 1.8. "
                "Typical carbon sequestration: 150-250 tCO2 per hectare per year. "
                "Locations: Sundarbans, Bhitarkanika, Pichavaram, mangrove delta regions. "
                "Key indicators: high vegetation density, moderate salinity 20-35 PSU, rich soil carbon.",
        "metadata": {
            "ecosystem_type": "mangrove",
            "ecosystem_multiplier": 1.8,
            "carbon_min": 150,
            "carbon_max": 250,
        },
    },
    {
        "id": "seagrass-001",
        "text": "Seagrass meadows are underwater flowering plant ecosystems that sequester carbon efficiently. "
                "They act as important blue carbon sinks in shallow coastal waters. "
                "Ecosystem type: seagrass. Ecosystem multiplier: 1.4. "
                "Typical carbon sequestration: 80-150 tCO2 per hectare per year. "
                "Locations: Chilika Lake, Gulf of Mannar, shallow coastal lagoons. "
                "Key indicators: submerged vegetation, low to moderate salinity 15-35 PSU.",
        "metadata": {
            "ecosystem_type": "seagrass",
            "ecosystem_multiplier": 1.4,
            "carbon_min": 80,
            "carbon_max": 150,
        },
    },
    {
        "id": "saltmarsh-001",
        "text": "Salt marshes are coastal wetland ecosystems dominated by halophytic grasses and herbs. "
                "They provide significant blue carbon storage capacity in their organic-rich soils. "
                "Ecosystem type: salt marsh. Ecosystem multiplier: 1.2. "
                "Typical carbon sequestration: 50-100 tCO2 per hectare per year. "
                "Locations: Godavari Delta, Krishna Delta, estuarine salt marshes. "
                "Key indicators: moderate vegetation density, high salinity 25-45 PSU.",
        "metadata": {
            "ecosystem_type": "salt_marsh",
            "ecosystem_multiplier": 1.2,
            "carbon_min": 50,
            "carbon_max": 100,
        },
    },
    {
        "id": "tidalflat-001",
        "text": "Tidal flats are unvegetated or sparsely vegetated intertidal areas consisting of mud or sand. "
                "They contribute to blue carbon through sediment trapping and organic matter accumulation. "
                "Ecosystem type: tidal flat. Ecosystem multiplier: 0.9. "
                "Typical carbon sequestration: 20-60 tCO2 per hectare per year. "
                "Locations: Rann of Kutch, Chilika periphery, open tidal zones. "
                "Key indicators: very low vegetation density, variable salinity.",
        "metadata": {
            "ecosystem_type": "tidal_flat",
            "ecosystem_multiplier": 0.9,
            "carbon_min": 20,
            "carbon_max": 60,
        },
    },
    {
        "id": "coastal-wetland-001",
        "text": "Coastal wetlands are diverse transitional ecosystems between terrestrial and marine environments. "
                "They include brackish marshes, estuaries, and mixed coastal habitats with carbon sequestration potential. "
                "Ecosystem type: coastal wetland. Ecosystem multiplier: 1.1. "
                "Typical carbon sequestration: 40-90 tCO2 per hectare per year. "
                "Locations: general coastal areas, mixed estuarine zones, river deltas. "
                "Key indicators: mixed vegetation, variable salinity 10-30 PSU, moderate soil carbon.",
        "metadata": {
            "ecosystem_type": "coastal_wetland",
            "ecosystem_multiplier": 1.1,
            "carbon_min": 40,
            "carbon_max": 90,
        },
    },
]


def get_pinecone_client():
    from pinecone import Pinecone

    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY not set")
    return Pinecone(api_key=api_key)


def ingest_carbon_documents():
    try:
        from pinecone import ServerlessSpec

        pc = get_pinecone_client()
        model = SentenceTransformer(MODEL_NAME)

        existing_indexes = [idx.name for idx in pc.list_indexes()]

        if INDEX_NAME not in existing_indexes:
            logger.info(f"Creating Pinecone index: {INDEX_NAME}")
            pc.create_index(
                name=INDEX_NAME,
                dimension=EMBEDDING_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=os.getenv("PINECONE_ENV", "us-east-1")),
            )

        index = pc.Index(INDEX_NAME)
        stats = index.describe_index_stats()

        if stats.total_vector_count > 0:
            logger.info(f"Pinecone index already has {stats.total_vector_count} vectors, skipping ingest.")
            return

        logger.info("Ingesting carbon coefficient documents into Pinecone...")
        vectors = []
        for doc in CARBON_DOCUMENTS:
            embedding = model.encode(doc["text"]).tolist()
            vectors.append({
                "id": doc["id"],
                "values": embedding,
                "metadata": {**doc["metadata"], "text": doc["text"]},
            })

        index.upsert(vectors=vectors)
        logger.info(f"Successfully ingested {len(vectors)} documents into Pinecone.")

    except Exception as e:
        logger.error(f"Failed to ingest RAG documents: {e}")
        raise
