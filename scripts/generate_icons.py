#!/usr/bin/env python3
"""Draws the Throughline app icons (the route-line mark) as PNGs using only the standard library."""
import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "icons"
INK, TEAL, WHITE, AMBER = (20, 32, 51), (79, 179, 177), (255, 255, 255), (224, 169, 53)
PATH = [(4, 22), (12, 22), (20, 10), (28, 10)]   # same route as the in-app logo, on a 32-unit grid
PAD = 0.2                                         # keeps the mark inside the "maskable" safe zone


def seg_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def blend(base, color, alpha):
    return tuple(round(b + (c - b) * alpha) for b, c in zip(base, color))


def draw(size):
    scale = size * (1 - 2 * PAD) / 32
    to_px = lambda p: (size * PAD + p[0] * scale, size * PAD + p[1] * scale)
    points = [to_px(p) for p in PATH]
    line_half, dot_r = 1.75 * scale, 3.5 * scale
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            cx, cy = x + 0.5, y + 0.5
            pixel = INK
            d = min(seg_distance(cx, cy, *points[i], *points[i + 1]) for i in range(len(points) - 1))
            pixel = blend(pixel, TEAL, max(0.0, min(1.0, line_half - d + 0.5)))
            for (sx, sy), color in ((points[0], WHITE), (points[-1], AMBER)):
                pixel = blend(pixel, color, max(0.0, min(1.0, dot_r - math.hypot(cx - sx, cy - sy) + 0.5)))
            rows.extend(pixel)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        (OUT / f"icon-{size}.png").write_bytes(draw(size))
        print(f"wrote icons/icon-{size}.png")