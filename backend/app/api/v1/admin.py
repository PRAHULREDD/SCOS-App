from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.db.database import get_db
from app.api.dependencies import verify_admin
from app.services.analytics_service import analytics_service
from app.schemas.requests import AdminCreateUser
from app.repositories.user_repo import user_repo
from app.repositories.analytics_repo import incident_repo, contractor_repo
from app.repositories.complaint_repo import complaint_repo
from app.core.auth import get_password_hash
from app.models.domain import User, Complaint, DumpingIncident, Contractor

router = APIRouter()


@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """
    Admin overview endpoint. Returns stats used by admin.js:
    total_complaints, pending_complaints, collection_rate,
    active_incidents_count, average_ai_confidence,
    top_contractors, recent_incidents.
    """
    # Count complaints
    total_result = await db.execute(select(func.count()).select_from(Complaint))
    total_complaints = total_result.scalar() or 0

    pending_result = await db.execute(
        select(func.count()).select_from(Complaint).filter(Complaint.status == "PENDING")
    )
    pending_complaints = pending_result.scalar() or 0

    resolved_result = await db.execute(
        select(func.count()).select_from(Complaint).filter(Complaint.status == "RESOLVED")
    )
    resolved_complaints = resolved_result.scalar() or 0

    collection_rate = round((resolved_complaints / total_complaints * 100), 1) if total_complaints > 0 else 0.0

    # Incidents
    incidents = await incident_repo.get_active(db)
    total_incidents = len(incidents)
    avg_confidence = sum(i.confidence for i in incidents) / total_incidents if total_incidents > 0 else 0

    # Contractors
    contractors = await contractor_repo.get_all_ordered(db)

    return {
        "total_complaints": total_complaints,
        "pending_complaints": pending_complaints,
        "resolved_complaints": resolved_complaints,
        "collection_rate": collection_rate,
        "active_incidents_count": total_incidents,
        "average_ai_confidence": round(avg_confidence, 2),
        "top_contractors": [
            {
                "id": c.id,
                "name": c.name,
                "completion_rate": c.completion_rate,
                "satisfaction_score": c.satisfaction_score,
                "response_time_hours": c.response_time_hours,
                "active_drivers": c.active_drivers,
            }
            for c in contractors[:5]
        ],
        "recent_incidents": [
            {
                "id": i.id,
                "zone": i.zone,
                "cluster_id": i.cluster_id,
                "description": i.description,
                "severity": i.severity,
                "predicted_culprit": i.predicted_culprit,
                "common_time": i.common_time,
                "confidence": i.confidence,
                "lat": i.lat,
                "lng": i.lng,
                "status": i.status,
                "detected_at": i.detected_at.isoformat() if i.detected_at else None,
            }
            for i in incidents[:10]
        ],
    }


@router.get("/waste_heatmap")
async def get_waste_heatmap(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Returns complaint heatmap data for the admin map view."""
    result = await db.execute(
        select(Complaint).filter(Complaint.lat.isnot(None)).filter(Complaint.lng.isnot(None))
    )
    complaints = result.scalars().all()
    return {
        "heatmap_points": [
            {
                "lat": c.lat,
                "lng": c.lng,
                "zone": c.zone,
                "waste_type": c.waste_type,
                "status": c.status,
            }
            for c in complaints
        ],
        "total": len(complaints),
    }


@router.get("/illegal_dumping")
async def get_illegal_dumping(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Returns illegal dumping incidents for the admin illegal dumping view."""
    incidents = await incident_repo.get_active(db)
    high_risk = [i for i in incidents if i.severity == "HIGH"]

    # avg_clear_time is mocked since we don't track clear time
    return {
        "active_count": len(incidents),
        "active_incidents": len(incidents),
        "high_risk_count": len(high_risk),
        "avg_clear_time": 2.4,
        "avg_clear_hours": 2.4,
        "incidents": [
            {
                "id": i.id,
                "zone": i.zone,
                "description": i.description,
                "severity": i.severity,
                "predicted_culprit": i.predicted_culprit,
                "confidence": i.confidence,
                "lat": i.lat,
                "lng": i.lng,
                "status": i.status,
                "detected_at": i.detected_at.isoformat() if i.detected_at else None,
            }
            for i in incidents
        ],
    }


@router.get("/complaints")
async def list_complaints(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """
    Returns all complaints (newest first) for the admin complaint management panel.
    Used by admin.js to display pending/in-progress complaints and enable driver assignment.
    """
    result = await db.execute(
        select(Complaint).order_by(desc(Complaint.created_at))
    )
    complaints = result.scalars().all()
    return {
        "complaints": [
            {
                "id": c.id,
                "citizen_id": c.citizen_id,
                "zone": c.zone,
                "area": c.area,
                "waste_type": c.waste_type,
                "severity_level": c.severity_level,
                "status": c.status,
                "lat": c.lat,
                "lng": c.lng,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in complaints
        ]
    }


@router.get("/drivers")
async def list_drivers(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """
    Returns all registered driver accounts.
    Used by admin.js to populate the driver selection dropdown during task assignment.
    """
    result = await db.execute(
        select(User).filter(User.role == "DRIVER").order_by(User.name)
    )
    drivers = result.scalars().all()
    return {
        "drivers": [
            {
                "id": d.id,
                "name": d.name,
                "email": d.email,
            }
            for d in drivers
        ]
    }


@router.post("/create_user")
async def create_user(
    user_data: AdminCreateUser,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    existing = await user_repo.get_by_email(db, user_data.email)
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user_data = {
        "email": user_data.email,
        "name": user_data.name,
        "password_hash": get_password_hash(user_data.password),
        "role": user_data.role,  # already uppercased by validator
    }
    await user_repo.create(db, obj_in=new_user_data)
    return {"message": f"{user_data.role} account created successfully"}


from pydantic import BaseModel
from app.websocket.manager import manager
from app.repositories.driver_repo import driver_task_repo
from app.models.domain import DriverTask


class AssignTaskRequest(BaseModel):
    driver_id: int
    complaint_id: int
    waste_type: str = "General"
    address: str = "Unknown"


@router.post("/assign_task")
async def assign_task(
    req: AssignTaskRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    # 1. Create the task in DB
    new_task = DriverTask(
        driver_id=req.driver_id,
        complaint_id=req.complaint_id,
        priority="HIGH",
        waste_type=req.waste_type,
        address=req.address,
        status="ASSIGNED"
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)

    # 2. Update complaint status to IN_PROGRESS
    complaint = await complaint_repo.get(db, req.complaint_id)
    if complaint:
        complaint.status = "IN_PROGRESS"
        db.add(complaint)
        await db.commit()

    # 3. Trigger WebSocket notification
    await manager.notify_driver_new_task(req.driver_id, req.complaint_id)

    return {"message": "Task assigned and driver notified", "task_id": new_task.id}
