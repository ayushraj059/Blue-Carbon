from fastapi import APIRouter
from agents.ops_monitor import get_ops_metrics
from models.schemas import OpsMetrics

router = APIRouter()


@router.get("/ops", response_model=OpsMetrics)
async def get_ops():
    return get_ops_metrics()
