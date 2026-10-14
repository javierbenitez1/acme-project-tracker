"""Sign-in protection. Every attempt is recorded with the device and a masked network address, so people
can spot sign-ins that weren't them. Five failed attempts in a row lock the account for 15 minutes, and
attempts during a lock are refused even with the right password. Addresses are masked before they are
stored (203.0.113.x), so the full address is never kept."""
import ipaddress
import math
from datetime import datetime, timedelta, timezone

from . import db
from .errors import ApiError

MAX_FAILURES = 5
LOCK_MINUTES = 15
BROWSERS = [("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"),
            ("CriOS/", "Chrome"), ("Safari/", "Safari")]
SYSTEMS = [("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Windows", "Windows"),
           ("Mac OS X", "macOS"), ("Macintosh", "macOS"), ("CrOS", "ChromeOS"), ("Linux", "Linux")]


# ---------- pure helpers (unit tested) ----------

def describe_device(user_agent):
    """A readable device from a browser's user agent, for example "Firefox on Linux"."""
    ua = user_agent or ""
    browser = next((name for marker, name in BROWSERS if marker in ua), None)
    system = next((name for marker, name in SYSTEMS if marker in ua), None)
    if browser and system:
        return f"{browser} on {system}"
    return browser or system or "Unknown device"


def mask_ip(address):
    """Keeps only the network part: 203.0.113.45 becomes 203.0.113.x, and IPv6 keeps its first 3 groups."""
    try:
        ip = ipaddress.ip_address((address or "").strip())
    except ValueError:
        return None
    if ip.version == 4:
        return ".".join(str(ip).split(".")[:3]) + ".x"
    return ":".join(ip.exploded.split(":")[:3]) + "::/48"


def client_address(headers):
    """The visitor's address. CloudFront puts the original client first in X-Forwarded-For."""
    forwarded = (headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return forwarded or None


def summarize(events):
    """events: newest first. Returns this sign-in, the one before it, and failed attempts in between."""
    successes = [e for e in events if e["succeeded"]]
    current = successes[0] if successes else None
    previous = successes[1] if len(successes) > 1 else None
    failed = [e for e in events if not e["succeeded"]
              and (previous is None or e["created_at"] > previous["created_at"])
              and (current is None or e["created_at"] < current["created_at"])]
    return {"current": current, "previous": previous, "failed_since_previous": len(failed), "recent": events[:10]}


def lock_until(events, now):
    """events: oldest first. Five failures in a row lock the account for 15 minutes from the fifth.
    A successful sign-in resets the count, attempts refused during a lock don't count, and the count
    starts again once a lock ends. Returns when the current lock ends, or None."""
    count, until = 0, None
    for event in events:
        if event.get("blocked"):
            continue
        if until and event["created_at"] >= until:
            count, until = 0, None
        if event["succeeded"]:
            count = 0
            continue
        count += 1
        if count >= MAX_FAILURES:
            until, count = event["created_at"] + timedelta(minutes=LOCK_MINUTES), 0
    return until if until and now < until else None


def locked_message(until, now):
    minutes = max(1, math.ceil((until - now).total_seconds() / 60))
    return (f"Too many failed sign-in attempts. For your security, this account is locked for "
            f"{minutes} more minute{'' if minutes == 1 else 's'}. Try again then, or ask an administrator for help.")


# ---------- database ----------

def record_sign_in(cur, user_id, succeeded, headers, blocked=False):
    cur.execute("INSERT INTO sign_in_events (user_id, succeeded, blocked, device, ip_masked) VALUES (%s, %s, %s, %s, %s)",
                (user_id, succeeded, blocked, describe_device(headers.get("user-agent"))[:100],
                 mask_ip(client_address(headers))))


def locked_until(cur, user_id):
    cur.execute("SELECT succeeded, blocked, created_at FROM sign_in_events"
                " WHERE user_id = %s AND created_at > NOW() - INTERVAL '2 hours' ORDER BY created_at, id", (user_id,))
    return lock_until(cur.fetchall(), datetime.now(timezone.utc))


def locked_error(until):
    return ApiError(423, "ACCOUNT_LOCKED", locked_message(until, datetime.now(timezone.utc)))


def register(router):
    """Adds GET /auth/sign-ins and GET /auth/health to the auth service's router."""

    @router.route("GET", "/sign-ins")
    def my_sign_ins(req):
        with db.transaction() as cur:
            cur.execute("SELECT id, succeeded, blocked, device, ip_masked, created_at FROM sign_in_events"
                        " WHERE user_id = %s ORDER BY created_at DESC, id DESC LIMIT 50", (req.user["id"],))
            events = cur.fetchall()
        return 200, summarize(events)

    @router.route("GET", "/health", auth=False)
    def health(req):
        """Used by the sign-in page's status line. Touching the database also wakes it up early."""
        with db.transaction() as cur:
            cur.execute("SELECT 1 AS ok")
            cur.fetchone()
        return 200, {"status": "ok"}