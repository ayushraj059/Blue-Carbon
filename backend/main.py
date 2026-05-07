import os
import json
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()

# Disable litellm Redis auto-detection (it picks up REDIS_URL env var)
try:
    import litellm
    litellm.cache = None
except Exception:
    pass

from db.database import init_db
from routers import upload, pipeline, credits, ops, map_upload
from redis_client import get_async_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Blue Carbon Registry...")
    await init_db()
    logger.info("Database initialized")

    try:
        from rag.ingest import ingest_carbon_documents
        ingest_carbon_documents()
        logger.info("RAG documents loaded")
    except Exception as e:
        logger.warning(f"RAG ingest skipped: {e}")

    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="Blue Carbon Registry API",
    description="Agentic AI pipeline for blue carbon MRV and blockchain registration",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(pipeline.router, prefix="/api", tags=["Pipeline"])
app.include_router(credits.router, prefix="/api", tags=["Credits"])
app.include_router(ops.router, prefix="/api", tags=["Ops"])
app.include_router(map_upload.router, prefix="/api", tags=["Map Analysis"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "blue-carbon-registry"}


@app.websocket("/ws/pipeline/{run_id}")
async def websocket_pipeline(websocket: WebSocket, run_id: str):
    await websocket.accept()
    logger.info(f"WebSocket connected for run {run_id}")

    redis_client = await get_async_client()
    pubsub = redis_client.pubsub()
    channel = f"pipeline:{run_id}"

    try:
        await pubsub.subscribe(channel)
        await websocket.send_json({"run_id": run_id, "step": "connected", "status": "ok", "message": "WebSocket connected"})

        while True:
            try:
                message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=30.0)
                if message and message.get("type") == "message":
                    data = json.loads(message["data"])
                    await websocket.send_json(data)

                    if data.get("step") in ("complete", "pipeline") and data.get("status") in ("success", "failed"):
                        break
                else:
                    await websocket.send_json({"run_id": run_id, "step": "heartbeat", "status": "ok", "message": "ping"})
                    await asyncio.sleep(1)

            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"run_id": run_id, "step": "heartbeat", "status": "ok", "message": "ping"})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for run {run_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {run_id}: {e}")
        try:
            await websocket.send_json({"run_id": run_id, "step": "error", "status": "failed", "message": str(e)})
        except Exception:
            pass
    finally:
        await pubsub.unsubscribe(channel)
        await redis_client.aclose()
