import os
import json
import vlc
import time
import logging
import subprocess
import threading
import keyboard
import signal
import sys
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

DEFAULT_CONFIG = {
    "display_name": "Main Gallery Display",
    "videos": [],
    "admin_password": generate_password_hash("admin"),
    "preview_enabled": True
}


class VideoPlayer:
    def __init__(self):
        self.instance = vlc.Instance([
            '--no-xlib',  # Disable X11 dependency
            '--no-snapshot-preview',  # Disable snapshot preview window
            '--no-osd',  # Disable on-screen display
            '--no-video-title-show',  # Disable video title display
            '--no-video-title',  # Ensure no video title
            '--no-snapshot-sequential',  # Don't add number to snapshots
            '--fullscreen'
        ])
        self.list_player = self.instance.media_list_player_new()
        self.media_list = self.instance.media_list_new()
        self.list_player.set_media_list(self.media_list)

        # Get the underlying media player for fullscree
        self.player = self.list_player.get_media_player()
        self.player.set_fullscreen(True)

        self.snapshot_path = os.path.join(CONFIG_DIR, "current_frame.png")
        self.snapshot_lock = threading.Lock()
        self.snapshot_thread = None

        self.load_config()

        # Only start snapshot thread if preview is enabled
        self._start_or_stop_preview()

        logger.info("VideoPlayer initialized")

    def _snapshot_loop(self):
        """Continuously take snapshots of the video output"""
        while True:
            try:
                if self.player.is_playing():
                    with self.snapshot_lock:
                        self.player.video_take_snapshot(
                            0, self.snapshot_path, 0, 0)
            except Exception as e:
                logger.error(f"Error taking snapshot: {e}")
            time.sleep(1)  # Take snapshot every second

    def _start_or_stop_preview(self):
        """Start or stop the preview based on config"""
        preview_enabled = self.config.get('preview_enabled', False)

        # Stop existing thread if it's running
        if self.snapshot_thread and self.snapshot_thread.is_alive():
            logger.info("Stopping existing preview thread")
            self.snapshot_thread = None

        # Start new thread if preview is enabled
        if preview_enabled and not self.snapshot_thread:
            logger.info("Starting preview thread")
            self.snapshot_thread = threading.Thread(
                target=self._snapshot_loop, daemon=True)
            self.snapshot_thread.start()

        # Clean up snapshot file if preview is disabled
        if not preview_enabled and os.path.exists(self.snapshot_path):
            try:
                os.remove(self.snapshot_path)
            except Exception as e:
                logger.error(f"Error removing snapshot file: {e}")

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = DEFAULT_CONFIG.copy()
            self.save_config()

        # Scan videos directory and update available videos
        available_videos = []
        for file in os.listdir(VIDEO_DIR):
            if file.lower().endswith(('.mp4', '.avi', '.mkv')):
                video_path = os.path.join(VIDEO_DIR, file)
                # Check if video already exists in config
                existing = next(
                    (v for v in self.config['videos'] if v['path'] == video_path), None)
                if existing:
                    available_videos.append(existing)
                else:
                    available_videos.append({
                        'path': video_path,
                        'name': file,
                        'enabled': True,
                        'order': len(available_videos)
                    })

        self.config['videos'] = available_videos
        self.save_config()
        self.update_playlist()

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
                logger.info("Config saved successfully")
            # Update preview thread state after config save
            self._start_or_stop_preview()
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def update_playlist(self):
        # Clear existing playlist
        self.media_list.lock()
        while self.media_list.count() > 0:
            self.media_list.remove_index(0)

        # Add enabled videos in correct order
        enabled_videos = sorted(
            [v for v in self.config['videos'] if v['enabled']],
            key=lambda x: x['order']
        )

        for video in enabled_videos:
            media = self.instance.media_new(video['path'])
            self.media_list.add_media(media)

        self.media_list.unlock()

        # Start playback if not already playing
        if not self.list_player.is_playing():
            self.list_player.set_playback_mode(vlc.PlaybackMode.loop)
            self.list_player.play()


player = VideoPlayer()

# Flask routes


def check_auth(username, password):
    """Check if username/password combination is valid."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # We only check password since we're using a single admin user
            return check_password_hash(config.get('admin_password', DEFAULT_CONFIG['admin_password']), password)
    except FileNotFoundError:
        # If config doesn't exist, use default password
        return password == "admin"


def authenticate():
    """Send a 401 response that enables basic auth."""
    return Response(
        'Could not verify your credentials.\n'
        'Please login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


@app.route('/')
@requires_auth
def index():
    return render_template('index.html',
                           config=player.config,
                           museum_name="Poulsbo Historical Society")


@app.route('/system/restart_daemon', methods=['POST'])
@requires_auth
def restart_daemon():
    logger.info("Received restart request, terminating process...")
    os._exit(0)  # Force immediate exit, systemd will restart us


@app.route('/update_config', methods=['POST'])
@requires_auth
def update_config():
    try:
        data = request.get_json()
        logger.info("Received config update")

        if 'display_name' in data:
            player.config['display_name'] = data['display_name']
        if 'videos' in data:
            # Ensure order is properly set as integer
            for video in data['videos']:
                video['order'] = int(video['order'])
                video['enabled'] = bool(video['enabled'])
            player.config['videos'] = data['videos']

        player.save_config()
        restart_daemon()
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/system/restart', methods=['POST'])
@requires_auth
def restart_system():
    subprocess.run(['sudo', 'reboot'])
    return jsonify({'status': 'success'})


@app.route('/preview.png')
@requires_auth
def preview():
    """Serve the latest video snapshot"""
    if not player.config.get('preview_enabled', False):
        return '', 404

    try:
        if not os.path.exists(player.snapshot_path):
            return send_file('static/images/no-preview.png', mimetype='image/png')

        with player.snapshot_lock:
            return send_file(player.snapshot_path, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error serving preview: {e}")
        return send_file('static/images/no-preview.png', mimetype='image/png')


@app.route('/toggle_preview', methods=['POST'])
@requires_auth
def toggle_preview():
    try:
        player.config['preview_enabled'] = not player.config.get(
            'preview_enabled', False)
        player.save_config()
        return jsonify({'status': 'success', 'preview_enabled': player.config['preview_enabled']})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def cleanup():
    print("Stopping PHS Video Player...")
    # Stop systemd service and prevent auto-restart
    try:
        subprocess.run(['sudo', 'systemctl', 'stop', 'phs-video-player'])
        # Ensure the process exits
        sys.exit(0)
    finally:
        os._exit(0)


def main():
    from threading import Thread

    # Start Flask in a separate thread
    flask_thread = Thread(target=lambda: app.run(
        host='0.0.0.0', port=5000), daemon=True)
    flask_thread.start()

    print("PHS Video Player started. Press Ctrl+Q to stop.")

    # Register Ctrl+Q shortcut
    keyboard.add_hotkey('ctrl+q', cleanup)

    # Keep the main thread running to handle keyboard events
    keyboard.wait('ctrl+q')


if __name__ == '__main__':
    main()
