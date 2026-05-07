from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db import crud
from models.schemas import PipelineRunResponse

router = APIRouter()


@router.get("/pipeline/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_status(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await crud.get_pipeline_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    return PipelineRunResponse(
        run_id=str(run.id),
        status=run.status,
        created_at=run.created_at,
        updated_at=run.updated_at,
        input_filename=run.input_filename,
        result=run.result,
    )
