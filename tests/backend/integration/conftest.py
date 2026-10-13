"""Fixtures for integration tests against the running API (local proxy by default).
Set API_URL to test a deployed environment instead, e.g. API_URL=https://<cloudfront>/api"""
import os
import uuid

import pytest
import requests

API = os.getenv("API_URL", "http://localhost:3001/api").rstrip("/")
ADMIN = (os.getenv("ADMIN_USERNAME", "admin"), os.getenv("ADMIN_PASSWORD", "Admin123!"))


def login(username, password):
    response = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=60)
    assert response.status_code == 200, response.text
    return response.json()


class Client:
    def __init__(self, token=None):
        self.token = token

    def request(self, method, path, body=None):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return requests.request(method, f"{API}/{path.lstrip('/')}", json=body, headers=headers, timeout=60)

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, body=None):
        return self.request("POST", path, body)

    def put(self, path, body=None):
        return self.request("PUT", path, body)

    def delete(self, path):
        return self.request("DELETE", path)


@pytest.fixture(scope="session", autouse=True)
def api_is_up():
    try:
        requests.get(API.rsplit("/api", 1)[0] + "/", timeout=10)
    except requests.RequestException:
        pytest.skip(f"API not reachable at {API}. Start it with ./bin/start-dev.sh")


@pytest.fixture(scope="session")
def run_id():
    return uuid.uuid4().hex[:6]


@pytest.fixture(scope="session")
def admin():
    return Client(login(*ADMIN)["access_token"])


@pytest.fixture(scope="session")
def manager_account(admin, run_id):
    creds = {"username": f"it_mgr_{run_id}", "password": "Manager123"}
    response = admin.post("users", {**creds, "name": f"Test Manager {run_id}", "role": "manager",
                                    "email": f"it_mgr_{run_id}@acme.test", "job_title": "QA Manager"})
    assert response.status_code == 201, response.text
    return {**response.json(), **creds}


@pytest.fixture(scope="session")
def employee_account(admin, manager_account, run_id):
    creds = {"username": f"it_emp_{run_id}", "password": "Employee123"}
    response = admin.post("users", {**creds, "name": f"Test Employee {run_id}", "role": "employee",
                                    "email": f"it_emp_{run_id}@acme.test", "job_title": "QA Engineer",
                                    "manager_id": manager_account["id"]})
    assert response.status_code == 201, response.text
    return {**response.json(), **creds}


@pytest.fixture(scope="session")
def manager(manager_account):
    return Client(login(manager_account["username"], manager_account["password"])["access_token"])


@pytest.fixture(scope="session")
def employee(employee_account):
    return Client(login(employee_account["username"], employee_account["password"])["access_token"])
