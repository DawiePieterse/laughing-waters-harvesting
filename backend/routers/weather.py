from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from db import get_session
from models import WeatherHistory
from security import get_current_admin
from weather import fetch_weather, sync_recent_weather

router = APIRouter(prefix="/api/weather", tags=["weather"])

# Hardcoded for testing per explicit request - not tied to SystemSetting's
# gps_lat/gps_lon, which drive a separate feature (per-dispatch weather
# capture in routers/lots.py, and the Weather tab's history below via
# weather.farm_coords()).
_LAT, _LON = -25.572747, 31.606722


@router.get("/current")
def current_weather():
    return fetch_weather(_LAT, _LON)


# ---------------------------------------------------------------------------
# Weather tab: daily-aggregated history, admin-JWT-gated. The Owner View's
# token-gated equivalent (routers/owner_view.py) calls build_weather_history()
# directly, same split as analysis.py/build_analysis_summary().
# ---------------------------------------------------------------------------

# key -> (source column on WeatherHistory, aggregation, unit, decimals).
# agg is one of "mean"/"sum"/"max", applied over a calendar day's hourly
# rows. uv_index uses the day's peak (not a mean - "how strong did it get")
# and sunshine_duration_s is summed then converted seconds->hours for a
# legible unit. weather_code/condition are categorical, not chartable as a
# line, so they're deliberately left out of this registry.
_METRICS = [
    {"key": "temp_c", "label": "Temperature", "source": "temp_c", "agg": "mean", "unit": "°C", "decimals": 1},
    {"key": "humidity_pct", "label": "Humidity", "source": "humidity_pct", "agg": "mean", "unit": "%", "decimals": 0},
    {"key": "dew_point_c", "label": "Dew Point", "source": "dew_point_c", "agg": "mean", "unit": "°C", "decimals": 1},
    {"key": "precipitation_mm", "label": "Precipitation", "source": "precipitation_mm", "agg": "sum", "unit": "mm", "decimals": 1},
    {"key": "wind_speed_kmh", "label": "Wind Speed", "source": "wind_speed_kmh", "agg": "mean", "unit": "km/h", "decimals": 1},
    {"key": "soil_temp_6cm_c", "label": "Soil Temp (6cm)", "source": "soil_temp_6cm_c", "agg": "mean", "unit": "°C", "decimals": 1},
    {"key": "uv_index", "label": "UV Index", "source": "uv_index", "agg": "max", "unit": "", "decimals": 1},
    {"key": "sunshine_hours", "label": "Sunshine", "source": "sunshine_duration_s", "agg": "sum", "unit": "hrs",
     "decimals": 1, "scale": 1 / 3600},
]


def _metrics_public() -> list:
    return [{"key": m["key"], "label": m["label"], "unit": m["unit"], "decimals": m["decimals"]} for m in _METRICS]


def build_weather_history(session: Session) -> dict:
    """Daily-aggregated WeatherHistory for the Weather tab - see _METRICS
    for per-metric aggregation. Grouped by plain calendar year (1 Jan -
    31 Dec), deliberately NOT the Aug-anchored harvest season used
    elsewhere in this app (analysis.py's _season_day) - weather doesn't
    follow the picking season the way harvest data does, and "what was the
    weather like in 2023" naturally means the calendar year. current_year
    is simply today's calendar year - the one bucket that, being still in
    progress, only covers 1 Jan through whatever's been synced so far
    rather than a full year."""
    rows = session.exec(select(WeatherHistory).order_by(WeatherHistory.timestamp)).all()

    by_day: dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        d = r.timestamp.date()  # already local wall-clock (see models.py) - no to_local()
        for m in _METRICS:
            v = getattr(r, m["source"])
            if v is not None:
                by_day[d][m["key"]].append(v * m.get("scale", 1))

    points = []
    for d in sorted(by_day):
        point = {"date": d.isoformat(), "year": d.year, "day_of_year": d.timetuple().tm_yday}
        for m in _METRICS:
            vals = by_day[d].get(m["key"], [])
            if not vals:
                point[m["key"]] = None
                continue
            if m["agg"] == "mean":
                val = sum(vals) / len(vals)
            elif m["agg"] == "sum":
                val = sum(vals)
            else:
                val = max(vals)
            point[m["key"]] = round(val, m["decimals"])
        points.append(point)

    return {
        "metrics": _metrics_public(),
        "years": sorted({p["year"] for p in points}),
        "current_year": date.today().year,
        "last_synced": rows[-1].timestamp.isoformat() if rows else None,
        "points": points,
    }


@router.get("/history")
def weather_history(session: Session = Depends(get_session), admin=Depends(get_current_admin)):
    """Admin-JWT-gated Weather tab data - syncs the latest hours from
    Open-Meteo first (best-effort, see weather.sync_recent_weather) then
    returns the full daily-aggregated history."""
    sync_recent_weather(session)
    return build_weather_history(session)
