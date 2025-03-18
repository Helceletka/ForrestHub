from pathlib import Path

from app.custom_loader import CustomLoader
from app.database import Database
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")
db = Database()


def path_exists(path):
    """Vrací True, pokud cesta existuje, jinak False."""
    return Path(path).exists()


def create_app(config_class: object | str, ssl_context=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Enable CORS
    CORS(app)


    # Initialize the database
    db.init(app.config["EXECUTABLE_DIR"], app.config["DATAFILE"] + ".json")

    # Set custom Jinja loader
    loader_locations = [
        app.config.get("GAMES_FOLDER"),
        app.config.get("TEMPLATES_FOLDER"),
        app.config.get("ASSETS_FOLDER"),
        app.config.get("PAGES_FOLDER"),
        app.config.get("GAMES_FOLDER_LIVE"),
    ]

    app.jinja_loader = CustomLoader(loader_locations)

    # Add custom Jinja filter
    app.jinja_env.filters["path_exists"] = path_exists

    # Register Blueprints
    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from app.errors import errors as errors_blueprint
    app.register_blueprint(errors_blueprint)

    # Import and register SocketIO events
    from app.socketio_events import socketio_bp as socketio_blueprint
    app.register_blueprint(socketio_blueprint)

    # Initialize SocketIO with eventlet support
    # socketio.init_app(app, cors_allowed_origins="*", ssl_context=ssl_context)
    app.run(host="0.0.0.0", ssl_context=ssl_context, debug=True, use_reloader=False, port=app.config.get("PORT"))

    # Spustit asynchronní úkol na pozadí
    socketio.start_background_task(db.save_data_periodically)

    return app
