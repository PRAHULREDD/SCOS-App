from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.domain import Complaint
from app.repositories.base import BaseRepository

class ComplaintRepository(BaseRepository[Complaint]):
    async def get_by_citizen(self, db: AsyncSession, citizen_id: int, skip: int = 0, limit: int = 100) -> List[Complaint]:
        result = await db.execute(
            select(Complaint)
            .filter(Complaint.citizen_id == citizen_id)
            .order_by(desc(Complaint.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_pending(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Complaint]:
        result = await db.execute(
            select(Complaint)
            .filter(Complaint.status == "PENDING")
            .order_by(desc(Complaint.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def update_status(self, db: AsyncSession, complaint_id: int, status: str) -> Complaint:
        complaint = await self.get(db, complaint_id)
        if complaint:
            complaint.status = status
            db.add(complaint)
            await db.commit()
            await db.refresh(complaint)
        return complaint

complaint_repo = ComplaintRepository(Complaint)
