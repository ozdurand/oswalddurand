"""Utilities for sanitizing user input to reduce prompt-injection risk."""

import re
from typing import Pattern

# Common prompt-injection patterns to redact. Keep this conservative.
_PATTERNS = [
    r"ignore (the )?system prompt",
    r"disregard (the )?instructions",
    r"ignore previous (instructions|messages|prompts)",
    r"do not follow (the )?system prompt",
    r"follow these instructions",
    r"follow only these instructions",
    r"execute the following",
    r"run the following",
    r"sudo\b",
    r"bash -c",
    r"sh -c",
]

_COMPILED: list[Pattern] = [re.compile(p, re.I) for p in _PATTERNS]


def detect_prompt_injection(text: str) -> bool:
    """Return True if text matches any known injection pattern."""
    if not text:
        return False
    for rx in _COMPILED:
        if rx.search(text):
            return True
    return False


def sanitize_user_message(text: str) -> str:
    """Sanitize free-form user input before placing into prompts.

    - Redacts lines or phrases that look like prompt-injection attempts.
    - Replaces code-fence blocks with a safe placeholder.
    - Collapses excessive whitespace.
    """
    if not text:
        return text

    # Normalize whitespace
    s = text.replace("\r\n", "\n")

    # Replace code fences entirely to avoid executable instructions slipping in
    s = re.sub(r"```[\s\S]*?```", "```[REDACTED_CODE]```", s, flags=re.I)

    # Redact suspicious phrases
    for rx in _COMPILED:
        s = rx.sub("[REDACTED_INJECTION]", s)

    # Remove any leftover lines that begin with obvious instruction verbs to be conservative
    lines = []
    for line in s.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(
            r"^(ignore|disregard|do not|follow|execute|run)\b", stripped, flags=re.I
        ):
            # redact the whole line
            lines.append("[REDACTED_INJECTION]")
            continue
        lines.append(line)

    out = "\n".join(lines)
    # Collapse multiple blank lines
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def safe_truncate(text: str, max_chars: int = 3000) -> str:
    """Truncate text conservatively to a maximum number of characters.

    Helps avoid very large injected payloads making it into prompts.
    """
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 12].rsplit(" ", 1)[0] + "... [TRUNCATED]"
