"""Locust load test — simulate real user traffic patterns.

Usage:
    pip install locust
    cd tests/loadtest
    locust -f locustfile.py --host=http://localhost:8000
    # Open http://localhost:8089 in browser to start test
"""

import random
import string

from locust import HttpUser, between, task


def random_string(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


class CampusMatchUser(HttpUser):
    """Simulates a real user: register -> browse needs -> view detail -> create need"""

    wait_time = between(1, 5)
    token: str = ""
    user_id: int = 0

    def on_start(self):
        """Register or login to get a token."""
        username = f"loadtest_{random_string()}"
        password = "test123456"

        # Register
        resp = self.client.post("/api/v1/auth/register", json={
            "username": username,
            "password": password,
        })
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
            self.user_id = resp.json()["user"]["id"]
        elif resp.status_code == 400:
            # Already exists — login
            resp = self.client.post("/api/v1/auth/login", json={
                "username": username,
                "password": password,
            })
            if resp.status_code == 200:
                self.token = resp.json()["access_token"]
                self.user_id = resp.json()["user"]["id"]

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(5)
    def health_check(self):
        self.client.get("/api/v1/health")

    @task(4)
    def browse_needs(self):
        self.client.get("/api/v1/needs", params={"page": 1, "page_size": 10})

    @task(3)
    def view_profile(self):
        if self.token:
            self.client.get("/api/v1/profile/me", headers=self.headers)

    @task(2)
    def list_conversations(self):
        if self.token:
            self.client.get("/api/v1/messages/conversations", headers=self.headers)

    @task(1)
    def get_notifications(self):
        if self.token:
            self.client.get("/api/v1/messages/notifications", headers=self.headers)

    @task(1)
    def create_need(self):
        if not self.token:
            return
        types = ["组队", "求助", "技能交换"]
        need_type = random.choice(types)
        self.client.post("/api/v1/needs", json={
            "type": need_type,
            "title": f"Load Test {need_type} {random_string(4)}",
            "description": f"性能测试需求描述 {random_string(20)}",
            "selection_mode": random.choice(["single", "multi"]),
        }, headers=self.headers)

    @task(1)
    def admin_stats(self):
        if self.token:
            self.client.get("/api/v1/admin/stats", headers=self.headers)
