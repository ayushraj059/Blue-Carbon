from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from sqlalchemy.dialects.postgresql import insert
from db.database import PipelineRun, CarbonCredit
from datetime import datetime, timezone
import uuid
from typing import Optional, List, Dict, Any


# --- PipelineRun CRUD ---

async def create_pipeline_run(db: AsyncSession, filename: str) -> PipelineRun:
    run = PipelineRun(
        id=uuid.uuid4(),
        status="pending",
        input_filename=filename,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def get_pipeline_run(db: AsyncSession, run_id: str) -> Optional[PipelineRun]:
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == uuid.UUID(run_id)))
    return result.scalar_one_or_none()


async def update_pipeline_run(
    db: AsyncSession,
    run_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
) -> Optional[PipelineRun]:
    values = {"status": status, "updated_at": datetime.now(timezone.utc)}
    if result is not None:
        values["result"] = result

    await db.execute(
        update(PipelineRun)
        .where(PipelineRun.id == uuid.UUID(run_id))
        .values(**values)
    )
    await db.commit()
    return await get_pipeline_run(db, run_id)


async def list_pipeline_runs(db: AsyncSession, limit: int = 20, offset: int = 0) -> List[PipelineRun]:
    result = await db.execute(
        select(PipelineRun).order_by(desc(PipelineRun.created_at)).limit(limit).offset(offset)
    )
    return result.scalars().all()


# --- CarbonCredit CRUD ---

async def create_carbon_credit(
    db: AsyncSession,
    project_id: str,
    site_id: str,
    carbon_tons: float,
    verification_status: str = "PENDING",
    blockchain_tx_hash: Optional[str] = None,
    blockchain_block_number: Optional[int] = None,
) -> CarbonCredit:
    credit = CarbonCredit(
        id=uuid.uuid4(),
        project_id=project_id,
        site_id=site_id,
        carbon_tons=carbon_tons,
        verification_status=verification_status,
        blockchain_tx_hash=blockchain_tx_hash,
        blockchain_block_number=blockchain_block_number,
        created_at=datetime.now(timezone.utc),
    )
    db.add(credit)
    await db.commit()
    await db.refresh(credit)
    return credit


async def get_carbon_credit(db: AsyncSession, project_id: str) -> Optional[CarbonCredit]:
    result = await db.execute(
        select(CarbonCredit).where(CarbonCredit.project_id == project_id)
    )
    return result.scalar_one_or_none()


async def list_carbon_credits(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> List[CarbonCredit]:
    result = await db.execute(
        select(CarbonCredit).order_by(desc(CarbonCredit.created_at)).limit(limit).offset(offset)
    )
    return result.scalars().all()


async def count_carbon_credits(db: AsyncSession) -> int:
    from sqlalchemy import func
    result = await db.execute(select(func.count()).select_from(CarbonCredit))
    return result.scalar()


async def update_carbon_credit_blockchain(
    db: AsyncSession,
    project_id: str,
    tx_hash: str,
    block_number: int,
    verification_status: str = "VERIFIED",
) -> Optional[CarbonCredit]:
    await db.execute(
        update(CarbonCredit)
        .where(CarbonCredit.project_id == project_id)
        .values(
            blockchain_tx_hash=tx_hash,
            blockchain_block_number=block_number,
            verification_status=verification_status,
        )
    )
    await db.commit()
    return await get_carbon_credit(db, project_id)
