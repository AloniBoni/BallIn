import threading
import time

# --- Users ---
# Each user is a record: {"password": hash, "role": "player"|"scout", "profile": {...}}.
_users_lock = threading.Lock()
_users: dict[str, dict] = {}


def get_user(username: str) -> dict | None:
    """Return the full user record {password, role, profile}, or None if unknown."""
    with _users_lock:
        record = _users.get(username)
        return dict(record) if record is not None else None


def add_user(username: str, hashed_password: str, role: str, profile: dict | None = None) -> bool:
    """Register a user with a role and optional profile. Returns False if the name is taken."""
    with _users_lock:
        if username in _users:
            return False
        _users[username] = {
            "password": hashed_password,
            "role": role,
            "profile": profile or {},
        }
        return True


def get_user_role(username: str) -> str | None:
    """Return the user's role (player/scout), or None if unknown."""
    with _users_lock:
        record = _users.get(username)
        return record["role"] if record is not None else None


def get_user_profile(username: str) -> dict | None:
    """Return a copy of the user's profile dict, or None if unknown."""
    with _users_lock:
        record = _users.get(username)
        return dict(record["profile"]) if record is not None else None


# --- Revoked tokens (by JTI) ---
_revoked_lock = threading.Lock()
_revoked_tokens: set[str] = set()


def revoke_token(jti: str) -> None:
    with _revoked_lock:
        _revoked_tokens.add(jti)


def is_token_revoked(jti: str) -> bool:
    with _revoked_lock:
        return jti in _revoked_tokens


# --- Request counters ---
_counters_lock = threading.Lock()
_counters = {"success": 0, "fail": 0}


def increment_success() -> None:
    with _counters_lock:
        _counters["success"] += 1


def increment_fail() -> None:
    with _counters_lock:
        _counters["fail"] += 1


def get_counters() -> dict:
    with _counters_lock:
        return dict(_counters)


# --- Health ---
_health_lock = threading.Lock()
_health = "ok"


def set_health(status: str) -> None:
    global _health
    with _health_lock:
        _health = status


def get_health() -> str:
    with _health_lock:
        return _health


# Set once at import time; never reset
startup_time: float = time.time()
