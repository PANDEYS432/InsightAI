"""
agent_routes.py
Flask Blueprint — adds the Accident Data Agent as a parallel feature.
Register in app.py with:
    from agent_routes import agent_bp
    app.register_blueprint(agent_bp)
"""

import uuid
import logging
import os

import requests
from flask import Blueprint, render_template, request, jsonify, session

logger = logging.getLogger(__name__)

agent_bp = Blueprint("agent", __name__)

_agents: dict = {}


def _get_agent():
    from models.agent_tools.agent import AccidentAgent

    sid = session.setdefault("id", str(uuid.uuid4()))
    if sid not in _agents:
        _agents[sid] = AccidentAgent(
            backend=os.getenv("AGENT_BACKEND", "sarvam"),
            data_api_base=os.getenv("DATA_API_BASE_URL", "http://localhost:8001"),
            sarvam_api_key=os.getenv("SARVAM_API_KEY", ""),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        )
    return _agents[sid]


@agent_bp.route("/agent")
def agent_page():
    return render_template("agent.html")


@agent_bp.route("/agent/chat", methods=["POST"])
def agent_chat():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()

    if not user_message:
        return jsonify({"success": False, "error": "No message provided"}), 400

    agent = _get_agent()
    try:
        response = agent.chat(user_message)
        return jsonify({"success": True, "response": response})
    except Exception as exc:
        logger.error("Agent chat error: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@agent_bp.route("/agent/reset", methods=["POST"])
def agent_reset():
    _get_agent().reset()
    return jsonify({"success": True, "status": "conversation reset"})


@agent_bp.route("/agent/datasets")
def agent_datasets():
    base = os.getenv("DATA_API_BASE_URL", "http://localhost:8001")
    try:
        resp = requests.get(f"{base}/datasets", timeout=5)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.ConnectionError:
        return jsonify({
            "error": "Data API not running. Start: uvicorn accident_api.main:app --port 8001"
        }), 503
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503


@agent_bp.route("/agent/status")
def agent_status():
    base = os.getenv("DATA_API_BASE_URL", "http://localhost:8001")
    backend = os.getenv("AGENT_BACKEND", "sarvam")
    try:
        resp = requests.get(f"{base}/", timeout=3)
        data = resp.json()
        return jsonify({
            "data_api": "ok",
            "backend": backend,
            "loaded_datasets": data.get("loaded_datasets", "?"),
        })
    except Exception:
        return jsonify({"data_api": "unreachable", "backend": backend}), 503
