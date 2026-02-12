import os
import requests
from dotenv import load_dotenv
from datetime import datetime, date
from typing import Dict, Any
from urllib.parse import urlencode

load_dotenv()

# Configuration from environment
CAL_API_BASE_URL = os.getenv("CAL_API_BASE_URL")
CAL_BOOKING_BASE_URL = os.getenv("CAL_BOOKING_BASE_URL")
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE")
DEFAULT_EVENT_SLUG = "30min"
CAL_API_VERSION = os.getenv("CAL_API_VERSION")
CAL_API_KEY = os.getenv("CAL_API_KEY")
CAL_USERNAME = os.getenv("CAL_USERNAME")

# Validate critical variables
if not CAL_API_KEY:
    raise ValueError("CAL_API_KEY is not set in the environment variables")
if not CAL_USERNAME:
    raise ValueError("CAL_USERNAME is not set in the environment variables")


def check_calendar_availability(
    date_str: str,
    event_type_slug: str = DEFAULT_EVENT_SLUG,
    timezone: str = DEFAULT_TIMEZONE,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """
    Fetch available time slots for a given date from Cal.com API (v2).
    """
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if parsed_date < date.today():
            return {
                "error":
                "invalid_date", "message": "Cannot query past dates"
                }
    except ValueError:
        return {
            "error":
            "invalid_date_format", "message": "Date must be YYYY-MM-DD"
            }

    if not CAL_API_KEY or not CAL_USERNAME:
        return {"error": "config_error", "message": "Missing API credentials"}

    # V2 Endpoint uses /v2/slots/available
    url = f"{CAL_API_BASE_URL}/v2/slots/available"

    # V2 uses 'startTime' and 'endTime' instead of 'start' and 'end'
    params = {
        "usernameList[]": [CAL_USERNAME],  # v2 accepts a list of usernames
        "eventTypeSlug": event_type_slug,
        "startTime": f"{date_str}T00:00:00Z",
        "endTime": f"{date_str}T23:59:59Z",
        "timeZone": timezone,
    }

    headers = {
        "Authorization": f"Bearer {CAL_API_KEY}",
        "cal-api-version": CAL_API_VERSION,
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout
        )

        print(f"CAL.COM STATUS: {response.status_code}")

        # Check for unauthorized errors early
        if response.status_code == 401:
            return {
                "error":
                "unauthorized", "message": "Invalid API Key or Version header."
                }

        response.raise_for_status()
        data = response.json()

        # Handle the v2 response structure
        if data.get("status") == "success":
            slots_data = data.get("data", {})
            # v2 slots are usually nested under data['slots']
            available_slots = slots_data.get("slots", [])

            return {
                "status": "success",
                "date": date_str,
                "slots": available_slots,
                "timezone": timezone,
            }

        return {"status": "api_error", "data": data}

    except requests.RequestException as ex:
        status_code = None
        if hasattr(ex, "response") and ex.response:
            status_code = getattr(ex.response, "status_code", None)

        return {
            "error": "request_failed",
            "message": str(ex),
            "status_code": status_code,
        }


def get_cal_com_booking_link(
    date_str: str,
    event_type_slug: str = DEFAULT_EVENT_SLUG,
    username: str = CAL_USERNAME
) -> str:
    """
    Generate a direct link to the Cal.com booking page.
    """
    base_url = f"{CAL_BOOKING_BASE_URL}/{username}/{event_type_slug}"
    query_string = urlencode({"date": date_str})

    return f"{base_url}?{query_string}"
