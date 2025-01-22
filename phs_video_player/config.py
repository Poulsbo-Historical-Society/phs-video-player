import os
import json
import logging
from werkzeug.security import generate_password_hash
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigManager:
    DEFAULT_CONFIG = {
        "display_name": "Main Gallery Display",
        "videos": [],
        "admin_password": generate_password_hash("admin"),
        "preview_enabled": False,
        "dark_mode": True
    }

    def __init__(self, config_file: str, video_dir: str, snapshot_dir: str):
        """
        Initialize the configuration manager.

        Args:
            config_file: Path to the configuration file
            video_dir: Directory containing video files
        """
        self.config_file = config_file
        self.video_dir = video_dir
        self.snapshot_dir = snapshot_dir
        self.config: Dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from file or create default if not exists."""
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            logger.info("No config file found, creating default configuration")
            self.config = self.DEFAULT_CONFIG.copy()
            self.save_config()
        except json.JSONDecodeError:
            logger.error(
                "Invalid config file format, using default configuration")
            self.config = self.DEFAULT_CONFIG.copy()
            self.save_config()

        # Ensure all default keys exist
        for key, value in self.DEFAULT_CONFIG.items():
            if key not in self.config:
                self.config[key] = value

        # Update video list
        self._update_video_list()

    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            raise

    def _update_video_list(self) -> None:
        """Scan video directory and update video list with metadata."""
        available_videos = []
        existing_videos = {v['path']: v for v in self.config['videos']}

        try:
            for file in os.listdir(self.video_dir):
                if file.lower().endswith(('.mp4', '.avi', '.mkv')):
                    video_path = os.path.join(self.video_dir, file)

                    if video_path in existing_videos:
                        # Keep existing video entry but ensure all fields exist
                        video_entry = existing_videos[video_path].copy()
                        video_entry.setdefault('name', file)
                        video_entry.setdefault('enabled', True)
                        video_entry.setdefault('order', len(available_videos))
                        video_entry.setdefault('title', os.path.splitext(file)[
                                               0].replace('_', ' ').title())
                        video_entry.setdefault('description', '')
                        video_entry.setdefault('duration', 0)
                    else:
                        # Create new video entry
                        video_entry = {
                            'path': video_path,
                            'name': file,
                            'enabled': True,
                            'order': len(available_videos),
                            'title': os.path.splitext(file)[0].replace('_', ' ').title(),
                            'description': '',
                            'duration': 0
                        }

                    available_videos.append(video_entry)

            self.config['videos'] = available_videos
            self.save_config()

        except Exception as e:
            logger.error(f"Error updating video list: {e}")
            raise

    def update_display_name(self, name: str) -> None:
        """Update the display name in the configuration."""
        self.config['display_name'] = name
        self.save_config()

    def update_videos(self, videos: list) -> None:
        """
        Update video configurations while preserving metadata.

        Args:
            videos: List of video configurations to update
        """
        existing_videos = {v['path']: v for v in self.config['videos']}
        updated_videos = []

        for video in videos:
            existing = existing_videos.get(video['path'], {})
            updated_video = {
                'path': video['path'],
                'name': existing.get('name', video.get('name')),
                'title': existing.get('title', video.get('title')),
                'description': existing.get('description', video.get('description')),
                'duration': existing.get('duration', video.get('duration', 0)),
                'enabled': video['enabled'],
                'order': video['order']
            }
            updated_videos.append(updated_video)

        self.config['videos'] = updated_videos
        self.save_config()

    def get_enabled_videos(self) -> list:
        """Return list of enabled videos sorted by order."""
        enabled_videos = [v for v in self.config['videos'] if v['enabled']]
        return sorted(enabled_videos, key=lambda x: x['order'])

    def toggle_preview(self) -> bool:
        """Toggle preview state and return new state."""
        self.config['preview_enabled'] = not self.config.get(
            'preview_enabled', False)
        self.save_config()
        return self.config['preview_enabled']

    def toggle_dark_mode(self) -> bool:
        """Toggle dark mode state and return new state."""
        self.config['dark_mode'] = not self.config.get('dark_mode', True)
        self.save_config()
        return self.config['dark_mode']

    def update_password(self, new_password: str) -> None:
        """Update admin password."""
        self.config['admin_password'] = generate_password_hash(new_password)
        self.save_config()

    def get_config(self) -> Dict[str, Any]:
        """Return current configuration."""
        return self.config.copy()

    def get_video_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """Get video configuration by path."""
        for video in self.config['videos']:
            if video['path'] == path:
                return video.copy()
        return None
