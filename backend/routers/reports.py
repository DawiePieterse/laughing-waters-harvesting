import os
from collections import Counter
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlmodel import Session, select

from db import DATA_DIR, get_session
from excel_io import rows_to_xlsx_bytes
from models import Block, Device, HarvestRecord, Lot, ReceivingRecord, Supplier, Team
from routers.dashboard import dashboard_summary
from routers.lots import list_in_transit, list_pending, list_received
from routers.payments import _worker_ids_for_supplier
from security import get_current_admin
from timeutil import day_bounds, local_str, to_local

router = APIRouter(prefix="/api/reports", tags=["reports"])
XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

REPORTS_DIR = os.path.join(DATA_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def _xlsx_response(headers, rows, sheet_title, filename):
    data = rows_to_xlsx_bytes(headers, rows, sheet_title)
    # Every generated report is also kept on disk in data/reports/, so it's
    # swept up by whatever backup routine already covers the data/ folder -
    # not just left in whichever browser downloaded it.
    with open(os.path.join(REPORTS_DIR, filename), "wb") as f:
        f.write(data)
    return Response(content=data, media_type=XLSX_MEDIA,
                     headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _mean(values: list, places: int):
    """Blank rather than 0 when nothing was measured - an empty cell reads as
    "not recorded", where 0 would read as a freezing morning."""
    if not values:
        return ""
    return round(sum(values) / len(values), places) if places else round(sum(values) / len(values))


@router.get("/daily-harvest")
def daily_harvest_report(day: date = Query(default_factory=date.today), supplier_id: Optional[int] = None,
                          session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    start, end = day_bounds(day)
    query = select(HarvestRecord).where(HarvestRecord.timestamp >= start, HarvestRecord.timestamp <= end)
    worker_ids = _worker_ids_for_supplier(session, supplier_id)
    if worker_ids is not None:
        query = query.where(HarvestRecord.worker_id.in_(worker_ids))
    records = session.exec(query).all()
    blocks = {b.id: b for b in session.exec(select(Block)).all()}
    teams = {t.id: t for t in session.exec(select(Team)).all()}

    totals: dict = {}
    for r in records:
        key = (r.block_id, r.team_id)
        entry = totals.setdefault(key, {"crates": 0, "kg": 0.0, "temps": [], "humidity": [],
                                         "conditions": Counter()})
        entry["crates"] += 1
        entry["kg"] += r.weight_kg - r.deduction_kg
        # Weather is stamped per crate at check-in and is absent on crates
        # captured before that existed, or when the lookup failed - so each
        # measure is averaged over whichever crates actually carry it.
        if r.weather_temp is not None:
            entry["temps"].append(r.weather_temp)
        if r.weather_humidity is not None:
            entry["humidity"].append(r.weather_humidity)
        if r.weather_condition:
            entry["conditions"][r.weather_condition] += 1

    headers = ["Date", "Block", "Variety", "Team", "Induna", "Crates", "Kg",
               "Avg Temp (°C)", "Avg Humidity (%)", "Conditions"]
    rows = []
    for (block_id, team_id), data in sorted(totals.items(), key=lambda x: (x[0][0] or "", x[0][1] or "")):
        block = blocks.get(block_id)
        team = teams.get(team_id)
        rows.append([
            day.isoformat(), block_id or "", block.variety if block else "", team.name if team else team_id or "",
            team.induna if team else "", data["crates"], round(data["kg"], 1),
            _mean(data["temps"], 1), _mean(data["humidity"], 0),
            # Whatever it was doing for most of the picking, so a block picked
            # through a passing shower doesn't read as a clear morning.
            data["conditions"].most_common(1)[0][0] if data["conditions"] else "",
        ])
    return _xlsx_response(headers, rows, "Daily Harvest", f"Daily_Harvest_{day}.xlsx")


@router.get("/lot-receiving")
def lot_receiving_report(date_from: date, date_to: date, supplier_id: Optional[int] = None,
                          session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    start, end = day_bounds(date_from, date_to)
    query = select(Lot).where(Lot.timestamp >= start, Lot.timestamp <= end)
    if supplier_id is not None:
        query = query.where(Lot.supplier_id == supplier_id)
    lots = session.exec(query.order_by(Lot.timestamp)).all()
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
            local_str(lot.timestamp), lot.team_id, lot.driver,
            lot.total_crates, round(lot.total_kg, 1), lot.status.value,
            local_str(lot.received_at),
            rec.actual_crates if rec else "", rec.discrepancy if rec else "",
            rec.condition if rec else "", rec.waste_kg if rec else "",
            lot.weather_temp if lot.weather_temp is not None else "",
            lot.weather_humidity if lot.weather_humidity is not None else "",
            lot.weather_condition or "",
        ])
    return _xlsx_response(headers, rows, "Lot & Receiving", f"Lot_Receiving_{date_from}_{date_to}.xlsx")


@router.get("/picking-notes")
def picking_notes_report(date_from: date, date_to: date, supplier_id: Optional[int] = None,
                          session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    start, end = day_bounds(date_from, date_to)
    query = select(Lot).where(Lot.timestamp >= start, Lot.timestamp <= end)
    if supplier_id is not None:
        query = query.where(Lot.supplier_id == supplier_id)
    lots = session.exec(query.order_by(Lot.timestamp)).all()
    receiving_by_lot = {}
    for rec in session.exec(select(ReceivingRecord)).all():
        receiving_by_lot.setdefault(rec.lot_id, rec)
    suppliers = {s.id: s for s in session.exec(select(Supplier)).all()}
    teams = {t.id: t for t in session.exec(select(Team)).all()}

    headers = ["Slip Number", "Date", "Time", "Block", "Team", "Crates Sent", "Crates Received",
               "Total Kg", "Driver", "Supplier", "Condition", "Notes", "Received By",
               "Weather", "Temp (°C)", "Humidity (%)"]
    entries = []
    for lot in lots:
        rec = receiving_by_lot.get(lot.id)
        supplier = suppliers.get(lot.supplier_id)
        team = teams.get(lot.team_id)
        # A lot has no block field of its own - it's stamped per crate, so the
        # slip's block(s) are whatever its HarvestRecords were captured against.
        crates = session.exec(select(HarvestRecord).where(HarvestRecord.lot_id == lot.id)).all()
        blocks = sorted({c.block_id for c in crates if c.block_id})
        local_ts = to_local(lot.timestamp)
        team_name = team.name if team else lot.team_id or ""
        entries.append((
            local_ts.date() if local_ts else date.min, team_name, local_ts,
            [
                lot.slip_number, local_ts.strftime("%Y-%m-%d") if local_ts else "",
                local_ts.strftime("%H:%M") if local_ts else "", ", ".join(blocks),
                team_name, lot.total_crates,
                rec.actual_crates if rec else "", round(lot.total_kg, 1), lot.driver,
                supplier.name if supplier else "",
                rec.condition if rec else "", rec.notes if rec else "", rec.received_by if rec else "",
                lot.weather_condition or "",
                lot.weather_temp if lot.weather_temp is not None else "",
                lot.weather_humidity if lot.weather_humidity is not None else "",
            ],
        ))
    entries.sort(key=lambda e: (e[0], e[1], e[2]))
    rows = [e[3] for e in entries]
    return _xlsx_response(headers, rows, "Picking Notes", f"Picking_Notes_{date_from}_{date_to}.xlsx")


@router.get("/team-picking-list")
def team_picking_list_report(date_from: date, date_to: date, supplier_id: Optional[int] = None,
                              session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    """Span Pluklys / Team Picking List: one row per team per day, with the
    day's blocks (kg + deductions) and dispatched lots (slip, crates, kg)
    laid out as repeating column groups - the same shape as the paper
    picking slip an induna's device prints."""
    start, end = day_bounds(date_from, date_to)

    worker_ids = _worker_ids_for_supplier(session, supplier_id)
    hr_query = select(HarvestRecord).where(HarvestRecord.timestamp >= start, HarvestRecord.timestamp <= end)
    if worker_ids is not None:
        hr_query = hr_query.where(HarvestRecord.worker_id.in_(worker_ids))
    records = session.exec(hr_query).all()

    lot_query = select(Lot).where(Lot.timestamp >= start, Lot.timestamp <= end)
    if supplier_id is not None:
        lot_query = lot_query.where(Lot.supplier_id == supplier_id)
    lots = session.exec(lot_query).all()

    teams = {t.id: t for t in session.exec(select(Team)).all()}
    blocks = {b.id: b for b in session.exec(select(Block)).all()}
    devices = {d.id: d for d in session.exec(select(Device)).all()}

    groups: dict = {}

    def _group(team_id, day):
        return groups.setdefault((team_id, day), {
            "devices": Counter(), "workers": set(), "blocks": {}, "lots": [],
        })

    for r in records:
        local_ts = to_local(r.timestamp)
        day = local_ts.date() if local_ts else date.min
        g = _group(r.team_id, day)
        if r.device_id:
            g["devices"][r.device_id] += 1
        if r.worker_id:
            g["workers"].add(r.worker_id)
        entry = g["blocks"].setdefault(r.block_id, {"kg": 0.0, "deductions": 0.0})
        entry["kg"] += r.weight_kg
        entry["deductions"] += r.deduction_kg

    for lot in lots:
        local_ts = to_local(lot.timestamp)
        day = local_ts.date() if local_ts else date.min
        g = _group(lot.team_id, day)
        if not g["devices"] and lot.device_id:
            g["devices"][lot.device_id] += 1
        g["lots"].append((local_ts, lot))

    max_blocks = max((len(g["blocks"]) for g in groups.values()), default=0)
    max_lots = max((len(g["lots"]) for g in groups.values()), default=0)

    headers = ["Field Station", "Data Capturer", "Team", "Induna", "Date", "Workers"]
    for i in range(1, max_blocks + 1):
        headers += [f"Block {i} Name", f"Block {i} Total Kg", f"Block {i} Deductions"]
    for i in range(1, max_lots + 1):
        headers += [f"Lot {i} Slip Number", f"Lot {i} Date", f"Lot {i} Time", f"Lot {i} Crates", f"Lot {i} Total Kg"]

    rows = []
    for (team_id, day), g in sorted(groups.items(), key=lambda kv: (kv[0][1], teams.get(kv[0][0]).name if teams.get(kv[0][0]) else kv[0][0] or "")):
        team = teams.get(team_id)
        device = devices.get(g["devices"].most_common(1)[0][0]) if g["devices"] else None
        row = [
            device.station if device else "", device.data_capturer if device else "",
            team.name if team else team_id or "", team.induna if team else "",
            day.isoformat() if day != date.min else "", len(g["workers"]),
        ]
        for block_id in sorted(g["blocks"], key=lambda x: x or ""):
            block = blocks.get(block_id)
            b = g["blocks"][block_id]
            row += [block.name or block_id if block else (block_id or ""), round(b["kg"], 1), round(b["deductions"], 1)]
        row += [""] * (3 * (max_blocks - len(g["blocks"])))
        for local_ts, lot in sorted(g["lots"], key=lambda x: x[1].timestamp):
            row += [
                lot.slip_number, local_ts.strftime("%Y-%m-%d") if local_ts else "",
                local_ts.strftime("%H:%M") if local_ts else "", lot.total_crates, round(lot.total_kg, 1),
            ]
        row += [""] * (5 * (max_lots - len(g["lots"])))
        rows.append(row)

    return _xlsx_response(headers, rows, "Team Picking List", f"Team_Picking_List_{date_from}_{date_to}.xlsx")


def _lot_rows(lots_data: list) -> list:
    return [[
        l["slip_number"], l["supplier_name"], l["team_id"] or "", l["driver"], l["total_crates"], l["total_kg"],
        l["age_minutes"],
    ] for l in lots_data]


@router.get("/harvesting-list")
def harvesting_list_report(period_start: date, period_end: date, supplier_id: Optional[int] = None,
                            session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    lots_data = list_pending(supplier_id=supplier_id, period_start=period_start, period_end=period_end,
                              session=session)
    headers = ["Slip Number", "Farm/Supplier", "Team", "Driver", "Crates", "Kg", "Age (min)"]
    return _xlsx_response(headers, _lot_rows(lots_data), "Harvesting",
                           f"Harvesting_{period_start}_{period_end}.xlsx")


@router.get("/in-transit-list")
def in_transit_list_report(period_start: date, period_end: date, supplier_id: Optional[int] = None,
                            session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    lots_data = list_in_transit(supplier_id=supplier_id, period_start=period_start, period_end=period_end,
                                 session=session)
    headers = ["Slip Number", "Farm/Supplier", "Team", "Driver", "Crates", "Kg", "Age (min)"]
    return _xlsx_response(headers, _lot_rows(lots_data), "In Transit",
                           f"In_Transit_{period_start}_{period_end}.xlsx")


@router.get("/received-list")
def received_list_report(period_start: date, period_end: date, supplier_id: Optional[int] = None,
                          session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    lots_data = list_received(period_start=period_start, period_end=period_end, supplier_id=supplier_id,
                               session=session)
    headers = ["Slip Number", "Farm/Supplier", "Team", "Driver", "Crates", "Kg", "Received At"]
    rows = [[
        l["slip_number"], l["supplier_name"], l["team_id"] or "", l["driver"], l["total_crates"], l["total_kg"],
        local_str(l["received_at"]),
    ] for l in lots_data]
    return _xlsx_response(headers, rows, "Received", f"Received_{period_start}_{period_end}.xlsx")


@router.get("/worker-harvest")
def worker_harvest_report(period_start: date, period_end: date, supplier_id: Optional[int] = None,
                           session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    summary = dashboard_summary(period_start, period_end, supplier_id, session, admin)
    headers = ["Emp Nr", "Name", "Farm/Supplier", "Crates", "Kg", "Amount Due", "Avg Kg/Crate"]
    rows = [[
        w["worker_id"], w["name"], w["supplier_name"], w["crates"], w["total_kg"], w["amount_due"],
        w["avg_kg_crate"],
    ] for w in summary["workers"]]
    return _xlsx_response(headers, rows, "Worker Harvest", f"Worker_Harvest_{period_start}_{period_end}.xlsx")


@router.get("/block-harvest")
def block_harvest_report(period_start: date, period_end: date, supplier_id: Optional[int] = None,
                          session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    summary = dashboard_summary(period_start, period_end, supplier_id, session, admin)
    headers = ["Block", "Crates", "Kg", "Avg Kg/Crate", "Avg Kg/Tree", "Avg Kg/Ha"]
    rows = [[
        b["name"], b["crates"], b["total_kg"], b["avg_kg_crate"],
        b["avg_kg_tree"] if b["avg_kg_tree"] is not None else "",
        b["avg_kg_hectare"] if b["avg_kg_hectare"] is not None else "",
    ] for b in summary["blocks"]]
    return _xlsx_response(headers, rows, "Block Harvest", f"Block_Harvest_{period_start}_{period_end}.xlsx")
