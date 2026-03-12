from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging
import re

logger = logging.getLogger(__name__)


def get_current_datetime_payload(timezone_name: str | None):
    tz_name = timezone_name or "Asia/Kolkata"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz_name = "Asia/Kolkata"
        tz = ZoneInfo(tz_name)

    now = datetime.now(tz)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "iso": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "timezone": tz_name
    }


def get_business_phone(data, default_number):
    """
    Extracts the business phone number from Vapi payloads.
    Handles dictionary objects (phone calls), strings (web tests),
    and None/missing values (chat tests).
    """
    message = data.get("message", {})
    # 1. Try to get it from the common locations in the payload
    raw_phone = (
        message.get("phoneNumber") or
        data.get("phoneNumber") or
        message.get("call", {}).get("phoneNumber")
    )

    # 2. Extract the string if it's an object/dictionary
    if isinstance(raw_phone, dict):
        return raw_phone.get("number", default_number)

    # 3. Apply hardcoded fallback if extraction failed or returned "None"
    return str(raw_phone) if raw_phone and str(raw_phone).lower() != "none" else default_number


def extract_slots_safely(slots_data, date_str):
    """
    The 'Drill Down' Logic:
    Handles both flat lists (Web Test) and nested dicts (Live API).
    """
    if not slots_data or not isinstance(slots_data, dict):
        return []

    day_info = slots_data.get(date_str, [])

    # If the API returned {"date": {"date": [list]}}
    if isinstance(day_info, dict):
        return day_info.get(date_str, [])

    # If the API/Test returned {"date": [list]}
    return day_info


def normalize_vapi_date(date_input: str) -> str:
    """
    Cleans and corrects years for dates coming from Vapi.
    Handles both 'YYYY-MM-DD' and 'YYYY-MM-DDTHH:MM:SS'
    """
    if not date_input:
        return date_input

    # 1. Strip time if it's a full timestamp (for availability checks)
    clean_date = date_input.split("T")[0] if "T" in date_input else date_input

    try:
        current_year = datetime.now().year
        parts = clean_date.split('-')

        # 2. Fix hallucinated years (2024/2025 -> current)
        if int(parts[0]) < current_year:
            parts[0] = str(current_year)
            return "-".join(parts)
    except Exception:
        pass

    return clean_date


def normalize_vapi_booking_time(time_input: str, timezone_name: str = "Asia/Kolkata") -> str:
    """
    Converts user/model provided time to UTC for Cal.com.
    - If input has timezone (Z or +HH:MM), respect it.
    - If input is naive, assume Asia/Kolkata.
    - Fixes hallucinated past years for YYYY-... inputs.
    """
    if not time_input or not isinstance(time_input, str):
        return None

    s = time_input.strip()

    # Year fix (only if starts with YYYY)
    if len(s) >= 4 and s[:4].isdigit():
        current_year = datetime.now().year
        try:
            y = int(s[:4])
            if y < current_year:
                s = str(current_year) + s[4:]
        except Exception:
            pass

    try:
        # Parse trailing Z as UTC
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"

        dt = datetime.fromisoformat(s)
        ist = ZoneInfo(timezone_name)

        # If naive, assume IST
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ist)

        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    except Exception as e:
        logger.error(f"Normalization failed, using raw: {e}")
        return time_input


def process_vendor_availability(raw_slots, date_str, timezone_name, pref_time=None):
    """
    Refines raw slots from Cal.com:
    1. Converts UTC timestamps to the Business's Local Time.
    2. Filters out slots that have already passed.
    3. Trims the list to a readable window for the AI.
    """
    try:
        vendor_tz = ZoneInfo(timezone_name)
        # Get the exact current time in the business's timezone
        now_local = datetime.now(timezone.utc).astimezone(vendor_tz)

        all_raw_date_slots = extract_slots_safely(raw_slots, date_str)
        # Ensure slots are in chronological order
        all_raw_date_slots.sort(key=lambda x: x.get("time"))

        future_slots = []
        for s in all_raw_date_slots:
            # Cal.com returns UTC strings ending in 'Z'
            utc_dt = datetime.fromisoformat(s.get("time").replace('Z', '+00:00'))
            local_dt = utc_dt.astimezone(vendor_tz)

            # Trust Cal.com's availability. Only filter slots that are
            # strictly in the past relative to the business's current time.
            if local_dt > now_local:
                s['display_time'] = local_dt.strftime("%I:%M %p")
                future_slots.append(s)

        if not future_slots:
            return [], 0

        # Smart windowing ensures we don't overwhelm the voice AI with 50 slots
        display_slots = get_smart_slots_window(future_slots, pref_time)
        return display_slots, len(future_slots)

    except Exception as e:
        logger.error(f"Error in slot processing: {e}")
        return [], 0


def utc_iso_to_ist_display(utc_iso: str) -> str:
    dt_utc = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    dt_ist = dt_utc.astimezone(ZoneInfo("Asia/Kolkata"))

    return dt_ist.strftime("%A, %B %d at %I:%M %p IST")


def utc_iso_to_tz_display(utc_iso: str, timezone_name: str) -> str:
    """
    Convert a UTC ISO string (Cal.com) into a readable time string
    in the business timezone from DB.
    """
    if not utc_iso:
        return ""

    tz_name = timezone_name or "Asia/Kolkata"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz_name = "Asia/Kolkata"
        tz = ZoneInfo(tz_name)

    # Cal.com uses 'Z' for UTC; datetime.fromisoformat needs '+00:00'
    dt_utc = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    dt_local = dt_utc.astimezone(tz)

    return dt_local.strftime(f"%A, %B %d %Y at %I:%M %p ({tz_name})")


def clean_vapi_email(raw_email: str) -> str:
    if not raw_email:
        return ""
    print(f"RAW uncleaned email from utils::--> {raw_email}")
    normalized = raw_email.lower().strip()

    # 1) Normalize common spoken separators first
    normalized = normalized.replace("at the rate", "@")
    normalized = normalized.replace("attherate", "@")
    normalized = normalized.replace("at therate", "@")
    normalized = normalized.replace("therate", "@")

    # 2) Replace the word "dot" only (word boundary)
    normalized = re.sub(r"\bdot\b", ".", normalized)

    # 3) Remove all whitespace
    normalized = re.sub(r"\s+", "", normalized)

    # 4) Collapse multiple @
    normalized = re.sub(r"@{2,}", "@", normalized)

    # 5) Optional fallback: if still missing '@', replace ONLY the last 'at' token
    if "@" not in normalized:
        normalized = re.sub(r"(.*)\bat\b(.*)$", r"\1@\2", normalized)

    print(f"cleaned email from utils::--> {normalized}")
    return normalized


# PRIVATE FUNCTIONS

def get_smart_slots_window(all_slots, preferred_time=None, window_size=20):
    """
    - If no time is picked, show 40 slots (approx 12-20 hours) to see the whole day.
    - If a time is picked, center the 20-slot window around that time.
    """
    if not all_slots:
        return []

    # Generic fix: If 'Anytime' is requested, show the whole day (up to 40 slots)
    if not preferred_time:
        return all_slots[:40]

    start_idx = 0
    raw_pref = preferred_time.upper().replace(" ", "")
    search_targets = [raw_pref]

    # Handle 24h to 12h conversion for searching (e.g. 19:00 -> 07:00PM)
    try:
        if ":" in preferred_time and "AM" not in raw_pref and "PM" not in raw_pref:
            temp_dt = datetime.strptime(preferred_time.strip(), "%H:%M")
            search_targets.append(temp_dt.strftime("%I:%M%p").upper())
            search_targets.append(temp_dt.strftime("%-I:%M%p").upper())

    except Exception:
        pass

    for i, slot in enumerate(all_slots):
        slot_display = slot.get("display_time", "").upper().replace(" ", "")
        if any(target in slot_display for target in search_targets):
            # Center the window: show 2 slots before the target time
            start_idx = max(0, i - 2)
            break

    return all_slots[start_idx: start_idx + window_size]
