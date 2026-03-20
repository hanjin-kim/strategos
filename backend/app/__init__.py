from flask import Flask, jsonify
from flask_cors import CORS


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    try:
        from app.api.scenario import scenario_bp
        app.register_blueprint(scenario_bp)
    except ImportError:
        pass

    try:
        from app.api.simulation import simulation_bp
        app.register_blueprint(simulation_bp)
    except ImportError:
        pass

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad request", "message": str(error)}), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found", "message": str(error)}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error", "message": str(error)}), 500

    return app
