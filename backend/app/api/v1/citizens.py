from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.dependencies import get_current_user
from app.schemas.requests import ReportIssueValidation
from app.services.complaint_service import complaint_service
from app.services.reward_service import reward_service
from app.models.domain import User

router = APIRouter()

@router.post("/report_issue")
async def report_issue(
    report_data: ReportIssueValidation,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    complaint = await complaint_service.create_complaint(
        db=db, 
        citizen_id=current_user.id, 
        data=report_data.dict()
    )
    return {"message": "Issue reported successfully. Image analysis queued.", "id": complaint.id}

@router.get("/my_reports")
async def get_my_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    complaints = await complaint_service.get_citizen_complaints(db, current_user.id)
    return {"reports": complaints}

@router.get("/rewards")
async def get_rewards(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rewards = await reward_service.get_available_rewards(db)
    return {
        "eco_points": current_user.eco_points,
        "available_rewards": rewards
    }

@router.post("/redeem")
async def redeem_reward(
    reward_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await reward_service.redeem_reward(db, current_user.id, reward_id)
    return result
