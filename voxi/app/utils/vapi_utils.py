def get_caller_number(data: dict):
    """Safely extracts the phone number from the Vapi webhook payload."""
    return (
        data.get("message", {})
            .get("call", {})
            .get("customer", {})
            .get("number")
    )


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
