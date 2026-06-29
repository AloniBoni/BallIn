import threading
import time

from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import IntegrityError

from .database import Base, session_scope


# --- Users (persistent, SQLite via SQLAlchemy) ---
class User(Base):
    """A Ball-In account. `profile` is a JSON blob: for players the stats +
    frozen-order vector + archetype; for scouts the org + saved need."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    def to_record(self) -> dict:
        """Match the legacy in-memory record shape callers expect."""
        return {"password": self.password_hash, "role": self.role, "profile": dict(self.profile or {})}


def get_user(username: str) -> dict | None:
    """Return the full user record {password, role, profile}, or None if unknown."""
    with session_scope() as s:
        user = s.query(User).filter_by(username=username).one_or_none()
        return user.to_record() if user is not None else None


def add_user(username: str, hashed_password: str, role: str, profile: dict | None = None) -> bool:
    """Register a user with a role and optional profile. Returns False if the name is taken."""
    try:
        with session_scope() as s:
            s.add(User(username=username, password_hash=hashed_password, role=role, profile=profile or {}))
        return True
    except IntegrityError:
        # Unique constraint on username — the name is already registered.
        return False


def get_user_role(username: str) -> str | None:
    """Return the user's role (player/scout), or None if unknown."""
    with session_scope() as s:
        user = s.query(User).filter_by(username=username).one_or_none()
        return user.role if user is not None else None


def get_user_profile(username: str) -> dict | None:
    """Return a copy of the user's profile dict, or None if unknown."""
    with session_scope() as s:
        user = s.query(User).filter_by(username=username).one_or_none()
        return dict(user.profile or {}) if user is not None else None


def update_user_profile(username: str, profile: dict) -> bool:
    """Replace a user's profile. Returns False if the user is unknown."""
    with session_scope() as s:
        user = s.query(User).filter_by(username=username).one_or_none()
        if user is None:
            return False
        user.profile = profile   # whole-dict reassignment -> tracked as dirty
        return True


def get_users_by_role(role: str) -> list[dict]:
    """Return [{username, profile}] for every user holding the given role."""
    with session_scope() as s:
        return [
            {"username": user.username, "profile": dict(user.profile or {})}
            for user in s.query(User).filter_by(role=role).all()
        ]


def delete_all_users() -> None:
    """Wipe the users table. Used by tests to isolate cases."""
    with session_scope() as s:
        s.query(User).delete()


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
