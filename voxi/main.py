from fastapi import FastAPI
from app.api import vapi_routes
from app.services.calendar_service import (
    check_calendar_availability,
    get_cal_com_booking_link
)

app = FastAPI(title="Voxi AI Receptionist", version="1.0")

app.include_router(vapi_routes.router)


@app.get("/availability/{date}")
def availability(date: str):
    """
    Get availability and booking link for a specific date.

    Example:
        GET /availability/2026-02-10
    """
    avail = check_calendar_availability(date)
    link = get_cal_com_booking_link(date)
    return {
        "date": date,
        "availability": avail,
        "direct_booking_link": link
    }
