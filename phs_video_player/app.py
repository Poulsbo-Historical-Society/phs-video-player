import os
import logging
from routes import init_routes
from config import ConfigManager
from video_player import VideoPlayer
from websocket import socketio, WebSocketManager
from flask import Flask, render_template, request, jsonify, Response, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the package directory
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

# Configuration
VIDEO_DIR = os.environ.get('PHS_VIDEO_DIR', "/path/to/videos")
CONFIG_DIR = os.environ.get(
    'PHS_CONFIG_DIR', os.path.expanduser('~/.phs-video-player'))
CONFIG_FILE = os.path.join(CONFIG_DIR, "player_config.json")

# Ensure config directory exists
os.makedirs(CONFIG_DIR, exist_ok=True)


def create_app():
    app = Flask(__name__)

    # Ensure config directory exists
    os.makedirs(CONFIG_DIR, exist_ok=True)

    # Initialize player
    config_manager = ConfigManager(CONFIG_FILE, VIDEO_DIR, CONFIG_DIR)
    player = VideoPlayer(config_manager)

    # Initialize WebSocket
    socketio.init_app(app)
    websocket_manager = WebSocketManager(player)
    player.set_websocket_manager(websocket_manager)

    # Initialize routes
    routes_bp = init_routes(config_manager, player)
    app.register_blueprint(routes_bp)

    return app


def main():
    app = create_app()
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()
