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

    # If the transcriber already put a '@' in there,
    # we should be very careful about replacing the word 'at'
    if "@" in cleaned:
        # Just handle dots and spaces
        cleaned = cleaned.replace(" dot ", ".")
        cleaned = cleaned.replace(" ", "")
    else:
        # No '@' found, so we must convert the word 'at'
        cleaned = cleaned.replace(" at therate ", "@")
        cleaned = cleaned.replace("attherate", "@")
        cleaned = cleaned.replace(" at ", "@")
        cleaned = cleaned.replace(" dot ", ".")
        cleaned = cleaned.replace(" ", "")

    # Final cleanup for any missed 'dot' words
    return cleaned.replace("dot", ".")
