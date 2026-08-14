from collections import defaultdict
from datetime import date, timedelta
from types import SimpleNamespace

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from db import get_session
from models import SystemSetting, WeatherHistory
from routers.analysis import build_analysis_summary
from security import get_current_admin
from weather import farm_coords, fetch_forecast_hourly, parse_hourly_rows, sync_recent_weather

router = APIRouter(prefix="/api/risk", tags=["risk"])

# ---------------------------------------------------------------------------
# Critical Season Risk Indicator: a transparent 0-100 score built from the
# weather drivers that best explained this farm's own 2020-2025 harvest
# variation - NOT a generic agronomy model. See build_risk_summary()'s
# docstring for the correlation study behind this list and its caveats.
#
# Each driver is measured over a fixed calendar window (same every year,
# regardless of when picking actually starts) and contributes up to 25
# risk points, scaled between the best and worst value seen across the six
# 2020-2025 seasons - so "25/25" means "as bad as the worst of the last six
# years for this factor", not an absolute agronomic threshold.
#
# build_harvest_forecast() (further below) reuses this exact same driver
# list and scoring to turn the current season's still-open windows into
# three kg predictions (Favorable/Expected/Unfavorable) instead of a single
# risk score - see that function's docstring for how.
# ---------------------------------------------------------------------------
DRIVERS = [
    {
        "key": "winter_chill", "label": "Winter Chill Accumulation",
        "window_md": ((5, 1), (7, 31)), "window_label": "1 May - 31 Jul",
        "field": "temp_c", "agg": "count_lt", "threshold": 10,
        "unit": "hours below 10°C", "direction": "lower_is_worse",
        "why": "Lychee flowering is induced by sustained winter cold. A mild "
               "winter here has meant fewer, weaker flowers and a smaller crop.",
    },
    {
        "key": "flowering_rain", "label": "Flowering-Period Rain Days",
        "window_md": ((8, 1), (9, 15)), "window_label": "1 Aug - 15 Sep",
        "field": "precipitation_mm", "agg": "count_days_gt", "threshold": 1,
        "unit": "days with >1mm rain", "direction": "lower_is_worse",
        "why": "Seasons with more rain days during flowering produced bigger "
               "harvests here - dry spells in this window line up with the "
               "hot, low-humidity stress that drives flower and fruitlet drop.",
    },
    {
        "key": "heat_stress", "label": "Fruit Development Heat Stress",
        "window_md": ((9, 16), (11, 15)), "window_label": "16 Sep - 15 Nov",
        "field": "temp_c", "agg": "count_gt", "threshold": 35,
        "unit": "hours above 35°C", "direction": "higher_is_worse",
        "why": "Extreme heat while fruit is sizing causes fruit drop and sunburn.",
    },
    {
        "key": "fruit_humidity", "label": "Fruit Development Humidity",
        "window_md": ((9, 16), (11, 15)), "window_label": "16 Sep - 15 Nov",
        "field": "humidity_pct", "agg": "mean",
        "unit": "% mean relative humidity", "direction": "lower_is_worse",
        "why": "Low humidity while fruit is sizing coincided with smaller "
               "harvests here, consistent with added water stress on the crop.",
    },
]

_BANDS = [(25, "Low"), (50, "Moderate"), (75, "Elevated"), (101, "High")]

# How far ahead a real Open-Meteo forecast reaches - the free forecast API
# tops out at 16 days. Anything in a driver's window beyond this still gets
# blended into the harvest forecast, just from the historical scenario
# range rather than an actual forecast - see _segment_days().
FORECAST_HORIZON_DAYS = 16


def _band(score: float) -> str:
    for ceiling, name in _BANDS:
        if score < ceiling:
            return name
    return "High"


def _window_dates(year: int, window_md) -> tuple:
    (sm, sd), (em, ed) = window_md
    return date(year, sm, sd), date(year, em, ed)


def _window_status(year: int, window_md, today: date) -> str:
    start, end = _window_dates(year, window_md)
    if today < start:
        return "pending"
    if today > end:
        return "final"
    return "in_progress"


def _date_range_rows(by_date: dict, start: date, end: date) -> list:
    rows = []
    d = start
    while d <= end:
        rows.extend(by_date.get(d, ()))
        d += timedelta(days=1)
    return rows


def _window_rows(by_date: dict, year: int, window_md, cutoff: date = None) -> list:
    start, end = _window_dates(year, window_md)
    if cutoff is not None and cutoff < end:
        end = cutoff
    return _date_range_rows(by_date, start, end)


def _driver_value(rows: list, driver: dict):
    field = driver["field"]
    if driver["agg"] == "count_lt":
        vals = [v for v in (getattr(r, field) for r in rows) if v is not None]
        return float(sum(1 for v in vals if v < driver["threshold"])) if vals else None
    if driver["agg"] == "count_gt":
        vals = [v for v in (getattr(r, field) for r in rows) if v is not None]
        return float(sum(1 for v in vals if v > driver["threshold"])) if vals else None
    if driver["agg"] == "count_days_gt":
        days = {r.timestamp.date() for r in rows
                if getattr(r, field) is not None and getattr(r, field) > driver["threshold"]}
        any_data = any(getattr(r, field) is not None for r in rows)
        return float(len(days)) if any_data else None
    if driver["agg"] == "mean":
        vals = [v for v in (getattr(r, field) for r in rows) if v is not None]
        return sum(vals) / len(vals) if vals else None
    raise ValueError(f"unknown agg {driver['agg']}")


def _risk_points(value, hist_values: list, direction: str):
    """0-25 risk points, scaled linearly between the best and worst value
    seen across the 2020-2025 reference seasons. Clamped at both ends, so a
    value beyond any historical extreme still just reads as "as bad/good as
    the worst/best seen so far" rather than extrapolating past it."""
    if value is None or not hist_values:
        return None
    lo, hi = min(hist_values), max(hist_values)
    if hi == lo:
        return 12.5  # no variation across the reference seasons - neutral
    frac = (hi - value) / (hi - lo) if direction == "lower_is_worse" else (value - lo) / (hi - lo)
    return round(25 * max(0.0, min(1.0, frac)), 1)


def _compute_driver_state(session: Session) -> dict:
    """Shared setup behind both build_risk_summary() and
    build_harvest_forecast(): per-(driver,year) status/value against real
    WeatherHistory, and the fixed 2020-2025 reference range each driver is
    normalized against. Pulled out as its own function so the two features
    can't silently drift apart the way duplicated windowing logic would
    risk - build_risk_summary() is a thin wrapper over this."""
    settings = session.exec(select(SystemSetting)).first()
    current_year = settings.current_harvest_year if settings else date.today().year

    analysis = build_analysis_summary(session)
    historical_years = analysis["historical_years"]
    kg_by_year = {m["year"]: m["total_kg"] for m in analysis["monthly"]}
    all_years = sorted(set(historical_years) | {current_year})

    rows = session.exec(select(WeatherHistory)).all()
    by_date = defaultdict(list)
    for r in rows:
        by_date[r.timestamp.date()].append(r)

    today = date.today()

    # value/status per (driver, year)
    value_by_year = {d["key"]: {} for d in DRIVERS}
    status_by_year = {d["key"]: {} for d in DRIVERS}
    for year in all_years:
        for d in DRIVERS:
            status = _window_status(year, d["window_md"], today)
            status_by_year[d["key"]][year] = status
            if status == "pending":
                value_by_year[d["key"]][year] = None
                continue
            cutoff = today if status == "in_progress" else None
            w_rows = _window_rows(by_date, year, d["window_md"], cutoff)
            value_by_year[d["key"]][year] = _driver_value(w_rows, d)

    # Fixed 2020-2025 reference range per driver, for normalizing every
    # season (including the current one) on the same scale.
    hist_range = {
        d["key"]: [value_by_year[d["key"]][y] for y in historical_years
                    if value_by_year[d["key"]].get(y) is not None]
        for d in DRIVERS
    }

    return {
        "current_year": current_year, "historical_years": historical_years, "all_years": all_years,
        "kg_by_year": kg_by_year, "by_date": by_date, "today": today,
        "value_by_year": value_by_year, "status_by_year": status_by_year, "hist_range": hist_range,
    }


def build_risk_summary(session: Session) -> dict:
    """Critical Season Risk Indicator: a transparent 0-100 score of how this
    season's weather compares to the six 2020-2025 reference seasons on the
    four factors (see DRIVERS above) that best correlated with this farm's
    own season-total kg over that period.

    That correlation study (Pearson/Spearman over daily WeatherHistory
    aggregated into calendar windows, against HistoricalHarvest season
    totals) is a one-off analysis behind this driver list, not something
    recomputed live - with only six seasons of harvest history, re-deriving
    "best" drivers from a live, shrinking or growing sample would make the
    scoring formula itself drift season to season. Two honest caveats worth
    keeping in mind everywhere this score is shown: six seasons is too few
    for any of these correlations to be statistically significant, and this
    farm's yields also show a visible alternate-bearing pattern (a heavy
    crop tends to follow a light one) that weather alone doesn't explain.

    Each driver is scored per season (including in-progress current one) by
    _risk_points() against the fixed 2020-2025 range, and summed to 0-100.
    A component whose calendar window hasn't closed yet for the current
    season is left out of the sum (never assumed to be zero risk) - see
    "known_count" on each season entry.
    """
    state = _compute_driver_state(session)
    current_year = state["current_year"]
    all_years = state["all_years"]
    value_by_year = state["value_by_year"]
    status_by_year = state["status_by_year"]
    hist_range = state["hist_range"]

    drivers_out = [{
        "key": d["key"], "label": d["label"], "window": d["window_label"],
        "unit": d["unit"], "direction": d["direction"], "why": d["why"],
        "historical_min": round(min(hist_range[d["key"]]), 1) if hist_range[d["key"]] else None,
        "historical_max": round(max(hist_range[d["key"]]), 1) if hist_range[d["key"]] else None,
    } for d in DRIVERS]

    seasons = []
    for year in all_years:
        components = []
        known_sum = 0.0
        known_count = 0
        for d in DRIVERS:
            value = value_by_year[d["key"]][year]
            status = status_by_year[d["key"]][year]
            risk_points = None
            if status == "final" and value is not None:
                risk_points = _risk_points(value, hist_range[d["key"]], d["direction"])
                if risk_points is not None:
                    known_sum += risk_points
                    known_count += 1
            components.append({
                "key": d["key"], "status": status,
                "value": round(value, 1) if value is not None else None,
                "risk_points": risk_points,
            })
        risk_score = round(known_sum, 1) if known_count == len(DRIVERS) else None
        seasons.append({
            "year": year, "is_current": year == current_year,
            "total_kg": state["kg_by_year"].get(year, 0.0),
            "components": components,
            "known_count": known_count,
            "score_so_far": round(known_sum, 1) if known_count else None,
            "risk_score": risk_score,
            "band": _band(risk_score) if risk_score is not None else None,
        })

    return {
        "current_year": current_year,
        "historical_years": state["historical_years"],
        "driver_count": len(DRIVERS),
        "drivers": drivers_out,
        "seasons": seasons,
    }


@router.get("/summary")
def risk_summary(session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    """Admin-JWT-gated Risk tab data - see build_risk_summary(). The Owner
    View's token-gated equivalent (routers/owner_view.py) calls that same
    function directly, same split as analysis.py/weather.py."""
    return build_risk_summary(session)


# ---------------------------------------------------------------------------
# Harvest Forecast: three current-season kg predictions (Favorable/Expected/
# Unfavorable), built by projecting each still-open driver window forward
# and running the projection through the exact same _risk_points() scoring
# as the real Risk tab, then converting the resulting score to kg via a
# regression fit on the six historical (risk_score, total_kg) pairs.
# ---------------------------------------------------------------------------

def _segment_days(window_start: date, window_end: date, today: date, horizon_days: int) -> dict:
    """Splits a driver's fixed window into three non-overlapping date
    ranges relative to today, each clipped to the window itself:
    "actual" (window_start..today, real data), "forecast" (today+1..
    today+horizon_days, a real short-range forecast), and "assumed"
    (whatever's left, a historical-scenario assumption). Returns
    (start, end) tuples or None for an empty segment.

    This one formula degrades correctly for every case without having to
    branch on the driver's status: a window that's fully in the past
    collapses to "actual" = the whole window; a window entirely beyond the
    forecast horizon collapses to "assumed" = the whole window; a window
    whose remainder is fully inside the forecast horizon leaves "assumed"
    empty. horizon_days=0 (used when the forecast fetch itself failed)
    collapses "forecast" to always-empty, folding everything not yet
    actual into "assumed" instead - the graceful-degradation path."""
    def clip(a, b):
        lo, hi = max(a, window_start), min(b, window_end)
        return (lo, hi) if lo <= hi else None

    return {
        "actual": clip(window_start, today),
        "forecast": clip(today + timedelta(days=1), today + timedelta(days=horizon_days)),
        "assumed": clip(today + timedelta(days=horizon_days + 1), window_end),
    }


def _segment_day_count(segment) -> int:
    return (segment[1] - segment[0]).days + 1 if segment else 0


def _scenario_raw_value(hist_values: list, direction: str, scenario: str):
    """The three what-if raw values a driver could plausibly take, drawn
    straight from the six 2020-2025 seasons already on file: "expected" is
    their mean, "favorable" is the best of the six, "unfavorable" the
    worst - best/worst per the driver's own direction, so e.g. for a
    lower-is-worse driver "favorable" means the highest historical value."""
    if not hist_values:
        return None
    if scenario == "expected":
        return sum(hist_values) / len(hist_values)
    best = max(hist_values) if direction == "lower_is_worse" else min(hist_values)
    worst = min(hist_values) if direction == "lower_is_worse" else max(hist_values)
    return best if scenario == "favorable" else worst


def _project_driver(d: dict, state: dict, forecast_by_date: dict, forecast_unavailable: bool) -> dict:
    """One still-open driver's actual/forecast/assumed day-split and its
    three scenario-projected raw values (not yet converted to risk
    points). If either the actual or forecast segment has days but no
    usable data (a genuine gap - a down sensor or an unreachable forecast
    provider), the whole driver falls back to the pure historical-scenario
    value for its entire window instead of blending a partial gap in as if
    it meant "no risk" - flagged via "data_gap" so the caller can tell."""
    year = state["current_year"]
    today = state["today"]
    window_start, window_end = _window_dates(year, d["window_md"])
    window_total_days = (window_end - window_start).days + 1
    horizon = 0 if forecast_unavailable else FORECAST_HORIZON_DAYS
    segs = _segment_days(window_start, window_end, today, horizon)

    actual_days = _segment_day_count(segs["actual"])
    forecast_days = _segment_day_count(segs["forecast"])
    assumed_days = _segment_day_count(segs["assumed"])

    actual_value = _driver_value(_date_range_rows(state["by_date"], *segs["actual"]), d) if segs["actual"] else None
    forecast_value = _driver_value(_date_range_rows(forecast_by_date, *segs["forecast"]), d) if segs["forecast"] else None

    data_gap = (actual_days > 0 and actual_value is None) or (forecast_days > 0 and forecast_value is None)
    hist_values = state["hist_range"][d["key"]]

    if data_gap or not hist_values:
        scenarios = {s: _scenario_raw_value(hist_values, d["direction"], s)
                     for s in ("favorable", "expected", "unfavorable")}
        return {"data_gap": True, "actual_days": 0, "forecast_days": 0,
                "assumed_days": window_total_days, "scenarios": scenarios}

    scenarios = {}
    for s in ("favorable", "expected", "unfavorable"):
        scenario_value = _scenario_raw_value(hist_values, d["direction"], s)
        if d["agg"] == "mean":
            weighted = (actual_days * (actual_value or 0) + forecast_days * (forecast_value or 0)
                        + assumed_days * scenario_value)
            scenarios[s] = weighted / window_total_days
        else:
            rate = scenario_value / window_total_days
            scenarios[s] = (actual_value or 0) + (forecast_value or 0) + rate * assumed_days

    return {"data_gap": False, "actual_days": actual_days, "forecast_days": forecast_days,
            "assumed_days": assumed_days, "scenarios": scenarios}


def _ols_fit(xs: list, ys: list):
    """Hand-rolled least-squares line + Pearson r - no numpy/scipy in this
    project's dependencies, and n=6 makes a manual fit trivial. Returns
    None if there's too little variation to fit anything meaningful."""
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    slope = sxy / sxx
    intercept = my - slope * mx
    r = sxy / ((sxx ** 0.5) * (syy ** 0.5))
    return {"slope": round(slope, 2), "intercept": round(intercept, 1), "r": round(r, 3), "n_seasons": n}


def build_harvest_forecast(session: Session) -> dict:
    """Three kg predictions for the CURRENT season - Favorable/Expected/
    Unfavorable - rather than one falsely-precise number, since most of a
    season's outcome still depends on weather that hasn't happened yet.

    Each of the four DRIVERS' still-open window is projected forward (see
    _project_driver()): actual data where it exists, a real Open-Meteo
    forecast for up to the next 16 days, and a historical-scenario
    assumption (this driver's best/mean/worst of the six 2020-2025 seasons)
    for whatever's beyond that. Projected values are scored with the exact
    same _risk_points() used by the real Risk tab, so a scenario's 0-100
    score is directly comparable to any real season's score. That score is
    converted to a kg prediction via a simple linear regression fit on the
    six historical (risk_score, total_kg) pairs (see _ols_fit(); this
    project's dependencies don't include numpy/scipy, hence hand-rolled).

    Two things worth knowing about the numbers this produces: the
    Unfavorable scenario combines each driver's own worst historical YEAR
    (four different real years, not one real season that was worst on all
    four at once), so its score can exceed any real season's actual score -
    the regression is extrapolating past its six fitted points for that
    scenario, not interpolating within them. And if the Open-Meteo forecast
    call itself fails, every driver just falls back to a pure
    historical-scenario projection for its whole open window (see
    forecast_unavailable in the return value) rather than the endpoint
    failing outright.
    """
    sync_recent_weather(session)  # keep "actual" as fresh as the Weather tab would
    state = _compute_driver_state(session)

    forecast_unavailable = False
    forecast_by_date = defaultdict(list)
    try:
        lat, lon = farm_coords(session)
        raw = fetch_forecast_hourly(lat, lon, days=FORECAST_HORIZON_DAYS)
        for row in parse_hourly_rows(raw):
            forecast_by_date[row["timestamp"].date()].append(SimpleNamespace(**row))
    except Exception:
        forecast_unavailable = True

    horizon = 0 if forecast_unavailable else FORECAST_HORIZON_DAYS
    forecast_horizon_end = state["today"] + timedelta(days=horizon) if horizon else None

    driver_data = []
    scenario_points = {"favorable": [], "expected": [], "unfavorable": []}
    for d in DRIVERS:
        status = state["status_by_year"][d["key"]][state["current_year"]]
        window_start, window_end = _window_dates(state["current_year"], d["window_md"])
        window_total_days = (window_end - window_start).days + 1
        hist_values = state["hist_range"][d["key"]]

        if status == "final":
            value = state["value_by_year"][d["key"]][state["current_year"]]
            if value is None or not hist_values:
                raw_vals = {s: _scenario_raw_value(hist_values, d["direction"], s)
                            for s in scenario_points} if hist_values else {s: None for s in scenario_points}
                data_gap, actual_days, forecast_days, assumed_days = True, 0, 0, window_total_days
            else:
                raw_vals = {s: value for s in scenario_points}
                data_gap, actual_days, forecast_days, assumed_days = False, window_total_days, 0, 0
        else:
            proj = _project_driver(d, state, forecast_by_date, forecast_unavailable)
            raw_vals, data_gap = proj["scenarios"], proj["data_gap"]
            actual_days, forecast_days, assumed_days = proj["actual_days"], proj["forecast_days"], proj["assumed_days"]

        rp = {s: (_risk_points(raw_vals[s], hist_values, d["direction"]) if raw_vals[s] is not None else None)
              for s in scenario_points}
        for s in scenario_points:
            scenario_points[s].append(rp[s])

        driver_data.append({
            "key": d["key"], "label": d["label"], "window": d["window_label"], "unit": d["unit"],
            "status": status, "actual_days": actual_days, "forecast_days": forecast_days,
            "assumed_days": assumed_days, "data_gap": data_gap,
            "scenarios": {s: {"value": round(raw_vals[s], 1) if raw_vals[s] is not None else None,
                               "risk_points": rp[s]} for s in scenario_points},
        })

    # Historical (risk_score, total_kg) pairs for the regression - computed
    # directly from `state` rather than by calling build_risk_summary()
    # (which would reload and re-group the entire WeatherHistory table a
    # second time via its own _compute_driver_state() call). Every
    # historical year is always "final" on every driver by definition
    # (they're all in the past), so this reproduces exactly what
    # build_risk_summary() would report as that season's risk_score.
    hist_pairs = []
    for year in state["historical_years"]:
        comp_scores = [
            _risk_points(state["value_by_year"][d["key"]][year], state["hist_range"][d["key"]], d["direction"])
            for d in DRIVERS
        ]
        if all(p is not None for p in comp_scores):
            hist_pairs.append((round(sum(comp_scores), 1), state["kg_by_year"].get(year, 0.0)))
    regression = _ols_fit([p[0] for p in hist_pairs], [p[1] for p in hist_pairs])
    six_season_avg_kg = sum(p[1] for p in hist_pairs) / len(hist_pairs) if hist_pairs else None

    scenarios_out = {}
    for s, points in scenario_points.items():
        if any(p is None for p in points):
            scenarios_out[s] = {"risk_score": None, "band": None, "predicted_kg": None, "vs_avg_pct": None}
            continue
        score = round(sum(points), 1)
        predicted_kg = None
        vs_avg_pct = None
        if regression:
            predicted_kg = round(max(0.0, regression["intercept"] + regression["slope"] * score), 1)
            if six_season_avg_kg:
                vs_avg_pct = round((predicted_kg - six_season_avg_kg) / six_season_avg_kg * 100, 1)
        scenarios_out[s] = {"risk_score": score, "band": _band(score),
                             "predicted_kg": predicted_kg, "vs_avg_pct": vs_avg_pct}

    return {
        "current_year": state["current_year"],
        "forecast_unavailable": forecast_unavailable,
        "forecast_horizon_end": forecast_horizon_end.isoformat() if forecast_horizon_end else None,
        "six_season_avg_kg": round(six_season_avg_kg, 1) if six_season_avg_kg is not None else None,
        "regression": regression,
        "scenarios": scenarios_out,
        "drivers": driver_data,
    }


@router.get("/forecast")
def risk_forecast(session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    """Admin-JWT-gated Harvest Forecast data - see build_harvest_forecast().
    The Owner View's token-gated equivalent (routers/owner_view.py) calls
    that same function directly, same split as every other pair here."""
    return build_harvest_forecast(session)
