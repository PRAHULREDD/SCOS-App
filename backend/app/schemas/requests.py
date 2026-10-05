from pydantic import BaseModel, Field, field_validator
from typing import Optional

VALID_ROLES = {"CITIZEN", "DRIVER", "ADMIN"}

class UserRegister(BaseModel):
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=6, max_length=100)
    name: str = Field(..., min_length=2, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v

class AdminCreateUser(BaseModel):
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(..., max_length=50)
    name: str = Field(..., min_length=2, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        upper = v.upper()
        if upper not in VALID_ROLES:
            raise ValueError(f"Role must be one of {VALID_ROLES}")
        return upper

class ReportIssueValidation(BaseModel):
    zone: str = Field(..., min_length=1, max_length=100)
    area: str = Field(..., min_length=1, max_length=100)
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    waste_type: Optional[str] = Field(default="General", max_length=50)
    severity_level: Optional[str] = Field(default="MEDIUM", max_length=20)

class CompletePickupValidation(BaseModel):
    complaint_id: int = Field(..., gt=0)
