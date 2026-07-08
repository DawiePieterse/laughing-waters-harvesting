from fastapi import APIRouter

from weather import fetch_weather

router = APIRouter(prefix="/api/weather", tags=["weather"])

# Hardcoded for testing per explicit request - not tied to SystemSetting's
# gps_lat/gps_lon, which drive a separate feature (per-dispatch weather
# capture in routers/lots.py).
_LAT, _LON = -25.572747, 31.606722


@router.get("/current")
def current_weather():
    return fetch_weather(_LAT, _LON)
