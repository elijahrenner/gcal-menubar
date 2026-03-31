#!/usr/bin/env python3
"""Google Calendar menu bar app — shows your next event."""

import os
import sys
import json
import datetime
import threading
import webbrowser

import rumps
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(APP_DIR, "token.json")
CREDS_PATH = os.path.join(APP_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
REFRESH_SECONDS = 60


def get_credentials():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_PATH):
                rumps.alert(
                    "Setup needed",
                    f"Place your Google OAuth credentials.json in:\n{APP_DIR}",
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


def fetch_next_event(creds):
    service = build("calendar", "v3", credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=5,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return result.get("items", [])


def format_time(event):
    start = event["start"].get("dateTime", event["start"].get("date"))
    if "T" in start:
        dt = datetime.datetime.fromisoformat(start)
        now = datetime.datetime.now(dt.tzinfo)
        diff = dt - now
        minutes = int(diff.total_seconds() / 60)
        if minutes < 0:
            return "now"
        elif minutes < 60:
            return f"in {minutes}m"
        elif minutes < 1440:
            hours = minutes // 60
            mins = minutes % 60
            return f"in {hours}h{mins}m" if mins else f"in {hours}h"
        else:
            return dt.strftime("%a %I:%M %p").replace(" 0", " ")
    else:
        event_date = datetime.date.fromisoformat(start)
        today = datetime.date.today()
        diff = (event_date - today).days
        if diff == 0:
            return "today"
        elif diff == 1:
            return "tomorrow"
        else:
            return event_date.strftime("%a %b %d").replace(" 0", " ")


def format_title(event):
    summary = event.get("summary", "No title")
    time_str = format_time(event)
    if len(summary) > 30:
        summary = summary[:28] + "…"
    return f"📅 {summary} — {time_str}"


class CalendarMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__("📅 Loading…", quit_button=None)
        self.events = []
        self.creds = get_credentials()
        self.menu = [
            rumps.MenuItem("Refresh", callback=self._refresh_clicked),
            rumps.MenuItem("Open Google Calendar", callback=self._open_gcal),
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]
        self._refresh()
        self.timer = rumps.Timer(self._timer_tick, REFRESH_SECONDS)
        self.timer.start()

    def _timer_tick(self, _):
        threading.Thread(target=self._refresh, daemon=True).start()

    def _refresh_clicked(self, _):
        threading.Thread(target=self._refresh, daemon=True).start()

    def _open_gcal(self, _):
        webbrowser.open("https://calendar.google.com")

    def _refresh(self):
        try:
            if self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            self.events = fetch_next_event(self.creds)
            if self.events:
                self.title = format_title(self.events[0])
            else:
                self.title = "📅 No upcoming events"
        except Exception as e:
            self.title = "📅 ⚠ Error"
            print(f"Refresh error: {e}", file=sys.stderr)


if __name__ == "__main__":
    CalendarMenuBarApp().run()
