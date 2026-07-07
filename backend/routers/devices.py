from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select

from db import get_session
from models import Device, DeviceRole
from security import get_current_admin

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceIn(SQLModel):
    id: str
    station: str = ""
    role: DeviceRole
    team_id: Optional[str] = None
    induna: str = ""
    data_capturer: str = ""
    active: bool = True


@router.get("/{device_id}")
def get_device(device_id: str, session: Session = Depends(get_session)):
    """Called by a device on load to determine its own role/team/induna and
    lock the UI accordingly. No auth required - devices identify themselves
    by an id chosen once during on-device setup."""
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Unknown device id - check Settings > Device Setup")
    device.last_seen = datetime.now(timezone.utc)
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


@router.get("")
def list_devices(session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    return session.exec(select(Device)).all()


@router.post("")
def upsert_device(device_in: DeviceIn, session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    existing = session.get(Device, device_in.id)
    device = Device(**device_in.model_dump(), last_seen=existing.last_seen if existing else None)
    session.merge(device)
    session.commit()
    return {"ok": True}


@router.delete("/{device_id}")
def delete_device(device_id: str, session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    device = session.get(Device, device_id)
    if device:
        session.delete(device)
        session.commit()
    return {"ok": True}
