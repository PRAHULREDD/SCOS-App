from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.analytics_repo import incident_repo
from typing import Dict, Any

class AnalyticsService:
    @staticmethod
    async def get_admin_overview(db: AsyncSession) -> Dict[str, Any]:
        incidents = await incident_repo.get_active(db)
        
        # Aggregate logic
        total_incidents = len(incidents)
        
        return {
            "active_incidents_count": total_incidents,
            "recent_incidents": incidents[:10]
        }

analytics_service = AnalyticsService()
