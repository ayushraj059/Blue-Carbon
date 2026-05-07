import os
import uuid
import logging
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db import crud
from models.schemas import UploadResponse
from vision.analyzer import analyze_image_bytes
from vision.static_maps import (
    fetch_satellite_image,
    reverse_geocode,
    calculate_area_hectares,
    get_polygon_center,
)
from routers.upload import _run_pipeline_task

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class PolygonCoord(BaseModel):
    lat: float
    lng: float


class MapSnapshotRequest(BaseModel):
    polygon_coords: List[PolygonCoord]
    location: Optional[str] = None
    area_hectares: Optional[float] = None


def _build_csv(site_id: str, location: str, analysis: dict, area_hectares: float) -> str:
    return (
        "site_id,location,vegetation_density,soil_carbon_pct,water_salinity,area_hectares,measurement_date\n"
        f"{site_id},{location},{analysis['vegetation_density']:.3f},"
        f"{analysis['soil_carbon_pct']:.2f},{analysis['water_salinity']:.1f},"
        f"{area_hectares:.2f},{date.today().isoformat()}\n"
    )


@router.post("/analyze-image", response_model=dict)
async def analyze_image_endpoint(
    image: UploadFile = File(...),
    location: str = Form(...),
    area_hectares: float = Form(...),
):
    """Analyze an uploaded satellite/aerial image with Gemini Vision. Returns raw analysis."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files accepted (jpg, png, webp)")

    image_bytes = await image.read()
    try:
        analysis = analyze_image_bytes(image_bytes, image.content_type)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {e}")

    return {
        "location": location,
        "area_hectares": area_hectares,
        "site_id": f"IMG-{uuid.uuid4().hex[:6].upper()}",
        "measurement_date": date.today().isoformat(),
        **analysis,
    }


@router.post("/upload-image", response_model=UploadResponse)
async def upload_from_image(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    location: str = Form(...),
    area_hectares: float = Form(...),
    site_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Analyze uploaded satellite image with Gemini, then run the full pipeline."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files accepted")

    image_bytes = await image.read()
    try:
        analysis = analyze_image_bytes(image_bytes, image.content_type)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {e}")

    generated_site_id = site_id or f"IMG-{uuid.uuid4().hex[:6].upper()}"
    csv_content = _build_csv(generated_site_id, location, analysis, area_hectares)

    run = await crud.create_pipeline_run(db, f"img_{generated_site_id}.csv")
    run_id = str(run.id)

    csv_path = os.path.join(UPLOAD_DIR, f"{run_id}_img.csv")
    with open(csv_path, "w") as f:
        f.write(csv_content)

    background_tasks.add_task(_run_pipeline_task, run_id, csv_path)

    return UploadResponse(
        run_id=run_id,
        message=f"Detected: {analysis['ecosystem_type']} (confidence {analysis['confidence']:.0%}). Pipeline started.",
        filename=f"img_{generated_site_id}.csv",
    )


@router.post("/map-snapshot", response_model=UploadResponse)
async def map_snapshot(
    background_tasks: BackgroundTasks,
    body: MapSnapshotRequest,
    db: AsyncSession = Depends(get_db),
):
    """Draw polygon on Google Maps → auto-fetch satellite image → Gemini analysis → pipeline."""
    coords = [{"lat": c.lat, "lng": c.lng} for c in body.polygon_coords]

    if len(coords) < 3:
        raise HTTPException(status_code=400, detail="Polygon needs at least 3 coordinates")

    area_hectares = body.area_hectares or calculate_area_hectares(coords)
    if area_hectares <= 0:
        raise HTTPException(status_code=400, detail="Calculated area is zero — check coordinates")

    location = body.location
    if not location:
        center = get_polygon_center(coords)
        location = reverse_geocode(center["lat"], center["lng"])

    try:
        image_bytes = fetch_satellite_image(coords, area_hectares)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Satellite image fetch failed: {e}")

    try:
        analysis = analyze_image_bytes(image_bytes, "image/png")
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {e}")

    site_id = f"MAP-{uuid.uuid4().hex[:6].upper()}"
    csv_content = _build_csv(site_id, location, analysis, area_hectares)

    run = await crud.create_pipeline_run(db, f"map_{site_id}.csv")
    run_id = str(run.id)

    csv_path = os.path.join(UPLOAD_DIR, f"{run_id}_map.csv")
    with open(csv_path, "w") as f:
        f.write(csv_content)

    background_tasks.add_task(_run_pipeline_task, run_id, csv_path)

    return UploadResponse(
        run_id=run_id,
        message=(
            f"Satellite image analyzed: {analysis['ecosystem_type']} detected at {location} "
            f"({area_hectares:.1f} ha, confidence {analysis['confidence']:.0%}). Pipeline started."
        ),
        filename=f"map_{site_id}.csv",
    )
