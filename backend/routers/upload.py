import os
import shutil
import logging
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db import crud
from models.schemas import UploadResponse
from workflow.pipeline import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def _run_pipeline_task(run_id: str, file_path: str):
    from db.database import AsyncSessionLocal
    from db import crud as db_crud

    async with AsyncSessionLocal() as db:
        try:
            await db_crud.update_pipeline_run(db, run_id, "running")
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_pipeline, run_id, file_path)
            status = result.get("status", "failed")
            if status not in ("complete", "failed"):
                status = "failed"
            await db_crud.update_pipeline_run(db, run_id, status, result)

            if status == "complete" and result.get("blockchain_result"):
                blockchain_result = result["blockchain_result"]
                for br in blockchain_result.get("blockchain_results", []):
                    if br.get("status") == "success":
                        await db_crud.create_carbon_credit(
                            db=db,
                            project_id=br["project_id"],
                            site_id=br["site_id"],
                            carbon_tons=br["carbon_tons"],
                            verification_status="VERIFIED",
                            blockchain_tx_hash=br["tx_hash"],
                            blockchain_block_number=br["block_number"],
                        )

        except Exception as e:
            logger.error(f"Background pipeline task failed for {run_id}: {e}")
            await db_crud.update_pipeline_run(db, run_id, "failed", {"error": str(e)})


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    run = await crud.create_pipeline_run(db, file.filename)
    run_id = str(run.id)

    file_path = os.path.join(UPLOAD_DIR, f"{run_id}_{file.filename}")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    background_tasks.add_task(_run_pipeline_task, run_id, file_path)

    return UploadResponse(
        run_id=run_id,
        message="File uploaded successfully. Pipeline started.",
        filename=file.filename,
    )
