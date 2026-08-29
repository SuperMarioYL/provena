"""Toy knowledge base the demo agent grounds its conclusions on.

This file is the *source* the agent reads. It deliberately exposes a small,
stable surface (a few functions with readable signatures) so the toy agent can
emit claims grounded on each function's definition span. Editing a function's
signature here is the demo's mutation: the FileSpan the agent cited no longer
matches its recorded content, so the cascade engine flags the grounded claim
(and everything depending on it) stale.

Keep this file self-contained and import-free so line numbers stay stable and
the agent's AST walk is predictable.
"""


def parse_config(path: str) -> dict:
    """Parse a config file at ``path`` into a dictionary."""
    return {"path": path, "options": {}}


def validate_user(user_id: str) -> bool:
    """Return True if ``user_id`` identifies a known user."""
    return len(user_id) > 0


def resolve_endpoint(name: str) -> str:
    """Resolve a logical endpoint name to a concrete URL."""
    return f"https://example.test/{name}"


def build_profile(user_id: str) -> dict:
    """Assemble a user profile from config, validation, and endpoint resolution."""
    config = parse_config(user_id)
    valid = validate_user(user_id)
    endpoint = resolve_endpoint(user_id)
    return {"config": config, "valid": valid, "endpoint": endpoint}
