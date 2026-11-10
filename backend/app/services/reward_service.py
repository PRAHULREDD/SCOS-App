from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Reward, RewardRedemption, User
from app.repositories.reward_repo import reward_repo
from typing import List, Dict, Any


class RewardService:
    @staticmethod
    async def get_available_rewards(db: AsyncSession) -> List[Reward]:
        return await reward_repo.get_active(db)

    @staticmethod
    async def redeem_reward(
        db: AsyncSession, user_id: int, reward_id: int
    ) -> Dict[str, Any]:

        # Lock order is always User first, then Reward.
        # populate_existing refreshes potentially stale ORM objects.
        user_result = await db.execute(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await db.rollback()
            return {"success": False, "message": "Reward or user not found"}

        reward_result = await db.execute(
            select(Reward)
            .where(Reward.id == reward_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        reward = reward_result.scalar_one_or_none()

        if not reward:
            await db.rollback()
            return {"success": False, "message": "Reward or user not found"}

        if not reward.is_active:
            await db.rollback()
            return {
                "success": False,
                "message": "This reward is currently unavailable",
            }

        if user.eco_points < reward.points_cost:
            await db.rollback()
            return {"success": False, "message": "Not enough eco-points"}

        reward_title = reward.title
        user.eco_points -= reward.points_cost

        db.add(
            RewardRedemption(
                user_id=user_id,
                reward_id=reward_id,
            )
        )

        await db.commit()
        await db.refresh(user)

        return {
            "success": True,
            "message": f"Successfully redeemed {reward_title}",
            "remaining_points": user.eco_points,
        }


reward_service = RewardService()
