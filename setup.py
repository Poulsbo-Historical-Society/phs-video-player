from setuptools import setup, find_packages

setup(
    name="phs-video-player",
    version="0.1",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "Flask>=3.0.0",
        "python-vlc>=3.0.20123",
        "Werkzeug>=3.0.1",
    ],
    entry_points={
        "console_scripts": [
            "phs-video-player=phs_video_player.app:main",
        ],
    },
)