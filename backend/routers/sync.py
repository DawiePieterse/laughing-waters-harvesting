from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, SQLModel, select

from db import get_own_supplier_id, get_session
from models import HarvestRecord, Lot, LotStatus

router = APIRouter(prefix="/api/sync", tags=["sync"])


class HarvestRecordIn(SQLModel):
    uuid: str
    timestamp: datetime
    worker_id: Optional[str] = None
    block_id: Optional[str] = None
    weight_kg: float
    deduction_kg: float = 0.0
    device_id: Optional[str] = None
    team_id: Optional[str] = None
    notes: str = ""
    slip_number: Optional[str] = None  # which lot (picking slip) this crate belongs to, if any


class HarvestSyncBatch(SQLModel):
    records: list[HarvestRecordIn]


def _resolve_lot_id(session: Session, slip_number: Optional[str], device_id, team_id, timestamp) -> Optional[int]:
    if not slip_number:
        return None
    lot = session.exec(select(Lot).where(Lot.slip_number == slip_number)).first()
    if lot:
        return lot.id
    # Field device hasn't dispatched the slip yet (crate saved before "Send
    # Picking Slip" was tapped) - create a placeholder lot so the crate has
    # somewhere to attach; totals get filled in when the slip is dispatched.
    # Field devices only ever capture the farm's own fruit.
    lot = Lot(slip_number=slip_number, timestamp=timestamp, device_id=device_id,
              team_id=team_id, status=LotStatus.created, supplier_id=get_own_supplier_id(session))
    session.add(lot)
    session.commit()
    session.refresh(lot)
    return lot.id


@router.post("/harvest")
def sync_harvest(batch: HarvestSyncBatch, session: Session = Depends(get_session)):
    """Idempotent upsert by client-generated uuid - safe for a field device
    to retry the same batch after regaining mobile signal."""
    accepted = 0
    for r in batch.records:
        existing = session.get(HarvestRecord, r.uuid)
        lot_id = _resolve_lot_id(session, r.slip_number, r.device_id, r.team_id, r.timestamp)
        record = HarvestRecord(
            uuid=r.uuid, timestamp=r.timestamp, worker_id=r.worker_id, block_id=r.block_id,
            weight_kg=r.weight_kg, deduction_kg=r.deduction_kg, device_id=r.device_id,
            team_id=r.team_id, lot_id=lot_id, notes=r.notes,
            synced_at=existing.synced_at if existing else datetime.now(timezone.utc),
        )
        session.merge(record)
        accepted += 1
    session.commit()
    return {"accepted": accepted}
