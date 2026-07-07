import json
from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlmodel import Session, select

from db import get_session
from excel_io import rows_to_xlsx_bytes
from models import HarvestRecord, Payment, PaymentStatus, RateSetting, RateType, Worker
from security import get_current_admin

router = APIRouter(prefix="/api/payments", tags=["payments"])


def _tier_rate_for_weight(weight_kg: float, tiers: dict[str, float]) -> float:
    """Classify a crate into the nearest configured size tier (largest tier
    key <= the crate's weight, else the smallest tier) and return its rate.
    Tiers mirror the farm's real per-crate-size wage categories (e.g. 1 /
    1.5 / 2 kg classes) rather than a flat rate per kg."""
    if not tiers:
        return 0.0
    keys = sorted(float(k) for k in tiers)
    chosen = keys[0]
    for k in keys:
        if weight_kg >= k:
            chosen = k
    return tiers[str(chosen) if str(chosen) in tiers else next(k for k in tiers if float(k) == chosen)]


def _worker_totals(session: Session, period_start: date, period_end: date):
    start_dt = datetime.combine(period_start, time.min)
    end_dt = datetime.combine(period_end, time.max)
    records = session.exec(
        select(HarvestRecord).where(HarvestRecord.timestamp >= start_dt, HarvestRecord.timestamp <= end_dt)
    ).all()
    setting = session.exec(select(RateSetting).order_by(RateSetting.effective_date.desc())).first()
    tiers = json.loads(setting.tier_rates_json) if setting else {}

    totals: dict[str, dict] = {}
    for r in records:
        if not r.worker_id:
            continue
        net_kg = r.weight_kg - r.deduction_kg
        entry = totals.setdefault(r.worker_id, {"total_kg": 0.0, "amount": 0.0})
        entry["total_kg"] += net_kg
        if setting and setting.rate_type == RateType.per_crate_tier:
            entry["amount"] += _tier_rate_for_weight(net_kg, tiers)
        else:
            entry["amount"] += net_kg * (setting.default_rate_per_kg if setting else 0.0)
    return totals, setting


@router.post("/calculate")
def calculate_payments(period_start: date, period_end: date, session: Session = Depends(get_session),
                        admin=Depends(get_current_admin)):
    totals, setting = _worker_totals(session, period_start, period_end)
    rate_applied = setting.default_rate_per_kg if setting else 0.0
    results = []
    for worker_id, data in totals.items():
        existing = session.exec(
            select(Payment).where(Payment.worker_id == worker_id, Payment.period_start == period_start,
                                   Payment.period_end == period_end)
        ).first()
        payment = existing or Payment(worker_id=worker_id, period_start=period_start, period_end=period_end)
        payment.total_kg = round(data["total_kg"], 2)
        payment.rate_applied = rate_applied
        payment.amount_due = round(data["amount"], 2)
        if payment.status != PaymentStatus.paid:
            payment.status = PaymentStatus.pending if payment.amount_paid == 0 else PaymentStatus.partial
        session.add(payment)
        results.append(payment)
    session.commit()
    for p in results:
        session.refresh(p)
    return results


@router.get("")
def list_payments(period_start: Optional[date] = None, period_end: Optional[date] = None,
                   session: Session = Depends(get_session)):
    query = select(Payment)
    if period_start:
        query = query.where(Payment.period_start == period_start)
    if period_end:
        query = query.where(Payment.period_end == period_end)
    return session.exec(query).all()


@router.patch("/{payment_id}")
def update_payment(payment_id: int, amount_paid: float, status: PaymentStatus,
                    session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    payment = session.get(Payment, payment_id)
    if not payment:
        return {"error": "not found"}
    payment.amount_paid = amount_paid
    payment.status = status
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return payment


@router.get("/export")
def export_payments(period_start: date, period_end: date, fmt: str = Query("xlsx", pattern="^(csv|xlsx)$"),
                     session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    payments = session.exec(
        select(Payment).where(Payment.period_start == period_start, Payment.period_end == period_end)
    ).all()
    workers = {w.id: w for w in session.exec(select(Worker)).all()}

    headers = ["Emp Nr", "Naam & Van", "Total Kg", "Rate", "Amount Due", "Amount Paid", "Bank", "Account", "Status"]
    rows = []
    for p in payments:
        w = workers.get(p.worker_id)
        rows.append([
            p.worker_id, w.name if w else "", p.total_kg, p.rate_applied, p.amount_due,
            p.amount_paid, w.bank if w else "", w.account if w else "", p.status.value,
        ])

    if fmt == "xlsx":
        data = rows_to_xlsx_bytes(headers, rows, "Payments")
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    else:
        from excel_io import rows_to_csv_bytes
        data = rows_to_csv_bytes(headers, rows)
        media = "text/csv"
        ext = "csv"
    filename = f"Wages_{period_start}_{period_end}.{ext}"
    return Response(content=data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
