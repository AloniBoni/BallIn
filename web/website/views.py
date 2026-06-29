import io
import os
import time

from flask import Blueprint, request, jsonify, render_template
from PIL import Image

from .auth import check_token
from .models import (
    get_health, set_health,
    get_counters, startup_time,
    increment_success, increment_fail,
    get_user_profile, update_user_profile, get_users_by_role,
)
from .mlcore import get_mlcore
from .profile_utils import build_profile

views_bp = Blueprint("views", __name__)

# KNN comparables: default returned, and a hard cap so a caller can't request a
# huge k. Interest is counted above this similarity threshold.
DEFAULT_K = 5
MAX_K = 25
INTEREST_THRESHOLD = 0.5

# interface.md: "Supported image types SHALL be PNG and JPEG" and uploads MUST
# end in ".png" or ".jpeg". Kept to exactly those two to match the wire contract.
_ALLOWED_EXTENSIONS = {".png", ".jpeg"}


def _err(status: int, message: str):
    return jsonify({"error": {"http_status": status, "message": message}}), status


@views_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@views_bp.route("/classifier", methods=["POST"])
def classifier():
    username, jti, _role = check_token()
    if username is None:
        increment_fail()
        return _err(401, "Missing or invalid token")

    if "image" not in request.files:
        increment_fail()
        return _err(400, "No image field in request")

    file = request.files["image"]
    ext = os.path.splitext((file.filename or "").lower())[1]
    if ext not in _ALLOWED_EXTENSIONS:
        increment_fail()
        return _err(400, "Unsupported image format")

    image_bytes = file.read()
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image.load()
    except Exception:
        increment_fail()
        return _err(400, "Unsupported image format")

    try:
        # Imported lazily so the heavy torch dependency is only required when the
        # classifier route is actually exercised (keeps the test suite torch-free).
        from .classifier import get_classifier
        matches = get_classifier().predict(image)
    except Exception:
        set_health("error")
        increment_fail()
        return _err(500, "Model inference failed")

    # A successful inference proves classification is currently working, so clear
    # any prior "error" health (set by a transient failure or a failed warmup).
    set_health("ok")
    increment_success()
    return jsonify({"matches": matches}), 200


@views_bp.route("/profile", methods=["GET"])
def profile():
    # Any authenticated user can read their own profile. The role rides in the
    # token, so the response is self-describing for the client UI.
    username, _jti, role = check_token()
    if username is None:
        return _err(401, "Missing or invalid token")
    return jsonify({
        "username": username,
        "role": role,
        "profile": get_user_profile(username) or {},
    }), 200


@views_bp.route("/profile", methods=["PATCH"])
def update_profile():
    # Edit your own profile. Role rides in the token and is NOT editable here —
    # we rebuild the profile under the caller's existing role.
    username, _jti, role = check_token()
    if username is None:
        return _err(401, "Missing or invalid token")

    profile, err = build_profile(role, request.get_json(silent=True))
    if err is not None:
        return _err(400, err)

    # Re-classify the archetype from the rebuilt vector (stub until Dev A's model).
    if role == "player":
        profile["archetype"] = get_mlcore().archetype(profile["vector"])

    if not update_user_profile(username, profile):
        return _err(404, "User not found")
    return jsonify({"username": username, "role": role, "profile": profile}), 200


@views_bp.route("/profile/comparables", methods=["GET"])
def profile_comparables():
    # KNN comparables for the signed-in player: the k nearest NBA reference
    # players to their feature vector. Players only (scouts have no vector).
    username, _jti, role = check_token()
    if username is None:
        return _err(401, "Missing or invalid token")
    if role != "player":
        return _err(403, "Comparables are available to players only")

    vector = (get_user_profile(username) or {}).get("vector")
    if not vector:
        return _err(400, "Profile has no feature vector")

    k = request.args.get("k", default=DEFAULT_K, type=int) or DEFAULT_K
    k = max(1, min(k, MAX_K))
    return jsonify({"comparables": get_mlcore().comparables(vector, k)}), 200


@views_bp.route("/profile/interest", methods=["GET"])
def profile_interest():
    # Reverse fit-scorer: how many / which scouts' saved needs match this player
    # ("N scouts are looking for a profile like yours"). The SAME fit_score
    # function as the scout-side search, called in the opposite direction.
    username, _jti, role = check_token()
    if username is None:
        return _err(401, "Missing or invalid token")
    if role != "player":
        return _err(403, "Interest is available to players only")

    vector = (get_user_profile(username) or {}).get("vector")
    if not vector:
        return _err(400, "Profile has no feature vector")

    core = get_mlcore()
    matches = []
    for scout in get_users_by_role("scout"):
        need = scout["profile"].get("need")
        if not need:
            continue
        score = core.fit_score(core.need_to_vector(need), vector)
        if score >= INTEREST_THRESHOLD:
            matches.append({
                "org": scout["profile"].get("org"),
                "need": need,
                "score": round(score, 3),
            })
    matches.sort(key=lambda m: m["score"], reverse=True)
    return jsonify({"count": len(matches), "scouts": matches}), 200


@views_bp.route("/status", methods=["GET"])
def status():
    # Public health endpoint — no token required.
    counters = get_counters()
    return jsonify({
        "status": {
            "uptime": round(time.time() - startup_time, 3),
            "processed": {
                "success": counters["success"],
                "fail": counters["fail"],
            },
            "health": get_health(),
            "api_version": 1,
        }
    }), 200
