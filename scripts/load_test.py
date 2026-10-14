#!/usr/bin/env python3
"""Load test against the running API: concurrent virtual users repeatedly load the busiest screens.

Usage:
  API_URL=https://<cloudfront-domain>/api .venv/bin/python scripts/load_test.py
  USERS=20 REQUESTS=15 to change the load (defaults shown)
"""
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import requests

API = os.getenv("API_URL", "http://localhost:3001/api").rstrip("/")
USERS = int(os.getenv("USERS", "20"))
REQUESTS = int(os.getenv("REQUESTS", "15"))
ENDPOINTS = ["dashboard", "projects", "milestones", "actions/summary"]


def login():
    response = requests.post(f"{API}/auth/login", json={"username": "dana.whitfield", "password": "Demo1234!"}, timeout=90)
    response.raise_for_status()
    return response.json()["access_token"]


def virtual_user(token, index):
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"
    results = []
    for i in range(REQUESTS):
        endpoint = ENDPOINTS[(index + i) % len(ENDPOINTS)]
        start = time.perf_counter()
        try:
            status = session.get(f"{API}/{endpoint}", timeout=60).status_code
        except requests.RequestException:
            status = 0
        results.append((endpoint, status, (time.perf_counter() - start) * 1000))
    return results


def percentile(values, pct):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))]


def summarize(label, rows):
    times = [ms for _, _, ms in rows]
    ok = sum(1 for _, status, _ in rows if status == 200)
    return (f"| {label} | {len(rows)} | {100 * ok / len(rows):.1f}% | {statistics.median(times):.0f} ms "
            f"| {percentile(times, 95):.0f} ms | {percentile(times, 99):.0f} ms | {max(times):.0f} ms |")


def main():
    print(f"Target: {API}\nWarming up (wakes the database and Lambdas)...")
    token = login()
    for endpoint in ENDPOINTS:
        requests.get(f"{API}/{endpoint}", headers={"Authorization": f"Bearer {token}"}, timeout=90)

    print(f"Running {USERS} concurrent users x {REQUESTS} requests each...\n")
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=USERS) as pool:
        batches = list(pool.map(lambda i: virtual_user(token, i), range(USERS)))
    elapsed = time.perf_counter() - started
    rows = [row for batch in batches for row in batch]
    failures = {}
    for _, status, _ in rows:
        if status != 200:
            failures[status] = failures.get(status, 0) + 1

    print(f"{len(rows)} requests in {elapsed:.1f}s = {len(rows) / elapsed:.1f} requests/second\n")
    print("| Endpoint | Requests | Success | Median | p95 | p99 | Max |")
    print("|---|---|---|---|---|---|---|")
    for endpoint in ENDPOINTS:
        print(summarize(f"GET /{endpoint}", [r for r in rows if r[0] == endpoint]))
    print(summarize("**All**", rows))
    if failures:
        print(f"\nNon-200 responses: {failures}")


if __name__ == "__main__":
    main()