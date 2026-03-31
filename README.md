# GCal Menu Bar

A lightweight macOS menu bar app that shows your next Google Calendar event. Built with Python and rumps.

## Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Google Calendar API**.
3. Create OAuth 2.0 credentials (Desktop application) and download `credentials.json`.
4. Place `credentials.json` in the project directory.
5. Run the app — it will open a browser window for Google sign-in on first launch.

## Run from source

```bash
pip3 install rumps google-api-python-client google-auth-oauthlib
python3 gcal_menubar.py
```

## Build .app bundle

```bash
pip3 install py2app
python3 setup.py py2app
```

The built app will be in `dist/GCal Menu Bar.app`.
