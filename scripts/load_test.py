"""
Load test with Locust — simulates concurrent webhook messages.

Usage:
    pip install locust
    locust -f scripts/load_test.py --host https://api-iag2.ianexo.com.br \
           --users 50 --spawn-rate 5 --run-time 2m --headless

To test locally:
    locust -f scripts/load_test.py --host http://localhost:8000 \
           --users 10 --spawn-rate 2 --run-time 30s --headless

Environment variables:
    CHATNEXO_API_KEY  — key sent in X-Api-Key header (required)
    ADMIN_API_KEY     — key for /admin/* endpoints (optional)
"""

from __future__ import annotations

import json
import os
import random
import string
import uuid

from locust import HttpUser, between, task


def _rand_phone() -> str:
    return "+55119" + "".join(random.choices(string.digits, k=8))


def _rand_account() -> str:
    return str(uuid.uuid4())


_MESSAGES = [
    "Olá, preciso de ajuda com meu acesso",
    "Não consigo entrar na plataforma",
    "Quero um reembolso",
    "Meu curso não está aparecendo",
    "Qual é o prazo para reembolso?",
    "Não recebi o link de acesso",
    "Preciso trocar meu email de cadastro",
    "O vídeo não carrega",
]

CHATNEXO_API_KEY = os.getenv("CHATNEXO_API_KEY", "changeme")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "changeme")


class WebhookUser(HttpUser):
    """Simulates ChatNexo sending inbound messages."""

    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        self.account_id = _rand_account()
        self.phone = _rand_phone()
        self.conversation_id = str(random.randint(10000, 99999))

    @task(10)
    def send_message(self) -> None:
        payload = {
            "account_id": self.account_id,
            "phone": self.phone,
            "conversation_id": self.conversation_id,
            "text": random.choice(_MESSAGES),
            "message_id": str(uuid.uuid4()),
            "contact_name": "Aluno Teste",
        }
        with self.client.post(
            "/webhook/message",
            json=payload,
            headers={"x-api-key": CHATNEXO_API_KEY},
            catch_response=True,
        ) as resp:
            if resp.status_code == 202:
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Unauthorized — set CHATNEXO_API_KEY env var")
            else:
                resp.failure(f"Unexpected {resp.status_code}: {resp.text[:200]}")

    @task(1)
    def health_check(self) -> None:
        self.client.get("/health")


class AdminUser(HttpUser):
    """Simulates admin panel polling DLQ and health."""

    wait_time = between(5.0, 15.0)

    @task(3)
    def list_dlq(self) -> None:
        with self.client.get(
            "/admin/dlq?page=1&page_size=20",
            headers={"x-api-key": ADMIN_API_KEY},
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 403):
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @task(1)
    def health_check(self) -> None:
        self.client.get("/health")
