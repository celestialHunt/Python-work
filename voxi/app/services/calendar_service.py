import os
import requests
from datetime import datetime, date
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

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
