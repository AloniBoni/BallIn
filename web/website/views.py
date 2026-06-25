import io
import os
import time

from flask import Blueprint, request, jsonify, render_template
from PIL import Image

from .auth import check_token
from .classifier import get_classifier
from .models import (
    get_health, set_health,
    get_counters, startup_time,
    increment_success, increment_fail,
)

views_bp = Blueprint("views", __name__)

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
