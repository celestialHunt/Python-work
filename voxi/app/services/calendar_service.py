import os
import requests
from dotenv import load_dotenv
from datetime import datetime, date
from typing import Dict, Any

load_dotenv()


CAL_BASE_URL = os.getenv("CAL_BASE_URL")
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE")
DEFAULT_EVENT_SLUG = "30min"
API_VERSION = "2024-09-04"

CAL_API_KEY = os.getenv("CAL_API_KEY")
if not CAL_API_KEY:
    raise ValueError("CAL_API_KEY is not set in the environment variables")

CAL_USERNAME = os.getenv("CAL_USERNAME")
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

    Args:
        date_str: Date in YYYY-MM-DD format
        event_type_slug: Cal.com event type slug (default: "30min")
        timezone: IANA timezone name (default: "Asia/Kolkata")
        timeout: HTTP request timeout in seconds

    Returns:
        Dict with available slots or error information
    """

    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if parsed_date < date.today():
            return {"error": "invalid_date", "message":
                    "Cannot query past dates"
                    }
    except ValueError:
        return {"error": "invalid_date_format", "message":
                "Date must be YYYY-MM-DD"
                }

    params: Dict[str, str] = {
        "username": CAL_USERNAME,
        "eventTypeSlug": event_type_slug,
        "start": f"{date_str}T00:00:00Z",
        "end": f"{date_str}T23:59:59Z",
        "timeZone": timezone,
    }

    headers = {
        "Authorization": f"Bearer {CAL_API_KEY}",
        "cal-api-version": API_VERSION,
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            f"{CAL_BASE_URL}/v2/slots",
            params=params,
            headers=headers,
            timeout=timeout
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            slots = data.get("data", {})
            # Optional: normalize / enrich response here
            return {
                "status": "success",
                "date": date_str,
                "slots": slots.get(date_str, []),
                "timezone": timezone,
            }

        return {"status": "api_error", "data": data}

    except requests.Timeout:
        return {"error": "timeout", "message":
                f"Request timed out after {timeout}s"
                }
    except requests.RequestException as e:
        return {
            "error": "request_failed",
            "message": str(e),
            "status_code": getattr(e.response, "status_code", None)
            if hasattr(e, "response")
            else None,
        }
    except ValueError as e:
        # JSON decode error etc.
        return {"error": "invalid_response", "message": str(e)}


def get_cal_com_booking_link(
    date_str: str,
    event_type_slug: str = DEFAULT_EVENT_SLUG,
    username: str = CAL_USERNAME
) -> str:
    """
    Generate a direct link to the Cal.com booking page for a specific date
    and event type. The user can see available slots and book immediately.

    Args:
        date_str: Date in YYYY-MM-DD format
        event_type_slug: Which meeting type (e.g. "30min", "coffee-chat-45")
        username: Cal.com username (defaults to the one from env)

    Returns:
        Full booking URL string
    """
    return f"{CAL_BASE_URL}/{username}/{event_type_slug}?date={date_str}"


# Optional: small test / example usage (only runs if file executed directly)
if __name__ == "__main__":
    print(get_cal_com_booking_link("2026-02-06"))
    # → https://cal.com/pranav-chitrans-nunnxo/30min?date=2026-02-06

    print(get_cal_com_booking_link("2026-02-10", "45min"))
    # → https://cal.com/pranav-chitrans-nunnxo/45min?date=2026-02-10
