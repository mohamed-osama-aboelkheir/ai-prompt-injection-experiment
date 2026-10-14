import os

from flask import Flask
from flask_cors import CORS

from config import Config
from models import db
from routes.auth_routes import auth_bp
from routes.team_routes import team_bp
from routes.task_routes import task_bp
from routes.ai_routes import ai_bp


def create_app():
    # Fail fast if the JWT secret is missing, rather than signing tokens with None.
    if not Config.JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET is not set. Set it in your .env (e.g. `openssl rand -hex 32`)."
        )

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    CORS(app)  # Enable CORS for the React frontend

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(team_bp, url_prefix="/api/team")
    app.register_blueprint(task_bp, url_prefix="/api/tasks")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    # Debug off by default; opt in with FLASK_DEBUG=1 for local development only.
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=5000)
