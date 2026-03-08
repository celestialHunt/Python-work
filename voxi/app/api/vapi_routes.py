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
    normalize_vapi_booking_time,
    process_vendor_availability
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
        print(f"DEBUG FULL PAYLOAD: {json.dumps(data, indent=2)}")

        # 1. IDENTIFY THE BUSINESS
        # Uses the utility to handle both Live Phone Calls and Web/Chat tests
        business_phone = get_business_phone(data, "+18622252071")
        print(f"business_phone***-->: {business_phone}")

        # 2. EXTRACT TOOL CALL METADATA
        message = data.get("message", {})
        tool_calls = message.get("toolCalls", [])
        if not tool_calls:
            return {
                "results": [{"toolCallId": "none", "result": "Internal acknowledgement: No tool execution required."}]
            }

        tool_call = tool_calls[0]
        tool_call_id = tool_call.get("id")
        arguments = tool_call.get("function", {}).get("arguments", {})

        date_str = normalize_vapi_date(arguments.get("date"))
        print(f"date_str***-->: {date_str}")
        pref_time = arguments.get("preferred_time")
        print(f"pref_time***-->: {pref_time}")
        if not date_str:
            return {"results": [{"toolCallId": tool_call_id, "result": "Please provide a specific date."}]}

        # 3. DATABASE LOOKUP
        customer = get_customer_by_phone(business_phone)
        print(f"✅🧑‍🧒CUSTOMER FOUND: {customer}")
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
            timezone=customer.get("timezone", "Asia/Kolkata")
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

        return {"results": [{"toolCallId": tool_call_id, "result": result_string}]}

    except Exception as e:
        logger.error(f"Availability Route Error: {e}")
        return {"results": [{"toolCallId": "error", "result": "Technical difficulty."}]}


@router.post("/book-appointment")
async def vapi_book_appointment(request: Request):
    """Handles final booking with email cleaning and normalized timestamps."""
    try:
        data = await request.json()
        print(f"DEBUG FULL PAYLOAD book app****: {json.dumps(data, indent=2)}")
        message = data.get("message", {})
        tool_call = message.get("toolCalls", [{}])[0]
        tool_call_id = tool_call.get("id")
        args = tool_call.get("function", {}).get("arguments", {})
        start_time = normalize_vapi_booking_time(args.get("time"))

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
                start_time=start_time,
                timezone=customer.get("timezone", "Asia/Kolkata"),
                agenda=args.get("agenda")
            )
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

        return {"results": [{"toolCallId": tool_call_id, "result": result_string}]}

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

        # 3. Clean Inputs
        target_email = clean_vapi_email(args.get("email"))

        if not target_email:
            return {"results": [
                {
                    "toolCallId": tool_call_id,
                    "result": "I need your email to find the booking."
                }
            ]}

        # 4. CALL YOUR SERVICE FUNCTION
        result = await cancel_cal_booking(
            api_key=customer.get("cal_api_key"),
            email=target_email,
            booking_uid=args.get("booking_uid")
        )

        # 3. HANDLE THE RESULT TYPE (String vs Dictionary)
        if isinstance(result, dict):
            # If multiple bookings were found, your code returns a dict
            options = ", ".join([f"at {a['time']}" for a in result.get("appointments", [])])
            result_string = f"I found multiple appointments for you: {options}. Which one would you like to cancel?"
        else:
            result_string = result

        return {"results": [{"toolCallId": tool_call_id, "result": result_string}]}

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
        tool_call = data.get("message", {}).get("toolCalls", [{}])[0]
        tool_call_id = tool_call.get("id")
        args = tool_call.get("function", {}).get("arguments", {})

        business_phone = get_business_phone(data, "+16088837790")
        customer = get_customer_by_phone(business_phone)
        if not customer:
            return {"results": [{"toolCallId": tool_call_id, "result": "Business record missing."}]}

        # Normalize the new time (Fixes the 2024/2025 year hallucination)
        target_email = clean_vapi_email(args.get("email"))
        new_time = normalize_vapi_booking_time(args.get("new_start_time"))

        # 3. CALL YOUR SERVICE (Phase 1 & 2 combined)
        # This will either return a Success string, an Error string, or a Dictionary for multiple matches.
        result = await reschedule_cal_booking(
            api_key=customer.get("cal_api_key"),
            email=target_email,
            new_start_time=new_time,
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
