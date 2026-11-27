from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models import (
    VehicleMovement,
    DirectionEnum,
    VehicleCategoryEnum,
    GateCorridorEnum,
    CaptureSourceEnum,
)

# Real-world approximate coordinates around Nyamira Town & key approaches
CORRIDOR_COORDS = {
    GateCorridorEnum.KISII_NYAMIRA: (-0.5715, 34.9220),
    GateCorridorEnum.SOTIK_NYAMIRA: (-0.5680, 34.9560),
    GateCorridorEnum.KEBIRIGO_IKONGE: (-0.5850, 34.9460),
    GateCorridorEnum.TOWN_HOSPITAL_JCT: (-0.5633, 34.9358),
}


def seed_initial_movements(db: Session) -> None:
    """Populate realistic Nyamira town entry/exit records if the table is empty."""
    if db.query(VehicleMovement).count() > 0:
        return

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    sample_records = [
        # Completed ENTRY -> EXIT pair (dwell = 75 mins)
        VehicleMovement(
            plate_number="KDA 214M",
            direction=DirectionEnum.ENTRY,
            corridor=GateCorridorEnum.KISII_NYAMIRA,
            vehicle_category=VehicleCategoryEnum.MATATU_PSV,
            trip_purpose="Passenger Stage Drop-off",
            source=CaptureSourceEnum.ANPR,
            latitude=-0.5715,
            longitude=34.9220,
            timestamp=now - timedelta(hours=3, minutes=10),
            is_currently_inside=False,
        ),
        VehicleMovement(
            plate_number="KDA 214M",
            direction=DirectionEnum.EXIT,
            corridor=GateCorridorEnum.SOTIK_NYAMIRA,
            vehicle_category=VehicleCategoryEnum.MATATU_PSV,
            trip_purpose="Outbound Route to Sotik",
            source=CaptureSourceEnum.ANPR,
            latitude=-0.5680,
            longitude=34.9560,
            timestamp=now - timedelta(hours=1, minutes=55),
            paired_entry_id=1,
            dwell_minutes=75.0,
            is_currently_inside=False,
        ),
        # Completed ENTRY -> EXIT pair (dwell = 140 mins)
        VehicleMovement(
            plate_number="KDB 809F",
            direction=DirectionEnum.ENTRY,
            corridor=GateCorridorEnum.KEBIRIGO_IKONGE,
            vehicle_category=VehicleCategoryEnum.CARGO_AGRO,
            trip_purpose="Tea & Avocado Produce Delivery",
            source=CaptureSourceEnum.MANUAL,
            latitude=-0.5850,
            longitude=34.9460,
            timestamp=now - timedelta(hours=4, minutes=30),
            is_currently_inside=False,
        ),
        VehicleMovement(
            plate_number="KDB 809F",
            direction=DirectionEnum.EXIT,
            corridor=GateCorridorEnum.KISII_NYAMIRA,
            vehicle_category=VehicleCategoryEnum.CARGO_AGRO,
            trip_purpose="Outbound Toward Kisii Market",
            source=CaptureSourceEnum.ANPR,
            latitude=-0.5715,
            longitude=34.9220,
            timestamp=now - timedelta(hours=2, minutes=10),
            paired_entry_id=3,
            dwell_minutes=140.0,
            is_currently_inside=False,
        ),
        # Vehicles currently inside Nyamira town
        VehicleMovement(
            plate_number="KDC 512T",
            direction=DirectionEnum.ENTRY,
            corridor=GateCorridorEnum.KISII_NYAMIRA,
            vehicle_category=VehicleCategoryEnum.DELIVERY_VAN,
            trip_purpose="Pharmacy & Agro-Vet Supply",
            source=CaptureSourceEnum.ANPR,
            latitude=-0.5715,
            longitude=34.9220,
            timestamp=now - timedelta(minutes=48),
            is_currently_inside=True,
        ),
        VehicleMovement(
            plate_number="GK 418C",
            direction=DirectionEnum.ENTRY,
            corridor=GateCorridorEnum.TOWN_HOSPITAL_JCT,
            vehicle_category=VehicleCategoryEnum.GOVERNMENT,
            trip_purpose="County Health & Referral Inspection",
            source=CaptureSourceEnum.MANUAL,
            latitude=-0.5633,
            longitude=34.9358,
            timestamp=now - timedelta(minutes=92),
            is_currently_inside=True,
        ),
        # Overstay anomaly (> 4 hours inside town)
        VehicleMovement(
            plate_number="KDD 901L",
            direction=DirectionEnum.ENTRY,
            corridor=GateCorridorEnum.SOTIK_NYAMIRA,
            vehicle_category=VehicleCategoryEnum.PRIVATE,
            trip_purpose="Town Commercial & Banking Stop",
            source=CaptureSourceEnum.ANPR,
            latitude=-0.5680,
            longitude=34.9560,
            timestamp=now - timedelta(hours=5, minutes=20),
            is_currently_inside=True,
            anomaly_flag="Extended Dwell (>240 mins inside town)",
        ),
    ]

    db.add_all(sample_records)
    db.commit()
