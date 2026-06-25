import uuid
import datetime

import jwt
from flask import Blueprint, request, current_app, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from .models import (
    get_user, add_user,
    revoke_token, is_token_revoked,
    increment_success, increment_fail,
)

auth_bp = Blueprint("auth", __name__)

# Upper bounds on credential length. Usernames are stored in-memory and embedded
# in every JWT; oversized passwords make password hashing an unauthenticated CPU
# DoS vector, so both are capped before any hashing happens.
USERNAME_MAX_LEN = 64
PASSWORD_MAX_LEN = 4096

# The two account roles in Ball-In. Frozen here so register and the role checks
# agree on the exact set of accepted values.
VALID_ROLES = {"player", "scout"}


def _err(status: int, message: str):
    return jsonify({"error": {"http_status": status, "message": message}}), status


def check_token() -> tuple[str | None, str | None, str | None]:
    """Validate Bearer token. Returns (username, jti, role) or (None, None, None) on failure."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, None, None
    token = auth[7:]
    try:
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET"],
            algorithms=["HS256"],
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None, None, None
    jti = payload.get("jti")
    if not jti or is_token_revoked(jti):
        return None, None, None
    return payload.get("sub"), jti, payload.get("role")


def require_role(required_role: str) -> tuple[str | None, str | None]:
    """Gate an endpoint by role.

    Returns (username, jti) if the caller holds a valid token with the required
    role, otherwise (None, None) — the caller turns that into a 401/403.
    """
    username, jti, role = check_token()
    if username is None or role != required_role:
        return None, None
    return username, jti


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("username"), str) or not isinstance(data.get("password"), str):
        increment_fail()
        return _err(400, "Missing username or password")
    username = data["username"].strip()
    password = data["password"]
    if not username or not password:
        increment_fail()
        return _err(400, "Missing username or password")
    if len(username) > USERNAME_MAX_LEN or len(password) > PASSWORD_MAX_LEN:
        increment_fail()
        return _err(400, "Username or password too long")
    role = data.get("role")
    if role not in VALID_ROLES:
        increment_fail()
        return _err(400, "Role must be 'player' or 'scout'")
    hashed = generate_password_hash(password)
    if not add_user(username, hashed, role):
        increment_fail()
        return _err(409, "Username already exists")
    increment_success()
    return jsonify({"message": "User registered successfully"}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("username"), str) or not isinstance(data.get("password"), str):
        increment_fail()
        return _err(400, "Missing username or password")
    username = data["username"].strip()
    password = data["password"]
    if not username or not password:
        increment_fail()
        return _err(400, "Missing username or password")
    # Reject oversized credentials before check_password_hash to close the same
    # CPU-DoS path that the length cap closes on /register.
    if len(username) > USERNAME_MAX_LEN or len(password) > PASSWORD_MAX_LEN:
        increment_fail()
        return _err(400, "Username or password too long")
    record = get_user(username)
    if record is None or not check_password_hash(record["password"], password):
        increment_fail()
        return _err(401, "Invalid username or password")
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": username,
        "role": record["role"],
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + datetime.timedelta(hours=24),
    }
    token = jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")
    increment_success()
    return jsonify({"token": token}), 200


@auth_bp.route("/logout", methods=["POST"])
def logout():
    username, jti, _role = check_token()
    if username is None:
        increment_fail()
        return _err(401, "Missing or invalid token")
    revoke_token(jti)
    increment_success()
    return jsonify({"message": "Logged out successfully"}), 200
