import os
import requests
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any
from dotenv import load_dotenv
import logging
# import json
from app.utils.vapi_utils import (
    normalize_vapi_booking_time,
    utc_iso_to_tz_display
)

load_dotenv()
logger = logging.getLogger(__name__)

CAL_API_BASE_URL = os.getenv("CAL_API_BASE_URL")
CAL_API_VERSION = os.getenv("CAL_API_VERSION")


def check_calendar_availability(
    date_str: str,
    api_key: str,
    username: str,
    event_type_slug: str,
    timezone_name: str
) -> Dict[str, Any]:
    """
    Fetch available slots using specific business credentials and timezone.
    """
    logger.info(f"Checking availability. Current server-aware time is: {datetime.now()}")
    # 1. Validation
    if not all([api_key, username, timezone_name, event_type_slug]):
        return {
            "status": "error",
            "message": "Missing business configuration in database"
        }

    try:
        requested_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = date.today()
        if requested_date < today:
            return {"status": "error", "message": "Cannot query past dates"}
        end_time_iso = f"{date_str}T23:59:59Z"

        if requested_date == today:
            now_local = datetime.now(ZoneInfo(timezone_name))
            start_time_iso = now_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            # For future dates, search from the very beginning of that day
            start_time_iso = f"{date_str}T00:00:00Z"

            # End time is always the very end of the requested day
            end_time_iso = f"{date_str}T23:59:59Z"

    except ValueError:
        return {"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}

    # 2. Request Setup
    url = f"{CAL_API_BASE_URL}/v2/slots/available"
    params = {
        "usernameList[]": [username],
        "eventTypeSlug": event_type_slug,
        "startTime": start_time_iso,
        "endTime": end_time_iso,
        "timeZone": timezone_name,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "cal-api-version": CAL_API_VERSION,
        "Accept": "application/json",
    }

    # 3. Execution
    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10
        )
        print("\ncalendar service checkAvailability response:::--->", {response})
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            return {
                "status": "success",
                "slots": {date_str: data.get("data", {}).get("slots", [])}
            }
        return {"status": "error", "message": "Cal.com API returned failure"}

    except Exception as e:
        logger.error(f"Availability API Failure: {str(e)}")
        return {"status": "error", "message": str(e)}


def create_cal_booking(
    api_key,
    event_type_id,
    name,
    email,
    start_time,
    timezone_name,
    agenda=None
):
    """
    Handles the actual API call to Cal.com to create a booking.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "cal-api-version": CAL_API_VERSION,
        "Content-Type": "application/json"
    }

    start_time = normalize_vapi_booking_time(start_time, timezone_name)
    if not start_time:
        logger.error("Missing/invalid start_time after normalization")
        return None

    payload = {
        "start": start_time,
        "eventTypeId": int(event_type_id),
        "attendee": {
            "name": name or "Guest",
            "email": email,
            "timeZone": timezone_name
        },
        "bookingFieldsResponses": {
            "notes": agenda
        },
        "metadata": {
            "agenda": agenda
        }
    }
    # print(f"DEBUG FULL PAYLOAD book app****: {json.dumps(payload, indent=2)}\n")

    try:
        response = requests.post(
            f"{CAL_API_BASE_URL}/v2/bookings",
            json=payload,
            headers=headers,
            timeout=15.0
        )
        print("\ncalendar service createBooking response:::--->", {response})
        # Log the specific error from Cal.com if it fails
        if response.status_code not in [200, 201]:
            logger.error(f"Cal.com Booking Error: {response.status_code} - {response.text}")
        return response

    except Exception as e:
        logger.error(f"Booking API Exception: {e}")
        return None


async def cancel_cal_booking(
    api_key: str,
    email: str,
    timezone_name: str,
    booking_uid: str = None
):
    """
    If booking_uid is provided: Cancels that specific booking.
    If NOT provided: Searches for all active bookings matching
    the email and returns them.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "cal-api-version": CAL_API_VERSION,
        "Content-Type": "application/json"
    }

    # --- PHASE 1: DIRECT CANCELLATION (If we have the UID) ---
    if booking_uid:
        print(f"DEBUG: Executing direct cancellation for UID: {booking_uid}\n")
        cancel_url = f"{CAL_API_BASE_URL}/v2/bookings/{booking_uid}/cancel"

        # V2 Requirement: cancellationReason is mandatory for Host-initiated cancels
        payload = {
            "cancellationReason": "Cancelled via Enceptor AI Voice Assistant",
            "cancelSubsequentBookings": False
        }

        try:
            res = requests.post(
                cancel_url,
                headers=headers,
                json=payload,
                timeout=15
            )
            print(f"DEBUG: Cancel Status: {res.status_code}\n")

            if res.status_code in [200, 201]:
                return f"✅ Success: Appointment for {email} has been cancelled."
            else:
                error_data = res.json()
                msg = error_data.get("error", {}).get("message") or error_data.get("message") or "Unknown error"

                return f"❌ Failed to cancel: {msg}"

        except Exception as e:
            return f"⚠️ Technical error during cancellation: {str(e)}"

    # --- PHASE 2: DISCOVERY (Search for bookings using direct API filters) ---
    list_url = f"{CAL_API_BASE_URL}/v2/bookings"
    try:
        # LET THE API FILTER BY EMAIL AND STATUS
        params = {
            "attendeeEmail": email,
            "status": "upcoming",
            "take": 5
        }
        response = requests.get(
            list_url,
            headers=headers,
            params=params,
            timeout=15
        )

        if response.status_code != 200:
            return f"❌ Error: Unable to access calendar (Status {response.status_code})"

        data = response.json()
        bookings = data.get("data", [])
        active_matches = []

        for b in bookings:
            # Every booking here already matches the email thanks to 'params'
            start_raw = b.get("start")
            try:
                display_time = utc_iso_to_tz_display(start_raw, timezone_name)
            except Exception:
                display_time = start_raw

            active_matches.append({
                "booking_uid": b.get("uid"),
                "time": display_time
            })

        # --- PHASE 3: RESULTS HANDLING ---
        if not active_matches:
            return {"status": "none_found", "email": email}

        # If only ONE booking is found, we can cancel it after user confirms
        if len(active_matches) == 1:
            single_uid = active_matches[0]["booking_uid"]
            # found_time = active_matches[0]["time"]
            print(f"DEBUG: Only one match found ({single_uid} under {email}). Proceeding to auto-cancel.\n")
            return {
                "status": "single_found",
                "appointment": active_matches[0],
                "email": email
            }

        # If MULTIPLE bookings are found, return the list so the AI can ask the user
        return {
            "status": "multiple_found",
            "appointments": active_matches,
            "email": email
        }

    except Exception as e:
        print(f"❌ CRITICAL SEARCH ERROR: {str(e)}\n")
        return f"Technical issue while searching for bookings: {str(e)}"


async def reschedule_cal_booking(
    api_key: str,
    email: str,
    timezone_name: str,
    new_start_time: str = None,
    booking_uid: str = None
):
    """
    Reschedules an appointment.
    1. If booking_uid is missing, it searches for active bookings under the email.
    2. If no bookings found, it informs the agent (so the agent can tell the caller).
    3. If one is found (or provided), it executes the reschedule.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "cal-api-version": CAL_API_VERSION,
        "Content-Type": "application/json"
    }

    # --- PHASE 1: DISCOVERY (If we don't have a valid UID) ---
    if not booking_uid:
        list_url = f"{CAL_API_BASE_URL}/v2/bookings"
        try:
            params = {
                "attendeeEmail": email,
                "status": "upcoming",
                "take": 5
            }

            # Fetch recent bookings to find a match
            response = requests.get(
                list_url,
                headers=headers,
                params=params,
                timeout=15
            )
            print("\ncalendar service reschedule response:::--->", {response})
            if response.status_code == 401:
                return "❌ API Key Error: The access token is invalid. Please check your Cal.com settings."

            if response.status_code != 200:
                return f"❌ Calendar Access Error: Status {response.status_code}"

            data = response.json()
            bookings = data.get("data", [])
            print(f"bookings data reschedule app from calendar service****: {bookings}\n")

            active_matches = []
            for b in bookings:
                start_raw = b.get("start")
                try:
                    display_time = utc_iso_to_tz_display(start_raw, timezone_name)
                except Exception:
                    display_time = start_raw

                active_matches.append({
                    "booking_uid": b.get("uid"),
                    "time": display_time
                })
                print(f"calendar service--reschedule booking -- active_matches****: {active_matches}\n")

            # HANDLE Results NO BOOKINGS FOUND
            if not active_matches:
                return (
                    f"I searched for appointments under '{email}', "
                    "but I couldn't find any active bookings to reschedule."
                )

            # HANDLE MULTIPLE BOOKINGS
            if len(active_matches) > 1:
                return {
                    "info": "Multiple bookings found. Ask the user which one they want to move.",
                    "appointments": active_matches
                }

            # Exactly one found? Auto-assign the UID to proceed to Phase 2
            booking_uid = active_matches[0].get("booking_uid")
            found_time = active_matches[0]['time']

            # If the user JUST wanted to know "When is my meeting?" (no new_start_time provided)
            if not new_start_time:
                return (
                    f"I found your appointment for {found_time}. "
                    "What new time or date would you like to move it to?"
                )

        except Exception as e:
            logger.error(f"Search Error: {e}")
            return f"⚠️ Technical error during search: {str(e)}"

    # --- PHASE 2: EXECUTION (Move the booking) ---
    reschedule_url = f"{CAL_API_BASE_URL}/v2/bookings/{booking_uid}/reschedule"
    try:
        # Prepare Times
        start_utc = normalize_vapi_booking_time(new_start_time, timezone_name)
        payload = {
            "start": start_utc,
            "reschedulingReason": "Rescheduled via AI Voice Assistant"
        }
        print(f"Calendar Service reschedule payload:::---***{payload}\n")
        res = requests.post(
            reschedule_url,
            headers=headers,
            json=payload,
            timeout=15
        )

        if res.status_code in [200, 201]:
            start_local = datetime.fromisoformat(new_start_time.replace("Z", "+00:00"))
            if start_local.tzinfo is None:
                start_local = start_local.replace(tzinfo=ZoneInfo(timezone_name))
            else:
                start_local = start_local.astimezone(ZoneInfo(timezone_name))

            readable_time = start_local.strftime("%A, %B %d at %I:%M %p")
            return f"✅ Success! Your appointment has been rescheduled to {readable_time}."

        # Handle specific API failures
        error_data = res.json()
        error_msg = error_data.get("error", {}).get("message") or error_data.get("message")

        if "token" in str(error_msg).lower():
            return "❌ Authorization failed: The API key is invalid or has expired."

        return f"❌ Could not reschedule: {error_msg if error_msg else 'The slot might be taken.'}"

    except Exception as e:
        logger.error(f"Reschedule Execution Error: {e}")
        return f"⚠️ Technical error during reschedule: {str(e)}"
