from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from db.database import get_db
from db import crud
from models.schemas import CarbonCreditResponse

router = APIRouter()


@router.get("/credits", response_model=List[CarbonCreditResponse])
async def list_credits(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    credits = await crud.list_carbon_credits(db, limit=limit, offset=offset)
    return [
        CarbonCreditResponse(
            id=str(c.id),
            project_id=c.project_id,
            site_id=c.site_id,
            carbon_tons=c.carbon_tons,
            verification_status=c.verification_status,
            blockchain_tx_hash=c.blockchain_tx_hash,
            blockchain_block_number=c.blockchain_block_number,
            created_at=c.created_at,
        )
        for c in credits
    ]


@router.get("/credit/{project_id}", response_model=CarbonCreditResponse)
async def get_credit(project_id: str, db: AsyncSession = Depends(get_db)):
    credit = await crud.get_carbon_credit(db, project_id)
    if not credit:
        raise HTTPException(status_code=404, detail="Credit not found")

    return CarbonCreditResponse(
        id=str(credit.id),
        project_id=credit.project_id,
        site_id=credit.site_id,
        carbon_tons=credit.carbon_tons,
        verification_status=credit.verification_status,
        blockchain_tx_hash=credit.blockchain_tx_hash,
        blockchain_block_number=credit.blockchain_block_number,
        created_at=credit.created_at,
    )
