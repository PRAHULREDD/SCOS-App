from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.reward_repo import reward_repo
from app.repositories.user_repo import user_repo
from app.models.domain import Reward, RewardRedemption
from typing import List, Dict, Any


class RewardService:
    @staticmethod
    async def get_available_rewards(db: AsyncSession) -> List[Reward]:
        return await reward_repo.get_active(db)

    @staticmethod
    async def redeem_reward(db: AsyncSession, user_id: int, reward_id: int) -> Dict[str, Any]:
        reward = await reward_repo.get(db, reward_id)
        user = await user_repo.get(db, user_id)

        if not reward or not user:
            return {"success": False, "message": "Reward or user not found"}

        if user.eco_points < reward.points_cost:
            return {"success": False, "message": "Not enough eco-points"}

        # Deduct points and record redemption in a single transaction
        reward_title = reward.title  # capture before commit expires the object
        user.eco_points -= reward.points_cost
        db.add(user)

        redemption = RewardRedemption(user_id=user_id, reward_id=reward_id)
        db.add(redemption)

        await db.commit()
        await db.refresh(user)

        return {
            "success": True,
            "message": f"Successfully redeemed {reward_title}",
            "remaining_points": user.eco_points,
        }



reward_service = RewardService()

