#!/usr/bin/env python3
"""Google Calendar menu bar app — shows your next event.

Made by Elijah Renner
"""

import os
import sys
import json
import fcntl
import datetime
import threading
import subprocess

import rumps
import objc
from AppKit import (
    NSImage, NSFont, NSColor, NSBezierPath, NSMakeRect, NSMakeSize,
    NSFontAttributeName, NSForegroundColorAttributeName,
    NSGraphicsContext, NSCompositingOperationSourceOver,
    NSString, NSStatusBar,
)
from PyObjCTools import AppHelper
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(APP_DIR, "token.json")
CREDS_PATH = os.path.join(APP_DIR, "credentials.json")
LOCK_PATH = os.path.join(APP_DIR, ".gcal_menubar.lock")

_lock_file = open(LOCK_PATH, "w")
try:
    fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit(0)
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
PREFS_PATH = os.path.join(APP_DIR, "prefs.json")
REFRESH_SECONDS = 60
MAX_TITLE_LEN = 20

ACCENT_COLORS = {
    "Green":        (0.24, 0.49, 0.25),
    "Stanford Red":  (0.55, 0.07, 0.09),
    "YC Orange":    (1.00, 0.40, 0.00),
    "Blue":         (0.20, 0.40, 0.80),
    "Purple":       (0.50, 0.25, 0.70),
    "Teal":         (0.18, 0.55, 0.55),
    "Pink":         (0.85, 0.25, 0.45),
    "Gray":         (0.45, 0.45, 0.45),
}
DEFAULT_COLOR = "Green"


def load_accent_color():
    if os.path.exists(PREFS_PATH):
        try:
            with open(PREFS_PATH) as f:
                return json.load(f).get("accent_color", DEFAULT_COLOR)
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_COLOR


def save_accent_color(name):
    prefs = {}
    if os.path.exists(PREFS_PATH):
        try:
            with open(PREFS_PATH) as f:
                prefs = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    prefs["accent_color"] = name
    with open(PREFS_PATH, "w") as f:
        json.dump(prefs, f)


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
    return f"{summary} {time_str}"


def make_pill_image(text, color_name=None):
    """Render text with a colored accent bar on the left."""
    font = NSFont.menuBarFontOfSize_(0)
    text_color = NSColor.blackColor()
    attrs = {
        NSFontAttributeName: font,
        NSForegroundColorAttributeName: text_color,
    }
    ns_text = NSString.stringWithString_(text)
    text_size = ns_text.sizeWithAttributes_(attrs)

    bar_w = 3
    gap = 5
    pad_r = 1
    h = 16
    w = bar_w + gap + text_size.width + pad_r

    img = NSImage.alloc().initWithSize_(NSMakeSize(w, h))
    img.lockFocus()

    # Colored vertical accent bar (rounded)
    r, g, b = ACCENT_COLORS.get(color_name or DEFAULT_COLOR, ACCENT_COLORS[DEFAULT_COLOR])
    accent = NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 0.9)
    accent.setFill()
    bar_inset = 1
    bar_rect = NSMakeRect(0, bar_inset, bar_w, h - bar_inset * 2)
    bar_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        bar_rect, bar_w / 2, bar_w / 2
    )
    bar_path.fill()

    # Draw text
    text_x = bar_w + gap
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
        self.accent_color = load_accent_color()
        self.creds = get_credentials()

        color_menu = rumps.MenuItem("Accent Color")
        self._color_items = {}
        for name in ACCENT_COLORS:
            item = rumps.MenuItem(name, callback=self._color_picked)
            item.state = name == self.accent_color
            self._color_items[name] = item
            color_menu.add(item)

        self.menu = [
            rumps.MenuItem("Skip", callback=self._skip_clicked),
            rumps.MenuItem("Refresh", callback=self._refresh_clicked),
            rumps.MenuItem("Open Google Calendar", callback=self._open_gcal),
            color_menu,
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]
        self.title = "Loading…"
        self._started = False
        self.timer = rumps.Timer(self._timer_tick, REFRESH_SECONDS)
        self.timer.start()

    def _set_pill(self, text):
        """Update the menu bar icon with accent bar + text."""
        color = self.accent_color
        def _update():
            try:
                nsitem = self._nsapp.nsstatusitem
                nsitem.setImage_(make_pill_image(text, color))
                nsitem.setTitle_("")
                nsitem.setHighlightMode_(True)
            except AttributeError:
                self.title = text
        AppHelper.callAfter(_update)

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

    def _color_picked(self, sender):
        self.accent_color = sender.title
        save_accent_color(sender.title)
        for name, item in self._color_items.items():
            item.state = name == sender.title
        if self.events:
            self._set_pill(format_title(self.events[self.event_index]))

    def _open_gcal(self, _):
        subprocess.Popen(["open", "-a", "Google Calendar"])

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
