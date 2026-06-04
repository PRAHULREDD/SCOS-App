from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.domain import DumpingIncident, Contractor
from app.repositories.base import BaseRepository

class DumpingIncidentRepository(BaseRepository[DumpingIncident]):
    async def get_active(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DumpingIncident]:
        result = await db.execute(
            select(DumpingIncident)
            .filter(DumpingIncident.status == "ACTIVE")
            .order_by(desc(DumpingIncident.detected_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

class ContractorRepository(BaseRepository[Contractor]):
    async def get_all_ordered(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Contractor]:
        result = await db.execute(
            select(Contractor)
            .order_by(desc(Contractor.completion_rate))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

incident_repo = DumpingIncidentRepository(DumpingIncident)
contractor_repo = ContractorRepository(Contractor)
