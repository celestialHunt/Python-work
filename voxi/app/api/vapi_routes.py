from fastapi import APIRouter, Body
from pydantic import BaseModel

router = APIRouter(prefix="/vapi")


class AvailabilityRequest(BaseModel):
    date: str
    # duration_minutes: int = 30   # optional


@router.post("/check-availability")
async def check_availability(data: dict = Body(...)):
    print("Received body from Vapi:", data)

    date = data.get("date", "unknown")
    # duration = data.get("duration_minutes", 30)

    return {
        "success": True,
        "date": date,
        "available_slots": ["10:00 AM", "11:30 AM", "02:00 PM", "04:00 PM"],
        "message": f"These are the open 30-minute slots on {date}."
    }
