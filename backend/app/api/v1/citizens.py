from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.database import get_db
from app.api.dependencies import get_current_user, verify_citizen
from app.schemas.requests import ReportIssueValidation
from app.services.complaint_service import complaint_service
from app.services.reward_service import reward_service
from app.models.domain import User

router = APIRouter()


@router.post("/report_issue")
async def report_issue(
    report_data: ReportIssueValidation,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_citizen)
):
    # create_complaint returns {"id": ..., "points": ...} — no ORM object to expire
    result = await complaint_service.create_complaint(
        db=db,
        citizen_id=current_user.id,
        data=report_data.model_dump()
    )
    return {
        "message": "Issue reported successfully. Image analysis queued.",
        "id": result["id"],
        "points": result["points"],
    }



@router.get("/my_reports")
async def get_my_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_citizen)
):
    complaints = await complaint_service.get_citizen_complaints(db, current_user.id)
    # Serialize ORM objects to dicts
    result = []
    for c in complaints:
        result.append({
            "id": c.id,
            "zone": c.zone,
            "area": c.area,
            "waste_type": c.waste_type,
            "severity_level": c.severity_level,
            "status": c.status,
            "lat": c.lat,
            "lng": c.lng,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return {"reports": result}


@router.get("/dashboard")
async def get_citizen_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_citizen)
):
    """Returns stats for the citizen dashboard."""
    complaints = await complaint_service.get_citizen_complaints(db, current_user.id)
    total = len(complaints)
    resolved = sum(1 for c in complaints if c.status == "RESOLVED")
    pending = sum(1 for c in complaints if c.status == "PENDING")

    # Simulated cleanliness score based on resolution rate
    resolution_rate = (resolved / total * 100) if total > 0 else 75.0
    cleanliness_score = round(min(100, 50 + resolution_rate / 2), 1)

    return {
        "eco_points": current_user.eco_points,
        "total_reports": total,
        "resolved_reports": resolved,
        "pending_reports": pending,
        "cleanliness_score": cleanliness_score,
        "user_name": current_user.name,
    }


@router.get("/rewards")
async def get_rewards(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_citizen)
):
    rewards = await reward_service.get_available_rewards(db)
    rewards_list = [
        {
            "id": r.id,
            "title": r.title,
            "provider": r.provider,
            "category": r.category,
            "points_cost": r.points_cost,
            "image_url": r.image_url,
        }
        for r in rewards
    ]
    return {
        "eco_points": current_user.eco_points,
        "available_rewards": rewards_list
    }


class RedeemRequest(BaseModel):
    reward_id: int


@router.post("/redeem_reward")
async def redeem_reward(
    req: RedeemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_citizen)
):
    result = await reward_service.redeem_reward(db, current_user.id, req.reward_id)
    # reward_service already returns remaining_points; no second DB fetch needed
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Redemption failed"))
    return result

