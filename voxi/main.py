from fastapi import FastAPI, Request
import requests
from dotenv import load_dotenv
from app.api import vapi_routes
from app.services.calendar_service import (
    CAL_BASE_URL,
    CAL_API_KEY,
    CAL_API_VERSION,
    check_calendar_availability,
    get_cal_com_booking_link
)

load_dotenv()
app = FastAPI(title="Voxi AI Receptionist", version="1.0")

app.include_router(vapi_routes.router)

HEADERS = {
    "Authorization": f"Bearer {CAL_API_KEY}",
    "cal-api-version": f"{CAL_API_VERSION}",
    "Content-Type": "application/json"
}


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


@app.post("/book")
async def book_appointment(request: Request):
    try:
        data = await request.json()

        # This structure matches how Vapi sends tool call arguments
        # It's deeply nested: message -> toolCalls -> function -> arguments
        tool_calls = data.get("message", {}).get("toolCalls", [{}])
        args = tool_calls[0].get("function", {}).get("arguments", {})

        print(
            f"""Received booking request for: {args.get('name')} at
            {args.get('time')}"""
        )

        url = f"{CAL_BASE_URL}/v2/bookings"
        payload = {
            "start": args.get("time"),
            "eventTypeId": 1335354,  # Use your real ID from the Cal dashboard
            "attendee": {
                "name": args.get("name", "Customer"),
                "email": args.get("email"),
                "timeZone": "Asia/Kolkata",
                "language": "en"
            },
            # Note: Cal.com V2 sometimes requires a title at the root level
            "title": f"Meeting with {args.get('name', 'Customer')}"
        }
        response = requests.post(url, json=payload, headers=HEADERS)
        if response.status_code in [200, 201]:
            return {"results": "Booking confirmed! See you then."}
        else:
            return {"results": f"Booking failed: {response.text}"}

    except Exception as ex:
        return {"results": f"System error: {str(ex)}"}
