import os
import secrets

from flask import Flask, jsonify, request

from .auth import auth_bp
from .views import views_bp
from .models import increment_fail

# Endpoints whose errors count toward the /status "fail" tally (interface.md).
# /status and / are deliberately excluded.
_COUNTED_PATHS = {"/register", "/login", "/logout", "/classifier"}


def _count_fail_if_relevant():
    """Increment the fail counter when an error handler fires for a counted endpoint.

    View-level errors (400/401/409/500) already self-count; this covers the
    framework-raised errors (404/405/413) that never reach the view body.
    """
    if request.path in _COUNTED_PATHS:
        increment_fail()


def create_app(secret_key: str = None) -> Flask:
    app = Flask(__name__)
    # Prefer an explicit secret (arg > JWT_SECRET env) so tokens survive restarts and
    # stay valid across multiple workers/processes. Fall back to a random per-process
    # secret only for local single-process dev where stability isn't required.
    app.config["JWT_SECRET"] = secret_key or os.environ.get("JWT_SECRET") or secrets.token_hex(32)

    # Cap request bodies so an oversized upload can't exhaust memory in file.read().
    # 10 MiB comfortably covers any reasonable PNG/JPEG.
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

    app.register_blueprint(auth_bp)
    app.register_blueprint(views_bp)

    @app.errorhandler(405)
    def method_not_allowed(e):
        _count_fail_if_relevant()
        return jsonify({"error": {"http_status": 405, "message": "Method not allowed"}}), 405

    @app.errorhandler(413)
    def payload_too_large(e):
        # interface.md documents only 400 for bad /classifier input, so surface an
        # oversized body as a 400 rather than leaking a 413 outside the contract.
        _count_fail_if_relevant()
        return jsonify({"error": {"http_status": 400, "message": "Image too large"}}), 400

    @app.errorhandler(404)
    def not_found(e):
        _count_fail_if_relevant()
        return jsonify({"error": {"http_status": 404, "message": "Not found"}}), 404

    @app.errorhandler(Exception)
    def internal_error(e):
        # Last line of defence: any uncaught exception must still leave the server
        # standing and the wire contract intact — a JSON error envelope, never an
        # HTML traceback. Real HTTP errors (404/405/...) are handled above.
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        return jsonify({"error": {"http_status": 500, "message": "Internal server error"}}), 500

    # Load and warm up the classifier once at startup so the first request pays no latency
    from .classifier import get_classifier
    from . import models
    from PIL import Image
    try:
        clf = get_classifier()
        clf.predict(Image.new("RGB", (224, 224)))
    except Exception:
        models.set_health("error")

    # Load the ML core singleton once at startup (same single-load pattern as the
    # classifier). Real models live behind get_mlcore(); never reload per request.
    from .mlcore import get_mlcore
    try:
        get_mlcore()
    except Exception:
        models.set_health("error")

    return app
