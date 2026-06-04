from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.driver_repo import driver_task_repo, driver_location_repo
from app.models.domain import DriverTask, DriverLocation
from typing import List, Optional

class DriverService:
    @staticmethod
    async def get_driver_tasks(db: AsyncSession, driver_id: int) -> List[DriverTask]:
        return await driver_task_repo.get_by_driver(db, driver_id=driver_id)

    @staticmethod
    async def complete_task(db: AsyncSession, task_id: int) -> Optional[DriverTask]:
        task = await driver_task_repo.update_status(db, task_id=task_id, status="COMPLETED")
        # Future: Trigger websocket broadcast to admin dashboard
        return task

    @staticmethod
    async def update_location(db: AsyncSession, driver_id: int, lat: float, lng: float) -> DriverLocation:
        location = await driver_location_repo.upsert_location(db, driver_id=driver_id, lat=lat, lng=lng)
        # Future: Emit location to websocket pool
        return location

driver_service = DriverService()
