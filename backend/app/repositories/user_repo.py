from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.domain import User
from app.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).filter(User.email == email))
        return result.scalars().first()

    async def add_eco_points(self, db: AsyncSession, user_id: int, points: int) -> Optional[User]:
        user = await self.get(db, user_id)
        if user:
            user.eco_points += points
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user

user_repo = UserRepository(User)
