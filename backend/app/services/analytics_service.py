from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.analytics_repo import incident_repo, contractor_repo
from typing import Dict, Any

class AnalyticsService:
    @staticmethod
    async def get_admin_overview(db: AsyncSession) -> Dict[str, Any]:
        incidents = await incident_repo.get_active(db)
        contractors = await contractor_repo.get_all_ordered(db)
        
        # Aggregate logic
        total_incidents = len(incidents)
        avg_confidence = sum(i.confidence for i in incidents) / total_incidents if total_incidents > 0 else 0
        
        return {
            "active_incidents_count": total_incidents,
            "average_ai_confidence": round(avg_confidence, 2),
            "top_contractors": contractors[:5],
            "recent_incidents": incidents[:10]
        }

analytics_service = AnalyticsService()
