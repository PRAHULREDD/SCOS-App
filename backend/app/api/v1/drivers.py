from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.api.dependencies import verify_driver
from app.services.driver_service import driver_service
from app.services.complaint_service import complaint_service
from app.models.domain import User, DriverTask, Complaint

router = APIRouter()


@router.get("/assigned_tasks")
async def get_assigned_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_driver)
):
    tasks = await driver_service.get_driver_tasks(db, current_user.id)
    result = []
    for t in tasks:
        result.append({
            "id": t.id,
            "complaint_id": t.complaint_id,
            "driver_id": t.driver_id,
            "priority": t.priority,
            "waste_type": t.waste_type,
            "address": t.address,
            "bin_fill_percent": t.bin_fill_percent,
            "distance_km": t.distance_km,
            "status": t.status,
            "assigned_at": t.assigned_at.isoformat() if t.assigned_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        })
    return {"tasks": result}


@router.get("/dashboard")
async def get_driver_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_driver)
):
    """Returns stats for the driver dashboard."""
    tasks = await driver_service.get_driver_tasks(db, current_user.id)
    total_tasks = len(tasks)
    completed_today = sum(1 for t in tasks if t.status == "COMPLETED")
    assigned = sum(1 for t in tasks if t.status == "ASSIGNED")

    return {
        "driver_name": current_user.name,
        "total_tasks": total_tasks,
        "completed_today": completed_today,
        "assigned_tasks": assigned,
    }


@router.get("/active_complaints")
async def get_active_complaints(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_driver)
):
    """Returns ASSIGNED tasks joined with their complaints for this driver."""
    result = await db.execute(
        select(DriverTask, Complaint)
        .join(Complaint, DriverTask.complaint_id == Complaint.id)
        .filter(DriverTask.driver_id == current_user.id)
        .filter(DriverTask.status == "ASSIGNED")
    )
    rows = result.all()
    output = []
    for task, comp in rows:
        output.append({
            "id": task.id,
            "complaint_id": comp.id,
            "area": comp.area,
            "zone": comp.zone,
            "waste_type": comp.waste_type or task.waste_type,
            "severity_level": comp.severity_level,
            "lat": comp.lat,
            "lng": comp.lng,
        })
    return output


@router.post("/complete_pickup")
async def complete_pickup(
    complaint_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_driver)
):
    """
    Complete a pickup for the current driver.
    Enforces driver ownership — a driver cannot complete another driver's task.
    Rejects already-completed tasks.
    """
    result = await db.execute(
        select(DriverTask)
        .filter(DriverTask.complaint_id == complaint_id)
        .filter(DriverTask.driver_id == current_user.id)
    )
    task = result.scalars().first()

    if not task:
        raise HTTPException(status_code=404, detail="No task found for this complaint assigned to you")

    if task.status == "COMPLETED":
        raise HTTPException(status_code=409, detail="Pickup already completed")

    if task.status != "ASSIGNED":
        raise HTTPException(status_code=409, detail=f"Task is in state '{task.status}', cannot complete")

    task_id = task.id  # capture before commit expiration

    await driver_service.complete_task(db, task_id)

    # Update the originating complaint to RESOLVED
    await complaint_service.update_complaint_status(db, complaint_id, "RESOLVED")

    return {"message": "Pickup marked as complete", "task_id": task_id}


@router.post("/update_location")
async def update_location(
    lat: float = Form(...),
    lng: float = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_driver)
):
    # Basic coordinate sanity check
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise HTTPException(status_code=422, detail="Invalid GPS coordinates")
    await driver_service.update_location(db, current_user.id, lat, lng)
    return {"message": "Location updated"}
