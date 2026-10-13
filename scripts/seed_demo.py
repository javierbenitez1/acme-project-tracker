#!/usr/bin/env python3
"""Loads realistic demo data through the API, so every record follows the same rules as the app.

Usage:
  .venv/bin/python scripts/seed_demo.py            # add demo data (skips if it's already there)
  .venv/bin/python scripts/seed_demo.py --reset    # local only: clear the database first, then seed
  API_URL=https://<cloudfront-domain>/api .venv/bin/python scripts/seed_demo.py   # seed a deployed copy
"""
import os
import sys
from datetime import date, timedelta

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API = os.getenv("API_URL", "http://localhost:3001/api").rstrip("/")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!")
DEMO_PASSWORD = "Demo1234!"
TODAY = date.today()

MANAGERS = [
    ("dana.whitfield", "Dana Whitfield", "Director, Digital Engineering"),
    ("marcus.chen", "Marcus Chen", "Program Manager, Branch Operations"),
    ("priya.raman", "Priya Raman", "Lead, Risk Technology"),
]
EMPLOYEES = [
    ("leo.martins", "Leo Martins", "Senior iOS Engineer", "dana.whitfield"),
    ("aisha.okafor", "Aisha Okafor", "Product Designer", "dana.whitfield"),
    ("sam.kowalski", "Sam Kowalski", "Backend Engineer", "dana.whitfield"),
    ("nina.patel", "Nina Patel", "QA Engineer", "dana.whitfield"),
    ("diego.alvarez", "Diego Alvarez", "Field Systems Engineer", "marcus.chen"),
    ("hannah.lee", "Hannah Lee", "Business Analyst", "marcus.chen"),
    ("omar.haddad", "Omar Haddad", "Network Engineer", "marcus.chen"),
    ("grace.kim", "Grace Kim", "Data Engineer", "priya.raman"),
    ("ravi.shah", "Ravi Shah", "Machine Learning Engineer", "priya.raman"),
    ("tess.morgan", "Tess Morgan", "Security Analyst", "priya.raman"),
]


def d(days):
    return str(TODAY + timedelta(days=days))


class Session:
    """A signed-in API client that stops the script with a clear message if any call fails."""

    def __init__(self, username, password):
        response = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=60)
        if response.status_code != 200:
            sys.exit(f"Sign-in failed for {username}: {response.text}")
        self.token = response.json()["access_token"]

    def call(self, method, path, body=None):
        response = requests.request(method, f"{API}/{path}", json=body, timeout=60,
                                    headers={"Authorization": f"Bearer {self.token}"})
        if response.status_code >= 400:
            sys.exit(f"{method} /{path} failed ({response.status_code}): {response.text}")
        return response.json() if response.content else None

    def get(self, path):
        return self.call("GET", path)

    def post(self, path, body=None):
        return self.call("POST", path, body or {})

    def put(self, path, body):
        return self.call("PUT", path, body)

    def delete(self, path, body=None):
        return self.call("DELETE", path, body)


def reset_local_database():
    """Clears every table except the signing key, then recreates the admin account."""
    if "localhost" not in API:
        sys.exit("--reset only works against the local database.")
    sys.path.insert(0, os.path.join(ROOT, "backend", "_shared"))
    import psycopg
    from core.auth import hash_password

    with psycopg.connect("host=localhost port=5432 user=postgres password=postgres123 dbname=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'app_config'")
            tables = [row[0] for row in cur.fetchall()]
            cur.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")
            cur.execute("INSERT INTO users (username, password_hash, name, email, job_title, role)"
                        " VALUES (%s, %s, %s, %s, %s, 'admin')",
                        (ADMIN_USERNAME, hash_password(ADMIN_PASSWORD), "Alex Rivera", "alex.rivera@acme.com",
                         "Platform Administrator"))
    print("Cleared the local database.")


def main():
    if "--reset" in sys.argv:
        reset_local_database()

    admin = Session(ADMIN_USERNAME, ADMIN_PASSWORD)
    if admin.get("users?search=dana.whitfield"):
        print("Demo data is already loaded. Run with --reset to start fresh (local only).")
        return

    ids = {}
    for username, name, title in MANAGERS:
        ids[username] = admin.post("users", {"username": username, "password": DEMO_PASSWORD, "name": name,
                                             "email": f"{username}@acme.com", "job_title": title,
                                             "role": "manager"})["id"]
    for username, name, title, manager in EMPLOYEES:
        ids[username] = admin.post("users", {"username": username, "password": DEMO_PASSWORD, "name": name,
                                             "email": f"{username}@acme.com", "job_title": title,
                                             "role": "employee", "manager_id": ids[manager]})["id"]
    print(f"Created {len(MANAGERS)} managers and {len(EMPLOYEES)} employees.")

    sessions = {}

    def as_user(username):
        if username not in sessions:
            sessions[username] = Session(username, DEMO_PASSWORD)
        return sessions[username]

    def project(manager, name, department, start, end, budget, description, status="active"):
        return admin.post("projects", {"name": name, "department": department, "description": description,
                                       "manager_id": ids[manager], "start_date": d(start), "end_date": d(end),
                                       "budget_planned": budget, "status": status})

    def team(manager, proj, *people):
        as_user(manager).post(f"projects/{proj['id']}/members", {"user_ids": [ids[p] for p in people]})

    def milestone(manager, proj, name, start, end, after=(), description=None):
        body = {"project_id": proj["id"], "name": name, "start_date": d(start), "end_date": d(end)}
        if after:
            body["depends_on"] = [m["id"] for m in after]
        if description:
            body["description"] = description
        return as_user(manager).post("milestones", body)

    def task(manager, ms, title, who=None, due=None):
        body = {"milestone_id": ms["id"], "title": title}
        if who:
            body["assignee_id"] = ids[who]
        if due is not None:
            body["due_date"] = d(due)
        return as_user(manager).post("deliverables", body)

    def set_status(username, item, status, note=None):
        body = {"status": status, **({"status_note": note} if note else {})}
        return as_user(username).put(f"deliverables/{item['id']}", body)

    def finish_milestone(manager, ms):
        as_user(manager).put(f"milestones/{ms['id']}", {"status": "done"})

    def assign(manager, ms, who, hours):
        as_user(manager).post(f"milestones/{ms['id']}/assignments", {"user_id": ids[who], "hours_per_day": hours})

    def spend(manager, proj, amount, category, days_ago, description):
        as_user(manager).post("budgets", {"project_id": proj["id"], "amount": amount, "category": category,
                                          "entry_date": d(-days_ago), "description": description})

    # 1. Mobile Banking Refresh: on track
    mobile = project("dana.whitfield", "Mobile Banking Refresh", "Digital", -45, 75, 250000,
                     "Rebuild the transfers and payments experience in the consumer mobile app.")
    team("dana.whitfield", mobile, "leo.martins", "aisha.okafor", "sam.kowalski", "nina.patel")
    discovery = milestone("dana.whitfield", mobile, "Discovery", -45, -25)
    for t in (task("dana.whitfield", discovery, "Interview 20 customers about transfers", "aisha.okafor", -30),
              task("dana.whitfield", discovery, "Map the current app's pain points", "leo.martins", -27)):
        set_status("dana.whitfield", t, "done")
    finish_milestone("dana.whitfield", discovery)
    design = milestone("dana.whitfield", mobile, "Experience design", -25, 5, [discovery])
    set_status("aisha.okafor", task("dana.whitfield", design, "Prototype the new transfers flow", "aisha.okafor", -10), "done")
    set_status("aisha.okafor", task("dana.whitfield", design, "Run usability tests with 8 customers", "aisha.okafor", 3), "in_progress")
    task("dana.whitfield", design, "Accessibility review of the prototype", "nina.patel", 5)
    build = milestone("dana.whitfield", mobile, "Build the app", 5, 50, [design])
    task("dana.whitfield", build, "Build the transfers module", "leo.martins", 30)
    task("dana.whitfield", build, "Integrate the payments API", "sam.kowalski", 40)
    task("dana.whitfield", build, "Automated regression suite", "nina.patel", 48)
    launch = milestone("dana.whitfield", mobile, "Pilot and launch", 50, 75, [build])
    task("dana.whitfield", launch, "Pilot with 500 employees", None, 60)
    task("dana.whitfield", launch, "Release to the app stores", "leo.martins", 75)
    assign("dana.whitfield", design, "aisha.okafor", 6)
    assign("dana.whitfield", design, "nina.patel", 2)
    assign("dana.whitfield", build, "leo.martins", 8)
    assign("dana.whitfield", build, "sam.kowalski", 4)
    assign("dana.whitfield", build, "nina.patel", 4)
    spend("dana.whitfield", mobile, 52000, "labor", 40, "Discovery and design team")
    spend("dana.whitfield", mobile, 8000, "software", 30, "Prototyping and research tools")
    spend("dana.whitfield", mobile, 30000, "labor", 10, "Design sprint")

    # 2. Branch Kiosk Rollout: at risk (behind schedule, blocked install, vendor delay)
    kiosk = project("marcus.chen", "Branch Kiosk Rollout", "Branch Operations", -70, 12, 180000,
                    "Install self-service kiosks in 12 branches so customers can skip the teller line.")
    team("marcus.chen", kiosk, "diego.alvarez", "hannah.lee", "omar.haddad")
    surveys = milestone("marcus.chen", kiosk, "Site surveys", -70, -45)
    set_status("marcus.chen", task("marcus.chen", surveys, "Survey 12 branch floor plans", "diego.alvarez", -50), "done")
    finish_milestone("marcus.chen", surveys)
    order = milestone("marcus.chen", kiosk, "Order the kiosks", -45, -10, [surveys])
    for t in (task("marcus.chen", order, "Select the kiosk vendor", "hannah.lee", -35),
              task("marcus.chen", order, "Place the hardware order", "omar.haddad", -20)):
        set_status("marcus.chen", t, "done")
    finish_milestone("marcus.chen", order)
    install = milestone("marcus.chen", kiosk, "Install at branches", -10, 2, [order])
    golive = milestone("marcus.chen", kiosk, "Go-live review", 2, 6, [install])
    as_user("marcus.chen").put(f"milestones/{install['id']}", {
        "end_date": d(8), "change_reason": "Card reader shipment delayed by the vendor", "shift_dependents": True})
    set_status("diego.alvarez", task("marcus.chen", install, "Install at 5 downtown branches", "diego.alvarez", -2), "done")
    set_status("diego.alvarez", task("marcus.chen", install, "Install at 7 suburban branches", "diego.alvarez", 6), "blocked",
               "Vendor shipped the wrong card readers. Replacements arrive next week.")
    set_status("hannah.lee", task("marcus.chen", install, "Train branch staff on the kiosks", "hannah.lee", 7), "in_progress")
    task("marcus.chen", install, "Cut over branch networks", "omar.haddad", 8)
    task("marcus.chen", golive, "Go-live sign-off with the regional VP", "hannah.lee", 12)
    assign("marcus.chen", install, "diego.alvarez", 8)
    assign("marcus.chen", install, "hannah.lee", 4)
    assign("marcus.chen", install, "omar.haddad", 4)
    spend("marcus.chen", kiosk, 85000, "hardware", 40, "Kiosk hardware for 12 branches")
    spend("marcus.chen", kiosk, 25000, "labor", 20, "Installation crews")
    spend("marcus.chen", kiosk, 10000, "travel", 5, "Branch visits")

    # 3. Real-Time Fraud Alerts: off track (over budget, overdue milestone)
    fraud = project("priya.raman", "Real-Time Fraud Alerts", "Risk Technology", -50, 40, 100000,
                    "Flag suspicious card transactions within seconds and alert customers on their phones.")
    team("priya.raman", fraud, "grace.kim", "ravi.shah", "tess.morgan", "sam.kowalski")
    pipeline = milestone("priya.raman", fraud, "Transaction data pipeline", -50, -20)
    set_status("priya.raman", task("priya.raman", pipeline, "Stream card transactions into the warehouse", "grace.kim", -25), "done")
    finish_milestone("priya.raman", pipeline)
    model = milestone("priya.raman", fraud, "Train the detection model", -20, -3, [pipeline])
    set_status("grace.kim", task("priya.raman", model, "Label 6 months of disputed transactions", "grace.kim", -12), "done")
    set_status("ravi.shah", task("priya.raman", model, "Train and tune the anomaly model", "ravi.shah", -5), "in_progress")
    alerts = milestone("priya.raman", fraud, "Real-time alerting service", -3, 25, [model])
    task("priya.raman", alerts, "Build the alert API", "sam.kowalski", 20)
    task("priya.raman", alerts, "Push notifications to the mobile app", None, 25)
    review = milestone("priya.raman", fraud, "Security and compliance review", 25, 40, [alerts])
    task("priya.raman", review, "Penetration test", "tess.morgan", 35)
    task("priya.raman", review, "Model risk sign-off", "ravi.shah", 40)
    assign("priya.raman", model, "grace.kim", 4)
    assign("priya.raman", model, "ravi.shah", 8)
    assign("priya.raman", alerts, "sam.kowalski", 4)
    assign("priya.raman", alerts, "grace.kim", 4)
    assign("priya.raman", review, "tess.morgan", 4)
    assign("priya.raman", review, "ravi.shah", 4)
    as_user("priya.raman").put(f"projects/{fraud['id']}", {
        "budget_planned": 120000, "change_reason": "Added GPU capacity for model training"})
    spend("priya.raman", fraud, 60000, "contractors", 45, "Data labeling vendor")
    spend("priya.raman", fraud, 31500, "software", 25, "GPU compute")
    spend("priya.raman", fraud, 40000, "labor", 8, "Model training sprint")

    # 4. Data Warehouse Migration: completed and archived
    warehouse = project("dana.whitfield", "Data Warehouse Migration", "Data", -150, -5, 300000,
                        "Move reporting off the legacy warehouse onto the cloud data platform.")
    team("dana.whitfield", warehouse, "grace.kim", "sam.kowalski")
    previous = []
    for name, start, end, title, who, due in (
            ("Inventory data sources", -150, -110, "Catalog 140 legacy tables", "grace.kim", -120),
            ("Migrate pipelines", -110, -40, "Rebuild the nightly loads", "sam.kowalski", -60),
            ("Validate and cut over", -40, -8, "Reconcile the finance reports", "grace.kim", -15)):
        ms = milestone("dana.whitfield", warehouse, name, start, end, previous)
        set_status("dana.whitfield", task("dana.whitfield", ms, title, who, due), "done")
        finish_milestone("dana.whitfield", ms)
        previous = [ms]
    spend("dana.whitfield", warehouse, 200000, "labor", 140, "Migration team")
    spend("dana.whitfield", warehouse, 60000, "software", 90, "Cloud data platform licenses")
    spend("dana.whitfield", warehouse, 24000, "contractors", 30, "Report validation")
    as_user("dana.whitfield").post(f"projects/{warehouse['id']}/complete",
                                   {"reason": "Cut over on schedule. The legacy warehouse is retired."})

    # 5. Legacy Intranet Sunset: archived by the admin
    intranet = project("marcus.chen", "Legacy Intranet Sunset", "Workplace", -90, 30, 60000,
                       "Retire the old intranet and move its content to the new workplace hub.")
    team("marcus.chen", intranet, "hannah.lee")
    audit = milestone("marcus.chen", intranet, "Content audit", -90, -60)
    set_status("marcus.chen", task("marcus.chen", audit, "Audit 3,000 intranet pages", "hannah.lee", -70), "done")
    finish_milestone("marcus.chen", audit)
    milestone("marcus.chen", intranet, "Migrate to the workplace hub", -60, 30, [audit])
    spend("marcus.chen", intranet, 15000, "labor", 60, "Content audit")
    admin.delete(f"projects/{intranet['id']}", {"reason": "Folded into the 2027 workplace program."})

    # 6. Customer Onboarding Portal: planning, starts in two weeks
    portal = project("priya.raman", "Customer Onboarding Portal", "Digital", 14, 120, 200000,
                     "Let new business customers open accounts online without visiting a branch.", "planning")
    team("priya.raman", portal, "hannah.lee", "tess.morgan")
    requirements = milestone("priya.raman", portal, "Requirements", 14, 35)
    task("priya.raman", requirements, "Interview onboarding specialists", "hannah.lee", 28)
    portal_build = milestone("priya.raman", portal, "Build the portal", 35, 100, [requirements])
    milestone("priya.raman", portal, "Launch", 100, 120, [portal_build])
    assign("priya.raman", requirements, "tess.morgan", 4)

    # Manual action items, including one that was already resolved with a note
    as_user("dana.whitfield").post("actions", {
        "title": "Review the payments API contract before build starts", "priority": "high",
        "assignee_id": ids["leo.martins"], "project_id": mobile["id"], "due_date": d(4)})
    shared = as_user("dana.whitfield").post("actions", {
        "title": "Share usability findings with leadership", "priority": "medium",
        "assignee_id": ids["aisha.okafor"], "project_id": mobile["id"], "due_date": d(1)})
    as_user("aisha.okafor").put(f"actions/{shared['id']}", {
        "status": "done", "resolution_note": "Shared the readout deck in Monday's leadership review."})
    as_user("marcus.chen").post("actions", {
        "title": "Confirm training dates with branch managers", "priority": "medium",
        "assignee_id": ids["hannah.lee"], "project_id": kiosk["id"], "due_date": d(2)})
    as_user("priya.raman").post("actions", {
        "title": "Escalate the GPU overspend to finance", "priority": "high",
        "project_id": fraud["id"], "due_date": d(1)})

    print("Loaded 6 projects with milestones, deliverables, budgets and action items.\n")
    print("Demo sign-ins:")
    print(f"  Administrator  {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
    print(f"  Managers       dana.whitfield, marcus.chen, priya.raman / {DEMO_PASSWORD}")
    print(f"  Employees      leo.martins, diego.alvarez, ravi.shah (and others) / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()