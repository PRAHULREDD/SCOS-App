"""
SCOS Database Seeder
Usage: python seed_db.py [--force]

--force: Re-hash and update passwords even for existing users.

Seeds:
  - 4 users (1 CITIZEN with points, 1 DRIVER, 1 ADMIN, 1 CITIZEN)
  - 5 Reward items
  - 2 Complaint records
  - 2 DumpingIncident records
  - 2 Contractor records
"""
import asyncio
import sys
import os

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import engine, SessionLocal, Base
from app.models.domain import (
    User, Complaint, Reward, DumpingIncident, Contractor
)
from app.core.auth import get_password_hash, verify_password


USERS = [
    {
        "name": "Citizen John",
        "email": "citizen@city.com",
        "role": "CITIZEN",
        "password": "password",
        "eco_points": 1240,
    },
    {
        "name": "Driver Dave",
        "email": "driver@city.com",
        "role": "DRIVER",
        "password": "password",
        "eco_points": 0,
    },
    {
        "name": "Admin Alice",
        "email": "admin@city.com",
        "role": "ADMIN",
        "password": "password",
        "eco_points": 0,
    },
    {
        "name": "Elena Santos",
        "email": "elena@city.com",
        "role": "CITIZEN",
        "password": "password",
        "eco_points": 2410,
    },
]

REWARDS = [
    {"title": "Free Bus Pass", "provider": "City Transit", "category": "Transport", "points_cost": 200, "image_url": "", "is_active": 1},
    {"title": "10% Grocery Discount", "provider": "GreenMart", "category": "Shopping", "points_cost": 150, "image_url": "", "is_active": 1},
    {"title": "Tree Planting Certificate", "provider": "GreenCity NGO", "category": "Environment", "points_cost": 100, "image_url": "", "is_active": 1},
    {"title": "Free Coffee", "provider": "Cafe Eco", "category": "Food", "points_cost": 50, "image_url": "", "is_active": 1},
    {"title": "Museum Entry Pass", "provider": "City Museum", "category": "Culture", "points_cost": 300, "image_url": "", "is_active": 1},
]

COMPLAINTS = [
    {
        "citizen_id": 1,  # Citizen John (seeded first)
        "zone": "Zone A",
        "area": "Market Street",
        "waste_type": "Plastic",
        "severity_level": "HIGH",
        "status": "PENDING",
        "lat": 12.9716,
        "lng": 77.5946,
    },
    {
        "citizen_id": 4,  # Elena Santos
        "zone": "Zone B",
        "area": "Park Road",
        "waste_type": "Organic",
        "severity_level": "MEDIUM",
        "status": "RESOLVED",
        "lat": 12.9800,
        "lng": 77.6000,
    },
]

INCIDENTS = [
    {
        "zone": "Zone C",
        "cluster_id": "CLU-001",
        "description": "Repeated dumping near school zone",
        "severity": "HIGH",
        "predicted_culprit": "Commercial vehicles",
        "common_time": "2AM-4AM",
        "confidence": 0.87,
        "lat": 12.9750,
        "lng": 77.5980,
        "status": "ACTIVE",
    },
    {
        "zone": "Zone D",
        "cluster_id": "CLU-002",
        "description": "Construction debris on footpath",
        "severity": "MEDIUM",
        "predicted_culprit": "Construction site",
        "common_time": "6AM-8AM",
        "confidence": 0.72,
        "lat": 12.9680,
        "lng": 77.6010,
        "status": "ACTIVE",
    },
]

CONTRACTORS = [
    {"name": "GreenFleet Ltd", "completion_rate": 0.92, "satisfaction_score": 4.5, "response_time_hours": 2.1, "active_drivers": 12},
    {"name": "CleanCity Corp", "completion_rate": 0.87, "satisfaction_score": 4.2, "response_time_hours": 3.4, "active_drivers": 8},
]


async def ensure_tables():
    """Create tables if they don't exist (safe to call repeatedly)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Tables verified/created")


async def seed_users(db: AsyncSession, force: bool = False):
    for u in USERS:
        result = await db.execute(select(User).filter(User.email == u["email"]))
        existing = result.scalars().first()

        if existing:
            if force or not verify_password(u["password"], existing.password_hash):
                existing.password_hash = get_password_hash(u["password"])
                existing.eco_points = u["eco_points"]
                db.add(existing)
                print(f"  Updated: {u['email']}")
            else:
                print(f"  Skipped (exists): {u['email']}")
        else:
            new_user = User(
                name=u["name"],
                email=u["email"],
                password_hash=get_password_hash(u["password"]),
                role=u["role"],
                eco_points=u["eco_points"],
            )
            db.add(new_user)
            print(f"  Added {u['role']}: {u['email']}")

    await db.commit()


async def seed_rewards(db: AsyncSession):
    from app.models.domain import Reward
    result = await db.execute(select(Reward))
    if result.scalars().first():
        print("  Rewards already seeded — skipping")
        return
    for r in REWARDS:
        db.add(Reward(**r))
    await db.commit()
    print(f"  Added {len(REWARDS)} rewards")


async def seed_complaints(db: AsyncSession):
    from app.models.domain import Complaint
    result = await db.execute(select(Complaint))
    if result.scalars().first():
        print("  Complaints already seeded — skipping")
        return
    for c in COMPLAINTS:
        db.add(Complaint(**c))
    await db.commit()
    print(f"  Added {len(COMPLAINTS)} complaints")


async def seed_incidents(db: AsyncSession):
    from app.models.domain import DumpingIncident
    result = await db.execute(select(DumpingIncident))
    if result.scalars().first():
        print("  Incidents already seeded — skipping")
        return
    for i in INCIDENTS:
        db.add(DumpingIncident(**i))
    await db.commit()
    print(f"  Added {len(INCIDENTS)} dumping incidents")


async def seed_contractors(db: AsyncSession):
    from app.models.domain import Contractor
    result = await db.execute(select(Contractor))
    if result.scalars().first():
        print("  Contractors already seeded — skipping")
        return
    for c in CONTRACTORS:
        db.add(Contractor(**c))
    await db.commit()
    print(f"  Added {len(CONTRACTORS)} contractors")


async def main():
    force = "--force" in sys.argv
    print("SCOS Database Seeder")
    print("=" * 40)

    await ensure_tables()

    async with SessionLocal() as db:
        print("\n[Users]")
        await seed_users(db, force=force)

        print("\n[Rewards]")
        await seed_rewards(db)

        print("\n[Complaints]")
        await seed_complaints(db)

        print("\n[Incidents]")
        await seed_incidents(db)

        print("\n[Contractors]")
        await seed_contractors(db)

    print("\n✓ Database seeded successfully")
    print("\nCredentials:")
    for u in USERS:
        print(f"  {u['role']:8} {u['email']:30} password={u['password']}")


if __name__ == "__main__":
    asyncio.run(main())
