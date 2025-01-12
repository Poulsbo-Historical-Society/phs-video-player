import os
import json
import vlc
import time
import logging
import subprocess
from flask import Flask, render_template, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

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
    "admin_password": generate_password_hash("admin")
}


class VideoPlayer:
    def __init__(self):
        self.instance = vlc.Instance(['--no-xlib'])
        self.player = self.instance.media_player_new()
        self.playlist = []
        self.current_index = 0
        self.load_config()

        # Set up event manager right away
        self.event_manager = self.player.event_manager()
        self.event_manager.event_attach(
            vlc.EventType.MediaPlayerEndReached, self._on_media_end)
        logger.info("VideoPlayer initialized")

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                self.config = json.load(f)
                logger.info(f"Loaded config from {CONFIG_FILE}")
        except FileNotFoundError:
            logger.info("No config file found, using defaults")
            self.config = DEFAULT_CONFIG.copy()
            self.save_config()

        # Scan videos directory and update available videos
        available_videos = []
        try:
            for file in os.listdir(VIDEO_DIR):
                if file.lower().endswith(('.mp4', '.avi', '.mkv')):
                    video_path = os.path.join(VIDEO_DIR, file)
                    # Check if video already exists in config
                    existing = next(
                        (v for v in self.config['videos'] if v['path'] == video_path), None)
                    if existing:
                        logger.info(f"Found existing video config for {file}")
                        available_videos.append(existing)
                    else:
                        logger.info(f"Adding new video: {file}")
                        available_videos.append({
                            'path': video_path,
                            'name': file,
                            'enabled': True,
                            'order': len(available_videos)
                        })

            self.config['videos'] = available_videos
            self.save_config()
            self.update_playlist()
        except Exception as e:
            logger.error(f"Error scanning video directory: {e}")

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
                logger.info("Config saved successfully")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def update_playlist(self):
        # Sort videos by order and filter enabled ones
        enabled_videos = sorted(
            [v for v in self.config['videos'] if v['enabled']],
            key=lambda x: x['order']
        )
        self.playlist = [v['path'] for v in enabled_videos]

        logger.info(f"Updated playlist with {len(self.playlist)} videos")
        logger.info(f"Playlist: {self.playlist}")

        # Force restart of playback
        self.current_index = 0
        if self.playlist:
            if self.player.is_playing():
                logger.info("Stopping current playback")
                self.player.stop()
            self.play_next()

    def _on_media_end(self, event):
        logger.info(f"Video ended (current_index: {self.current_index})")
        # We're in an event callback, so schedule the next video with a small delay
        import threading
        threading.Timer(0.5, self._play_next_delayed).start()

    def _play_next_delayed(self):
        self.current_index += 1
        if self.current_index >= len(self.playlist):
            logger.info("Reached end of playlist, restarting from beginning")
            self.current_index = 0
        self.play_next()

    def play_next(self):
        if not self.playlist:
            logger.warning("No videos in playlist")
            return

        video_path = self.playlist[self.current_index]
        logger.info(f"Playing video: {
                    video_path} (index: {self.current_index})")

        # Stop any current playback
        self.player.stop()

        # Check for matching subtitle file
        srt_path = os.path.splitext(video_path)[0] + '.srt'

        # Create and set new media
        media = self.instance.media_new(video_path)

        # If subtitle file exists, add it to the media
        if os.path.exists(srt_path):
            logger.info(f"Found subtitle file: {srt_path}")
            media.add_options(f'sub-file={srt_path}')
        else:
            logger.info("No subtitle file found")

        self.player.set_media(media)

        # Ensure we're in fullscreen mode
        self.player.set_fullscreen(True)

        # Small delay to ensure media is loaded
        time.sleep(0.1)

        # Play and verify it started
        result = self.player.play()
        logger.info(f"Play command result: {result}")

        # Wait a bit and check if we're actually playing
        time.sleep(0.2)
        if not self.player.is_playing():
            logger.error("Failed to start playback, retrying...")
            self.player.play()


player = VideoPlayer()

# Flask routes


@app.route('/')
def index():
    return render_template('index.html',
                           config=player.config,
                           museum_name="Poulsbo Historical Society")


@app.route('/update_config', methods=['POST'])
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
        player.update_playlist()
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/system/restart', methods=['POST'])
def restart_system():
    subprocess.run(['sudo', 'reboot'])
    return jsonify({'status': 'success'})


@app.route('/system/restart_daemon', methods=['POST'])
def restart_daemon():
    logger.info("Received restart request, terminating process...")
    os._exit(0)  # Force immediate exit, systemd will restart us


def main():
    app.run(host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()
