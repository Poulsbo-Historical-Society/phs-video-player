class VideoPlayerClient {
    constructor(options = {}) {
        this.socket = io(options.socketUrl);
        this.baseUrl = options.baseUrl || '';
        this.onConnectionChange = options.onConnectionChange;
        this.onMetadataUpdate = options.onMetadataUpdate;
        this.onPlaylistUpdate = options.onPlaylistUpdate;
        this.onStatusUpdate = options.onStatusUpdate;

        this._setupSocketHandlers();
    }

    _setupSocketHandlers() {
        // Connection handling
        this.socket.on('connect', () => {
            if (this.onConnectionChange) {
                this.onConnectionChange(true);
            }
        });

        this.socket.on('disconnect', () => {
            if (this.onConnectionChange) {
                this.onConnectionChange(false);
            }
        });

        // Data updates
        this.socket.on('metadata_update', (data) => {
            if (this.onMetadataUpdate) {
                this.onMetadataUpdate(data);
            }
        });

        this.socket.on('playlist_update', (data) => {
            if (this.onPlaylistUpdate) {
                this.onPlaylistUpdate(data);
            }
        });

        this.socket.on('status_update', (data) => {
            if (this.onStatusUpdate) {
                this.onStatusUpdate(data);
            }
        });
    }

    // API Methods
    async updateConfig(config) {
        try {
            const response = await fetch(`${this.baseUrl}/update_config`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error updating config:', error);
            throw error;
        }
    }

    async togglePreview() {
        try {
            const response = await fetch(`${this.baseUrl}/toggle_preview`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error toggling preview:', error);
            throw error;
        }
    }

    async restartSystem() {
        try {
            const response = await fetch(`${this.baseUrl}/system/restart`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error restarting system:', error);
            throw error;
        }
    }

    async restartDaemon() {
        try {
            const response = await fetch(`${this.baseUrl}/system/restart_daemon`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error restarting daemon:', error);
            throw error;
        }
    }

    // Video selection helper
    async selectVideo(videoData) {
        const videos = Array.from(document.querySelectorAll('.video-item'))
            .map((item, index) => ({
                path: item.dataset.path,
                name: item.dataset.name,
                enabled: item === videoData.element,
                order: index
            }));

        await this.updateConfig({
            display_name: document.querySelector('h2').textContent,
            videos: videos
        });
    }

    // Utility methods
    formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    disconnect() {
        this.socket.disconnect();
    }
}