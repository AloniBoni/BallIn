"""Ball-In profile construction & validation.

Turns the raw JSON a client sends at registration into the stored profile —
including the standardized-order feature vector the ML core consumes. Kept out
of auth.py so the wire-validation rules live in one place and can be unit-tested
on their own.

Vector order is FROZEN — see mlcore.FEATURE_ORDER / CLAUDE.md §5. Registration,
NBA seeding and scout needs must all build vectors in this exact order.
"""

from .mlcore import FEATURE_ORDER, FEATURE_DIM

# Court positions -> the integer used in the "position_encoded" feature slot.
# Frozen alongside the feature schema so registration, seeding and scout needs
# all encode position the same way.
POSITION_ENCODING = {"PG": 1, "SG": 2, "SF": 3, "PF": 4, "C": 5}

# The numeric stats a player supplies at registration: everything in
# FEATURE_ORDER except position, which arrives as a court-position string and is
# encoded server-side.
PLAYER_STAT_FIELDS = [f for f in FEATURE_ORDER if f != "position_encoded"]

# Caps on scout free-text fields so a profile can't smuggle in a huge blob.
ORG_MAX_LEN = 120
NEED_MAX_LEN = 120


def _to_number(value):
    """Coerce a JSON value to float, rejecting bools and non-numerics.

    bool is excluded explicitly because it is a subclass of int — True would
    otherwise slip through as 1.0.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def build_player_profile(raw):
    """Validate a player's raw stats and build the stored profile.

    Returns (profile, None) on success or (None, error_message) on bad input.
    The profile carries the raw stats, the encoded position, and the
    frozen-order feature vector the ML core scores against.
    """
    if not isinstance(raw, dict):
        return None, "Player profile must be an object with stats"

    position = raw.get("position")
    if not isinstance(position, str) or position.upper() not in POSITION_ENCODING:
        return None, "position must be one of PG, SG, SF, PF, C"
    position = position.upper()

    stats = {}
    for field in PLAYER_STAT_FIELDS:
        number = _to_number(raw.get(field))
        if number is None:
            return None, f"Missing or non-numeric stat: {field}"
        stats[field] = number

    # Assemble the vector in the single frozen order. position_encoded is the
    # only derived slot; every other slot reads straight from the stats.
    vector = []
    for field in FEATURE_ORDER:
        if field == "position_encoded":
            vector.append(float(POSITION_ENCODING[position]))
        else:
            vector.append(stats[field])
    assert len(vector) == FEATURE_DIM

    return {"position": position, "stats": stats, "vector": vector}, None


def build_scout_profile(raw):
    """Validate a scout's org + saved need.

    Returns (profile, None) on success or (None, error_message) on bad input.
    """
    if not isinstance(raw, dict):
        return None, "Scout profile must be an object with org and need"

    org = raw.get("org")
    need = raw.get("need")
    if not isinstance(org, str) or not org.strip():
        return None, "Scout profile requires a non-empty 'org'"
    if not isinstance(need, str) or not need.strip():
        return None, "Scout profile requires a non-empty 'need'"
    org, need = org.strip(), need.strip()
    if len(org) > ORG_MAX_LEN or len(need) > NEED_MAX_LEN:
        return None, "org or need too long"

    return {"org": org, "need": need}, None


def build_profile(role, raw):
    """Dispatch to the per-role builder. Returns (profile, error_message)."""
    if role == "player":
        return build_player_profile(raw)
    if role == "scout":
        return build_scout_profile(raw)
    return None, "Unknown role"
