from fastapi import APIRouter, Request
from app.services.calendar_service import (
    check_calendar_availability,
    CAL_API_BASE_URL,
    CAL_API_VERSION
)
import requests
from datetime import datetime, timedelta
from app.services.database_service import get_customer_by_phone
from app.utils.vapi_utils import get_caller_number, clean_vapi_email

router = APIRouter(prefix="/vapi", tags=["vapi"])


@router.post("/inbound")
async def handle_vapi_call(request: Request):
    data = await request.json()
    customer_number = get_caller_number(data)

    if customer_number:
        customer = get_customer_by_phone(customer_number)
        if customer:
            # Personalize the greeting using the DB record
            business_name = customer.get('business_name', 'there')
            return {
                "assistant": {
                    "firstMessage": (
                        f"Hello {business_name}! "
                        "How can I help with your calendar today?"
                    )
                }
            }

    # Fallback greeting if no customer is found
    return {
        "assistant": {"firstMessage": "Hello there! How can I help you today?"}
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

    # 3. Now check the database
    customer_number = get_caller_number(data)
    customer = get_customer_by_phone(customer_number)
    if not customer:
        msg = (
            "I'm sorry, I couldn't find your business record "
            "to check the calendar."
        )
        return {
            "results": [{
                "toolCallId": tool_call_id,
                "result": msg
            }]
        }

    # 4. Call your working calendar service
    # avail = check_calendar_availability(date_str)
    avail = check_calendar_availability(
        date_str=date_str,
        api_key=customer.get("cal_api_key"),
        username=customer.get("cal_username"),
        event_type_slug=customer.get("event_type_slug", "30min"),
        timezone=customer.get("timezone", "Asia/Kolkata")
    )

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

    # 1. Argument presence validation
    if not args or not isinstance(args, dict):
        result_string = (
            "Sorry, I need name, email, and time to book. "
            "Can you provide them again?"
        )
        return {
            "results":
            [{"toolCallId": tool_call_id, "result": result_string}]
        }

    # 2. Customer Lookup
    customer_number = get_caller_number(data)
    customer = get_customer_by_phone(customer_number)

    # 3. Hard Stop if not in DB
    if not customer:
        msg = (
            "I'm sorry, I cannot book because the business record "
            "is missing."
        )
        return {"results": [{"toolCallId": tool_call_id, "result": msg}]}

    # 4. Extract DB values (No .env fallbacks)
    api_key = customer.get("cal_api_key")
    tz = customer.get("timezone", "UTC")
    # Safely convert event_id to integer
    try:
        event_id = int(customer.get("event_type_id"))
    except (TypeError, ValueError):
        msg = "Internal Error: Business calendar is not configured correctly."
        return {"results": [{"toolCallId": tool_call_id, "result": msg}]}

    # 5. Build Headers and Payload
    booking_headers = {
        "Authorization": f"Bearer {api_key}",
        "cal-api-version": CAL_API_VERSION,
        "Content-Type": "application/json"
    }

    # 6. Email parsing & validation
    raw_email = args.get("email", "")
    email = clean_vapi_email(raw_email)

    if "@" not in email or "." not in email.split("@")[-1]:
        result_string = (
            "Sorry, the email doesn't look valid. "
            "Please provide a correct email."
        )
        return {
            "results":
            [{"toolCallId": tool_call_id, "result": result_string}]
        }

    # 7. Start time validation
    start_time = args.get("time")
    if not start_time:
        result_string = "Sorry, I need a time to book the appointment."
        return {
            "results":
            [{"toolCallId": tool_call_id, "result": result_string}]
        }

    payload = {
        "start": start_time,
        "eventTypeId": event_id,
        "attendee": {
            "name": args.get("name", "Guest"),
            "email": email,
            "timeZone": tz
        },
        "metadata": {}
    }

    # 8. Execution
    url = f"{CAL_API_BASE_URL}/v2/bookings"
    try:
        response = requests.post(
            url,
            json=payload,
            headers=booking_headers,
            timeout=15.0
        )

        if response.status_code in [200, 201]:
            result_string = (
                "Successfully booked! "
                "You will receive an email confirmation shortly."
            )
        else:
            result_string = (
                f"Sorry, booking failed (error {response.status_code}). "
                "Can you try again?"
            )

    except Exception as e:
        import traceback
        traceback.print_exc()
        result_string = f"Technical issue: {str(e)}"

    return {"results": [{"toolCallId": tool_call_id, "result": result_string}]}
