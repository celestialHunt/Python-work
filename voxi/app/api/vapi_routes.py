from fastapi import APIRouter, Request
import json
import logging
from datetime import datetime
from app.services.database_service import (
    get_customer_by_phone
)
from app.utils.vapi_utils import (
    clean_vapi_email,
    get_business_phone,
    normalize_vapi_date,
    process_vendor_availability,
    get_current_datetime_payload
)
from app.services.calendar_service import (
    check_calendar_availability,
    create_cal_booking,
    cancel_cal_booking,
    reschedule_cal_booking
)


router = APIRouter(prefix="/vapi", tags=["vapi"])
logger = logging.getLogger(__name__)


@router.post("/check-availability")
async def vapi_check_availability(request: Request):
    try:
        data = await request.json()
        # print(f"DEBUG FULL PAYLOAD: {json.dumps(data, indent=2)}")

        # 1. IDENTIFY THE BUSINESS
        # Uses the utility to handle both Live Phone Calls and Web/Chat tests
        business_phone = get_business_phone(data, "+18622252071")
        print(f"business_phone***-->: {business_phone}\n")

        # 2. EXTRACT TOOL CALL METADATA
        message = data.get("message", {})
        tool_calls = message.get("toolCalls") or message.get("toolCallList") or []
        if not tool_calls:
            return {"results": []}

        tool_call = tool_calls[0]
        tool_call_id = tool_call.get("id")
        arguments = tool_call.get("function", {}).get("arguments", {})

        date_str = normalize_vapi_date(arguments.get("date"))
        print(f"date_str***-->: {date_str}\n")
        pref_time = arguments.get("preferred_time")
        print(f"pref_time***-->: {pref_time}\n")
        if not date_str:
            return {"results": [{"toolCallId": tool_call_id, "result": "Please provide a specific date."}]}

        # 3. DATABASE LOOKUP
        customer = get_customer_by_phone(business_phone)
        print(f"✅🧑‍🧒CUSTOMER FOUND: {customer}\n")
        if not customer:
            return {
                "results": [
                    {
                        "toolCallId": tool_call_id,
                        "result": "I'm sorry, this business is not configured yet."
                    }
                ]
            }

        # 4. Call Cal.com using THIS business's specific credentials
        avail = check_calendar_availability(
            date_str=date_str,
            api_key=customer.get("cal_api_key"),
            username=customer.get("cal_username"),
            event_type_slug=customer.get("event_type_slug", "30min"),
            timezone_name=customer.get("timezone", "Asia/Kolkata")
        )

        if avail.get("status") == "error":
            # Specific handle for Cal.com being unreachable
            logger.error(f"Cal.com API Error: {avail.get('message')}")
            return {
                "results": [{
                    "toolCallId": tool_call_id,
                    "result": (
                        "I'm having a brief connection issue with the calendar. "
                        "One moment while I try that again."
                    )
                }]
            }

        # 5. PROCESS SLOTS
        if avail.get("status") == "success":
            logger.info(f"Checking availability. Current server-aware time is: {datetime.now()}")
            display_slots, total_future = process_vendor_availability(
                raw_slots=avail.get("slots", {}),
                date_str=date_str,
                timezone_name=customer.get("timezone", "Asia/Kolkata"),
                pref_time=pref_time
            )
            if not display_slots:
                result_string = (
                    f"I'm sorry, there are no available slots left for {date_str}. "
                    "Should I check for the following day instead?"
                )
            else:
                times_list = [s['display_time'] for s in display_slots]
                result_string = f"Available slots for {date_str}:\n" + ", ".join(times_list)
                if total_future > len(display_slots):
                    result_string += ". Other times are also available later in the day."
        else:
            result_string = "I'm having trouble accessing the calendar right now."

        return {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": result_string
                }
            ],
            "variableValues": {
                "vendor_timezone": customer.get("timezone", "Asia/Kolkata")
            }
        }

    except Exception as e:
        logger.error(f"Availability Route Error: {e}")
        return {"results": [{"toolCallId": "error", "result": "Technical difficulty."}]}


@router.post("/book-appointment")
async def vapi_book_appointment(request: Request):
    """Handles final booking with email cleaning and normalized timestamps."""
    try:
        data = await request.json()
        # print(f"DEBUG FULL PAYLOAD book app****: {json.dumps(data, indent=2)}")
        message = data.get("message", {})
        tool_calls = message.get("toolCalls") or message.get("toolCallList") or [{}]
        tool_call = tool_calls[0]
        tool_call_id = tool_call.get("id")
        args = tool_call.get("function", {}).get("arguments", {})

        # 1. Identify the Business
        business_phone = get_business_phone(data, "+18622252071")
        customer = get_customer_by_phone(business_phone)

        if not customer:
            return {"results": [{"toolCallId": tool_call_id, "result": "Business record missing."}]}

        # 3. Execute request to Cal.com
        try:
            response = create_cal_booking(
                api_key=customer.get("cal_api_key"),
                event_type_id=customer.get("event_type_id"),
                name=args.get("name"),
                email=clean_vapi_email(args.get("email")),
                start_time=args.get("time"),
                timezone_name=customer.get("timezone", "Asia/Kolkata"),
                agenda=args.get("agenda")
            )
            if not response:
                result_string = "I couldn't understand the time you requested. could you repeat the time you want?"
            else:
                if response.status_code in [200, 201]:
                    result_string = "Great! You are all booked. Check your email for the confirmation."
                else:
                    error_data = response.json() if response.text else "No error body"
                    logger.error(f"Booking Failed for {business_phone}: {response.status_code} - {error_data}")
                    result_string = (
                        "It looks like that specific slot was just taken. "
                        "Could we try the next available time?"
                    )

        except Exception as api_err:
            # This catches network timeouts or connection drops
            logger.error(f"Inner API Exception: {api_err}")
            result_string = "I'm having a bit of trouble connecting to the booking system. One moment."

        return {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": result_string
                }
            ],
            "variableValues": {
                "vendor_timezone": customer.get("timezone", "Asia/Kolkata")
            }
        }

    except Exception as e:
        logger.error(f"Global Booking Route Error: {e}")
        return {"results": [{"toolCallId": "error", "result": "System error. Please try again."}]}


@router.post("/cancel-appointment")
async def vapi_cancel_appointment(request: Request):
    """
    Production route to cancel a booking.
    Matches the business, finds the latest booking by email, and cancels it.
    """
    try:
        data = await request.json()

        # 1. Extract Tool Details
        message = data.get("message", {})
        tool_calls = message.get("toolCalls", [{}])
        tool_call = tool_calls[0]
        tool_call_id = tool_call.get("id")
        args = tool_call.get("function", {}).get("arguments", {})

        # 2. Identify the Business
        business_phone = get_business_phone(data, "+18622252071")
        customer = get_customer_by_phone(business_phone)

        if not customer:
            return {
                "results": [
                    {
                        "toolCallId": tool_call_id,
                        "result": "Business config not found."
                    }
                ]
            }

        # 3) Clean inputs
        target_email = clean_vapi_email(args.get("email"))
        if not target_email or "@" not in target_email:
            return {
                "results": [
                    {
                        "toolCallId": tool_call_id,
                        "result": "I need a valid email address. Please spell it out."
                    }
                ]
            }

        # 4. CALL YOUR SERVICE FUNCTION
        result = await cancel_cal_booking(
            api_key=customer.get("cal_api_key"),
            email=target_email,
            timezone_name=customer.get("timezone", "Asia/Kolkata"),
            booking_uid=args.get("booking_uid")
        )

        # 5. HANDLE THE RESULT TYPE (String vs Dictionary)
        # Always return machine-readable JSON to the model
        if isinstance(result, dict):
            result_string = json.dumps(result)
        else:
            result_string = result

        return {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": result_string
                }
            ],
            "variableValues": {
                "vendor_timezone": customer.get("timezone", "Asia/Kolkata")
            }
        }

    except Exception as e:
        logger.error(f"Cancel Route Error: {e}")
        return {
            "results": [
                {
                    "toolCallId": "error",
                    "result": "I ran into a technical issue while trying to cancel."
                }
            ]
        }


@router.post("/reschedule-appointment")
async def vapi_reschedule_appointment(request: Request):
    """
    Finds the existing booking and patches it with a new 'start' time.
    """
    try:
        data = await request.json()
        message = data.get("message", {})
        tool_calls = message.get("toolCalls") or message.get("toolCallList") or [{}]
        logger.info(f"RESCHEDULE tool_calls count={len(tool_calls)}")
        logger.info(f"RESCHEDULE tool_calls args={[tc.get('function', {}).get('arguments', {}) for tc in tool_calls]}")
        tool_call = tool_calls[0]
        tool_call_id = tool_call.get("id")
        args = tool_call.get("function", {}).get("arguments", {})
        print("tool_calls_count:", len(tool_calls))
        print("tool_calls_args:", [tc.get("function", {}).get("arguments", {}) for tc in tool_calls])
        # print(f"DEBUG FULL PAYLOAD reschedule app****: {json.dumps(data, indent=2)}")

        business_phone = get_business_phone(data, "+18622252071")
        customer = get_customer_by_phone(business_phone)
        if not customer:
            return {"results": [{"toolCallId": tool_call_id, "result": "Business record missing."}]}

        # 3. CALL SERVICE (Phase 1 & 2 combined)
        # Service now receives 'None' for new_time if the user just wanted a lookup
        result = await reschedule_cal_booking(
            api_key=customer.get("cal_api_key"),
            email=clean_vapi_email(args.get("email")),
            timezone_name=customer.get("timezone", "Asia/Kolkata"),
            new_start_time=args.get("new_start_time"),
            booking_uid=args.get("booking_uid")
        )

        # 4. Handle Response Type (Matches your Cancel logic)
        if isinstance(result, dict):
            # Handles the "Multiple bookings found" dictionary
            options = ", ".join([f"at {a['time']}" for a in result.get("appointments", [])])
            result_string = f"I found multiple appointments for you: {options}. Which one should I move?"
        else:
            # Handles the Success/Error strings
            result_string = result

        return {"results": [{"toolCallId": tool_call_id, "result": result_string}]}

    except Exception as e:
        logger.error(f"Reschedule Route Error: {e}")
        return {"results": [{"toolCallId": "error", "result": "Technical error during rescheduling."}]}


@router.post("/current-datetime")
async def vapi_current_datetime(request: Request):
    data = await request.json()
    message = data.get("message", {})
    tool_calls = message.get("toolCalls") or message.get("toolCallList") or []
    if not tool_calls:
        return {"results": []}

    results = []
    for tc in tool_calls:
        tool_call_id = tc.get("id")
        args = tc.get("function", {}).get("arguments", {}) or {}
        result_obj = get_current_datetime_payload(args.get("timezone_name"))
        results.append({"toolCallId": tool_call_id, "result": result_obj})

    return {"results": results}
