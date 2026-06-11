from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.dependencies import verify_admin
from app.services.analytics_service import analytics_service
from app.schemas.requests import AdminCreateUser
from app.repositories.user_repo import user_repo
from app.core.auth import get_password_hash
from app.models.domain import User

router = APIRouter()

@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    stats = await analytics_service.get_admin_overview(db)
    return stats

@router.post("/create_user")
async def create_user(
    user_data: AdminCreateUser,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    new_user_data = {
        "email": user_data.email,
        "name": user_data.name,
        "password_hash": get_password_hash(user_data.password),
        "role": user_data.role.upper()
    }
    await user_repo.create(db, obj_in=new_user_data)
    return {"message": f"{user_data.role} account created successfully"}

from pydantic import BaseModel
from app.websocket.manager import manager
from app.repositories.driver_repo import driver_task_repo
from app.models.domain import DriverTask

class AssignTaskRequest(BaseModel):
    driver_id: int
    complaint_id: int
    waste_type: str = "General"
    address: str = "Unknown"

@router.post("/assign_task")
async def assign_task(
    req: AssignTaskRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    # 1. Create the task in DB
    new_task = DriverTask(
        driver_id=req.driver_id,
        complaint_id=req.complaint_id,
        priority="HIGH",
        waste_type=req.waste_type,
        address=req.address,
        status="ASSIGNED"
    )
    db.add(new_task)
    await db.commit()
    
    # 2. Trigger WebSocket notification instantly
    await manager.notify_driver_new_task(req.driver_id, req.complaint_id)
    
    return {"message": "Task assigned and driver notified"}
