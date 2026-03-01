import asyncio
from app.services.calendar_service import reschedule_cal_booking

# --- CONFIGURATION ---
# Ensure this key is active and has "Bookings: Read/Write" permissions in Cal.com
TEST_API_KEY = "cal_live_2d369e9aa9fbe1b936ca1910f7557701"
TEST_EMAIL = "chitrans.pranav@gmail.com"
# A time in the future (ISO format)
NEW_TIME = "2026-03-01T12:00:00Z"


async def run_test():
    print("🚀 Starting Dynamic Reschedule Test...")
    print(f"Searching for bookings for: {TEST_EMAIL}")
    print(f"Proposed New Time: {NEW_TIME}")
    print("-" * 30)

    # Note: We pass booking_uid=None to FORCE the service to search for the ID
    result = await reschedule_cal_booking(
        api_key=TEST_API_KEY,
        email=TEST_EMAIL,
        new_start_time=NEW_TIME,
        booking_uid=None
    )

    print(f"RESULT: {result}")

if __name__ == "__main__":
    asyncio.run(run_test())
