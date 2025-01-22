from flask import Blueprint, render_template, request, jsonify, Response, send_file
from werkzeug.security import check_password_hash
from functools import wraps
import subprocess
import os
import logging

logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint('routes', __name__)


def check_auth(username, password):
    """Check if username/password combination is valid."""
    try:
        # Access config through current_app
        config = bp.config_manager.get_config()
        return check_password_hash(config['admin_password'], password)
    except Exception as e:
        logger.error(f"Auth error: {e}")
        return False


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


def init_routes(config_manager, video_player):
    """Initialize routes with required dependencies."""
    bp.config_manager = config_manager
    bp.video_player = video_player

    @bp.route('/')
    @requires_auth
    def index():
        return render_template('index.html',
                               config=config_manager.get_config(),
                               museum_name="Poulsbo Historical Society")

    @bp.route('/simple')
    @requires_auth
    def simple():
        return render_template('simple.html',
                               config=config_manager.get_config(),
                               museum_name="Poulsbo Historical Society")

    @bp.route('/update_config', methods=['POST'])
    @requires_auth
    def update_config():
        try:
            data = request.get_json()
            logger.info("Received config update")

            if 'display_name' in data:
                config_manager.update_display_name(data['display_name'])

            if 'videos' in data:
                config_manager.update_videos(data['videos'])
                video_player.update_playlist()

            return jsonify({'status': 'success'})
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @bp.route('/system/restart', methods=['POST'])
    @requires_auth
    def restart_system():
        try:
            subprocess.run(['sudo', 'reboot'])
            return jsonify({'status': 'success'})
        except Exception as e:
            logger.error(f"Error restarting system: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @bp.route('/system/restart_daemon', methods=['POST'])
    @requires_auth
    def restart_daemon():
        logger.info("Received restart request, terminating process...")
        os._exit(0)  # Force immediate exit, systemd will restart us

    @bp.route('/preview.png')
    @requires_auth
    def preview():
        """Serve the latest video snapshot"""
        config = config_manager.get_config()
        if not config.get('preview_enabled', False):
            return '', 404

        try:
            snapshot_path = video_player.get_snapshot_path()
            if not os.path.exists(snapshot_path):
                return send_file('static/images/no-preview.png', mimetype='image/png')

            with video_player.snapshot_lock:
                return send_file(snapshot_path, mimetype='image/png')
        except Exception as e:
            logger.error(f"Error serving preview: {e}")
            return send_file('static/images/no-preview.png', mimetype='image/png')

    @bp.route('/toggle_preview', methods=['POST'])
    @requires_auth
    def toggle_preview():
        try:
            preview_enabled = config_manager.toggle_preview()
            video_player.handle_preview_toggle(preview_enabled)
            return jsonify({
                'status': 'success',
                'preview_enabled': preview_enabled
            })
        except Exception as e:
            logger.error(f"Error toggling preview: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @bp.route('/toggle_dark_mode', methods=['POST'])
    @requires_auth
    def toggle_dark_mode():
        try:
            dark_mode = config_manager.toggle_dark_mode()
            return jsonify({
                'status': 'success',
                'dark_mode': dark_mode
            })
        except Exception as e:
            logger.error(f"Error toggling dark mode: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @bp.route('/update_password', methods=['POST'])
    @requires_auth
    def update_password():
        try:
            data = request.get_json()
            new_password = data.get('password')
            if not new_password:
                return jsonify({'status': 'error', 'message': 'No password provided'}), 400

            config_manager.update_password(new_password)
            return jsonify({'status': 'success'})
        except Exception as e:
            logger.error(f"Error updating password: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    return bp
