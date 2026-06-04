from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.dependencies import get_current_user
from app.services.driver_service import driver_service
from app.models.domain import User

router = APIRouter()

@router.get("/assigned_tasks")
async def get_assigned_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tasks = await driver_service.get_driver_tasks(db, current_user.id)
    return {"tasks": tasks}

@router.post("/complete_pickup")
async def complete_pickup(
    complaint_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = await driver_service.complete_task(db, complaint_id)
    return {"message": "Pickup marked as complete"}

@router.post("/update_location")
async def update_location(
    lat: float = Form(...),
    lng: float = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await driver_service.update_location(db, current_user.id, lat, lng)
    return {"message": "Location updated"}
