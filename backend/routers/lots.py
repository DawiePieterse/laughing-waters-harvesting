from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select

from db import get_own_supplier_id, get_session
from models import HarvestRecord, Lot, LotStatus, Supplier, SystemSetting
from timeutil import period_start_utc
from weather import fetch_weather as _fetch_weather

router = APIRouter(prefix="/api/lots", tags=["lots"])


class LotIn(SQLModel):
    """Request body schema for creating/upserting a lot."""
    slip_number: str
    timestamp: datetime
    device_id: Optional[str] = None
    team_id: Optional[str] = None
    supplier_id: Optional[int] = None
    driver: str = ""
    total_crates: int = 0
    total_kg: float = 0.0
    status: LotStatus = LotStatus.created
    whatsapp_sent: bool = False
    notes: str = ""


class ExternalLotIn(SQLModel):
    """Manual lot entry at the pack house for another farmer's fruit -
    there's no field-device dispatch step, so this goes straight into the
    in-transit list ready to be checked in like any other lot."""
    supplier_id: int
    timestamp: Optional[datetime] = None
    driver: str = ""
    total_crates: int
    total_kg: float
    notes: str = ""


def _urgency(age_minutes: float, settings: SystemSetting) -> str:
    if age_minutes >= settings.yellow_to_red_minutes:
        return "red"
    if age_minutes >= settings.green_to_yellow_minutes:
        return "yellow"
    return "green"


def _with_urgency(lot: Lot, settings: SystemSetting, suppliers: dict) -> dict:
    now = datetime.now(timezone.utc)
    ts = lot.timestamp if lot.timestamp.tzinfo else lot.timestamp.replace(tzinfo=timezone.utc)
    age_minutes = (now - ts).total_seconds() / 60
    supplier = suppliers.get(lot.supplier_id)
    return {
        **lot.model_dump(),
        "age_minutes": round(age_minutes),
        "urgency": _urgency(age_minutes, settings),
        "supplier_name": supplier.name if supplier else "",
        "is_own_farm": supplier.is_own_farm if supplier else False,
    }


def _supplier_map(session: Session) -> dict:
    return {s.id: s for s in session.exec(select(Supplier)).all()}


@router.get("/pending")
def list_pending(supplier_id: Optional[int] = None, period: Optional[str] = None,
                  session: Session = Depends(get_session)):
    """Crates already captured in the field whose picking slip hasn't been
    dispatched yet ('Send Picking Slip' not tapped). These lots exist only
    as placeholders (status=created, created on first crate sync) so their
    totals are computed live from HarvestRecord rather than stored on Lot.
    Always the farm's own fruit - other suppliers don't use field devices.

    period is optional and only applied when passed (dashboard KPI use) -
    left unfiltered by default so device screens always see every pending
    lot regardless of when picking started."""
    settings = session.exec(select(SystemSetting)).first() or SystemSetting()
    suppliers = _supplier_map(session)
    query = select(Lot).where(Lot.status == LotStatus.created)
    if supplier_id is not None:
        query = query.where(Lot.supplier_id == supplier_id)
    if period is not None:
        query = query.where(Lot.timestamp >= period_start_utc(period))
    lots = session.exec(query.order_by(Lot.timestamp.asc())).all()
    result = []
    for l in lots:
        crates = session.exec(select(HarvestRecord).where(HarvestRecord.lot_id == l.id)).all()
        if not crates:
            continue
        total_kg = sum(c.weight_kg - c.deduction_kg for c in crates)
        enriched = _with_urgency(l, settings, suppliers)
        enriched["total_crates"] = len(crates)
        enriched["total_kg"] = round(total_kg, 1)
        result.append(enriched)
    result.sort(key=lambda r: r["age_minutes"], reverse=True)
    return result


@router.get("/in-transit")
def list_in_transit(supplier_id: Optional[int] = None, period: Optional[str] = None,
                     session: Session = Depends(get_session)):
    """Landing view for the pack house app: dispatched lots not yet
    received, oldest (most urgent, red) first - own fruit and other
    suppliers' fruit together, distinguished by supplier_name.

    period is optional and only applied when passed (dashboard KPI use) -
    left unfiltered by default so the pack house gate always sees every
    truck currently on its way, regardless of when it was dispatched."""
    settings = session.exec(select(SystemSetting)).first() or SystemSetting()
    suppliers = _supplier_map(session)
    query = select(Lot).where(Lot.status == LotStatus.in_transit)
    if supplier_id is not None:
        query = query.where(Lot.supplier_id == supplier_id)
    if period is not None:
        query = query.where(Lot.timestamp >= period_start_utc(period))
    lots = session.exec(query.order_by(Lot.timestamp.asc())).all()
    enriched = [_with_urgency(l, settings, suppliers) for l in lots]
    enriched.sort(key=lambda r: r["age_minutes"], reverse=True)
    return enriched


@router.get("/received")
def list_received(period: str = "today", supplier_id: Optional[int] = None,
                   session: Session = Depends(get_session)):
    """Recently received lots for the dashboard, matching the period selector."""
    settings = session.exec(select(SystemSetting)).first() or SystemSetting()
    suppliers = _supplier_map(session)
    since = period_start_utc(period)
    # received_at is only ever set at gate check-in, so it alone defines
    # "received" - graded lots (status=processing_complete) stay in the list.
    query = (
        select(Lot)
        .where(Lot.received_at != None)  # noqa: E711
        .where(Lot.received_at >= since)
    )
    if supplier_id is not None:
        query = query.where(Lot.supplier_id == supplier_id)
    lots = session.exec(query.order_by(Lot.received_at.desc())).all()
    return [_with_urgency(l, settings, suppliers) for l in lots]


@router.get("")
def list_lots(status: Optional[str] = None, supplier_id: Optional[int] = None,
              session: Session = Depends(get_session)):
    query = select(Lot)
    if status:
        query = query.where(Lot.status == status)
    if supplier_id is not None:
        query = query.where(Lot.supplier_id == supplier_id)
    return session.exec(query.order_by(Lot.timestamp.desc())).all()


@router.get("/{lot_id}")
def get_lot(lot_id: int, session: Session = Depends(get_session)):
    lot = session.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Lot not found")
    crates = session.exec(select(HarvestRecord).where(HarvestRecord.lot_id == lot_id)).all()
    return {"lot": lot, "crates": crates}


@router.post("")
def upsert_lot(lot_in: LotIn, session: Session = Depends(get_session)):
    """Create or update a lot by slip_number (idempotent - safe to retry).
    Field devices never send supplier_id (they don't know about suppliers) -
    it's always own-farm fruit, so it's assigned automatically here."""
    existing = session.exec(select(Lot).where(Lot.slip_number == lot_in.slip_number)).first()
    data = lot_in.model_dump()
    if data.get("supplier_id") is None:
        data["supplier_id"] = get_own_supplier_id(session)
    lot = Lot(**data, id=existing.id if existing else None)

    if not existing and lot_in.status == LotStatus.in_transit:
        settings = session.exec(select(SystemSetting)).first()
        if settings and settings.gps_lat is not None and settings.gps_lon is not None:
            weather = _fetch_weather(settings.gps_lat, settings.gps_lon)
            lot.weather_temp = weather.get("temp")
            lot.weather_humidity = weather.get("humidity")
            lot.weather_condition = weather.get("condition", "")

    saved = session.merge(lot)
    session.commit()
    session.refresh(saved)
    return saved


@router.post("/external")
def create_external_lot(lot_in: ExternalLotIn, session: Session = Depends(get_session)):
    """Pack house staff logs an incoming delivery from another farmer who
    doesn't use the farm's field devices. Goes straight into the in-transit
    list, ready to be checked in through the normal receiving flow."""
    supplier = session.get(Supplier, lot_in.supplier_id)
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    timestamp = lot_in.timestamp or datetime.now(timezone.utc)
    slip_number = f"EXT-{lot_in.supplier_id}-{timestamp.strftime('%Y%m%d%H%M%S%f')}"
    lot = Lot(
        slip_number=slip_number,
        timestamp=timestamp,
        supplier_id=lot_in.supplier_id,
        driver=lot_in.driver,
        total_crates=lot_in.total_crates,
        total_kg=lot_in.total_kg,
        status=LotStatus.in_transit,
        notes=lot_in.notes,
    )
    session.add(lot)
    session.commit()
    session.refresh(lot)
    return lot
