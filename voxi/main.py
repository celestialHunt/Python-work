from fastapi import FastAPI
from app.api import vapi_routes
from dotenv import load_dotenv
from app.services.calendar_service import (
    check_calendar_availability,
    get_cal_com_booking_link,
)
import uvicorn

load_dotenv()

app = FastAPI(title="Voxi AI Receptionist")

# Mount Vapi routes
app.include_router(vapi_routes.router)


@app.get("/")
async def root():
    return {"message": "Voxi Server is Live"}


# ────────────────────────────────────────────────
#     Add this endpoint so /availability/... works
# ────────────────────────────────────────────────

@app.get("/availability/{date}", include_in_schema=False)
def availability(date: str):
    """
    Return available slots and a direct booking link for a given date.

    Example usage:
        GET /availability/2026-02-11
    """
    avail = check_calendar_availability(date)
    link = get_cal_com_booking_link(date)

    return {
        "date": date,
        "availability": avail,
        "direct_booking_link": link
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
