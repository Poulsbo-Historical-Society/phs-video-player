import vlc
import os
import logging
import threading
import math
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class VideoPlayer:
    def __init__(self, config_manager):
        """
        Initialize the video player with configuration manager.

        Args:
            config_manager: Instance of ConfigManager
        """
        self.config_manager = config_manager
        self.websocket_manager = None  # Will be set after initialization
        self.snapshot_path = os.path.join(os.path.dirname(
            config_manager.config_file), "current_frame.png")

        # Initialize VLC instances
        self.instance = vlc.Instance([
            '--no-xlib',
            '--no-snapshot-preview',
            '--no-osd',
            '--no-video-title-show',
            '--no-video-title',
            '--no-snapshot-sequential',
            '--fullscreen'
        ])

        # Separate instance for metadata extraction
        self.metadata_instance = vlc.Instance(['--no-video'])
        self.metadata_cache = {}

        # Initialize player components
        self.list_player = self.instance.media_list_player_new()
        self.media_list = self.instance.media_list_new()
        self.list_player.set_media_list(self.media_list)

        # Get the underlying media player for fullscreen
        self.player = self.list_player.get_media_player()
        self.player.set_fullscreen(True)

        # Preview handling
        self.snapshot_lock = threading.Lock()
        self.snapshot_thread = None
        self._start_or_stop_preview()

        # Initial playlist setup
        self.update_playlist()

    def set_websocket_manager(self, manager) -> None:
        """Set the WebSocket manager after initialization."""
        self.websocket_manager = manager

    def get_video_metadata(self, path: str) -> Dict[str, Any]:
        """
        Extract metadata from a video file using VLC.

        Args:
            path: Path to video file

        Returns:
            Dictionary containing video metadata
        """
        # Check cache first
        if path in self.metadata_cache:
            return self.metadata_cache[path]

        try:
            media = self.metadata_instance.media_new(path)
            media.parse()

            # Get duration in milliseconds and convert to minutes (rounded up)
            duration_ms = media.get_duration()
            duration_min = math.ceil(duration_ms / 60000)

            # Get title from metadata or use filename
            title = media.get_meta(vlc.Meta.Title)
            if not title:
                title = os.path.splitext(os.path.basename(path))[0]
                title = title.replace('_', ' ').replace('-', ' ').title()

            description = media.get_meta(vlc.Meta.Description) or ""

            metadata = {
                'title': title,
                'description': description,
                'duration': duration_min
            }

            # Cache the metadata
            self.metadata_cache[path] = metadata
            return metadata

        except Exception as e:
            logger.error(f"Error extracting metadata for {path}: {e}")
            metadata = {
                'title': os.path.splitext(os.path.basename(path))[0].replace('_', ' ').replace('-', ' ').title(),
                'description': '',
                'duration': 0
            }
            self.metadata_cache[path] = metadata
            return metadata

    def update_playlist(self) -> None:
        """Update the playlist based on enabled videos in config."""
        # Stop current playback
        self.list_player.stop()

        # Clear existing playlist
        self.media_list.lock()
        while self.media_list.count() > 0:
            self.media_list.remove_index(0)

        # Add enabled videos in correct order
        enabled_videos = self.config_manager.get_enabled_videos()

        for video in enabled_videos:
            media = self.instance.media_new(video['path'])
            self.media_list.add_media(media)

        self.media_list.unlock()

        # Start playback
        self.list_player.set_playback_mode(vlc.PlaybackMode.loop)
        self.list_player.play()

        # Notify websocket clients of playlist change
        if self.websocket_manager:
            self.websocket_manager.notify_playlist_change()

    def _snapshot_loop(self) -> None:
        """Continuously take snapshots of the video output."""
        while self.config_manager.config['preview_enabled']:
            try:
                if self.player.is_playing():
                    with self.snapshot_lock:
                        self.player.video_take_snapshot(
                            0, self.snapshot_path, 0, 0)
            except Exception as e:
                logger.error(f"Error taking snapshot: {e}")
            threading.Event().wait(1.0)  # Sleep for 1 second

    def _start_or_stop_preview(self) -> None:
        """Start or stop the preview based on config."""
        preview_enabled = self.config_manager.config['preview_enabled']

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

    def get_current_video(self) -> Optional[Dict[str, Any]]:
        """Get information about currently playing video."""
        media = self.player.get_media()
        if not media:
            return None

        mrl = media.get_mrl()
        # Find video info from config
        for video in self.config_manager.config['videos']:
            if video['path'] in mrl:
                return {
                    'title': video['title'],
                    'duration': video['duration'],
                    'path': video['path']
                }
        return None

    def get_playback_status(self) -> Dict[str, Any]:
        """Get current playback status."""
        return {
            'playing': self.player.is_playing(),
            'current_time': self.player.get_time() // 1000,  # Convert to seconds
            'current_video': self.get_current_video()
        }

    def preview_enabled(self) -> bool:
        """Check if preview is enabled."""
        return self.config_manager.config['preview_enabled']

    def update_metadata(self, video_path: str) -> None:
        """Update metadata for a specific video."""
        video = self.config_manager.get_video_by_path(video_path)
        if video:
            metadata = self.get_video_metadata(video_path)
            video.update(metadata)
            self.config_manager.save_config()

    def shutdown(self) -> None:
        """Clean shutdown of video player."""
        self.list_player.stop()
        if self.snapshot_thread:
            self.config_manager.config['preview_enabled'] = False
            self.snapshot_thread.join(timeout=1)
