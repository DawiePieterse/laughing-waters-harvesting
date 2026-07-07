from datetime import date

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import Response
from sqlmodel import Session, SQLModel, select

from db import get_session
from excel_io import parse_uploaded_table, rows_to_csv_bytes, rows_to_xlsx_bytes
from models import Block, RateSetting, RateType, SystemSetting, Team, Worker
from security import get_current_admin

router = APIRouter(prefix="/api", tags=["master-data"])


class RateSettingIn(SQLModel):
    effective_date: date
    rate_type: RateType = RateType.per_kg
    default_rate_per_kg: float = 0.0
    tier_rates_json: str = "{}"


def _export(headers, rows, fmt: str, filename: str):
    if fmt == "xlsx":
        data = rows_to_xlsx_bytes(headers, rows, filename)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    else:
        data = rows_to_csv_bytes(headers, rows)
        media = "text/csv"
        ext = "csv"
    return Response(content=data, media_type=media,
                     headers={"Content-Disposition": f'attachment; filename="{filename}.{ext}"'})


# --- Teams -------------------------------------------------------------

@router.get("/teams")
def list_teams(session: Session = Depends(get_session)):
    return session.exec(select(Team)).all()


@router.post("/teams")
def upsert_team(team: Team, session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    session.merge(team)
    session.commit()
    return {"ok": True}


@router.delete("/teams/{team_id}")
def deactivate_team(team_id: str, session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    obj = session.get(Team, team_id)
    if obj:
        obj.active = False
        session.add(obj)
        session.commit()
    return {"ok": True}


# --- Blocks --------------------------------------------------------------

@router.get("/blocks")
def list_blocks(session: Session = Depends(get_session)):
    return session.exec(select(Block)).all()


@router.post("/blocks")
def upsert_block(block: Block, session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    session.merge(block)
    session.commit()
    return {"ok": True}


@router.delete("/blocks/{block_id}")
def deactivate_block(block_id: str, session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    obj = session.get(Block, block_id)
    if obj:
        obj.active = False
        session.add(obj)
        session.commit()
    return {"ok": True}


@router.get("/blocks/export")
def export_blocks(fmt: str = Query("xlsx", pattern="^(csv|xlsx)$"), session: Session = Depends(get_session),
                   admin=Depends(get_current_admin)):
    blocks = session.exec(select(Block)).all()
    headers = ["id", "name", "variety", "trees", "hectares", "active"]
    rows = [[b.id, b.name, b.variety, b.trees, b.hectares, b.active] for b in blocks]
    return _export(headers, rows, fmt, "Blocks")


@router.post("/blocks/import")
async def import_blocks(file: UploadFile, session: Session = Depends(get_session),
                         admin=Depends(get_current_admin)):
    records = await parse_uploaded_table(file)
    count = 0
    for r in records:
        if not r.get("id"):
            continue
        active_raw = r.get("active", True)
        active = str(active_raw).strip().lower() not in ("false", "0", "no")
        session.merge(Block(
            id=str(r["id"]).strip(),
            name=r.get("name") or "",
            variety=r.get("variety") or "",
            trees=int(r.get("trees") or 0),
            hectares=float(r.get("hectares") or 0),
            active=active,
        ))
        count += 1
    session.commit()
    return {"imported": count}


# --- Workers ---------------------------------------------------------------

@router.get("/workers")
def list_workers(session: Session = Depends(get_session)):
    return session.exec(select(Worker)).all()


@router.post("/workers")
def upsert_worker(worker: Worker, session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    if worker.first_name or worker.last_name:
        worker.name = f"{worker.first_name} {worker.last_name}".strip()
    elif not worker.name:
        worker.name = worker.id
    session.merge(worker)
    session.commit()
    return {"ok": True}


@router.delete("/workers/{worker_id}")
def deactivate_worker(worker_id: str, session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    obj = session.get(Worker, worker_id)
    if obj:
        obj.active = False
        session.add(obj)
        session.commit()
    return {"ok": True}


@router.get("/workers/export")
def export_workers(fmt: str = Query("xlsx", pattern="^(csv|xlsx)$"), session: Session = Depends(get_session),
                    admin=Depends(get_current_admin)):
    workers = session.exec(select(Worker)).all()
    headers = ["emp_nr", "first_name", "last_name", "id_number", "bank", "account", "whatsapp_number", "active"]
    rows = [[w.id, w.first_name, w.last_name, w.id_number, w.bank, w.account, w.whatsapp_number, w.active]
            for w in workers]
    return _export(headers, rows, fmt, "Workers")


@router.post("/workers/import")
async def import_workers(file: UploadFile, session: Session = Depends(get_session),
                          admin=Depends(get_current_admin)):
    records = await parse_uploaded_table(file)
    count = 0
    for r in records:
        emp_nr = r.get("emp_nr") or r.get("id") or r.get("Emp Nr") or r.get("emp nr")
        if not emp_nr:
            continue
        active_raw = r.get("active", True)
        active = str(active_raw).strip().lower() not in ("false", "0", "no")
        first_name = r.get("first_name") or r.get("First Name") or ""
        last_name = r.get("last_name") or r.get("Last Name") or ""
        legacy_name = r.get("name") or r.get("Naam & Van") or ""
        if first_name or last_name:
            display_name = f"{first_name} {last_name}".strip()
        else:
            display_name = legacy_name
            parts = legacy_name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""
        session.merge(Worker(
            id=str(emp_nr).strip(),
            first_name=str(first_name).strip(),
            last_name=str(last_name).strip(),
            name=display_name,
            id_number=str(r.get("id_number") or "").strip(),
            bank=r.get("bank") or "",
            account=str(r.get("account") or ""),
            whatsapp_number=str(r.get("whatsapp_number") or ""),
            active=active,
        ))
        count += 1
    session.commit()
    return {"imported": count}


# --- Rate settings -----------------------------------------------------

@router.get("/rate-settings/current")
def current_rate_setting(session: Session = Depends(get_session)):
    setting = session.exec(select(RateSetting).order_by(RateSetting.effective_date.desc())).first()
    return setting


@router.post("/rate-settings")
def create_rate_setting(setting_in: RateSettingIn, session: Session = Depends(get_session),
                         admin=Depends(get_current_admin)):
    setting = RateSetting(**setting_in.model_dump())
    session.add(setting)
    session.commit()
    session.refresh(setting)
    return setting


# --- System settings (farm name, urgency thresholds, GPS, season) ------

@router.get("/system-settings")
def get_system_settings(session: Session = Depends(get_session)):
    return session.exec(select(SystemSetting)).first()


@router.put("/system-settings")
def update_system_settings(setting: SystemSetting, session: Session = Depends(get_session),
                            admin=Depends(get_current_admin)):
    existing = session.exec(select(SystemSetting)).first()
    setting.id = existing.id if existing else None
    session.merge(setting)
    session.commit()
    return {"ok": True}
