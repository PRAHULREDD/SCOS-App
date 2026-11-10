from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
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
            "description": c.description,
            "waste_type": c.waste_type,
            "severity_level": c.severity_level,
            "status": c.status,
            "lat": c.lat,
            "lng": c.lng,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return {"reports": result}


@router.get("/leaderboard")
async def get_citizen_leaderboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_citizen)
):
    """
    Returns authentic community leaderboard ranked by eco_points.
    Only includes users with role == 'CITIZEN'. Excludes ADMIN and DRIVER.
    """
    stmt = (
        select(User)
        .where(User.role == "CITIZEN")
        .order_by(desc(User.eco_points), User.name)
        .limit(20)
    )
    result = await db.execute(stmt)
    citizens = result.scalars().all()

    leaderboard = []
    user_rank = None
    for rank, citizen in enumerate(citizens, start=1):
        is_me = (citizen.id == current_user.id)
        if is_me:
            user_rank = rank
        leaderboard.append({
            "rank": rank,
            "id": citizen.id,
            "name": citizen.name or "Citizen",
            "eco_points": citizen.eco_points or 0,
            "is_current_user": is_me,
        })

    # If current user is not in top 20, calculate user's real ranking
    if user_rank is None:
        count_higher = await db.scalar(
            select(func.count(User.id)).where(
                User.role == "CITIZEN",
                User.eco_points > (current_user.eco_points or 0)
            )
        )
        user_rank = (count_higher or 0) + 1

    return {
        "leaderboard": leaderboard,
        "user_rank": user_rank,
        "user_points": current_user.eco_points or 0,
        "user_name": current_user.name or "Citizen"
    }


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

