def _ensure_str(value, default=""):
    """Return a string representation of *value*.
    Guarantees that the returned object is a ``str`` and never ``None``.
    """
    if isinstance(value, str):
        return value
    # For bytes, decode using utf‑8 with replacement of errors
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return default
    # Fallback for any other type
    return str(value) if value is not None else default


def score_response(user_input, ai_response):
    """
    Compute a quality score (0.0 – 1.0) for an AI's response given the original user input.

    The scoring rules are:
    * Penalize very short answers (< 50 characters)
    * Penalize the presence of weak/uncertain phrases
    * Reward long, detailed answers (> 300 characters)
    * Penalize responses that share little vocabulary with the user input
    * Reward the inclusion of fenced code blocks (