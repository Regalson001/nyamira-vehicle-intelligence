import random
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import Base, engine, get_db
from models import (
    VehicleMovement,
    MovementCreate,
    MovementResponse,
    SimulateRequest,
    DirectionEnum,
    VehicleCategoryEnum,
    GateCorridorEnum,
    CaptureSourceEnum,
)
from seed_data import seed_initial_movements, CORRIDOR_COORDS

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Nyamira Town Vehicle Entry, Exit & Route Intelligence API",
    version="1.0.0",
    description="Real-time gate telemetry, ENTRY/EXIT pairing, dwell analytics, and route intelligence for Nyamira town.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OVERSTAY_THRESHOLD_MINUTES = 240.0  # 4 hours


@app.on_event("startup")
def on_startup():
    db = next(get_db())
    try:
        seed_initial_movements(db)
    finally:
        db.close()


def _resolve_coordinates(corridor: GateCorridorEnum, lat: Optional[float], lng: Optional[float]) -> tuple[float, float]:
    base_lat, base_lng = CORRIDOR_COORDS[corridor]
    if lat is not None and lng is not None:
        return lat, lng
    # Slight jitter so multiple markers at a checkpoint remain distinguishable
    jitter_lat = random.uniform(-0.0025, 0.0025)
    jitter_lng = random.uniform(-0.0025, 0.0025)
    return round(base_lat + jitter_lat, 6), round(base_lng + jitter_lng, 6)


def _detect_anomalies(
    db: Session,
    plate: str,
    direction: DirectionEnum,
    event_time: datetime,
    dwell_minutes: Optional[float],
) -> Optional[str]:
    flags = []

    # 1. Late-night movement window (23:00 - 04:30)
    if event_time.hour >= 23 or event_time.hour < 4 or (event_time.hour == 4 and event_time.minute < 30):
        flags.append("Off-Peak Late-Night Transit")

    # 2. High repeat-pass frequency in last 6 hours
    window_start = event_time - timedelta(hours=6)
    recent_passes = (
        db.query(VehicleMovement)
        .filter(
            VehicleMovement.plate_number == plate,
            VehicleMovement.timestamp >= window_start,
            VehicleMovement.timestamp <= event_time,
        )
        .count()
    )
    if recent_passes >= 4:
        flags.append(f"Frequent Repeat Passes ({recent_passes + 1} in 6h)")

    # 3. Overstay on exit
    if direction == DirectionEnum.EXIT and dwell_minutes is not None and dwell_minutes > OVERSTAY_THRESHOLD_MINUTES:
        flags.append(f"Overstay Exit ({int(dwell_minutes)} mins)")

    return " | ".join(flags) if flags else None


@app.get("/api/health")
def health_check():
    return {"status": "ok", "town": "Nyamira", "coordinates": [-0.5633, 34.9358]}


@app.post("/api/events", response_model=MovementResponse, status_code=201)
def ingest_vehicle_event(payload: MovementCreate, db: Session = Depends(get_db)):
    event_time = payload.timestamp or datetime.now(timezone.utc).replace(tzinfo=None)
    lat, lng = _resolve_coordinates(payload.corridor, payload.latitude, payload.longitude)

    paired_entry_id: Optional[int] = None
    dwell_minutes: Optional[float] = None
    is_currently_inside = False

    if payload.direction == DirectionEnum.ENTRY:
        # Mark any prior open ENTRY for this plate as closed before opening a new one
        open_entries = (
            db.query(VehicleMovement)
            .filter(
                VehicleMovement.plate_number == payload.plate_number,
                VehicleMovement.direction == DirectionEnum.ENTRY,
                VehicleMovement.is_currently_inside == True,  # noqa: E712
            )
            .all()
        )
        for prev in open_entries:
            prev.is_currently_inside = False
        is_currently_inside = True

    elif payload.direction == DirectionEnum.EXIT:
        latest_entry = (
            db.query(VehicleMovement)
            .filter(
                VehicleMovement.plate_number == payload.plate_number,
                VehicleMovement.direction == DirectionEnum.ENTRY,
            )
            .order_by(desc(VehicleMovement.timestamp))
            .first()
        )
        if latest_entry:
            paired_entry_id = latest_entry.id
            latest_entry.is_currently_inside = False
            delta_mins = (event_time - latest_entry.timestamp).total_seconds() / 60.0
            dwell_minutes = round(max(delta_mins, 1.0), 1)
        is_currently_inside = False

    anomaly_flag = _detect_anomalies(db, payload.plate_number, payload.direction, event_time, dwell_minutes)

    record = VehicleMovement(
        plate_number=payload.plate_number,
        direction=payload.direction,
        corridor=payload.corridor,
        vehicle_category=payload.vehicle_category,
        trip_purpose=payload.trip_purpose,
        source=payload.source,
        latitude=lat,
        longitude=lng,
        timestamp=event_time,
        paired_entry_id=paired_entry_id,
        dwell_minutes=dwell_minutes,
        is_currently_inside=is_currently_inside,
        anomaly_flag=anomaly_flag,
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get("/api/movements", response_model=List[MovementResponse])
def list_movements(
    plate: Optional[str] = Query(default=None),
    corridor: Optional[str] = Query(default=None),
    direction: Optional[DirectionEnum] = Query(default=None),
    category: Optional[VehicleCategoryEnum] = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=150, ge=1, le=500),
    db: Session = Depends(get_db),
):
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
    query = db.query(VehicleMovement).filter(VehicleMovement.timestamp >= cutoff)

    if plate:
        query = query.filter(VehicleMovement.plate_number.ilike(f"%{plate.strip()}%"))
    if corridor:
        query = query.filter(VehicleMovement.corridor == corridor)
    if direction:
        query = query.filter(VehicleMovement.direction == direction)
    if category:
        query = query.filter(VehicleMovement.vehicle_category == category)

    return query.order_by(desc(VehicleMovement.timestamp)).limit(limit).all()


@app.get("/api/active-vehicles", response_model=List[MovementResponse])
def get_active_vehicles(db: Session = Depends(get_db)):
    """Return vehicles currently inside Nyamira town (latest open ENTRY per plate)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    records = (
        db.query(VehicleMovement)
        .filter(VehicleMovement.is_currently_inside == True)  # noqa: E712
        .order_by(desc(VehicleMovement.timestamp))
        .all()
    )

    # Refresh live dwell duration & overstay flag dynamically for active entries
    for rec in records:
        live_dwell = round(max((now - rec.timestamp).total_seconds() / 60.0, 1.0), 1)
        rec.dwell_minutes = live_dwell
        if live_dwell > OVERSTAY_THRESHOLD_MINUTES and not rec.anomaly_flag:
            rec.anomaly_flag = f"Extended Dwell ({int(live_dwell)} mins inside town)"

    return records


@app.get("/api/analytics")
def get_analytics(hours: int = Query(default=24, ge=1, le=168), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = now - timedelta(hours=hours)

    entries_today = (
        db.query(VehicleMovement)
        .filter(VehicleMovement.direction == DirectionEnum.ENTRY, VehicleMovement.timestamp >= today_start)
        .count()
    )
    exits_today = (
        db.query(VehicleMovement)
        .filter(VehicleMovement.direction == DirectionEnum.EXIT, VehicleMovement.timestamp >= today_start)
        .count()
    )

    active_vehicles = get_active_vehicles(db)
    currently_inside_count = len(active_vehicles)

    completed_dwells = [
        m.dwell_minutes
        for m in db.query(VehicleMovement)
        .filter(VehicleMovement.dwell_minutes.isnot(None), VehicleMovement.timestamp >= cutoff)
        .all()
    ]
    avg_dwell_minutes = round(sum(completed_dwells) / len(completed_dwells), 1) if completed_dwells else 0.0

    # Corridor breakdown
    corridor_stats = []
    for corr in GateCorridorEnum:
        c_entries = (
            db.query(VehicleMovement)
            .filter(VehicleMovement.corridor == corr, VehicleMovement.direction == DirectionEnum.ENTRY, VehicleMovement.timestamp >= cutoff)
            .count()
        )
        c_exits = (
            db.query(VehicleMovement)
            .filter(VehicleMovement.corridor == corr, VehicleMovement.direction == DirectionEnum.EXIT, VehicleMovement.timestamp >= cutoff)
            .count()
        )
        corridor_stats.append({
            "corridor": corr.value,
            "entries": c_entries,
            "exits": c_exits,
            "total": c_entries + c_exits,
            "coordinates": CORRIDOR_COORDS[corr],
        })

    # Category breakdown
    category_counts = {}
    for cat in VehicleCategoryEnum:
        category_counts[cat.value] = (
            db.query(VehicleMovement)
            .filter(VehicleMovement.vehicle_category == cat, VehicleMovement.timestamp >= cutoff)
            .count()
        )

    # Anomaly alerts
    flagged_movements = (
        db.query(VehicleMovement)
        .filter(VehicleMovement.anomaly_flag.isnot(None), VehicleMovement.timestamp >= cutoff)
        .order_by(desc(VehicleMovement.timestamp))
        .limit(20)
        .all()
    )

    alerts = [
        {
            "id": item.id,
            "plate_number": item.plate_number,
            "corridor": item.corridor.value,
            "direction": item.direction.value,
            "flag": item.anomaly_flag,
            "timestamp": item.timestamp.isoformat(),
        }
        for item in flagged_movements
    ]

    return {
        "kpis": {
            "entries_today": entries_today,
            "exits_today": exits_today,
            "currently_inside": currently_inside_count,
            "avg_dwell_minutes": avg_dwell_minutes,
            "active_alerts": len(alerts),
        },
        "corridor_stats": corridor_stats,
        "category_counts": category_counts,
        "alerts": alerts,
    }


@app.post("/api/simulate", response_model=List[MovementResponse], status_code=201)
def simulate_gate_traffic(req: SimulateRequest, db: Session = Depends(get_db)):
    """Simulate realistic Nyamira gate entries/exits, including pairing existing active vehicles."""
    sample_plates = [
        ("KDA 340P", VehicleCategoryEnum.MATATU_PSV, "Passenger Stage Shuttle"),
        ("KDB 119G", VehicleCategoryEnum.CARGO_AGRO, "Horticulture & Tea Transport"),
        ("KDC 774K", VehicleCategoryEnum.DELIVERY_VAN, "Retail & FMCG Distribution"),
        ("KDD 205B", VehicleCategoryEnum.PRIVATE, "Town Commute / Errands"),
        ("GK 892A", VehicleCategoryEnum.GOVERNMENT, "County Field Operations"),
        ("KDA 612R", VehicleCategoryEnum.MATATU_PSV, "Inter-Town Express"),
    ]
    corridors = list(GateCorridorEnum)
    created: List[MovementResponse] = []

    for _ in range(req.count):
        active_inside = (
            db.query(VehicleMovement)
            .filter(VehicleMovement.is_currently_inside == True)  # noqa: E712
            .all()
        )

        # 45% chance to exit a vehicle currently inside Nyamira if any exist
        if active_inside and random.random() < 0.45:
            target = random.choice(active_inside)
            payload = MovementCreate(
                plate_number=target.plate_number,
                direction=DirectionEnum.EXIT,
                corridor=random.choice(corridors),
                vehicle_category=target.vehicle_category,
                trip_purpose="Outbound Town Departure",
                source=CaptureSourceEnum.SIMULATOR,
            )
        else:
            plate, cat, purpose = random.choice(sample_plates)
            payload = MovementCreate(
                plate_number=plate,
                direction=DirectionEnum.ENTRY,
                corridor=random.choice(corridors),
                vehicle_category=cat,
                trip_purpose=purpose,
                source=CaptureSourceEnum.SIMULATOR,
            )

        created_item = ingest_vehicle_event(payload=payload, db=db)
        created.append(created_item)

    return created


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
