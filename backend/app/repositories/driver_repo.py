from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
from app.models.domain import DriverLocation, DriverTask
from app.repositories.base import BaseRepository

class DriverLocationRepository(BaseRepository[DriverLocation]):
    async def upsert_location(self, db: AsyncSession, driver_id: int, lat: float, lng: float) -> DriverLocation:
        result = await db.execute(select(DriverLocation).filter(DriverLocation.driver_id == driver_id))
        location = result.scalars().first()
        
        if location:
            location.lat = lat
            location.lng = lng
            location.updated_at = datetime.utcnow()
        else:
            location = DriverLocation(driver_id=driver_id, lat=lat, lng=lng)
            
        db.add(location)
        await db.commit()
        await db.refresh(location)
        return location

class DriverTaskRepository(BaseRepository[DriverTask]):
    async def get_by_driver(self, db: AsyncSession, driver_id: int, skip: int = 0, limit: int = 100) -> List[DriverTask]:
        result = await db.execute(
            select(DriverTask)
            .filter(DriverTask.driver_id == driver_id)
            .order_by(desc(DriverTask.assigned_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def update_status(self, db: AsyncSession, task_id: int, status: str) -> Optional[DriverTask]:
        task = await self.get(db, task_id)
        if task:
            task.status = status
            if status == "COMPLETED":
                task.completed_at = datetime.utcnow()
            db.add(task)
            await db.commit()
            await db.refresh(task)
        return task

driver_location_repo = DriverLocationRepository(DriverLocation)
driver_task_repo = DriverTaskRepository(DriverTask)
