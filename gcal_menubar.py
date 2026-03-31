#!/usr/bin/env python3
"""Google Calendar menu bar app — shows your next event."""

import os
import sys
import json
import datetime
import threading
import webbrowser

import rumps
import objc
from AppKit import (
    NSImage, NSFont, NSColor, NSBezierPath, NSMakeRect, NSMakeSize,
    NSFontAttributeName, NSForegroundColorAttributeName,
    NSGraphicsContext, NSCompositingOperationSourceOver,
    NSString, NSStatusBar,
)
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(APP_DIR, "token.json")
CREDS_PATH = os.path.join(APP_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
REFRESH_SECONDS = 60
MAX_TITLE_LEN = 20


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
    if len(summary) > MAX_TITLE_LEN:
        summary = summary[: MAX_TITLE_LEN - 1] + "…"
    return f"{summary} — {time_str}"


def make_pill_image(text):
    """Render text into a rounded-pill image for the menu bar."""
    font = NSFont.systemFontOfSize_weight_(11, 0.5)
    text_color = NSColor.blackColor()
    attrs = {
        NSFontAttributeName: font,
        NSForegroundColorAttributeName: text_color,
    }
    ns_text = NSString.stringWithString_(text)
    text_size = ns_text.sizeWithAttributes_(attrs)

    pad_x, pad_y = 10, 3
    stroke_w = 1.0
    w = text_size.width + pad_x * 2
    h = text_size.height + pad_y * 2
    h = min(h, 18)

    img = NSImage.alloc().initWithSize_(NSMakeSize(w, h))
    img.lockFocus()

    # Faint transparent background fill
    bg = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.5, 0.5, 0.5, 0.15)
    bg.setFill()
    radius = 4
    pill = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(0, 0, w, h), radius, radius
    )
    pill.fill()

    # Draw text centered
    text_x = (w - text_size.width) / 2
    text_y = (h - text_size.height) / 2
    ns_text.drawAtPoint_withAttributes_((text_x, text_y), attrs)

    img.unlockFocus()
    img.setTemplate_(False)
    return img


class CalendarMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__("", quit_button=None)
        self.events = []
        self.event_index = 0
        self.creds = get_credentials()
        self.menu = [
            rumps.MenuItem("Skip", callback=self._skip_clicked),
            rumps.MenuItem("Refresh", callback=self._refresh_clicked),
            rumps.MenuItem("Open Google Calendar", callback=self._open_gcal),
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]
        self.title = "Loading…"
        self._started = False
        self.timer = rumps.Timer(self._timer_tick, REFRESH_SECONDS)
        self.timer.start()

    def _set_pill(self, text):
        """Update the menu bar icon to a pill with the given text."""
        try:
            button = self._app.nsStatusItem.button()
            self.title = None
            button.setImage_(make_pill_image(text))
            button.setImagePosition_(0)  # NSImageOnly
        except AttributeError:
            self.title = text

    def _timer_tick(self, _):
        if not self._started:
            self._started = True
            self._refresh()
        else:
            threading.Thread(target=self._refresh, daemon=True).start()

    def _skip_clicked(self, _):
        if self.events and len(self.events) > 1:
            self.event_index = (self.event_index + 1) % len(self.events)
            self._set_pill(format_title(self.events[self.event_index]))

    def _refresh_clicked(self, _):
        self.event_index = 0
        threading.Thread(target=self._refresh, daemon=True).start()

    def _open_gcal(self, _):
        webbrowser.open("https://calendar.google.com")

    def _refresh(self):
        try:
            if self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            self.events = fetch_next_event(self.creds)
            if self.event_index >= len(self.events):
                self.event_index = 0
            if self.events:
                self._set_pill(format_title(self.events[self.event_index]))
            else:
                self._set_pill("No upcoming events")
        except Exception as e:
            self._set_pill("⚠ Error")
            print(f"Refresh error: {e}", file=sys.stderr)


if __name__ == "__main__":
    CalendarMenuBarApp().run()
