from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from app.db.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String) # CITIZEN, DRIVER, ADMIN
    eco_points = Column(Integer, default=0)

class Complaint(Base):
    __tablename__ = "complaints"
    id = Column(Integer, primary_key=True, index=True)
    citizen_id = Column(Integer)
    zone = Column(String)
    area = Column(String)
    waste_type = Column(String)
    severity_level = Column(String)
    status = Column(String, default="PENDING")
    lat = Column(Float)
    lng = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class DriverLocation(Base):
    __tablename__ = "driver_locations"
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer)
    lat = Column(Float)
    lng = Column(Float)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Reward(Base):
    __tablename__ = "rewards"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    provider = Column(String)
    category = Column(String)
    points_cost = Column(Integer)
    image_url = Column(String)
    is_active = Column(Integer, default=1)

class RewardRedemption(Base):
    __tablename__ = "reward_redemptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    reward_id = Column(Integer)
    redeemed_at = Column(DateTime, default=datetime.utcnow)

class DriverTask(Base):
    __tablename__ = "driver_tasks"
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer)
    complaint_id = Column(Integer)
    priority = Column(String, default="MEDIUM")
    waste_type = Column(String)
    address = Column(String)
    bin_fill_percent = Column(Integer, default=50)
    distance_km = Column(Float, default=0)
    status = Column(String, default="ASSIGNED")
    assigned_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class DumpingIncident(Base):
    __tablename__ = "dumping_incidents"
    id = Column(Integer, primary_key=True, index=True)
    zone = Column(String)
    cluster_id = Column(String)
    description = Column(String)
    severity = Column(String, default="MEDIUM")
    predicted_culprit = Column(String)
    common_time = Column(String)
    confidence = Column(Float, default=0)
    lat = Column(Float)
    lng = Column(Float)
    status = Column(String, default="ACTIVE")
    detected_at = Column(DateTime, default=datetime.utcnow)
    dispatched_at = Column(DateTime, nullable=True)

class Contractor(Base):
    __tablename__ = "contractors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    completion_rate = Column(Float, default=0)
    satisfaction_score = Column(Float, default=0)
    response_time_hours = Column(Float, default=0)
    active_drivers = Column(Integer, default=0)
