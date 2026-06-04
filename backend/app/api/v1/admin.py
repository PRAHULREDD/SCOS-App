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
