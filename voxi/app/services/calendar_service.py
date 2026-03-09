import os
import requests
from datetime import datetime, date
from typing import Dict, Any
from dotenv import load_dotenv
import logging
import json

load_dotenv()
logger = logging.getLogger(__name__)

CAL_API_BASE_URL = os.getenv("CAL_API_BASE_URL")
CAL_API_VERSION = os.getenv("CAL_API_VERSION")


def check_calendar_availability(
    date_str: str,
    api_key: str,
    username: str,
    event_type_slug: str,
    timezone: str
) -> Dict[str, Any]:
    """
    Fetch available slots using specific business credentials and timezone.
    """
    # 1. Validation
    if not all([api_key, username, timezone, event_type_slug]):
        return {
            "status": "error",
            "message": "Missing business configuration in database"
        }

    try:
        if datetime.strptime(date_str, "%Y-%m-%d").date() < date.today():
            return {"status": "error", "message": "Cannot query past dates"}
    except ValueError:
        return {"status": "error", "message": "Invalid date format"}

    # 2. Request Setup
    url = f"{CAL_API_BASE_URL}/v2/slots/available"
    params = {
        "usernameList[]": [username],
        "eventTypeSlug": event_type_slug,
        "startTime": f"{date_str}T00:00:00Z",
        "endTime": f"{date_str}T23:59:59Z",
        "timeZone": timezone,
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
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            return {
                "status": "success",
                "slots": {date_str: data.get("data", {}).get("slots", [])}
            }
        return {"status": "error", "message": "Cal.com API returned failure"}

    except Exception as e:
        return {"status": "error", "message": str(e)}


def create_cal_booking(
    api_key,
    event_type_id,
    name,
    email,
    start_time,
    timezone,
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

    payload = {
        "start": start_time,
        "eventTypeId": int(event_type_id),
        "attendee": {
            "name": name or "Guest",
            "email": email,
            "timeZone": timezone
        },
        "bookingFieldsResponses": {
            "notes": agenda
        },
        "metadata": {
            "agenda": agenda
        }
    }
    print(f"DEBUG FULL PAYLOAD book app****: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(
            f"{CAL_API_BASE_URL}/v2/bookings",
            json=payload,
            headers=headers,
            timeout=15.0
        )
        return response

    except Exception as e:
        logger.error(f"Booking API Exception: {e}")
        return None


async def cancel_cal_booking(
    api_key: str,
    email: str,
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

    # --- PHASE 1: DIRECT CANCELLATION ---
    if booking_uid:
        print(f"DEBUG: Executing direct cancellation for UID: {booking_uid}")
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
            print(f"DEBUG: Cancel Status: {res.status_code}")

            if res.status_code in [200, 201]:
                return f"✅ Success: Appointment for {email} has been cancelled."
            else:
                error_data = res.json()
                msg = error_data.get("error", {}).get("message") or error_data.get("message") or "Unknown error"

                return f"❌ Failed to cancel: {msg}"

        except Exception as e:
            return f"⚠️ Technical error during cancellation: {str(e)}"

    # --- PHASE 2: DISCOVERY (Search for bookings) ---
    print(f"DEBUG: Searching for bookings for attendee: {email}")
    list_url = f"{CAL_API_BASE_URL}/v2/bookings"
    try:
        # Fetch last 50 bookings to find matches
        response = requests.get(
            list_url,
            headers=headers,
            params={"take": 50},
            timeout=15
        )

        if response.status_code != 200:
            return f"❌ Error: Unable to access calendar (Status {response.status_code})"

        data = response.json()
        bookings = data.get("data", [])
        active_matches = []
        clean_email = email.lower().strip()
        today_iso = datetime.now().isoformat()

        for b in bookings:
            # ONLY look at 'upcoming' or 'booked' status
            if b.get("status", "").lower() not in ["upcoming", "booked"]:
                continue

            # ONLY look at future meetings
            if b.get("start") < today_iso:
                continue

            # Check all possible email locations in the response
            attendee_emails = [a.get("email", "").lower() for a in b.get("attendees", [])]
            response_email = b.get("responses", {}).get("email", "").lower()

            if clean_email in attendee_emails or clean_email == response_email:
                # Format a human-readable time for the AI to speak
                start_raw = b.get("start")
                try:
                    dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                    display_time = dt.strftime("%A, %B %d at %I:%M %p")
                except Exception:
                    display_time = start_raw  # Fallback if parsing fails

                active_matches.append({
                    "booking_uid": b.get("uid"),
                    "time": display_time
                })

        # --- PHASE 3: RESULTS HANDLING ---
        if not active_matches:
            return f"I couldn't find any active bookings for {email}."

        # If only ONE booking is found, we can be efficient and cancel it immediately
        if len(active_matches) == 1:
            single_uid = active_matches[0]["booking_uid"]
            print(f"DEBUG: Only one match found ({single_uid}). Proceeding to auto-cancel.")
            return await cancel_cal_booking(
                api_key=api_key,
                email=email,
                booking_uid=single_uid
            )

        # If MULTIPLE bookings are found, return the list so the AI can ask the user
        return {
            "info": "Multiple appointments found. Please ask the user which one they'd like to cancel.",
            "appointments": active_matches
        }

    except Exception as e:
        print(f"❌ CRITICAL SEARCH ERROR: {str(e)}")
        return f"Technical issue while searching for bookings: {str(e)}"


async def reschedule_cal_booking(
    api_key: str,
    email: str,
    new_start_time: str,
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
            # Fetch recent bookings to find a match
            response = requests.get(
                list_url,
                headers=headers,
                params={"take": 50},
                timeout=15
            )

            if response.status_code == 401:
                return "❌ API Key Error: The access token is invalid. Please check your Cal.com settings."

            if response.status_code != 200:
                return f"❌ Calendar Access Error: Status {response.status_code}"

            data = response.json()
            bookings = data.get("data", [])

            today_iso = datetime.now().isoformat()
            active_matches = []
            clean_email = email.lower().strip()

            for b in bookings:
                # ONLY look at 'upcoming' or 'booked' status
                if b.get("status", "").lower() not in ["upcoming", "booked"]:
                    continue

                # ONLY look at future meetings
                if b.get("start") < today_iso:
                    continue

                # Match email in attendees or response fields
                attendee_emails = [a.get("email", "").lower() for a in b.get("attendees", [])]
                responses_email = b.get("responses", {}).get("email", "").lower()

                if clean_email in attendee_emails or clean_email == responses_email:
                    start_raw = b.get("start")
                    try:
                        dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                        display_time = dt.strftime("%A, %B %d at %I:%M %p")
                    except Exception:
                        display_time = start_raw  # Fallback if parsing fails

                    active_matches.append({
                        "booking_uid": b.get("uid"),
                        "time": display_time
                    })

            # HANDLE NO BOOKINGS FOUND
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
            booking_uid = active_matches[0].get("uid")

        except Exception as e:
            return f"⚠️ Technical error during search: {str(e)}"

    # --- PHASE 2: EXECUTION (Move the booking) ---
    reschedule_url = f"{CAL_API_BASE_URL}/v2/bookings/{booking_uid}/reschedule"
    try:
        # Prepare Times
        start_dt = datetime.fromisoformat(new_start_time.replace("Z", "+00:00"))
        payload = {
            "start": start_dt.isoformat(),
            "reschedulingReason": "Rescheduled via AI Voice Assistant"
        }

        res = requests.post(
            reschedule_url,
            headers=headers,
            json=payload,
            timeout=15
        )

        if res.status_code in [200, 201]:
            readable_time = start_dt.strftime("%A, %B %d at %I:%M %p")
            return f"✅ Success! Your appointment has been rescheduled to {readable_time}."

        # Handle specific API failures
        error_data = res.json()
        error_msg = error_data.get("error", {}).get("message") or error_data.get("message")

        if "token" in str(error_msg).lower():
            return "❌ Authorization failed: The API key is invalid or has expired."

        return f"❌ Could not reschedule: {error_msg if error_msg else 'The slot might be taken.'}"

    except Exception as e:
        return f"⚠️ Technical error during reschedule: {str(e)}"
