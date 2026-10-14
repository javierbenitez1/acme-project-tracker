"""Sign-in history. Every sign-in attempt is recorded with the device and a masked network address, so
people can spot sign-ins that weren't them, and a failed attempt is never silently forgotten.
Addresses are masked before they are stored (203.0.113.x), so the full address is never kept."""
import ipaddress

from . import db

BROWSERS = [("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"),
            ("CriOS/", "Chrome"), ("Safari/", "Safari")]
SYSTEMS = [("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Windows", "Windows"),
           ("Mac OS X", "macOS"), ("Macintosh", "macOS"), ("CrOS", "ChromeOS"), ("Linux", "Linux")]


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


def record_sign_in(cur, user_id, succeeded, headers):
    cur.execute("INSERT INTO sign_in_events (user_id, succeeded, device, ip_masked) VALUES (%s, %s, %s, %s)",
                (user_id, succeeded, describe_device(headers.get("user-agent"))[:100],
                 mask_ip(client_address(headers))))


def summarize(events):
    """events: newest first. Returns this sign-in, the one before it, and failed attempts in between."""
    successes = [e for e in events if e["succeeded"]]
    current = successes[0] if successes else None
    previous = successes[1] if len(successes) > 1 else None
    failed = [e for e in events if not e["succeeded"]
              and (previous is None or e["created_at"] > previous["created_at"])
              and (current is None or e["created_at"] < current["created_at"])]
    return {"current": current, "previous": previous, "failed_since_previous": len(failed), "recent": events[:10]}


def register(router):
    """Adds GET /auth/sign-ins to the auth service's router."""

    @router.route("GET", "/sign-ins")
    def my_sign_ins(req):
        with db.transaction() as cur:
            cur.execute("SELECT id, succeeded, device, ip_masked, created_at FROM sign_in_events"
                        " WHERE user_id = %s ORDER BY created_at DESC, id DESC LIMIT 50", (req.user["id"],))
            events = cur.fetchall()
        return 200, summarize(events)