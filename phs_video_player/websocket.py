from flask_socketio import SocketIO, emit
import time
import threading
import logging

logger = logging.getLogger(__name__)

socketio = SocketIO()


class WebSocketManager:
    def __init__(self, player):
        self.player = player
        self.status_thread = None
        self.running = False

        # Register handlers
        @socketio.on('connect')
        def handle_connect():
            # Send initial metadata
            emit('metadata_update', {
                'videos': self.player.config_manager.config['videos'],
                'display_name': self.player.config_manager.config['display_name']
            })

            # Send current playlist
            self._send_playlist_update()

            # Start status updates if not already running
            self._ensure_status_updates()

    def _ensure_status_updates(self):
        if not self.status_thread or not self.status_thread.is_alive():
            self.running = True
            self.status_thread = threading.Thread(
                target=self._status_update_loop)
            self.status_thread.daemon = True
            self.status_thread.start()

    def _status_update_loop(self):
        while self.running:
            try:
                current_status = self._get_current_status()
                socketio.emit('status_update', current_status)
            except Exception as e:
                logger.error(f"Error in status update: {e}")
            time.sleep(5)

    def _get_current_status(self):
        player = self.player.player  # Get VLC media player instance
        return {
            'playing': player.is_playing(),
            'current_time': player.get_time() // 1000,  # Convert to seconds
            'current_video': self._get_current_video_info()
        }

    def _get_current_video_info(self):
        media = self.player.player.get_media()
        if not media:
            return None

        mrl = media.get_mrl()
        # Find video info from config
        for video in self.player.config_manager.config['videos']:
            if video['path'] in mrl:
                return {
                    'title': video['title'],
                    'duration': video['duration'],
                    'path': video['path']
                }
        return None

    def _send_playlist_update(self):
        enabled_videos = [
            v for v in self.player.config_manager.config['videos'] if v['enabled']]
        enabled_videos.sort(key=lambda x: x['order'])
        socketio.emit('playlist_update', {'playlist': enabled_videos})

    def notify_playlist_change(self):
        """Called when the playlist is modified"""
        self._send_playlist_update()

    def shutdown(self):
        """Clean shutdown of WebSocket manager"""
        self.running = False
        if self.status_thread:
            self.status_thread.join(timeout=1)
