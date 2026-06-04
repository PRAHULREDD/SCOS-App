from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.domain import Reward, RewardRedemption
from app.repositories.base import BaseRepository

class RewardRepository(BaseRepository[Reward]):
    async def get_active(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Reward]:
        result = await db.execute(
            select(Reward)
            .filter(Reward.is_active == 1)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

class RewardRedemptionRepository(BaseRepository[RewardRedemption]):
    async def get_by_user(self, db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100) -> List[RewardRedemption]:
        result = await db.execute(
            select(RewardRedemption)
            .filter(RewardRedemption.user_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

reward_repo = RewardRepository(Reward)
redemption_repo = RewardRedemptionRepository(RewardRedemption)
