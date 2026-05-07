from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class SiteRecord(BaseModel):
    site_id: str
    location: str
    vegetation_density: float
    soil_carbon_pct: float
    water_salinity: float
    area_hectares: float
    measurement_date: str


class CarbonEstimate(BaseModel):
    site_id: str
    location: str
    carbon_tons: float
    ecosystem_type: str
    ecosystem_multiplier: float
    area_hectares: float


class VerificationResult(BaseModel):
    site_id: str
    status: str  # PASS or FAIL
    reason_codes: List[str] = []
    anomalies: List[str] = []


class BlockchainResult(BaseModel):
    project_id: str
    tx_hash: str
    block_number: int
    carbon_tons: float
    status: str


class PipelineState(BaseModel):
    run_id: str
    raw_data: Optional[List[Dict[str, Any]]] = None
    validated_data: Optional[List[SiteRecord]] = None
    carbon_estimates: Optional[List[CarbonEstimate]] = None
    verification_result: Optional[List[VerificationResult]] = None
    blockchain_result: Optional[List[BlockchainResult]] = None
    errors: Optional[List[str]] = None
    retry_count: int = 0
    status: str = "pending"
    total_carbon_tons: float = 0.0


class PipelineRunResponse(BaseModel):
    run_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    input_filename: Optional[str]
    result: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class CarbonCreditResponse(BaseModel):
    id: str
    project_id: str
    site_id: str
    carbon_tons: float
    verification_status: str
    blockchain_tx_hash: Optional[str]
    blockchain_block_number: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    run_id: str
    message: str
    filename: str


class OpsMetrics(BaseModel):
    total_runs: int
    success_rate: float
    avg_pipeline_duration_seconds: float
    uptime_percentage: float
    agent_latencies: Dict[str, float]
    agent_success_counts: Dict[str, int]
    agent_failure_counts: Dict[str, int]


class WebSocketMessage(BaseModel):
    run_id: str
    step: str
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str
