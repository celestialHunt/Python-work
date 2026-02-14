from fastapi import APIRouter, Request
from app.services.calendar_service import (
    check_calendar_availability,
    CAL_API_BASE_URL,
    CAL_API_KEY,
    CAL_API_VERSION
)
import requests
from datetime import datetime, timedelta

router = APIRouter(prefix="/vapi", tags=["vapi"])

HEADERS = {
    "Authorization": f"Bearer {CAL_API_KEY}",
    "cal-api-version": CAL_API_VERSION,
    "Content-Type": "application/json"
}


@router.post("/check-availability")
async def vapi_check_availability(request: Request):
    data = await request.json()

    # 1. Extract the Tool Call ID (Vapi MUST have this back)
    message = data.get("message", {})
    tool_calls = message.get("toolCalls", [])
    if not tool_calls:
        return {"error": "No tool calls found"}

    tool_call = tool_calls[0]
    tool_call_id = tool_call.get("id")

    # 2. Extract the date from Vapi's arguments
    arguments = tool_call.get("function", {}).get("arguments", {})
    date_str = arguments.get("date")

    # 3. Call your working calendar service
    avail = check_calendar_availability(date_str)

    # 4. Format the result for Vapi
    if avail.get("status") == "success":
        slots_data = avail.get("slots", {})
        # slots_data is a dict like {"2026-02-12": [{"time": "..."}, ...]}
        date_slots = slots_data.get(date_str, [])

        if not date_slots:
            result_string = f"No slots available for {date_str}."
        else:
            formatted = []
            for s in date_slots[:5]:
                time_str = s.get("time")  # Cal.com v2 uses "time", not "start"
                if time_str and isinstance(time_str, str):
                    try:
                        dt = datetime.fromisoformat(time_str)
                        start = dt.strftime("%I:%M %p")
                        end = (dt + timedelta(minutes=30)).strftime("%I:%M %p")
                        formatted.append(f"{start} - {end}")
                    except ValueError:
                        formatted.append(time_str)

            result_string = (
                f"Available slots for {date_str}:\n" + "\n".join(formatted)
            )
            if formatted:
                result_string += "\nWhich time works best for you?"
            else:
                result_string += "\nNo times available that day."
    else:
        print(f"DEBUG: Availability failed with: {avail}")
        error_msg = avail.get("message", "Unknown error")
        result_string = (
            "Sorry, I couldn't check the calendar: "
            f"{error_msg}. Try a future date?"
        )

    # 5. Return the exact JSON structure Vapi requires
    return {
        "results": [
            {
                "toolCallId": tool_call_id,
                "result": result_string
            }
        ]
    }


@router.post("/book-appointment")
async def vapi_book_appointment(request: Request):
    data = await request.json()
    message = data.get("message", {})
    tool_calls = message.get("toolCalls", [])
    if not tool_calls:
        return {"error": "No tool calls found"}

    tool_call = tool_calls[0]
    tool_call_id = tool_call.get("id")
    args = tool_call.get("function", {}).get("arguments", {})

    print(f"BOOKING REQUEST RECEIVED: args = {args}")

    if not args or not isinstance(args, dict):
        result_string = (
            "Sorry, I need name, email, and time to book."
            "Can you provide them again?"
        )
        return {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": result_string
                }
            ]
        }

    # Email parsing — make it robust
    raw_email = args.get("email", "").lower().strip()
    print(f"see raw email value ::: {raw_email}")
    email = (
        raw_email.replace(" dot ", ".")
        .replace("dot", ".")
        .replace(" at ", "@")
        .replace("attherate", "@")
        .replace(" ", "")
    )

    print(f"Parsed email ::: {email}")
    # Basic validation
    if "@" not in email or "." not in email.split("@")[-1]:
        result_string = (
            "Sorry, the email doesn't look valid."
            "Please provide a correct email."
        )
        return {
            "results": [{"toolCallId": tool_call_id, "result": result_string}]
        }

    # Start time — assume Vapi sends ISO or "HH:MM AM/PM"
    start_time = args.get("time")
    if not start_time:
        result_string = "Sorry, I need a time to book the appointment."
        return {
            "results": [{"toolCallId": tool_call_id, "result": result_string}]
        }

    # Minimal payload
    payload = {
        "start": start_time,
        "eventTypeId": 4648515,
        "attendee": {
            "name": args.get("name", "Guest"),
            "email": email,
            "timeZone": "Asia/Kolkata"
        },
        "metadata": {}
    }

    print(f"BOOKING PAYLOAD: {payload}")
    print(f"Headers: {HEADERS}")
    url = f"{CAL_API_BASE_URL}/v2/bookings"
    print(f"Booking URL: {url}")
    try:
        print("Sending POST to Cal.com...")
        response = requests.post(
            url,
            json=payload,
            headers=HEADERS,
            timeout=15.0
        )

        print(f"CAL.COM BOOKING STATUS: {response.status_code}")
        print(f"CAL.COM BOOKING RESPONSE: {response.text}")

        if response.status_code in [200, 201]:
            try:
                data = response.json()
                if data.get("status") == "success":
                    print(f"CAL.COM BOOKING SUCCESS STATUS IN BODY**: {data}")
                    result_string = (
                        "Successfully booked! "
                        "You will receive an email confirmation shortly."
                    )
                else:
                    print(f"CAL.COM BOOKING FAILED IN BODY: {data}")
                    result_string = (
                        "Sorry, booking failed — Cal.com returned an error."
                    )
            except ValueError:
                result_string = (
                    "Booking may have succeeded but response was invalid."
                )
        else:
            result_string = (
                f"Sorry, booking failed (error {response.status_code}). "
                "Can you try again?"
            )

    except Exception as e:
        print(f"SERVER ERROR during booking: {str(e)}")
        result_string = (
            "It looks like there was a technical issue while booking your "
            "appointment. Let me try that again."
        )

    return {
        "results": [
            {
                "toolCallId": tool_call_id,
                "result": result_string
            }
        ]
    }
