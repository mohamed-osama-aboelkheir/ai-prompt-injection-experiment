"""
AI transcript-processing routes.

One endpoint, parametrized by ?defense=<name>, replaces the two near-identical routes
of the original. The authenticated user's id/team_id are threaded into the pipeline so
scoped defenses can enforce them (the original computed them and threw them away).

  GET  /api/ai/defenses                      -> catalog of defenses + availability
  POST /api/ai/process-transcript?defense=X  -> run a transcript through defense X
       optional query params: app_model, guardrail_model  (per-request model swap)
"""
import asyncio
import sys
from pathlib import Path

from flask import Blueprint, request, jsonify

from auth import require_auth, get_current_user

# Make backend/ importable so `defenses` and `agents` packages resolve.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import defenses  # noqa: E402
from llm import resolve_model  # noqa: E402

ai_bp = Blueprint("ai", __name__)

ALLOWED_EXTENSIONS = {"txt", "md", "markdown"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@ai_bp.route("/defenses", methods=["GET"])
def list_defenses():
    """Catalog of available defenses (for the UI dropdown / curl discovery)."""
    return jsonify({"defenses": defenses.describe()}), 200


@ai_bp.route("/process-transcript", methods=["POST"])
@require_auth
def process_transcript():
    user = get_current_user()
    if not user.team_id:
        return jsonify({"error": "User does not belong to a team"}), 400

    defense = request.args.get("defense", "none")
    if defense not in defenses.PROFILES:
        return jsonify({"error": f"Unknown defense {defense!r}", "known": defenses.DEFENSES}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed. Use .txt or .md files"}), 400

    try:
        transcript = file.read().decode("utf-8")
    except Exception as e:
        return jsonify({"error": f"Error reading file: {str(e)}"}), 400

    # Per-request model overrides (optional) — makes model-swapping a query param.
    try:
        app_model = resolve_model("app_model", override=request.args.get("app_model"))
        # Only resolve (and key-check) the judge when this defense actually runs it.
        guardrail_model = (resolve_model("guardrail_model", override=request.args.get("guardrail_model"))
                           if "guardrail" in defenses.PROFILES[defense]["prefilters"] else None)
    except ValueError as e:  # model's provider key missing / not reachable
        return jsonify({"error": str(e)}), 400

    caller = {"user_id": user.id, "team_id": user.team_id}
    try:
        result = asyncio.run(
            defenses.run_pipeline(
                defense, transcript, caller,
                app_model=app_model, guardrail_model=guardrail_model,
            )
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error processing transcript: {str(e)}"}), 500

    # Clean HTTP semantics: a blocked/unavailable defense is still a 200 with status.
    message = {
        "processed": "Transcript processed",
        "blocked": f"Transcript blocked by {result.get('blocked_by')}",
        "unavailable": f"Defense unavailable: {result.get('unavailable_reason')}",
    }.get(result["status"], "Transcript processed")
    return jsonify({"message": message, "result": result}), 200
