# PHS Video Player

A simple, robust video player system for the Poulsbo Historical Society museum displays. This system provides a web interface for managing video playlists across multiple display units, with automatic playback in a kiosk-mode setup.

## Features

- Simple web interface for managing video playlists
- Drag-and-drop reordering of videos
- Enable/disable videos without removing them
- Automatic looping playback
- Kiosk mode operation
- Persists configuration across reboots
- Support for multiple video formats via VLC
- Configurable display names for easy identification

## System Requirements

- Ubuntu Linux (tested on 22.04 LTS)
- Python 3.8+
- VLC media player
- Web browser (for admin interface)

## Installation

1. Install system dependencies:
```bash
sudo apt-get update
sudo apt-get install python3-pip vlc

# install python3.12
wget -qO- https://pascalroeleven.nl/deb-pascalroeleven.gpg | sudo tee /etc/apt/keyrings/deb-pascalroeleven.gpg
cat <<EOF | sudo tee /etc/apt/sources.list.d/pascalroeleven.sources
Types: deb
URIs: http://deb.pascalroeleven.nl/python3.12
Suites: bookworm-backports
Components: main
Signed-By: /etc/apt/keyrings/deb-pascalroeleven.gpg
EOF
sudo apt update
sudo apt install python3.12 python3.12-venv
```

2. Create the video directory:
```bash
sudo mkdir /opt/phs-videos
sudo chown $USER:$USER /opt/phs-videos
```

3. Install the PHS Video Player:
```bash
# Clone the repository
cd /opt
git clone https://github.com/Poulsbo-Historical-Society/phs-video-player.git
cd phs-video-player

# Create and activate virtual environment
python3.12 -m venv venv

# Install the package
sudo su
source venv/bin/activate
pip3 install -r requirements.txt
```

4. Configure the environment:
```bash
# Create environment file
sudo tee /etc/environment << 'EOF'
PHS_VIDEO_DIR=/opt/phs-videos
PHS_CONFIG_DIR=/opt/phs-video-player/config
EOF

# Reload environment variables
source /etc/environment
```

5. Create and enable the systemd service:
```bash
# Install service file
sudo tee /etc/systemd/system/phs-video-player.service << 'EOF'
[Unit]
Description=PHS Video Player
After=network.target

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
SupplementaryGroups=input
Environment=DISPLAY=:0
EnvironmentFile=/etc/environment
WorkingDirectory=/opt/phs-video-player
ExecStart=/bin/bash -c 'source venv/bin/activate && python phs_video_player/app.py'
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable phs-video-player
sudo systemctl start phs-video-player
```

## Usage

1. Place your video files in `/opt/phs-videos`

2. Access the admin interface:
   - From the display machine: Already visible in kiosk mode
   - From another computer on the network: `http://<display-ip>:5000`

3. Using the admin interface:
   - Set a display name to identify this unit
   - Enable/disable videos using checkboxes
   - Drag and drop to reorder videos
   - Click "Save Changes" to update the playlist
   - Use "Restart Video Player" if videos aren't playing correctly
   - Use "Restart Display System" only if necessary

## File Formats

Supported video formats include:
- MP4 (H.264)
- AVI
- MKV
- Other formats supported by VLC
