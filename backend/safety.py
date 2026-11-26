import re

INJECTION = [
    r"(?:ignore|disregard|override|forget)\s+(?:all\s+|the\s+|any\s+)?(?:previous|prior|above|system)\s+(?:instructions?|rules?|prompts?|policies)",
    r"(?:reveal|show|print|dump|expose)\s+(?:the\s+)?(?:system\s+prompt|hidden\s+(?:instructions?|rules?|approval\s+matrix)|internal\s+(?:instructions?|rules?))",
    r"act\s+as\s+(?:the\s+)?system",
    r"bypass\s+(?:all\s+|the\s+)?(?:safety|controls?|safeguards?)",
]

PII = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone": r"\b(?:\+91[- ]?)?[6-9]\d{9}\b",
    "pan": r"\b[A-Z]{5}\d{4}[A-Z]\b",
    "card": r"\b(?:\d[ -]*?){13,16}\b",
}


def inspect_query(text):
    return "security_prompt_injection" if any(re.search(p, text.lower()) for p in INJECTION) else None


def redact_pii(text):
    if not isinstance(text, str):
        return text
    for label, pattern in PII.items():
        text = re.sub(pattern, f"[REDACTED_{label.upper()}]", text)
    return text


def sanitize_evidence(text):
    """Neutralize any prompt-injection directives embedded inside retrieved documents."""
    if not isinstance(text, str):
        return ""
    cleaned = text
    for pattern in INJECTION:
        cleaned = re.sub(pattern, "[UNTRUSTED_DIRECTIVE_REMOVED]", cleaned, flags=re.I)
    return cleaned
