import asyncio
import os
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.database import get_db
from app.api.dependencies import verify_driver, get_current_user
from app.services.driver_service import driver_service
from app.services.complaint_service import complaint_service
from app.services.storage_service import (
    get_storage_service,
    BaseStorageService,
    LocalStorageService,
    StoredFile,
    StorageFileNotFoundError,
    StorageError,
)
from app.models.domain import User, DriverTask, Complaint

router = APIRouter()

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "uploads" / "proof_photos"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

MAX_PROOF_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_PROOF_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PROOF_MIMES = {"image/jpeg", "image/png", "image/webp"}


def validate_proof_image(file_bytes: bytes, filename: str, content_type: Optional[str]) -> str:
    """
    Validates uploaded proof image:
    1. Size limit (max 5MB)
    2. Non-empty
    3. Allowed extension (.jpg, .jpeg, .png, .webp)
    4. Allowed Content-Type header
    5. Real magic bytes match recognized image formats
    Returns the normalized extension.
    """
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    if len(file_bytes) > MAX_PROOF_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum allowed limit ({MAX_PROOF_FILE_SIZE // (1024*1024)}MB)"
        )

    ext = Path(filename).suffix.lower() if filename else ""
    if ext not in ALLOWED_PROOF_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_PROOF_EXTENSIONS))}"
        )

    if content_type and content_type.lower() not in ALLOWED_PROOF_MIMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported Content-Type '{content_type}'. Allowed: {', '.join(sorted(ALLOWED_PROOF_MIMES))}"
        )

    # Magic bytes check
    is_jpeg = file_bytes[:3] == b"\xff\xd8\xff"
    is_png = file_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    is_webp = len(file_bytes) >= 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP"

    if not (is_jpeg or is_png or is_webp):
        raise HTTPException(
            status_code=400,
            detail="Invalid image file format. Content does not match recognized image signatures."
        )

    if is_jpeg:
        return ".jpg"
    elif is_png:
        return ".png"
    elif is_webp:
        return ".webp"
    return ext


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
    proof_photo: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_driver),
    storage: BaseStorageService = Depends(get_storage_service)
):
    """
    Complete a pickup for the current driver.
    Enforces driver ownership — a driver cannot complete another driver's task.
    Rejects already-completed tasks.
    Validates and persists uploaded proof image linked durably to task and complaint.
    Handles orphaned files safely on database commit failures.
    """
    result = await db.execute(
        select(DriverTask)
        .filter(DriverTask.complaint_id == complaint_id)
        .filter(DriverTask.driver_id == current_user.id)
    )
    task = result.scalars().first()

    if not task:
        raise HTTPException(status_code=404, detail="No task found for this complaint assigned to you")

    if task.status == "COMPLETED" or task.proof_photo_url is not None:
        raise HTTPException(status_code=409, detail="Pickup already completed")

    if task.status != "ASSIGNED":
        raise HTTPException(status_code=409, detail=f"Task is in state '{task.status}', cannot complete")

    complaint_result = await db.execute(
        select(Complaint).filter(Complaint.id == complaint_id)
    )
    complaint = complaint_result.scalars().first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Originating complaint not found")

    file_bytes: Optional[bytes] = None
    verified_ext: Optional[str] = None
    content_type: Optional[str] = None

    if proof_photo and proof_photo.filename:
        file_bytes = await proof_photo.read()
        # Always validate uploaded file bytes (rejects 0-byte files with HTTP 400)
        verified_ext = validate_proof_image(
            file_bytes=file_bytes,
            filename=proof_photo.filename,
            content_type=proof_photo.content_type
        )
        content_type = proof_photo.content_type or (
            "image/jpeg" if verified_ext in (".jpg", ".jpeg")
            else "image/png" if verified_ext == ".png"
            else "image/webp"
        )

    # Establish exclusive ownership of this completion attempt before writing to storage
    claim_stmt = (
        update(DriverTask)
        .where(
            DriverTask.id == task.id,
            DriverTask.status == "ASSIGNED",
            DriverTask.proof_photo_url.is_(None)
        )
        .values(
            status="COMPLETED",
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
    )
    claim_res = await db.execute(claim_stmt)
    if claim_res.rowcount != 1:
        raise HTTPException(status_code=409, detail="Pickup already completed")

    created_storage_key: Optional[str] = None
    proof_url: Optional[str] = None

    if file_bytes is not None and verified_ext is not None:
        storage_key = f"proofs/tasks/task_{task.id}{verified_ext}"
        try:
            await storage.save_file(
                key=storage_key,
                content=file_bytes,
                content_type=content_type
            )
            created_storage_key = storage_key
            proof_url = f"/api/driver/proof/{task.id}"
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to persist proof photo: {e}")

    try:
        if proof_url:
            await db.execute(
                update(DriverTask)
                .where(DriverTask.id == task.id)
                .values(proof_photo_url=proof_url)
            )

        complaint.status = "RESOLVED"
        if proof_url:
            complaint.proof_photo_url = proof_url

        db.add(complaint)
        await db.commit()
        await db.refresh(task)
        await db.refresh(complaint)
    except Exception as e:
        await db.rollback()
        if created_storage_key:
            try:
                await storage.delete_file(created_storage_key)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Database commit failed during pickup completion: {e}")

    resp = {
        "message": "Pickup marked as complete",
        "task_id": task.id,
        "complaint_id": complaint_id
    }
    if proof_url:
        resp["proof_photo_url"] = proof_url

    return resp


@router.get("/proof/{task_id}")
@router.get("/proof_photo/{task_id}")
async def get_proof_photo(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: BaseStorageService = Depends(get_storage_service)
):
    """
    Authorized retrieval of completed pickup proof photo.
    Enforces role & ownership:
    - ADMIN: full access
    - DRIVER: assigned driver only
    - CITIZEN: reporting citizen of the linked complaint only
    """
    task_res = await db.execute(select(DriverTask).filter(DriverTask.id == task_id))
    task = task_res.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    complaint_res = await db.execute(select(Complaint).filter(Complaint.id == task.complaint_id))
    complaint = complaint_res.scalars().first()

    # Authorization Check
    if current_user.role == "ADMIN":
        pass  # Admin can view all proofs
    elif current_user.role == "DRIVER":
        if task.driver_id != current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden: You are not the driver assigned to this task")
    elif current_user.role == "CITIZEN":
        if not complaint or complaint.citizen_id != current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden: You did not submit the complaint for this pickup")
    else:
        raise HTTPException(status_code=403, detail="Forbidden: Unauthorized role")

    # Only serve proof if database record actually references a proof photo
    if not task.proof_photo_url:
        raise HTTPException(status_code=404, detail="No proof photo uploaded for this task")

    stored_file: Optional[StoredFile] = None

    # Step 1: Storage abstraction lookup with deterministic key
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate_key = f"proofs/tasks/task_{task_id}{ext}"
        try:
            if await storage.exists(candidate_key):
                stored_file = await storage.get_file(candidate_key)
                break
        except StorageError as e:
            raise HTTPException(status_code=500, detail=f"Storage provider error: {e}")

    # Step 2: Legacy local-file compatibility fallback
    if stored_file is None:
        legacy_dir = (
            storage.storage_root
            if isinstance(storage, LocalStorageService)
            else STORAGE_DIR
        )
        legacy_matches = []
        if legacy_dir and legacy_dir.is_dir():
            candidates = list(legacy_dir.glob(f"task_{task_id}_*"))
            legacy_matches = [
                p for p in candidates
                if p.is_file() and not p.name.endswith(".meta.json") and not p.name.startswith(".tmp")
            ]

        if len(legacy_matches) == 1:
            target_file = legacy_matches[0]
            try:
                content = await asyncio.to_thread(target_file.read_bytes)
                ext = target_file.suffix.lower()
                media_map = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".webp": "image/webp"
                }
                media_type = media_map.get(ext, "application/octet-stream")
                stored_file = StoredFile(content=content, content_type=media_type)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to read legacy proof photo: {e}")
        elif len(legacy_matches) > 1:
            raise HTTPException(
                status_code=409,
                detail=f"Ambiguous legacy proof photos found for task {task_id}; manual reconciliation required"
            )

    if stored_file is None:
        raise HTTPException(status_code=404, detail="Proof photo file not found on disk")

    return StreamingResponse(
        stored_file.to_stream(),
        media_type=stored_file.content_type
    )


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
