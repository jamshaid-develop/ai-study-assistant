"""
timer_utils.py — Live session state machine for the Study Planner
(PRD Sections 3.8 and 3.7b), now aware of both start AND end time.

Session lifecycle (per subject, each day):
  now <  start                → "upcoming"      (green if >5min away, blue if within 5min)
  start <= now < end          → "active":
        Status == Started      -> green, "In Progress — ends in Xm"
        Status == Pending,
          within 5min of start -> blue, "Starting now"
        Status == Pending,
          more than 5min in    -> red, "Xm late"
  now >= end                  → "ended"          -> always green, shows countdown to the
                                                     NEXT occurrence, and the caller should
                                                     reset Status back to Pending in the Sheet
                                                     so nothing stays stale into the next day.
"""

from datetime import datetime, time as dt_time, timedelta

LATE_GRACE_MINUTES = 5      # how long after start a "Pending" session gets a blue grace period before going red
UPCOMING_WINDOW_MINUTES = 5  # how close to start time the "upcoming" badge turns blue

STATUS_STARTED = "In Progress"


def _parse_clock(text: str) -> "dt_time | None":
    text = text.strip()
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def parse_time_range(time_slot: str):
    """
    Parses 'Subject Time' strings like '9:00 PM - 10:00 PM' into
    (start_time, end_time) as datetime.time objects. Returns None if it
    can't parse a start time; if the end time is missing/unparseable,
    defaults to 1 hour after start.
    """
    parts = time_slot.split("-")
    start_time = _parse_clock(parts[0]) if parts else None
    if start_time is None:
        return None

    end_time = _parse_clock(parts[1]) if len(parts) > 1 else None
    return start_time, end_time


def format_duration(total_minutes: int) -> str:
    """Formats minutes as 'Xh Ym' when 60+, otherwise 'Xm'. e.g. 1398 -> '23h 18m'."""
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def get_session_state(time_slot: str, status: str = "Pending", now: datetime | None = None) -> dict:
    """
    Returns the live state of a session as a dict:
      {
        "color": "green" | "blue" | "red" | "unknown",
        "label": human-readable text,
        "phase": "upcoming" | "upcoming_close" | "active_started" |
                 "active_grace" | "active_late" | "ended" | "unknown",
        "ended": bool — True once the session's end time has passed today
                 (caller should reset Status to Pending in the Sheet when this is True
                 and the stored Status isn't already Pending)
      }
    """
    now = now or datetime.now()
    parsed = parse_time_range(time_slot)

    if parsed is None:
        return {"color": "unknown", "label": "Time format not recognized", "phase": "unknown", "ended": False}

    start_time, end_time = parsed
    start_dt = datetime.combine(now.date(), start_time)

    if end_time is not None:
        end_dt = datetime.combine(now.date(), end_time)
        if end_dt <= start_dt:  # overnight session, e.g. 11:55 PM - 12:30 AM
            end_dt += timedelta(days=1)
    else:
        end_dt = start_dt + timedelta(hours=1)

    # ---- Session's window for today has fully passed ----
    if now >= end_dt:
        next_start = start_dt + timedelta(days=1)
        minutes_to_start = int((next_start - now).total_seconds() / 60)
        return {
            "color": "green",
            "label": f"Starts in {format_duration(minutes_to_start)}",
            "phase": "ended",
            "ended": True,
        }

    # ---- Not started yet today ----
    if now < start_dt:
        minutes_to_start = int((start_dt - now).total_seconds() / 60)
        if minutes_to_start > UPCOMING_WINDOW_MINUTES:
            return {
                "color": "green",
                "label": f"Starts in {format_duration(minutes_to_start)}",
                "phase": "upcoming",
                "ended": False,
            }
        return {
            "color": "blue",
            "label": f"Starting soon — {minutes_to_start} min left",
            "phase": "upcoming_close",
            "ended": False,
        }

    # ---- Currently within [start, end) — the session is "live" right now ----
    if status == STATUS_STARTED:
        minutes_to_end = int((end_dt - now).total_seconds() / 60)
        return {
            "color": "green",
            "label": f"✅ In Progress — ends in {format_duration(minutes_to_end)}",
            "phase": "active_started",
            "ended": False,
        }

    minutes_since_start = int((now - start_dt).total_seconds() / 60)
    if minutes_since_start <= LATE_GRACE_MINUTES:
        return {
            "color": "blue",
            "label": "Starting now" if minutes_since_start == 0 else f"Started {minutes_since_start} min ago",
            "phase": "active_grace",
            "ended": False,
        }

    return {
        "color": "red",
        "label": f"{format_duration(minutes_since_start)} late",
        "phase": "active_late",
        "ended": False,
    }


COLOR_HEX = {
    "green": "#2ed573",
    "blue": "#3498db",
    "red": "#e74c3c",
    "unknown": "#888888",
}


def color_badge_html(color: str, label: str) -> str:
    hex_color = COLOR_HEX.get(color, COLOR_HEX["unknown"])
    return (
        f'<span style="background-color:{hex_color}22; color:{hex_color}; '
        f'border:1px solid {hex_color}; padding:3px 10px; border-radius:12px; '
        f'font-size:13px; font-weight:600;">{label}</span>'
    )


def alert_sound_html(duration_seconds: int = 35) -> str:
    """Plays a repeating beep tone via the Web Audio API — no audio file needed."""
    return f"""
    <script>
    (function() {{
        try {{
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const totalMs = {duration_seconds * 1000};
            const beepEveryMs = 1200;
            let elapsed = 0;

            function beep() {{
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = "sine";
                osc.frequency.value = 880;
                gain.gain.setValueAtTime(0.15, ctx.currentTime);
                osc.start();
                osc.stop(ctx.currentTime + 0.25);
            }}

            const interval = setInterval(() => {{
                beep();
                elapsed += beepEveryMs;
                if (elapsed >= totalMs) clearInterval(interval);
            }}, beepEveryMs);
            beep();
        }} catch (e) {{ /* audio not available — fail silently */ }}
    }})();
    </script>
    """