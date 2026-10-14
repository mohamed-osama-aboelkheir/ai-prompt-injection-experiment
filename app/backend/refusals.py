"""Provider-neutral refusal heuristic shared by claude_runner and llm_runner."""

_REFUSAL_MARKERS = (
    "i can't help", "i cannot help", "i can't assist", "i cannot assist",
    "i won't", "i will not", "i'm not able to help", "i am not able to help",
    "i can't create", "i cannot create", "i'm unable to", "i am unable to",
    "against my", "i must decline",
)


def looks_like_refusal(text: str) -> bool:
    """Heuristic backup for refusals the transport doesn't tag with stop_reason."""
    low = text.strip().lower()
    if not low:
        return False
    head = low[:400]
    return any(marker in head for marker in _REFUSAL_MARKERS)
