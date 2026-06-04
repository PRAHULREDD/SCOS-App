from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.complaint_repo import complaint_repo
from app.repositories.user_repo import user_repo
from typing import Dict, Any, List
from app.models.domain import Complaint

class ComplaintService:
    @staticmethod
    async def create_complaint(db: AsyncSession, citizen_id: int, data: Dict[str, Any]) -> Complaint:
        # Create complaint
        data["citizen_id"] = citizen_id
        complaint = await complaint_repo.create(db=db, obj_in=data)
        
        # Reward citizen
        await user_repo.add_eco_points(db, citizen_id, 10)
        
        # Future: Push ARQ background job to analyze image fraud here
        return complaint

    @staticmethod
    async def get_citizen_complaints(db: AsyncSession, citizen_id: int) -> List[Complaint]:
        return await complaint_repo.get_by_citizen(db, citizen_id=citizen_id)

    @staticmethod
    async def update_complaint_status(db: AsyncSession, complaint_id: int, status: str) -> Complaint:
        return await complaint_repo.update_status(db, complaint_id=complaint_id, status=status)

complaint_service = ComplaintService()
