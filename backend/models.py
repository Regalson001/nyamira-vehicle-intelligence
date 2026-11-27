import re
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum as SAEnum
from pydantic import BaseModel, Field, field_validator
from database import Base

KENYAN_PLATE_REGEX = re.compile(r"^(?:K[A-Z]{2}\s?\d{3}[A-Z]|GK\s?\d{3}[A-Z]|CD\s?\d{2,3}[A-Z]?)$")


class DirectionEnum(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"


class VehicleCategoryEnum(str, Enum):
    MATATU_PSV = "Matatu/PSV"
    CARGO_AGRO = "Cargo/Agro-Freight"
    PRIVATE = "Private"
    DELIVERY_VAN = "Delivery Van"
    GOVERNMENT = "Government"


class GateCorridorEnum(str, Enum):
    KISII_NYAMIRA = "Kisii–Nyamira Road"
    SOTIK_NYAMIRA = "Sotik–Nyamira Road"
    KEBIRIGO_IKONGE = "Kebirigo–Ikonge Road"
    TOWN_HOSPITAL_JCT = "Nyamira Town Center / Hospital Junction"


class CaptureSourceEnum(str, Enum):
    ANPR = "ANPR"
    MANUAL = "MANUAL"
    SIMULATOR = "SIMULATOR"


class VehicleMovement(Base):
    """SQLAlchemy ORM model for every vehicle gate entry/exit event in Nyamira town."""
    __tablename__ = "vehicle_movements"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String(20), index=True, nullable=False)
    direction = Column(SAEnum(DirectionEnum), index=True, nullable=False)
    corridor = Column(SAEnum(GateCorridorEnum), index=True, nullable=False)
    vehicle_category = Column(SAEnum(VehicleCategoryEnum), index=True, nullable=False)
    trip_purpose = Column(String(120), nullable=False)
    source = Column(SAEnum(CaptureSourceEnum), default=CaptureSourceEnum.MANUAL, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)

    # Pairing & analytics fields computed automatically on ingestion
    paired_entry_id = Column(Integer, nullable=True)
    dwell_minutes = Column(Float, nullable=True)
    is_currently_inside = Column(Boolean, default=False, index=True)
    anomaly_flag = Column(String(200), nullable=True)


# --- Pydantic Schemas ---

class MovementCreate(BaseModel):
    plate_number: str = Field(..., min_length=5, max_length=15, examples=["KDA 123A"])
    direction: DirectionEnum
    corridor: GateCorridorEnum
    vehicle_category: VehicleCategoryEnum
    trip_purpose: str = Field(default="General Transit", min_length=2, max_length=120)
    source: CaptureSourceEnum = CaptureSourceEnum.MANUAL
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    timestamp: Optional[datetime] = None

    @field_validator("plate_number")
    @classmethod
    def validate_and_normalize_plate(cls, v: str) -> str:
        cleaned = re.sub(r"\s+", " ", v.strip().upper())
        # Insert space between prefix letters and digits if user wrote e.g. KDA123A
        match_compact = re.match(r"^([A-Z]{2,3})(\d{2,3})([A-Z]?)$", cleaned.replace(" ", ""))
        if match_compact:
            p1, p2, p3 = match_compact.groups()
            cleaned = f"{p1} {p2}{p3}"
        if not KENYAN_PLATE_REGEX.match(cleaned):
            raise ValueError(
                "Invalid Kenyan registration format. Expected formats like 'KDA 123A', 'KCA 456B', or 'GK 102B'."
            )
        return cleaned


class MovementResponse(BaseModel):
    id: int
    plate_number: str
    direction: DirectionEnum
    corridor: GateCorridorEnum
    vehicle_category: VehicleCategoryEnum
    trip_purpose: str
    source: CaptureSourceEnum
    latitude: float
    longitude: float
    timestamp: datetime
    paired_entry_id: Optional[int] = None
    dwell_minutes: Optional[float] = None
    is_currently_inside: bool
    anomaly_flag: Optional[str] = None

    class Config:
        from_attributes = True


class SimulateRequest(BaseModel):
    count: int = Field(default=8, ge=1, le=50)
