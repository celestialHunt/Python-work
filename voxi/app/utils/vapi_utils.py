from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)


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


def normalize_vapi_booking_time(time_input: str) -> str:
    """
    Specifically for booking, fixes the year while preserving
    the full ISO timestamp and offset.
    """
    if not time_input:
        return time_input

    current_year = str(datetime.now().year)
    # If the first 4 characters are a year in the past
    if int(time_input[:4]) < int(current_year):
        return current_year + time_input[4:]

    return time_input


def process_vendor_availability(raw_slots, date_str, timezone_name, pref_time=None):
    """
    Background Process:
    1. Converts UTC to Local.
    2. Filters out past slots.
    3. Centers around preferred time.
    """
    try:
        vendor_tz = ZoneInfo(timezone_name)
        now_local = datetime.now(timezone.utc).astimezone(vendor_tz)

        all_raw_date_slots = extract_slots_safely(raw_slots, date_str)
        all_raw_date_slots.sort(key=lambda x: x.get("time"))

        future_slots = []
        for s in all_raw_date_slots:
            # Cal.com returns UTC 'Z' strings
            utc_dt = datetime.fromisoformat(s.get("time").replace('Z', '+00:00'))
            local_dt = utc_dt.astimezone(vendor_tz)

            # Filter: Is this slot in the future?
            if local_dt > (now_local + timedelta(minutes=30)):
                s['display_time'] = local_dt.strftime("%I:%M %p")
                future_slots.append(s)

        if not future_slots:
            return [], 0

        display_slots = get_smart_slots_window(future_slots, pref_time)
        return display_slots, len(future_slots)

    except Exception as e:
        logger.error(f"Error in background slot processing: {e}")
        return [], 0


def clean_vapi_email(raw_email: str):
    if not raw_email:
        return ""

    cleaned = raw_email.lower().strip()

    # 1. Handle "the rate" variations specifically
    # These often appear as "at the rate", "at therate", or just "therate"
    cleaned = cleaned.replace("at the rate", "@")
    cleaned = cleaned.replace("at therate", "@")
    cleaned = cleaned.replace("attherate", "@")
    cleaned = cleaned.replace("therate", "@")  # This fixes your specific error

    # 2. If the transcriber already put a '@' in there
    if "@" in cleaned:
        cleaned = cleaned.replace(" dot ", ".")
        cleaned = cleaned.replace(" ", "")
    else:
        # 3. No '@' found, handle standalone "at"
        cleaned = cleaned.replace(" at ", "@")
        cleaned = cleaned.replace(" dot ", ".")
        cleaned = cleaned.replace(" ", "")

    # 4. Final cleanup for any missed 'dot' words and redundant '@'
    cleaned = cleaned.replace("dot", ".")

    # If the logic created "@@" (e.g., "at @"), fix it
    while "@@" in cleaned:
        cleaned = cleaned.replace("@@", "@")

    return cleaned


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
