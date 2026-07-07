from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlmodel import Session, select

from db import get_session
from excel_io import rows_to_xlsx_bytes
from models import Block, HarvestRecord, Lot, ReceivingRecord, Supplier, Team
from security import get_current_admin

router = APIRouter(prefix="/api/reports", tags=["reports"])
XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(headers, rows, sheet_title, filename):
    data = rows_to_xlsx_bytes(headers, rows, sheet_title)
    return Response(content=data, media_type=XLSX_MEDIA,
                     headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _day_bounds(day: date):
    return datetime.combine(day, time.min), datetime.combine(day, time.max)


@router.get("/daily-harvest")
def daily_harvest_report(day: date = Query(default_factory=date.today), session: Session = Depends(get_session),
                          admin=Depends(get_current_admin)):
    start, end = _day_bounds(day)
    records = session.exec(
        select(HarvestRecord).where(HarvestRecord.timestamp >= start, HarvestRecord.timestamp <= end)
    ).all()
    blocks = {b.id: b for b in session.exec(select(Block)).all()}
    teams = {t.id: t for t in session.exec(select(Team)).all()}

    totals: dict = {}
    for r in records:
        key = (r.block_id, r.team_id)
        entry = totals.setdefault(key, {"crates": 0, "kg": 0.0})
        entry["crates"] += 1
        entry["kg"] += r.weight_kg - r.deduction_kg

    headers = ["Block", "Variety", "Team", "Induna", "Crates", "Kg"]
    rows = []
    for (block_id, team_id), data in sorted(totals.items(), key=lambda x: (x[0][0] or "", x[0][1] or "")):
        block = blocks.get(block_id)
        team = teams.get(team_id)
        rows.append([
            block_id or "", block.variety if block else "", team.name if team else team_id or "",
            team.induna if team else "", data["crates"], round(data["kg"], 1),
        ])
    return _xlsx_response(headers, rows, "Daily Harvest", f"Daily_Harvest_{day}.xlsx")


@router.get("/lot-receiving")
def lot_receiving_report(date_from: date, date_to: date, session: Session = Depends(get_session),
                          admin=Depends(get_current_admin)):
    start, end = _day_bounds(date_from)[0], _day_bounds(date_to)[1]
    lots = session.exec(
        select(Lot).where(Lot.timestamp >= start, Lot.timestamp <= end).order_by(Lot.timestamp)
    ).all()
    receiving_by_lot = {}
    for rec in session.exec(select(ReceivingRecord)).all():
        receiving_by_lot.setdefault(rec.lot_id, rec)
    suppliers = {s.id: s for s in session.exec(select(Supplier)).all()}

    headers = ["Slip Number", "Supplier", "Dispatched", "Team", "Driver", "Expected Crates", "Kg Sent",
               "Status", "Received At", "Actual Crates", "Discrepancy", "Condition", "Waste Kg",
               "Temp (°C)", "Humidity (%)", "Weather"]
    rows = []
    for lot in lots:
        rec = receiving_by_lot.get(lot.id)
        supplier = suppliers.get(lot.supplier_id)
        rows.append([
            lot.slip_number, supplier.name if supplier else "",
            lot.timestamp.isoformat(sep=" ", timespec="minutes"), lot.team_id, lot.driver,
            lot.total_crates, round(lot.total_kg, 1), lot.status.value,
            lot.received_at.isoformat(sep=" ", timespec="minutes") if lot.received_at else "",
            rec.actual_crates if rec else "", rec.discrepancy if rec else "",
            rec.condition if rec else "", rec.waste_kg if rec else "",
            lot.weather_temp if lot.weather_temp is not None else "",
            lot.weather_humidity if lot.weather_humidity is not None else "",
            lot.weather_condition or "",
        ])
    return _xlsx_response(headers, rows, "Lot & Receiving", f"Lot_Receiving_{date_from}_{date_to}.xlsx")
