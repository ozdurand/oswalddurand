"""Helpers for rendering user messages into safe prompt fragments."""

from app.utils.sanitizer import safe_truncate


def render_user_message_for_model(text: str) -> str:
    """Wrap the user message in a predictable, neutral prefix and truncate.

    This makes it harder for prompt-injection strings to blend into system
    instructions and gives the model a clear signal about where user content
    begins.
    """
    if not text:
        return ""
    t = safe_truncate(text, max_chars=2800)
    # Use an explicit neutral prefix that the system prompt can rely on.
    return f"User query:\n---\n{t}\n---"
